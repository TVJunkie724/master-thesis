"""Deployment persistence queries."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.deployment import Deployment


class DeploymentRepository:
    """Repository for deployment history and output read models."""

    def __init__(self, db: Session):
        self.db = db

    def latest_successful_deploy(self, twin_id: str) -> Deployment | None:
        """Return the latest successful real or test deployment for a twin."""
        return (
            self.db.query(Deployment)
            .filter(
                Deployment.twin_id == twin_id,
                Deployment.status == "success",
                Deployment.operation_type.in_(["deploy", "test"]),
            )
            .order_by(Deployment.completed_at.desc())
            .first()
        )

    def list_for_twin(self, twin_id: str, limit: int) -> list[Deployment]:
        """Return deployment records ordered by newest first."""
        return (
            self.db.query(Deployment)
            .filter(Deployment.twin_id == twin_id)
            .order_by(Deployment.started_at.desc())
            .limit(limit)
            .all()
        )

