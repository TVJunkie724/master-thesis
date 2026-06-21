"""Deployment verification use cases."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from sqlalchemy.orm import Session, joinedload

from src.models.twin import DigitalTwin, TwinState
from src.repositories.twin_repository import TwinRepository
from src.services import deployment_service
from src.services.deployment_stream_service import create_session, get_session
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import DownstreamServiceError, EntityNotFoundError, ValidationError


ProjectPreparer = Callable[[DigitalTwin, str], Awaitable[str]]
SessionCreator = Callable[[str, str, str], Awaitable[Any]]
TaskScheduler = Callable[[Awaitable[Any]], Any]
InfrastructureVerifier = Callable[[str, str], Awaitable[dict[str, Any]]]


class DeploymentVerificationService:
    """Coordinates infrastructure and dataflow verification workflows."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        project_preparer: ProjectPreparer | None = None,
        session_creator: SessionCreator = create_session,
        task_scheduler: TaskScheduler = asyncio.create_task,
        infrastructure_verifier: InfrastructureVerifier | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.project_preparer = project_preparer or deployment_service.prepare_project_for_deployment
        self.session_creator = session_creator
        self.task_scheduler = task_scheduler
        self.infrastructure_verifier = infrastructure_verifier or self._verify_infrastructure_with_deployer

    async def verify_infrastructure(self, twin_id: str, user_id: str, *, test_mode: bool) -> dict[str, Any]:
        """Run structured infrastructure verification for a deployed twin."""
        twin = self._require_deployed_twin(
            twin_id,
            user_id,
            "verify infrastructure",
        )
        if test_mode:
            return self._mock_infrastructure_result()

        twin = self._reload_for_verification(twin_id, user_id)
        resource_name = await self._prepare_project(twin, user_id, "Failed to prepare project")
        provider = self._main_provider(twin)
        return await self.infrastructure_verifier(resource_name, provider)

    async def start_dataflow_verification(
        self,
        twin_id: str,
        user_id: str,
        body: dict[str, Any],
        *,
        test_mode: bool,
    ) -> dict[str, str]:
        """Start dataflow verification and return the SSE session contract."""
        self._require_deployed_twin(twin_id, user_id, "verify data flow")
        payload = self._validate_dataflow_payload(body)

        session_id = str(uuid.uuid4())
        await self.session_creator(twin_id, session_id, "verify_dataflow")
        if test_mode:
            return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

        twin = self._reload_for_verification(twin_id, user_id)
        resource_name = await self._prepare_project(twin, user_id, "Failed to prepare project")
        self.task_scheduler(
            self.proxy_dataflow_sse(
                session_id=session_id,
                resource_name=resource_name,
                payload=payload,
            )
        )
        return {"session_id": session_id, "sse_url": f"/sse/deploy/{session_id}"}

    async def proxy_dataflow_sse(self, session_id: str, resource_name: str, payload: dict[str, Any]) -> None:
        """Proxy Deployer dataflow SSE messages into the Management SSE session."""
        session = await get_session(session_id)
        if not session:
            return

        try:
            timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{deployment_service.DEPLOYER_API_URL}/dataflow/verify",
                    params={"project_name": resource_name},
                    json={"payload": payload},
                ) as response:
                    last_data = None
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            message = line[6:]
                            last_data = message
                            await session.push_log(message)

            verification_ok = True
            summary_message = "Data flow verification complete"
            if last_data:
                try:
                    summary = json.loads(last_data)
                    fail_count = summary.get("fail_count", 0)
                    verification_ok = fail_count == 0
                    if not verification_ok:
                        failed_phase = summary.get("failed_phase", "unknown")
                        summary_message = f"Verification failed at: {failed_phase}"
                except (json.JSONDecodeError, TypeError):
                    pass
            session.on_complete(success=verification_ok, message=summary_message)
        except Exception as exc:
            await session.push_log(
                json.dumps(
                    {
                        "timestamp": "",
                        "message": f"Verification error: {exc}",
                        "status": "fail",
                    }
                )
            )
            session.on_complete(success=False, message=str(exc))

    def _require_deployed_twin(self, twin_id: str, user_id: str, operation: str) -> DigitalTwin:
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        if twin.state != TwinState.DEPLOYED:
            raise ValidationError(f"Twin must be deployed to {operation} (current state: {twin.state})")
        return twin

    def _reload_for_verification(self, twin_id: str, user_id: str) -> DigitalTwin:
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

    async def _prepare_project(self, twin: DigitalTwin, user_id: str, message: str) -> str:
        try:
            return await self.project_preparer(twin, user_id)
        except Exception as exc:
            raise DownstreamServiceError(
                status_code=500,
                public_detail=f"{message}: {redact_secret_like_text(str(exc))}",
            ) from exc

    @staticmethod
    def _validate_dataflow_payload(body: dict[str, Any]) -> dict[str, Any]:
        payload = body.get("payload", {})
        if not payload or "iotDeviceId" not in payload:
            raise ValidationError("Request body must contain 'payload' with 'iotDeviceId' field")
        return payload

    @staticmethod
    def _main_provider(twin: DigitalTwin) -> str:
        if twin.optimizer_config and twin.optimizer_config.cheapest_l1:
            return twin.optimizer_config.cheapest_l1.lower()
        return "aws"

    @staticmethod
    async def _verify_infrastructure_with_deployer(resource_name: str, provider: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{deployment_service.DEPLOYER_API_URL}/infrastructure/verify",
                    params={"project_name": resource_name, "provider": provider},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise DownstreamServiceError(
                status_code=exc.response.status_code,
                public_detail=f"Deployer API error: {redact_secret_like_text(exc.response.text)}",
            ) from exc
        except httpx.RequestError as exc:
            raise DownstreamServiceError(
                status_code=503,
                public_detail=f"Deployer API unavailable: {redact_secret_like_text(str(exc))}",
            ) from exc

    @staticmethod
    def _mock_infrastructure_result() -> dict[str, Any]:
        return {
            "checks": [
                {"name": "L0 Setup resources", "status": "pass", "provider": "", "detail": "12 resources found", "layer": "L0"},
                {"name": "L0 Glue functions", "status": "pass", "provider": "", "detail": "cold-writer, hot-reader", "layer": "L0"},
                {"name": "IoT endpoint", "status": "pass", "provider": "AWS", "detail": "endpoint active", "layer": "L1"},
                {"name": "IoT devices registered", "status": "pass", "provider": "AWS", "detail": "2 device(s)", "layer": "L1"},
                {"name": "Functions deployed", "status": "pass", "provider": "AWS", "detail": "5 resources", "layer": "L2"},
                {"name": "Hot storage", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "Cold storage", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "Archive storage", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "Hot→Cold mover", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "Cold→Archive mover", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L3"},
                {"name": "TwinMaker workspace", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L4"},
                {"name": "TwinMaker entities", "status": "pass", "provider": "AWS", "detail": "2 entities created", "layer": "L4"},
                {"name": "ADT twins", "status": "skip", "provider": "", "detail": "L4 not Azure", "layer": "L4"},
                {"name": "Grafana workspace", "status": "pass", "provider": "AWS", "detail": "deployed", "layer": "L5"},
            ],
            "summary": {"pass_count": 13, "fail_count": 0, "skip_count": 1, "total": 14, "healthy": True},
        }
