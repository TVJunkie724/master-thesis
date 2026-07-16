from sqlalchemy.orm import Session

from src.models.credential_security_event import CredentialSecurityEvent


class CredentialSecurityEventRepository:
    """Append and owner-scoped read access for immutable audit evidence."""

    def __init__(self, db: Session):
        self._db = db

    def add(self, event: CredentialSecurityEvent) -> CredentialSecurityEvent:
        self._db.add(event)
        return event

    def list_for_user(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[CredentialSecurityEvent], int]:
        query = self._db.query(CredentialSecurityEvent).filter(
            CredentialSecurityEvent.user_id == user_id
        )
        total = query.count()
        items = (
            query.order_by(
                CredentialSecurityEvent.occurred_at.desc(),
                CredentialSecurityEvent.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total
