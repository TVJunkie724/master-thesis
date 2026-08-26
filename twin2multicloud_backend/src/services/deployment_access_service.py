"""Owner-scoped secret-free Layer Access read model."""

from __future__ import annotations

import hashlib
import threading

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from src.clients.deployer_client import DeployerClient
from src.models.deployment import Deployment
from src.models.twin import TwinState
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.schemas.deployment_access import (
    DeploymentAccessEvidence,
    DeploymentAccessCredential,
    DeploymentAccessSnapshot,
    SUPPORTED_DEPLOYMENT_ACCESS_PROFILES,
)
from src.services.service_errors import (
    ConflictError,
    EntityNotFoundError,
    ValidationError,
    DownstreamServiceError,
)
from src.services.deployment_service import prepare_project_for_deployment
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable


_ROTATION_GUARD = threading.Lock()
_ACTIVE_ROTATIONS: set[str] = set()


class DeploymentAccessService:
    """Build the public contract exclusively from persisted safe evidence."""

    def __init__(
        self,
        twin_repository: TwinRepository,
        deployment_repository: DeploymentRepository,
        *,
        db: Session | None = None,
        deployer_client: DeployerClient | None = None,
        project_preparer=prepare_project_for_deployment,
    ):
        self._twins = twin_repository
        self._deployments = deployment_repository
        self._db = db
        self._deployer = deployer_client or DeployerClient()
        self._project_preparer = project_preparer

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
        if profile not in SUPPORTED_DEPLOYMENT_ACCESS_PROFILES:
            raise ConflictError("DEPLOYMENT_ACCESS_PROFILE_NOT_SUPPORTED")
        try:
            evidence = DeploymentAccessEvidence.model_validate(
                deployment.deployment_access_evidence
            )
        except (PydanticValidationError, TypeError) as exc:
            raise ValidationError("DEPLOYMENT_ACCESS_EVIDENCE_INVALID") from exc
        if (evidence.profile_id, evidence.profile_version) != profile:
            raise ValidationError("DEPLOYMENT_ACCESS_EVIDENCE_PROFILE_MISMATCH")
        return DeploymentAccessSnapshot(
            twin_id=twin.id,
            deployment_id=deployment.id,
            generated_at=evidence.generated_at,
            availability="available",
            reason_code=None,
            surfaces=evidence.surfaces,
        )

    async def rotate_gcp_grafana_viewer(
        self,
        twin_id: str,
        user_id: str,
    ) -> DeploymentAccessCredential:
        """Rotate once while retaining only timestamp and fingerprint."""

        if self._db is None:
            raise RuntimeError("Rotation requires a database unit of work")
        snapshot = self.get_access(twin_id, user_id)
        l5 = snapshot.surfaces[1]
        if l5.provider != "gcp" or l5.auth.credential_action != "rotate":
            raise ConflictError("GCP_GRAFANA_VIEWER_ROTATION_NOT_AVAILABLE")
        deployment = self._deployments.latest_successful_deploy(twin_id)
        if deployment is None:
            raise ConflictError("DEPLOYMENT_ACCESS_DEPLOYMENT_NOT_FOUND")
        self._acquire_rotation(deployment.id)
        try:
            twin = self._twins.get_with_configs_for_user(twin_id, user_id)
            if twin is None:
                raise EntityNotFoundError("Twin not found")
            try:
                prepared = await self._project_preparer(
                    twin,
                    user_id,
                    frozen_graph_evidence=deployment.graph_validation,
                )
                self._deployments.assert_graph_compatible(
                    deployment,
                    prepared.graph_evidence,
                )
            except DownstreamServiceError:
                raise
            except Exception as exc:
                raise DownstreamServiceError(
                    status_code=500,
                    public_detail="Failed to prepare credential rotation",
                ) from exc
            try:
                payload = await self._deployer.rotate_gcp_grafana_viewer_credential(
                    prepared.resource_name,
                    prepared.operation_token,
                )
            except ExternalServiceUnavailable as exc:
                raise DownstreamServiceError(
                    status_code=503,
                    public_detail="Deployer API unavailable during credential rotation",
                ) from exc
            except ExternalServiceError as exc:
                raise DownstreamServiceError(
                    status_code=502,
                    public_detail="GCP Grafana Viewer rotation failed",
                ) from exc
            try:
                credential = DeploymentAccessCredential.model_validate(payload)
            except PydanticValidationError as exc:
                raise DownstreamServiceError(
                    status_code=502,
                    public_detail="Deployer returned an invalid rotation contract",
                ) from exc
            self._persist_rotation_metadata(deployment, credential)
            self._db.commit()
            return credential
        except Exception:
            self._db.rollback()
            raise
        finally:
            self._release_rotation(deployment.id)

    @staticmethod
    def _acquire_rotation(deployment_id: str) -> None:
        with _ROTATION_GUARD:
            if deployment_id in _ACTIVE_ROTATIONS:
                raise ConflictError("GCP_GRAFANA_VIEWER_ROTATION_IN_PROGRESS")
            _ACTIVE_ROTATIONS.add(deployment_id)

    @staticmethod
    def _release_rotation(deployment_id: str) -> None:
        with _ROTATION_GUARD:
            _ACTIVE_ROTATIONS.discard(deployment_id)

    @staticmethod
    def _persist_rotation_metadata(
        deployment: Deployment,
        credential: DeploymentAccessCredential,
    ) -> None:
        deployment.layer_access_credential_rotated_at = credential.issued_at
        deployment.layer_access_credential_fingerprint = hashlib.sha256(
            credential.password.encode("utf-8")
        ).hexdigest()
