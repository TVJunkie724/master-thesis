"""Persistence adapter for twin-scoped deployment preflight cache entries."""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from src.models.deployment_preflight import DeploymentPreflightCache


class DeploymentPreflightRepository:
    """Stores only the latest secret-free result for each twin/provider pair."""

    def __init__(self, db: Session):
        self._db = db

    def get(self, twin_id: str, provider: str) -> DeploymentPreflightCache | None:
        return (
            self._db.query(DeploymentPreflightCache)
            .filter(
                DeploymentPreflightCache.twin_id == twin_id,
                DeploymentPreflightCache.provider == provider,
            )
            .one_or_none()
        )

    def upsert(
        self,
        *,
        twin_id: str,
        provider: str,
        cloud_connection_id: str,
        connection_payload_fingerprint: str,
        supplied_permission_set_version: str | None,
        expected_permission_set_version: str,
        ready: bool,
        summary: str,
        checks_json: str,
        checked_at: datetime,
    ) -> DeploymentPreflightCache:
        now = datetime.utcnow()
        values = {
            "id": str(uuid.uuid4()),
            "twin_id": twin_id,
            "provider": provider,
            "cloud_connection_id": cloud_connection_id,
            "connection_payload_fingerprint": connection_payload_fingerprint,
            "supplied_permission_set_version": supplied_permission_set_version,
            "expected_permission_set_version": expected_permission_set_version,
            "ready": ready,
            "summary": summary,
            "checks_json": checks_json,
            "checked_at": checked_at,
            "created_at": now,
            "updated_at": now,
        }
        update_values = {
            key: value
            for key, value in values.items()
            if key not in {"id", "twin_id", "provider", "created_at"}
        }
        statement = sqlite_insert(DeploymentPreflightCache).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=["twin_id", "provider"],
            set_=update_values,
        )
        self._db.execute(statement)
        return (
            self._db.query(DeploymentPreflightCache)
            .populate_existing()
            .filter(
                DeploymentPreflightCache.twin_id == twin_id,
                DeploymentPreflightCache.provider == provider,
            )
            .one()
        )

    def delete(self, twin_id: str, provider: str) -> None:
        entry = self.get(twin_id, provider)
        if entry is not None:
            self._db.delete(entry)

    def delete_unrequired(self, twin_id: str, required_providers: set[str]) -> None:
        query = self._db.query(DeploymentPreflightCache).filter(
            DeploymentPreflightCache.twin_id == twin_id,
        )
        if required_providers:
            query = query.filter(
                DeploymentPreflightCache.provider.notin_(required_providers),
            )
        query.delete(synchronize_session="fetch")
