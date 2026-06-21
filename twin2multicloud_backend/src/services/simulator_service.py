"""IoT simulator download use cases."""

from __future__ import annotations

import io
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session, joinedload

from src.models.twin import DigitalTwin, TwinState
from src.repositories.twin_repository import TwinRepository
from src.services import deployment_service
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError
from src.services.test_deployment_service import TestDeploymentService


ProjectPreparer = Callable[[DigitalTwin, str], Awaitable[str]]
SimulatorFetcher = Callable[[str, str], Awaitable[bytes]]


@dataclass(frozen=True)
class SimulatorDownload:
    """Prepared simulator archive for the HTTP adapter."""

    content: io.BytesIO
    filename: str
    media_type: str = "application/zip"


class SimulatorDownloadService:
    """Coordinates simulator archive downloads from test mode or Deployer."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        project_preparer: ProjectPreparer | None = None,
        simulator_fetcher: SimulatorFetcher | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.project_preparer = project_preparer or deployment_service.prepare_project_for_deployment
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
            )

        twin = self._reload_for_download(twin_id, user_id)
        if not twin.optimizer_config or not twin.optimizer_config.cheapest_l1:
            raise EntityNotFoundError("Optimization not configured. Complete Step 2 first.")

        l1_provider = twin.optimizer_config.cheapest_l1.lower()
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

        content = await self.simulator_fetcher(resource_name, l1_provider)
        return SimulatorDownload(
            content=io.BytesIO(content),
            filename=f"simulator_{resource_name}_{l1_provider}.zip",
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

    @staticmethod
    async def _fetch_from_deployer(resource_name: str, l1_provider: str) -> bytes:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{deployment_service.DEPLOYER_API_URL}/projects/{resource_name}/simulator/{l1_provider}/download",
                    timeout=60.0,
                )
            except httpx.RequestError as exc:
                raise DownstreamServiceError(
                    status_code=502,
                    public_detail=f"Failed to connect to Deployer: {redact_secret_like_text(str(exc))}",
                ) from exc

        if response.status_code == 404:
            raise EntityNotFoundError("Simulator not available. Ensure L1 deployed.")
        if response.status_code != 200:
            raise DownstreamServiceError(
                status_code=response.status_code,
                public_detail=f"Deployer error: {redact_secret_like_text(response.text)}",
            )
        return response.content
