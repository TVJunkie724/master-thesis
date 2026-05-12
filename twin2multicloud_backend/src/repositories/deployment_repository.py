"""Repository for Deployment persistence and read models."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.models.deployment import Deployment


class DeploymentRepository:
    """Centralizes deployment history and status persistence queries."""

    def __init__(self, db: Session):
        self._db = db

    def create_running(
        self,
        twin_id: str,
        session_id: str,
        operation_type: str,
        description: str | None = None,
        operation_id: str | None = None,
    ) -> Deployment:
        deployment = Deployment(
            twin_id=twin_id,
            session_id=session_id,
            operation_type=operation_type,
            operation_id=operation_id,
            status="running",
            description=description,
        )
        self._db.add(deployment)
        return deployment

    def get_by_session_id(self, session_id: str) -> Deployment | None:
        return (
            self._db.query(Deployment)
            .filter(Deployment.session_id == session_id)
            .first()
        )

    def get_latest_successful_outputs(
        self,
        twin_id: str,
        operation_types: list[str] | None = None,
    ) -> Deployment | None:
        operations = operation_types or ["deploy", "test"]
        return (
            self._db.query(Deployment)
            .filter(
                Deployment.twin_id == twin_id,
                Deployment.status == "success",
                Deployment.operation_type.in_(operations),
            )
            .order_by(Deployment.completed_at.desc())
            .first()
        )

    def get_latest_for_twin(self, twin_id: str) -> Deployment | None:
        return (
            self._db.query(Deployment)
            .filter(Deployment.twin_id == twin_id)
            .order_by(Deployment.started_at.desc())
            .first()
        )

    def list_for_twin(self, twin_id: str, limit: int) -> list[Deployment]:
        return (
            self._db.query(Deployment)
            .filter(Deployment.twin_id == twin_id)
            .order_by(Deployment.started_at.desc())
            .limit(limit)
            .all()
        )

    def mark_success(
        self,
        deployment: Deployment,
        terraform_outputs: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
        operation_id: str | None = None,
    ) -> Deployment:
        deployment.status = "success"
        if operation_id:
            deployment.operation_id = operation_id
        deployment.terraform_outputs = terraform_outputs
        deployment.error_code = None
        deployment.error_message = None
        deployment.completed_at = completed_at or datetime.now(timezone.utc)
        return deployment

    def mark_failed(
        self,
        deployment: Deployment,
        error_message: str,
        terraform_outputs: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
        operation_id: str | None = None,
        error_code: str | None = None,
    ) -> Deployment:
        deployment.status = "failed"
        if operation_id:
            deployment.operation_id = operation_id
        deployment.error_code = error_code
        deployment.error_message = error_message
        deployment.terraform_outputs = terraform_outputs
        deployment.completed_at = completed_at or datetime.now(timezone.utc)
        return deployment
