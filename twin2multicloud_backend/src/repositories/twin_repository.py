"""Digital twin persistence queries."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

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

    def get_with_configs_for_user(self, twin_id: str, user_id: str) -> DigitalTwin | None:
        """Return an active twin with wizard configuration relationships loaded."""
        return (
            self.db.query(DigitalTwin)
            .options(
                joinedload(DigitalTwin.configuration),
                joinedload(DigitalTwin.optimizer_config),
                joinedload(DigitalTwin.deployer_config),
                joinedload(DigitalTwin.cost_calculation_runs),
            )
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
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

    def name_exists_for_user(
        self,
        name: str,
        user_id: str,
        exclude_twin_id: str | None = None,
    ) -> bool:
        """Compatibility helper for callers that only need duplicate existence."""
        return self.find_active_by_name(
            user_id=user_id,
            name=name,
            exclude_twin_id=exclude_twin_id,
        ) is not None

    def add(self, twin: DigitalTwin) -> DigitalTwin:
        """Add a twin to the current unit of work and return it."""
        self.db.add(twin)
        return twin

    def refresh(self, twin: DigitalTwin) -> None:
        """Refresh a twin from the database."""
        self.db.refresh(twin)

    @staticmethod
    def soft_delete(twin: DigitalTwin) -> DigitalTwin:
        """Mark a twin inactive and free its active display name."""
        twin.state = TwinState.INACTIVE
        twin.name = f"_deleted_{twin.id}_{twin.name}"
        return twin
