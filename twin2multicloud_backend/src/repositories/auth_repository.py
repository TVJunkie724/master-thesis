from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, or_, update
from sqlalchemy.orm import Session

from src.models.authentication import (
    AuthenticationEvent,
    AuthLoginTransaction,
    AuthSession,
    ExternalIdentity,
)


class AuthTransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, transaction: AuthLoginTransaction) -> None:
        self.db.add(transaction)

    def get(self, transaction_id: str) -> AuthLoginTransaction | None:
        return self.db.get(AuthLoginTransaction, transaction_id)

    def claim_callback(
        self,
        *,
        state_digest: str,
        provider: str,
        now: datetime,
    ) -> AuthLoginTransaction | None:
        result = self.db.execute(
            update(AuthLoginTransaction)
            .where(
                AuthLoginTransaction.state_digest == state_digest,
                AuthLoginTransaction.provider == provider,
                AuthLoginTransaction.status == "pending",
                AuthLoginTransaction.callback_consumed_at.is_(None),
                AuthLoginTransaction.cancelled_at.is_(None),
                AuthLoginTransaction.expires_at > now,
            )
            .values(callback_consumed_at=now)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            return None
        return self.db.query(AuthLoginTransaction).filter_by(state_digest=state_digest).one()

    def consume_exchange(self, transaction_id: str, now: datetime) -> bool:
        result = self.db.execute(
            update(AuthLoginTransaction)
            .where(
                AuthLoginTransaction.id == transaction_id,
                AuthLoginTransaction.status == "completed",
                AuthLoginTransaction.exchange_consumed_at.is_(None),
                AuthLoginTransaction.cancelled_at.is_(None),
                AuthLoginTransaction.expires_at > now,
            )
            .values(exchange_consumed_at=now)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def cancel(self, transaction_id: str, now: datetime) -> bool:
        result = self.db.execute(
            update(AuthLoginTransaction)
            .where(
                AuthLoginTransaction.id == transaction_id,
                AuthLoginTransaction.status.in_(("pending", "completed")),
                AuthLoginTransaction.exchange_consumed_at.is_(None),
                AuthLoginTransaction.cancelled_at.is_(None),
                AuthLoginTransaction.expires_at > now,
            )
            .values(status="cancelled", cancelled_at=now)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def delete_expired(self, now: datetime, limit: int = 100) -> int:
        ids = [
            row[0]
            for row in self.db.query(AuthLoginTransaction.id)
            .filter(
                or_(
                    AuthLoginTransaction.expires_at <= now,
                    AuthLoginTransaction.status.in_(("cancelled", "failed", "consumed")),
                )
            )
            .order_by(AuthLoginTransaction.expires_at.asc())
            .limit(limit)
            .all()
        ]
        if not ids:
            return 0
        return self.db.execute(
            delete(AuthLoginTransaction)
            .where(AuthLoginTransaction.id.in_(ids))
            .execution_options(synchronize_session=False)
        ).rowcount


class ExternalIdentityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find(self, provider: str, subject: str) -> ExternalIdentity | None:
        return self.db.query(ExternalIdentity).filter_by(
            provider=provider,
            subject=subject,
        ).first()

    def add(self, identity: ExternalIdentity) -> None:
        self.db.add(identity)


class AuthSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, session: AuthSession) -> None:
        self.db.add(session)

    def revoke(self, session_id: str, user_id: str, now: datetime, reason: str) -> bool:
        result = self.db.execute(
            update(AuthSession)
            .where(
                AuthSession.id == session_id,
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=now, revocation_reason=reason)
        )
        return result.rowcount == 1


class AuthenticationEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, event: AuthenticationEvent) -> None:
        self.db.add(event)
