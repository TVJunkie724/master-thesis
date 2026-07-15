"""Deployment command use cases for Digital Twins."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session, joinedload

from src.models.twin import DigitalTwin, TwinState
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_service import (
    PreparedDeploymentProject,
    prepare_project_for_deployment,
    run_real_deploy_stream,
    run_real_destroy_stream,
)
from src.services.deployment_stream_service import (
    cleanup_session,
    create_session,
    get_active_sessions_for_twin,
)
from src.services.errors import InvalidTwinStateTransition, OperationAlreadyInProgress
from src.services.provider_contract import provider_id_for_deployer_api
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import (
    ConflictError,
    DownstreamServiceError,
    EntityNotFoundError,
    ValidationError,
)
from src.services.twin_lifecycle_service import TwinLifecycleService

logger = logging.getLogger(__name__)

ActiveSessionProvider = Callable[[str], Awaitable[list[Any]]]
SessionCreator = Callable[[str, str, str], Awaitable[Any]]
SessionCleaner = Callable[[str], Awaitable[None]]
TaskScheduler = Callable[[Awaitable[Any]], Any]
ProjectPreparer = Callable[[DigitalTwin, str], Awaitable[PreparedDeploymentProject]]


class DeploymentOperationService:
    """Deploy and destroy command workflows."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        active_session_provider: ActiveSessionProvider = get_active_sessions_for_twin,
        session_creator: SessionCreator = create_session,
        session_cleaner: SessionCleaner = cleanup_session,
        task_scheduler: TaskScheduler = asyncio.create_task,
        project_preparer: ProjectPreparer = prepare_project_for_deployment,
        lifecycle_service: TwinLifecycleService | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.active_session_provider = active_session_provider
        self.session_creator = session_creator
        self.session_cleaner = session_cleaner
        self.task_scheduler = task_scheduler
        self.project_preparer = project_preparer
        self.lifecycle_service = lifecycle_service or TwinLifecycleService()

    async def deploy_twin(
        self,
        twin_id: str,
        user_id: str,
        *,
        test_mode: bool,
        test_stream_runner: Callable[..., Awaitable[Any]] | None = None,
        skip_state_validation: bool = False,
    ) -> dict[str, str]:
        """Start deployment and return the SSE session location."""
        if test_mode and test_stream_runner is None:
            raise ValidationError("Test deployment runner is not configured")
        twin = self._require_active_twin(twin_id, user_id)
        previous_state = twin.state
        self._start_deploy(twin, skip_state_validation=skip_state_validation)
        try:
            active_sessions = await self.active_session_provider(twin_id)
        except Exception as exc:
            self.lifecycle_service.rollback_deploy_start(
                twin, previous_state=previous_state
            )
            self.db.rollback()
            raise DownstreamServiceError(
                status_code=500,
                public_detail="Failed to check active deployment operations",
            ) from exc
        if active_sessions:
            self.lifecycle_service.rollback_deploy_start(
                twin, previous_state=previous_state
            )
            self.db.rollback()
            raise ConflictError("Deployment already in progress for this twin")
        self.db.commit()

        if test_mode:
            session_id = str(uuid.uuid4())
            operation = test_stream_runner(
                session_id=session_id,
                twin_id=twin_id,
                twin_name=twin.name,
                duration=30,
                should_fail=False,
            )
            await self._create_session_and_schedule(
                twin=twin,
                previous_state=previous_state,
                session_id=session_id,
                operation_type="test",
                operation=operation,
                rollback=self.lifecycle_service.rollback_deploy_start,
                failure_detail="Failed to start deployment session",
            )
            return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

        twin = self._reload_for_deployment(twin_id, user_id)
        try:
            prepared_project = await self.project_preparer(twin, user_id)
        except DownstreamServiceError as exc:
            safe_detail = redact_secret_like_text(exc.public_detail)
            logger.error(
                "Deploy preparation failed for twin '%s' (%s): %s",
                twin.name,
                twin_id,
                safe_detail,
            )
            self.lifecycle_service.rollback_deploy_start(
                twin, previous_state=previous_state
            )
            self.db.commit()
            raise DownstreamServiceError(
                status_code=exc.status_code,
                public_detail=safe_detail,
            ) from exc
        except Exception as exc:
            logger.error(
                "Deploy preparation failed for twin '%s' (%s) (%s)",
                twin.name,
                twin_id,
                type(exc).__name__,
            )
            self.lifecycle_service.rollback_deploy_start(
                twin, previous_state=previous_state
            )
            self.db.commit()
            raise DownstreamServiceError(
                status_code=500, public_detail="Failed to prepare project"
            ) from exc

        provider = self._main_provider(twin)
        session_id = str(uuid.uuid4())
        operation = run_real_deploy_stream(
            session_id=session_id,
            twin_id=twin_id,
            resource_name=prepared_project.resource_name,
            provider=provider,
            operation_token=prepared_project.operation_token,
        )
        await self._create_session_and_schedule(
            twin=twin,
            previous_state=previous_state,
            session_id=session_id,
            operation_type="deploy",
            operation=operation,
            rollback=self.lifecycle_service.rollback_deploy_start,
            failure_detail="Failed to start deployment session",
        )
        return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

    async def destroy_twin(
        self,
        twin_id: str,
        user_id: str,
        *,
        test_mode: bool,
        test_stream_runner: Callable[..., Awaitable[Any]] | None = None,
        skip_state_validation: bool = False,
    ) -> dict[str, str]:
        """Start infrastructure destroy and return the SSE session location."""
        if test_mode and test_stream_runner is None:
            raise ValidationError("Test destroy runner is not configured")
        twin = self._require_active_twin(twin_id, user_id)
        previous_state = twin.state
        self._start_destroy(twin, skip_state_validation=skip_state_validation)
        try:
            active_sessions = await self.active_session_provider(twin_id)
        except Exception as exc:
            self.lifecycle_service.rollback_destroy_start(
                twin, previous_state=previous_state
            )
            self.db.rollback()
            raise DownstreamServiceError(
                status_code=500,
                public_detail="Failed to check active deployment operations",
            ) from exc
        if active_sessions:
            self.lifecycle_service.rollback_destroy_start(
                twin, previous_state=previous_state
            )
            self.db.rollback()
            raise ConflictError("Destroy operation already in progress for this twin")
        self.db.commit()

        if test_mode:
            session_id = str(uuid.uuid4())
            operation = test_stream_runner(
                session_id=session_id,
                twin_id=twin_id,
                twin_name=twin.name,
                duration=20,
                should_fail=False,
            )
            await self._create_session_and_schedule(
                twin=twin,
                previous_state=previous_state,
                session_id=session_id,
                operation_type="destroy",
                operation=operation,
                rollback=self.lifecycle_service.rollback_destroy_start,
                failure_detail="Failed to start destroy session",
            )
            return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

        twin = self._reload_for_deployment(twin_id, user_id)
        try:
            prepared_project = await self.project_preparer(twin, user_id)
        except DownstreamServiceError as exc:
            safe_detail = redact_secret_like_text(exc.public_detail)
            logger.error(
                "Destroy preparation failed for twin '%s' (%s): %s",
                twin.name,
                twin_id,
                safe_detail,
            )
            self.lifecycle_service.rollback_destroy_start(
                twin, previous_state=previous_state
            )
            self.db.commit()
            raise DownstreamServiceError(
                status_code=exc.status_code,
                public_detail=safe_detail,
            ) from exc
        except Exception as exc:
            logger.error(
                "Destroy preparation failed for twin '%s' (%s) (%s)",
                twin.name,
                twin_id,
                type(exc).__name__,
            )
            self.lifecycle_service.rollback_destroy_start(
                twin, previous_state=previous_state
            )
            self.db.commit()
            raise DownstreamServiceError(
                status_code=500,
                public_detail="Failed to prepare project for destroy",
            ) from exc

        provider = self._main_provider(twin)
        session_id = str(uuid.uuid4())
        operation = run_real_destroy_stream(
            session_id=session_id,
            twin_id=twin_id,
            resource_name=prepared_project.resource_name,
            provider=provider,
            operation_token=prepared_project.operation_token,
        )
        await self._create_session_and_schedule(
            twin=twin,
            previous_state=previous_state,
            session_id=session_id,
            operation_type="destroy",
            operation=operation,
            rollback=self.lifecycle_service.rollback_destroy_start,
            failure_detail="Failed to start destroy session",
        )
        return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

    async def _create_session_and_schedule(
        self,
        *,
        twin: DigitalTwin,
        previous_state: TwinState,
        session_id: str,
        operation_type: str,
        operation: Awaitable[Any],
        rollback: Callable[..., DigitalTwin],
        failure_detail: str,
    ) -> None:
        """Create a session and compensate state when scheduling cannot start."""
        try:
            await self.session_creator(twin.id, session_id, operation_type)
            self.task_scheduler(operation)
        except Exception as exc:
            close_operation = getattr(operation, "close", None)
            if callable(close_operation):
                close_operation()
            try:
                await self.session_cleaner(session_id)
            except Exception as cleanup_exc:
                logger.error(
                    "Failed to clean deployment session %s (%s)",
                    session_id,
                    type(cleanup_exc).__name__,
                )
            rollback(twin, previous_state=previous_state)
            self.db.commit()
            raise DownstreamServiceError(
                status_code=500,
                public_detail=failure_detail,
            ) from exc

    def _require_active_twin(self, twin_id: str, user_id: str) -> DigitalTwin:
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        return twin

    def _reload_for_deployment(self, twin_id: str, user_id: str) -> DigitalTwin:
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
            )
            .first()
        )
        if not twin:
            raise EntityNotFoundError("Twin not found during reload")
        return twin

    @staticmethod
    def _main_provider(twin: DigitalTwin) -> str:
        if twin.optimizer_config and twin.optimizer_config.cheapest_l1:
            return provider_id_for_deployer_api(twin.optimizer_config.cheapest_l1)
        return "aws"

    def _start_deploy(self, twin: DigitalTwin, *, skip_state_validation: bool) -> None:
        try:
            if skip_state_validation:
                self.lifecycle_service.force_start_deploy_for_test(twin)
            else:
                self.lifecycle_service.start_deploy(twin)
        except OperationAlreadyInProgress as exc:
            raise ConflictError(exc.message) from exc
        except InvalidTwinStateTransition as exc:
            raise ValidationError(exc.message) from exc

    def _start_destroy(self, twin: DigitalTwin, *, skip_state_validation: bool) -> None:
        try:
            if skip_state_validation:
                self.lifecycle_service.force_start_destroy_for_test(twin)
            else:
                self.lifecycle_service.start_destroy(twin)
        except OperationAlreadyInProgress as exc:
            raise ConflictError(exc.message) from exc
        except InvalidTwinStateTransition as exc:
            raise ValidationError(exc.message) from exc
