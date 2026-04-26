"""Repository for DigitalTwin persistence and ownership queries."""

from sqlalchemy.orm import Session, joinedload

from src.models.twin import DigitalTwin, TwinState


class TwinRepository:
    """Centralizes DigitalTwin queries used by routes and services."""

    def __init__(self, db: Session):
        self._db = db

    def list_active_for_user(self, user_id: str) -> list[DigitalTwin]:
        return (
            self._db.query(DigitalTwin)
            .filter(
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .all()
        )

    def get_for_user(self, twin_id: str, user_id: str) -> DigitalTwin | None:
        return (
            self._db.query(DigitalTwin)
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
            )
            .first()
        )

    def get_active_for_user(self, twin_id: str, user_id: str) -> DigitalTwin | None:
        return (
            self._db.query(DigitalTwin)
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .first()
        )

    def get_with_configs_for_user(self, twin_id: str, user_id: str) -> DigitalTwin | None:
        return (
            self._db.query(DigitalTwin)
            .options(
                joinedload(DigitalTwin.configuration),
                joinedload(DigitalTwin.optimizer_config),
                joinedload(DigitalTwin.deployer_config),
            )
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .first()
        )

    def name_exists_for_user(
        self,
        name: str,
        user_id: str,
        exclude_twin_id: str | None = None,
    ) -> bool:
        query = self._db.query(DigitalTwin).filter(
            DigitalTwin.user_id == user_id,
            DigitalTwin.name.ilike(name),
            DigitalTwin.state != TwinState.INACTIVE,
        )
        if exclude_twin_id is not None:
            query = query.filter(DigitalTwin.id != exclude_twin_id)
        return query.first() is not None

    def add(self, twin: DigitalTwin) -> DigitalTwin:
        self._db.add(twin)
        return twin

    def soft_delete(self, twin: DigitalTwin) -> DigitalTwin:
        twin.state = TwinState.INACTIVE
        twin.name = f"_deleted_{twin.id}_{twin.name}"
        return twin
