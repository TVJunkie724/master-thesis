"""Persistence boundary for bounded telemetry verification evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.models.telemetry_verification import TelemetryVerification


class TelemetryVerificationRepository:
    """Create, complete, and bound telemetry verification records."""

    _MAX_TERMINAL_RECORDS_PER_TWIN = 25

    def __init__(self, db: Session):
        self._db = db

    def create_running(
        self,
        *,
        twin_id: str,
        deployment_id: str | None,
        session_id: str,
        device_id: str,
    ) -> TelemetryVerification:
        record = TelemetryVerification(
            twin_id=twin_id,
            deployment_id=deployment_id,
            session_id=session_id,
            device_id=device_id,
            status="running",
        )
        self._db.add(record)
        self._db.flush()
        self.prune_terminal_history(twin_id)
        return record

    def get_by_id(self, record_id: str) -> TelemetryVerification | None:
        return (
            self._db.query(TelemetryVerification)
            .filter(TelemetryVerification.id == record_id)
            .first()
        )

    def get_active_for_twin(self, twin_id: str) -> TelemetryVerification | None:
        return (
            self._db.query(TelemetryVerification)
            .filter(
                TelemetryVerification.twin_id == twin_id,
                TelemetryVerification.status == "running",
            )
            .order_by(TelemetryVerification.requested_at.desc())
            .first()
        )

    def list_for_twin(self, twin_id: str, *, limit: int) -> list[TelemetryVerification]:
        return (
            self._db.query(TelemetryVerification)
            .filter(TelemetryVerification.twin_id == twin_id)
            .order_by(TelemetryVerification.requested_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def mark_completed(
        record: TelemetryVerification,
        *,
        status: str,
        trace_id: str | None,
        result: dict[str, Any] | None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> TelemetryVerification:
        if status not in {"pass", "fail", "not_run"}:
            raise ValueError("Unsupported telemetry verification status")
        record.status = status
        record.trace_id = trace_id
        record.result = result
        record.error_code = error_code
        record.error_message = error_message
        record.completed_at = datetime.now(timezone.utc)
        return record

    def prune_terminal_history(self, twin_id: str) -> None:
        stale = (
            self._db.query(TelemetryVerification)
            .filter(
                TelemetryVerification.twin_id == twin_id,
                TelemetryVerification.status.in_(["pass", "fail", "not_run"]),
            )
            .order_by(TelemetryVerification.requested_at.desc())
            .offset(self._MAX_TERMINAL_RECORDS_PER_TWIN)
            .all()
        )
        for record in stale:
            self._db.delete(record)
