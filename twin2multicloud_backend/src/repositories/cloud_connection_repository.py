"""Repository for user-scoped CloudConnection persistence."""

from sqlalchemy.orm import Session

from src.models.cloud_connection import CloudConnection
from src.models.twin_config import TwinConfiguration


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

    def get_default_pricing(self, user_id: str, provider: str) -> CloudConnection | None:
        return (
            self._db.query(CloudConnection)
            .filter(
                CloudConnection.user_id == user_id,
                CloudConnection.provider == provider,
                CloudConnection.purpose == "pricing",
                CloudConnection.is_default_for_pricing.is_(True),
            )
            .one_or_none()
        )

    def clear_pricing_defaults(self, user_id: str, provider: str) -> None:
        (
            self._db.query(CloudConnection)
            .filter(
                CloudConnection.user_id == user_id,
                CloudConnection.provider == provider,
                CloudConnection.purpose == "pricing",
                CloudConnection.is_default_for_pricing.is_(True),
            )
            .update({CloudConnection.is_default_for_pricing: False}, synchronize_session="fetch")
        )

    def add(self, connection: CloudConnection) -> CloudConnection:
        self._db.add(connection)
        return connection

    def count_twin_bindings(self, connection_id: str) -> int:
        return (
            self._db.query(TwinConfiguration)
            .filter(
                (TwinConfiguration.aws_cloud_connection_id == connection_id)
                | (TwinConfiguration.azure_cloud_connection_id == connection_id)
                | (TwinConfiguration.gcp_cloud_connection_id == connection_id)
            )
            .count()
        )

    def delete(self, connection: CloudConnection) -> None:
        self._db.delete(connection)
