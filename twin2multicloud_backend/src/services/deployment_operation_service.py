"""Deployment command use cases for Digital Twins."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.orm import Session, joinedload

from src.models.twin import DigitalTwin
from src.repositories.twin_repository import TwinRepository
from src.services.deployment_service import (
    get_resource_name,
    prepare_project_for_deployment,
    run_real_deploy_stream,
    run_real_destroy_stream,
)
from src.services.deployment_stream_service import create_session, get_active_sessions_for_twin
from src.services.errors import InvalidTwinStateTransition, OperationAlreadyInProgress
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import ConflictError, DownstreamServiceError, EntityNotFoundError, ValidationError
from src.services.twin_lifecycle_service import TwinLifecycleService

logger = logging.getLogger(__name__)

ActiveSessionProvider = Callable[[str], Awaitable[list[Any]]]
SessionCreator = Callable[[str, str, str], Awaitable[Any]]
TaskScheduler = Callable[[Awaitable[Any]], Any]
ProjectPreparer = Callable[[DigitalTwin, str], Awaitable[str]]


class DeploymentOperationService:
    """Deploy and destroy command workflows."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        active_session_provider: ActiveSessionProvider = get_active_sessions_for_twin,
        session_creator: SessionCreator = create_session,
        task_scheduler: TaskScheduler = asyncio.create_task,
        project_preparer: ProjectPreparer = prepare_project_for_deployment,
        lifecycle_service: TwinLifecycleService | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.active_session_provider = active_session_provider
        self.session_creator = session_creator
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
        twin = self._require_active_twin(twin_id, user_id)
        previous_state = twin.state
        self._start_deploy(twin, skip_state_validation=skip_state_validation)
        self.db.commit()

        active_sessions = await self.active_session_provider(twin_id)
        if active_sessions:
            self.lifecycle_service.rollback_deploy_start(twin, previous_state=previous_state)
            self.db.commit()
            raise ConflictError("Deployment already in progress for this twin")

        if test_mode:
            if test_stream_runner is None:
                raise ValidationError("Test deployment runner is not configured")
            session_id = str(uuid.uuid4())
            await self.session_creator(twin_id, session_id, "test")
            self.task_scheduler(
                test_stream_runner(
                    session_id=session_id,
                    twin_id=twin_id,
                    twin_name=twin.name,
                    duration=30,
                    should_fail=False,
                )
            )
            return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

        twin = self._reload_for_deployment(twin_id, user_id)
        try:
            resource_name = await self.project_preparer(twin, user_id)
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            detail = getattr(exc, "detail", None)
            if status_code:
                safe_detail = redact_secret_like_text(str(detail))
                logger.error("Deploy preparation failed for twin '%s' (%s): %s", twin.name, twin_id, safe_detail)
                self.lifecycle_service.rollback_deploy_start(twin, previous_state=previous_state)
                self.db.commit()
                raise DownstreamServiceError(status_code=status_code, public_detail=safe_detail) from exc

            logger.error("Deploy preparation failed for twin '%s' (%s)", twin.name, twin_id, exc_info=True)
            self.lifecycle_service.rollback_deploy_start(twin, previous_state=previous_state)
            self.db.commit()
            raise DownstreamServiceError(status_code=500, public_detail="Failed to prepare project") from exc

        provider = self._main_provider(twin)
        session_id = str(uuid.uuid4())
        await self.session_creator(twin_id, session_id, "deploy")
        self.task_scheduler(
            run_real_deploy_stream(
                session_id=session_id,
                twin_id=twin_id,
                resource_name=resource_name,
                provider=provider,
            )
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
        twin = self._require_active_twin(twin_id, user_id)
        previous_state = twin.state
        self._start_destroy(twin, skip_state_validation=skip_state_validation)
        self.db.commit()

        active_sessions = await self.active_session_provider(twin_id)
        if active_sessions:
            self.lifecycle_service.rollback_destroy_start(twin, previous_state=previous_state)
            self.db.commit()
            raise ConflictError("Destroy operation already in progress for this twin")

        if test_mode:
            if test_stream_runner is None:
                raise ValidationError("Test destroy runner is not configured")
            session_id = str(uuid.uuid4())
            await self.session_creator(twin_id, session_id, "destroy")
            self.task_scheduler(
                test_stream_runner(
                    session_id=session_id,
                    twin_id=twin_id,
                    twin_name=twin.name,
                    duration=20,
                    should_fail=False,
                )
            )
            return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

        twin = self._reload_for_deployment(twin_id, user_id)
        resource_name = get_resource_name(twin)
        try:
            await self.project_preparer(twin, user_id)
        except Exception as exc:
            logger.warning("Project preparation failed during destroy: %s", exc)

        provider = self._main_provider(twin)
        session_id = str(uuid.uuid4())
        await self.session_creator(twin_id, session_id, "destroy")
        self.task_scheduler(
            run_real_destroy_stream(
                session_id=session_id,
                twin_id=twin_id,
                resource_name=resource_name,
                provider=provider,
            )
        )
        return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

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
            return twin.optimizer_config.cheapest_l1.lower()
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
