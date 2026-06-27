"""Application orchestrator for Digital Twin deployment workflows."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session

from src.clients.deployer_client import DeployerClient
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_operation_service import DeploymentOperationService
from src.services.deployment_read_service import DeploymentReadService
from src.services.simulator_service import SimulatorDownload, SimulatorDownloadService
from src.services.verification_service import DeploymentVerificationService

ActiveSessionProvider = Callable[[str], Awaitable[list[Any]]]
TestStreamRunner = Callable[..., Awaitable[Any]]


class DeploymentOrchestrator:
    """Facade for deployment-facing route workflows.

    The concrete command/read/verification/simulator services keep their focused
    responsibilities. This orchestrator is the Management API boundary that
    routes depend on, so workflow ownership is explicit and routes stay thin.
    """

    def __init__(
        self,
        *,
        read_service: DeploymentReadService,
        operation_service: DeploymentOperationService,
        verification_service: DeploymentVerificationService,
        simulator_service: SimulatorDownloadService,
        test_deploy_stream_runner: TestStreamRunner | None = None,
        test_destroy_stream_runner: TestStreamRunner | None = None,
    ) -> None:
        self.read_service = read_service
        self.operation_service = operation_service
        self.verification_service = verification_service
        self.simulator_service = simulator_service
        self.test_deploy_stream_runner = test_deploy_stream_runner
        self.test_destroy_stream_runner = test_destroy_stream_runner

    @classmethod
    def from_session(
        cls,
        db: Session,
        *,
        test_deploy_stream_runner: TestStreamRunner | None = None,
        test_destroy_stream_runner: TestStreamRunner | None = None,
    ) -> DeploymentOrchestrator:
        """Build the default orchestrator graph for one API request."""
        twin_repository = TwinRepository(db)
        deployer_client = DeployerClient()
        return cls(
            read_service=DeploymentReadService(
                twin_repository=twin_repository,
                deployment_repository=DeploymentRepository(db),
                deployer_client=deployer_client,
            ),
            operation_service=DeploymentOperationService(
                db=db,
                twin_repository=twin_repository,
            ),
            verification_service=DeploymentVerificationService(
                db=db,
                twin_repository=twin_repository,
                deployer_client=deployer_client,
            ),
            simulator_service=SimulatorDownloadService(
                db=db,
                twin_repository=twin_repository,
                deployer_client=deployer_client,
            ),
            test_deploy_stream_runner=test_deploy_stream_runner,
            test_destroy_stream_runner=test_destroy_stream_runner,
        )

    async def can_redeploy(self, twin_id: str, user_id: str) -> dict[str, Any]:
        """Return deployment cooldown readiness."""
        return await self.read_service.can_redeploy(twin_id, user_id)

    async def deploy_twin(
        self,
        twin_id: str,
        user_id: str,
        *,
        test_mode: bool,
        test_stream_runner: TestStreamRunner | None = None,
    ) -> dict[str, str]:
        """Start a deploy operation."""
        return await self.operation_service.deploy_twin(
            twin_id=twin_id,
            user_id=user_id,
            test_mode=test_mode,
            test_stream_runner=test_stream_runner or self.test_deploy_stream_runner,
        )

    async def destroy_twin(
        self,
        twin_id: str,
        user_id: str,
        *,
        test_mode: bool,
        test_stream_runner: TestStreamRunner | None = None,
    ) -> dict[str, str]:
        """Start a destroy operation."""
        return await self.operation_service.destroy_twin(
            twin_id=twin_id,
            user_id=user_id,
            test_mode=test_mode,
            test_stream_runner=test_stream_runner or self.test_destroy_stream_runner,
        )

    async def get_status(
        self,
        twin_id: str,
        user_id: str,
        *,
        active_session_provider: ActiveSessionProvider | None = None,
    ) -> dict[str, Any]:
        """Return deployment status and reconnect metadata."""
        return await self.read_service.get_status(
            twin_id=twin_id,
            user_id=user_id,
            active_session_provider=active_session_provider,
        )

    def get_outputs(self, twin_id: str, user_id: str) -> dict[str, Any]:
        """Return latest deployment outputs."""
        return self.read_service.get_outputs(twin_id, user_id)

    def get_history(self, twin_id: str, user_id: str, limit: int) -> dict[str, Any]:
        """Return deployment history."""
        return self.read_service.get_history(twin_id, user_id, limit)

    async def verify_infrastructure(self, twin_id: str, user_id: str, *, test_mode: bool) -> dict[str, Any]:
        """Run structured infrastructure verification."""
        return await self.verification_service.verify_infrastructure(
            twin_id=twin_id,
            user_id=user_id,
            test_mode=test_mode,
        )

    async def start_dataflow_verification(
        self,
        twin_id: str,
        user_id: str,
        body: dict[str, Any],
        *,
        test_mode: bool,
    ) -> dict[str, str]:
        """Start dataflow verification."""
        return await self.verification_service.start_dataflow_verification(
            twin_id=twin_id,
            user_id=user_id,
            body=body,
            test_mode=test_mode,
        )

    async def download_simulator(self, twin_id: str, user_id: str, *, test_mode: bool) -> SimulatorDownload:
        """Return the IoT simulator archive."""
        return await self.simulator_service.download(
            twin_id=twin_id,
            user_id=user_id,
            test_mode=test_mode,
        )
