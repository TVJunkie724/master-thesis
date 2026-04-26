"""Repository for user-scoped CloudConnection persistence."""

from sqlalchemy.orm import Session

from src.models.cloud_connection import CloudConnection


class CloudConnectionRepository:
    """Centralizes CloudConnection ownership and persistence queries."""

    def __init__(self, db: Session):
        self._db = db

    def list_for_user(self, user_id: str) -> list[CloudConnection]:
        return (
            self._db.query(CloudConnection)
            .filter(CloudConnection.user_id == user_id)
            .order_by(CloudConnection.created_at.desc())
            .all()
        )

    def get_for_user(self, connection_id: str, user_id: str) -> CloudConnection | None:
        return (
            self._db.query(CloudConnection)
            .filter(
                CloudConnection.id == connection_id,
                CloudConnection.user_id == user_id,
            )
            .first()
        )

    def add(self, connection: CloudConnection) -> CloudConnection:
        self._db.add(connection)
        return connection

    def delete(self, connection: CloudConnection) -> None:
        self._db.delete(connection)
