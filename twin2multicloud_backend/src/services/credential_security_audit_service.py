from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.models.credential_security_event import CredentialSecurityEvent
from src.repositories.credential_security_event_repository import (
    CredentialSecurityEventRepository,
)
from src.schemas.credential_security_event import CredentialSecurityEventDraft


class CredentialAuditWriteFailed(RuntimeError):
    """Raised when required audit evidence cannot be persisted."""


class CredentialSecurityAuditService:
    """Build append-only event rows from a closed, typed field set."""

    @staticmethod
    def append(db: Session, draft: CredentialSecurityEventDraft) -> CredentialSecurityEvent:
        event = CredentialSecurityEvent(**draft.model_dump(mode="json"))
        CredentialSecurityEventRepository(db).add(event)
        return event

    @classmethod
    def commit_standalone(cls, db: Session, draft: CredentialSecurityEventDraft) -> None:
        """Commit evidence that is independent of a business-state transaction."""
        try:
            db.rollback()
            cls.append(db, draft)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise CredentialAuditWriteFailed("Credential security audit write failed") from exc
