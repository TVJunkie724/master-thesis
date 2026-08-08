"""Owner-scoped secret-free Layer Access read model."""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from src.models.twin import TwinState
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployment_access import (
    DeploymentAccessEvidence,
    DeploymentAccessSnapshot,
)
from src.services.service_errors import (
    ConflictError,
    EntityNotFoundError,
    ValidationError,
)


class DeploymentAccessService:
    """Build the public contract exclusively from persisted safe evidence."""

    def __init__(
        self,
        twin_repository: TwinRepository,
        deployment_repository: DeploymentRepository,
    ):
        self._twins = twin_repository
        self._deployments = deployment_repository

    def get_access(self, twin_id: str, user_id: str) -> DeploymentAccessSnapshot:
        twin = self._twins.get_active_for_user(twin_id, user_id)
        if twin is None:
            raise EntityNotFoundError("Twin not found")
        if twin.state != TwinState.DEPLOYED:
            raise ConflictError("DEPLOYMENT_ACCESS_REQUIRES_DEPLOYED_TWIN")
        deployment = self._deployments.latest_successful_deploy(twin_id)
        if deployment is None:
            raise ConflictError("DEPLOYMENT_ACCESS_DEPLOYMENT_NOT_FOUND")

        profile = (deployment.profile_id, str(deployment.profile_version or ""))
        generated_at = deployment.completed_at or deployment.started_at
        if profile == ("five-layer-baseline", "1"):
            return DeploymentAccessSnapshot(
                twin_id=twin.id,
                deployment_id=deployment.id,
                generated_at=generated_at,
                availability="unsupported",
                reason_code="unsupported_historical_profile",
                surfaces=(),
            )
        if profile != ("five-layer-baseline", "2"):
            raise ConflictError("DEPLOYMENT_ACCESS_PROFILE_NOT_SUPPORTED")
        try:
            evidence = DeploymentAccessEvidence.model_validate(
                deployment.deployment_access_evidence
            )
        except (PydanticValidationError, TypeError) as exc:
            raise ValidationError(
                "DEPLOYMENT_ACCESS_EVIDENCE_INVALID"
            ) from exc
        return DeploymentAccessSnapshot(
            twin_id=twin.id,
            deployment_id=deployment.id,
            generated_at=evidence.generated_at,
            availability="available",
            reason_code=None,
            surfaces=evidence.surfaces,
        )
