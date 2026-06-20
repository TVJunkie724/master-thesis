"""Digital twin persistence queries."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.twin import DigitalTwin, TwinState


class TwinRepository:
    """Repository for DigitalTwin ownership and lifecycle queries."""

    def __init__(self, db: Session):
        self.db = db

    def get_active_for_user(self, twin_id: str, user_id: str) -> DigitalTwin | None:
        """Return a non-inactive twin owned by the given user."""
        return (
            self.db.query(DigitalTwin)
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .first()
        )

