"""Repository for Deployment persistence and read models."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.models.deployment import Deployment


class DeploymentRepository:
    """Centralizes deployment history and status persistence queries."""

    _GRAPH_STAGE_ORDER = ("package", "preplan", "terraform", "postapply")
    _MAX_TERMINAL_OPERATIONS_PER_TWIN = 100

    def __init__(self, db: Session):
        self._db = db

    def create_running(
        self,
        twin_id: str,
        session_id: str,
        operation_type: str,
        description: str | None = None,
        operation_id: str | None = None,
        idempotency_key: str | None = None,
        graph_evidence: dict[str, Any] | None = None,
    ) -> Deployment:
        evidence = dict(graph_evidence or {})
        deployment = Deployment(
            twin_id=twin_id,
            session_id=session_id,
            operation_type=operation_type,
            operation_id=operation_id,
            idempotency_key=idempotency_key,
            status="running",
            description=description,
            architecture_digest=evidence.get("architecture_digest"),
            graph_digest=evidence.get("graph_digest"),
            profile_id=evidence.get("profile_id"),
            profile_version=evidence.get("profile_version"),
            catalog_id=evidence.get("catalog_id"),
            catalog_version=evidence.get("catalog_version"),
            completed_stage=None,
            graph_validation=evidence or None,
        )
        self._db.add(deployment)
        self._db.flush()
        self.prune_terminal_history(twin_id)
        return deployment

    def get_by_idempotency_key(
        self,
        twin_id: str,
        operation_type: str,
        idempotency_key: str,
    ) -> Deployment | None:
        """Return the authoritative result of a previously accepted command."""

        return (
            self._db.query(Deployment)
            .filter(
                Deployment.twin_id == twin_id,
                Deployment.operation_type == operation_type,
                Deployment.idempotency_key == idempotency_key,
            )
            .first()
        )

    def get_active_for_twin(self, twin_id: str) -> Deployment | None:
        """Return a persisted active mutation independently of SSE process state."""

        return (
            self._db.query(Deployment)
            .filter(
                Deployment.twin_id == twin_id,
                Deployment.operation_type.in_(["deploy", "destroy", "test"]),
                Deployment.status.in_(["pending", "running"]),
            )
            .order_by(Deployment.started_at.desc())
            .first()
        )

    def prune_terminal_history(self, twin_id: str) -> None:
        """Bound retained operation and progress evidence per Twin."""

        from src.models.deployment_log import DeploymentLog

        stale = (
            self._db.query(Deployment)
            .filter(
                Deployment.twin_id == twin_id,
                Deployment.status.in_(["success", "failed"]),
            )
            .order_by(Deployment.started_at.desc())
            .offset(self._MAX_TERMINAL_OPERATIONS_PER_TWIN)
            .all()
        )
        if not stale:
            return
        session_ids = [deployment.session_id for deployment in stale]
        self._db.query(DeploymentLog).filter(
            DeploymentLog.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        for deployment in stale:
            self._db.delete(deployment)

    def mark_completed_stage(
        self,
        deployment: Deployment,
        completed_stage: str,
    ) -> Deployment:
        """Persist monotonic bounded graph-stage progress."""

        if completed_stage not in self._GRAPH_STAGE_ORDER:
            raise ValueError("Unknown deployment graph stage")
        current = deployment.completed_stage
        if current is not None and (
            self._GRAPH_STAGE_ORDER.index(completed_stage)
            < self._GRAPH_STAGE_ORDER.index(current)
        ):
            raise ValueError("Deployment graph stage cannot move backwards")
        deployment.completed_stage = completed_stage
        return deployment

    @staticmethod
    def assert_graph_compatible(
        deployment: Deployment,
        graph_evidence: dict[str, Any],
    ) -> None:
        """Reject retries/destroy when immutable graph evidence changed."""

        frozen = deployment.graph_validation
        if isinstance(frozen, dict) and frozen:
            expected: object = frozen
            actual: object = graph_evidence
        else:
            expected = (
                deployment.architecture_digest,
                deployment.graph_digest,
                deployment.profile_id,
                deployment.profile_version,
                deployment.catalog_id,
                deployment.catalog_version,
            )
            actual = (
                graph_evidence.get("architecture_digest"),
                graph_evidence.get("graph_digest"),
                graph_evidence.get("profile_id"),
                graph_evidence.get("profile_version"),
                graph_evidence.get("catalog_id"),
                graph_evidence.get("catalog_version"),
            )
        if expected != actual:
            from src.services.errors import DeploymentPackageBuildFailed

            raise DeploymentPackageBuildFailed(
                "Deployment graph evidence differs from the frozen operation",
                [
                    {
                        "code": "DEPLOYMENT_GRAPH_RESUME_MISMATCH",
                        "field": "graph_digest",
                        "message": "DEPLOYMENT_GRAPH_RESUME_MISMATCH",
                    }
                ],
            )

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

    def latest_successful_deploy(self, twin_id: str) -> Deployment | None:
        """Return the latest successful real or test deployment for a twin."""
        return self.get_latest_successful_outputs(
            twin_id, operation_types=["deploy", "test"]
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
        deployment_access_evidence: dict[str, Any] | None = None,
        completed_at: datetime | None = None,
        operation_id: str | None = None,
    ) -> Deployment:
        deployment.status = "success"
        if operation_id:
            deployment.operation_id = operation_id
        deployment.terraform_outputs = terraform_outputs
        deployment.deployment_access_evidence = deployment_access_evidence
        deployment.error_code = None
        deployment.error_message = None
        if deployment.graph_digest:
            deployment.completed_stage = "postapply"
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
