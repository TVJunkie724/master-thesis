"""IoT simulator download use cases."""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from src.clients.deployer_client import (
    MAX_SIMULATOR_ARCHIVE_BYTES,
    DeployerClient,
    DeployerSimulatorArchive,
)
from src.models.twin import DigitalTwin, TwinState
from src.repositories.twin_repository import TwinRepository
from src.services import deployment_service
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.provider_contract import provider_id_for_deployer_api
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError
from src.services.test_deployment_service import TestDeploymentService


ProjectPreparer = Callable[[DigitalTwin, str], Awaitable[str]]
SimulatorFetcher = Callable[[str, str], Awaitable[DeployerSimulatorArchive]]

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}\.zip$")
_PROVIDER_CREDENTIAL_CLASSES = {
    "aws": "aws_iot_device_certificate",
    "azure": "azure_iot_hub_device_identity",
    "gcp": "gcp_pubsub_topic_publisher",
}


@dataclass(frozen=True)
class SimulatorDownload:
    """Prepared simulator archive for the HTTP adapter."""

    content: io.BytesIO
    filename: str
    media_type: str = "application/zip"
    provider: str = "gcp"
    credential_class: str = "demo_non_secret"


class SimulatorDownloadService:
    """Coordinates simulator archive downloads from test mode or Deployer."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        project_preparer: ProjectPreparer | None = None,
        simulator_fetcher: SimulatorFetcher | None = None,
        deployer_client: DeployerClient | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.project_preparer = project_preparer or deployment_service.prepare_project_for_deployment
        self.deployer_client = deployer_client or DeployerClient()
        self.simulator_fetcher = simulator_fetcher or self._fetch_from_deployer

    async def download(self, twin_id: str, user_id: str, *, test_mode: bool) -> SimulatorDownload:
        """Return the simulator archive for a deployed twin."""
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        if twin.state != TwinState.DEPLOYED:
            raise ValidationError(f"Simulator only available for deployed twins. Current: {twin.state.value}")

        if test_mode:
            mock_archive = TestDeploymentService(self.db, self.twin_repository).build_mock_simulator_archive(
                twin_id=twin_id,
                user_id=user_id,
            )
            return SimulatorDownload(
                content=mock_archive.content,
                filename=mock_archive.filename,
                media_type=mock_archive.media_type,
                provider=mock_archive.provider,
                credential_class=mock_archive.credential_class,
            )

        twin = self._reload_for_download(twin_id, user_id)
        if not twin.optimizer_config or not twin.optimizer_config.cheapest_l1:
            raise EntityNotFoundError("Optimization not configured. Complete Step 2 first.")

        l1_provider = provider_id_for_deployer_api(twin.optimizer_config.cheapest_l1)
        try:
            resource_name = await self.project_preparer(twin, user_id)
        except Exception as exc:
            raise DownstreamServiceError(
                status_code=500,
                public_detail=(
                    "Failed to prepare project for simulator download: "
                    f"{redact_secret_like_text(str(exc))}"
                ),
            ) from exc

        archive = await self.simulator_fetcher(resource_name, l1_provider)
        self._validate_archive(archive, expected_provider=l1_provider)
        return SimulatorDownload(
            content=io.BytesIO(archive.content),
            filename=archive.filename,
            media_type=archive.media_type,
            provider=archive.provider,
            credential_class=archive.credential_class,
        )

    def _reload_for_download(self, twin_id: str, user_id: str) -> DigitalTwin:
        twin = (
            self.db.query(DigitalTwin)
            .options(
                joinedload(DigitalTwin.deployer_config),
                joinedload(DigitalTwin.optimizer_config),
                joinedload(DigitalTwin.configuration),
            )
            .filter(
                DigitalTwin.id == twin_id,
                DigitalTwin.user_id == user_id,
                DigitalTwin.state != TwinState.INACTIVE,
            )
            .first()
        )
        if not twin:
            raise EntityNotFoundError("Twin not found during reload")
        return twin

    async def _fetch_from_deployer(
        self,
        resource_name: str,
        l1_provider: str,
    ) -> DeployerSimulatorArchive:
        try:
            return await self.deployer_client.download_simulator(resource_name, l1_provider)
        except ExternalServiceUnavailable as exc:
            raise DownstreamServiceError(
                status_code=502,
                public_detail=f"Failed to connect to Deployer: {redact_secret_like_text(exc.message)}",
            ) from exc
        except ExternalServiceError as exc:
            if exc.upstream_status_code == 404:
                raise EntityNotFoundError("Simulator not available. Ensure L1 deployed.") from exc
            raise DownstreamServiceError(
                status_code=exc.upstream_status_code or 502,
                public_detail=f"Deployer error: {redact_secret_like_text(exc.public_detail)}",
            ) from exc

    @staticmethod
    def _validate_archive(
        archive: DeployerSimulatorArchive,
        *,
        expected_provider: str,
    ) -> None:
        if archive.provider != expected_provider:
            raise DownstreamServiceError(
                status_code=502,
                public_detail="Deployer returned mismatched simulator metadata.",
            )
        if archive.media_type != "application/zip" or not _SAFE_FILENAME.fullmatch(archive.filename):
            raise DownstreamServiceError(
                status_code=502,
                public_detail="Deployer returned an invalid simulator archive contract.",
            )
        if archive.credential_class != _PROVIDER_CREDENTIAL_CLASSES.get(expected_provider):
            raise DownstreamServiceError(
                status_code=502,
                public_detail="Deployer returned mismatched simulator credential metadata.",
            )
        if not archive.content or len(archive.content) > MAX_SIMULATOR_ARCHIVE_BYTES:
            raise DownstreamServiceError(
                status_code=502,
                public_detail="Deployer returned an invalid simulator archive size.",
            )
        if not zipfile.is_zipfile(io.BytesIO(archive.content)):
            raise DownstreamServiceError(
                status_code=502,
                public_detail="Deployer returned an invalid simulator archive.",
            )
