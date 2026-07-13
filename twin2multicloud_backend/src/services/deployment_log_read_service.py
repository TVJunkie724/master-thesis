"""Read-side service for persisted deployment log catchup."""

from __future__ import annotations

import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.deployment_log import DeploymentLog
from src.models.twin import DigitalTwin
from src.schemas.deployment_logs import (
    DeploymentLogEntryResponse,
    DeploymentLogPageResponse,
)


REDACTION = "[REDACTED]"
SECRET_ASSIGNMENT_PATTERNS = (
    re.compile(
        r'(?i)(\b(?:secret|password|token|private_key|access_key|client_secret|credential)[\w.-]*\b\s*[:=]\s*)(["\']?)([^"\'\s,}]+)(["\']?)'
    ),
    re.compile(
        r'(?i)(["\'](?:secret|password|token|private_key|access_key|client_secret|credential)[\w.-]*["\']\s*:\s*)(["\'])([^"\']+)(["\'])'
    ),
)
AWS_ACCESS_KEY_PATTERN = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)


class DeploymentLogReadService:
    """Returns bounded, owner-scoped deployment log pages for UI catchup."""

    def __init__(self, db: Session):
        self.db = db

    def get_page(
        self,
        twin: DigitalTwin,
        *,
        session_id: str | None,
        after_event_id: int,
        limit: int,
    ) -> DeploymentLogPageResponse:
        query = self.db.query(DeploymentLog).filter(DeploymentLog.twin_id == twin.id)
        latest_query = self.db.query(func.max(DeploymentLog.event_id)).filter(
            DeploymentLog.twin_id == twin.id
        )

        if session_id:
            query = query.filter(DeploymentLog.session_id == session_id)
            latest_query = latest_query.filter(DeploymentLog.session_id == session_id)

        if after_event_id > 0:
            query = query.filter(DeploymentLog.event_id > after_event_id)

        rows = query.order_by(DeploymentLog.event_id.asc()).limit(limit + 1).all()
        page_rows = rows[:limit]
        has_more = len(rows) > limit
        next_after_event_id = page_rows[-1].event_id if page_rows else after_event_id
        latest_event_id = latest_query.scalar()

        return DeploymentLogPageResponse(
            twin_id=twin.id,
            session_id=session_id,
            after_event_id=after_event_id,
            limit=limit,
            logs=[self._entry(row) for row in page_rows],
            has_more=has_more,
            next_after_event_id=next_after_event_id,
            latest_event_id=latest_event_id,
        )

    def _entry(self, row: DeploymentLog) -> DeploymentLogEntryResponse:
        return DeploymentLogEntryResponse(
            event_id=row.event_id,
            session_id=row.session_id,
            timestamp=row.timestamp,
            level=row.level,
            message=redact_log_message(row.message),
            operation_type=row.operation_type,
        )


def redact_log_message(message: str) -> str:
    redacted = PRIVATE_KEY_BLOCK_PATTERN.sub(REDACTION, message or "")
    redacted = AWS_ACCESS_KEY_PATTERN.sub(REDACTION, redacted)
    for pattern in SECRET_ASSIGNMENT_PATTERNS:
        redacted = pattern.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{REDACTION}{match.group(4)}",
            redacted,
        )
    return redacted
