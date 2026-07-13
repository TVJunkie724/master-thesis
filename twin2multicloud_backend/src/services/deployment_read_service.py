"""Read-side deployment use cases for Digital Twins."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from src.clients.deployer_client import DeployerClient
from src.models.twin import DigitalTwin, TwinState
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.services.provider_contract import is_gcp_provider
from src.services.service_errors import EntityNotFoundError
from src.services.deployment_operation_read_service import (
    build_deployment_history_response,
    build_deployment_outputs_response,
    build_deployment_status_response,
)

ActiveSessionProvider = Callable[[str], Awaitable[list[Any]]]


class DeploymentReadService:
    """Read-side deployment workflows used by the Management API routes."""

    def __init__(
        self,
        twin_repository: TwinRepository,
        deployment_repository: DeploymentRepository,
        deployer_client: DeployerClient | None = None,
    ):
        self.twin_repository = twin_repository
        self.deployment_repository = deployment_repository
        self.deployer_client = deployer_client or DeployerClient()

    async def can_redeploy(self, twin_id: str, user_id: str) -> dict[str, Any]:
        """Return redeploy readiness for a twin."""
        twin = self._require_twin(twin_id, user_id)
        uses_gcp_firestore = self._uses_gcp_firestore(twin)

        if not twin.destroyed_at or not uses_gcp_firestore:
            return {"ready": True, "remaining_seconds": 0}

        return await self.deployer_client.check_cooldown(
            destroyed_at=twin.destroyed_at,
            uses_gcp_firestore=uses_gcp_firestore,
        )

    async def get_status(
        self,
        twin_id: str,
        user_id: str,
        active_session_provider: ActiveSessionProvider | None = None,
    ) -> dict[str, Any]:
        """Return current deployment status and reconnect metadata."""
        twin = self._require_twin(twin_id, user_id)
        active_session = None

        if active_session_provider and twin.state in (TwinState.DEPLOYING, TwinState.DESTROYING):
            sessions = await active_session_provider(twin_id)
            if sessions:
                session = sessions[0]
                active_session = {
                    "session_id": session.session_id,
                    "sse_url": f"/sse/deploy/{session.session_id}",
                    "operation_type": session.operation_type,
                }

        latest_deployment = self.deployment_repository.get_latest_for_twin(twin_id)

        return build_deployment_status_response(
            twin,
            active_session=active_session,
            latest_deployment=latest_deployment,
        ).model_dump(mode="json")

    def get_outputs(self, twin_id: str, user_id: str) -> dict[str, Any]:
        """Return outputs from the latest successful deploy/test deployment."""
        self._require_twin(twin_id, user_id)
        deployment = self.deployment_repository.latest_successful_deploy(twin_id)

        return build_deployment_outputs_response(deployment).model_dump(mode="json")

    def get_history(self, twin_id: str, user_id: str, limit: int) -> dict[str, Any]:
        """Return deployment history for a twin."""
        self._require_twin(twin_id, user_id)
        deployments = self.deployment_repository.list_for_twin(twin_id, limit)

        return build_deployment_history_response(deployments).model_dump(mode="json")

    @staticmethod
    def _deployment_summary(deployment) -> dict[str, Any] | None:
        if not deployment:
            return None
        return {
            "id": deployment.id,
            "session_id": deployment.session_id,
            "operation_id": deployment.operation_id,
            "operation_type": deployment.operation_type,
            "status": deployment.status,
            "started_at": deployment.started_at.isoformat() if deployment.started_at else None,
            "completed_at": deployment.completed_at.isoformat() if deployment.completed_at else None,
            "error_code": deployment.error_code,
            "error_message": deployment.error_message,
        }

    def _require_twin(self, twin_id: str, user_id: str) -> DigitalTwin:
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    @staticmethod
    def _uses_gcp_firestore(twin: DigitalTwin) -> bool:
        provider_candidates = [
            getattr(getattr(twin, "optimizer_config", None), "cheapest_l3_hot", None),
            getattr(getattr(twin, "deployer_config", None), "layer_3_hot_provider", None),
        ]
        return any(is_gcp_provider(provider) for provider in provider_candidates if provider)
