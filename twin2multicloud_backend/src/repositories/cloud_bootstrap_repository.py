"""Owner-scoped persistence queries for guided bootstrap sessions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from src.models.cloud_bootstrap_session import (
    ACTIVE_BOOTSTRAP_STATES,
    CloudBootstrapSession,
)


class CloudBootstrapRepository:
    def __init__(self, db: Session):
        self._db = db

    def add(self, session: CloudBootstrapSession) -> None:
        self._db.add(session)

    def get_for_owner(
        self,
        session_id: str,
        user_id: str,
    ) -> CloudBootstrapSession | None:
        return (
            self._db.query(CloudBootstrapSession)
            .options(joinedload(CloudBootstrapSession.connection))
            .filter(
                CloudBootstrapSession.id == session_id,
                CloudBootstrapSession.user_id == user_id,
            )
            .one_or_none()
        )

    def get_by_create_idempotency(
        self,
        user_id: str,
        idempotency_key: str,
    ) -> CloudBootstrapSession | None:
        return (
            self._db.query(CloudBootstrapSession)
            .options(joinedload(CloudBootstrapSession.connection))
            .filter(
                CloudBootstrapSession.user_id == user_id,
                CloudBootstrapSession.create_idempotency_key == idempotency_key,
            )
            .one_or_none()
        )

    def get_active_for_scope(
        self,
        user_id: str,
        provider: str,
        target_scope_digest: str,
    ) -> CloudBootstrapSession | None:
        return (
            self._db.query(CloudBootstrapSession)
            .options(joinedload(CloudBootstrapSession.connection))
            .filter(
                CloudBootstrapSession.user_id == user_id,
                CloudBootstrapSession.provider == provider,
                CloudBootstrapSession.target_scope_digest == target_scope_digest,
                CloudBootstrapSession.state.in_(ACTIVE_BOOTSTRAP_STATES),
            )
            .one_or_none()
        )

    def list_for_owner(
        self,
        user_id: str,
        *,
        provider: str | None = None,
        active: bool | None = None,
    ) -> list[CloudBootstrapSession]:
        query = (
            self._db.query(CloudBootstrapSession)
            .options(joinedload(CloudBootstrapSession.connection))
            .filter(CloudBootstrapSession.user_id == user_id)
        )
        if provider is not None:
            query = query.filter(CloudBootstrapSession.provider == provider)
        if active is True:
            query = query.filter(CloudBootstrapSession.state.in_(ACTIVE_BOOTSTRAP_STATES))
        elif active is False:
            query = query.filter(~CloudBootstrapSession.state.in_(ACTIVE_BOOTSTRAP_STATES))
        return query.order_by(CloudBootstrapSession.updated_at.desc()).all()

    def list_stale_leases(
        self,
        user_id: str,
        cutoff: datetime,
    ) -> list[CloudBootstrapSession]:
        return (
            self._db.query(CloudBootstrapSession)
            .options(joinedload(CloudBootstrapSession.connection))
            .filter(
                CloudBootstrapSession.user_id == user_id,
                CloudBootstrapSession.state.in_(
                    ("bootstrap_running", "disposal_running")
                ),
                CloudBootstrapSession.lease_started_at.is_not(None),
                CloudBootstrapSession.lease_started_at <= cutoff,
            )
            .all()
        )
