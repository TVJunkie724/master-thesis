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

    def get_for_user(self, twin_id: str, user_id: str) -> DigitalTwin | None:
        """Return a twin owned by the given user, including inactive twins."""
        return (
            self.db.query(DigitalTwin)
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
            )
            .first()
        )

    def list_active_for_user(self, user_id: str) -> list[DigitalTwin]:
        """Return all active twins owned by a user."""
        return (
            self.db.query(DigitalTwin)
            .filter(
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .all()
        )

    def find_active_by_name(
        self,
        user_id: str,
        name: str,
        exclude_twin_id: str | None = None,
    ) -> DigitalTwin | None:
        """Return an active twin by case-insensitive name for duplicate checks."""
        query = self.db.query(DigitalTwin).filter(
            DigitalTwin.user_id == user_id,
            DigitalTwin.name.ilike(name),
            DigitalTwin.state != TwinState.INACTIVE,
        )
        if exclude_twin_id:
            query = query.filter(DigitalTwin.id != exclude_twin_id)
        return query.first()

    def add(self, twin: DigitalTwin) -> None:
        """Add a twin to the current unit of work."""
        self.db.add(twin)

    def refresh(self, twin: DigitalTwin) -> None:
        """Refresh a twin from the database."""
        self.db.refresh(twin)
