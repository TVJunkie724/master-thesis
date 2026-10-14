"""Deployment verification use cases."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session, joinedload

from src.clients.deployer_client import DeployerClient
from src.models.telemetry_verification import TelemetryVerification
from src.models.twin import DigitalTwin, TwinState
from src.repositories.deployment_repository import DeploymentRepository
from src.repositories.telemetry_verification_repository import (
    TelemetryVerificationRepository,
)
from src.repositories.twin_repository import TwinRepository
from src.schemas.telemetry_verification import (
    TelemetryVerificationEvidence,
    TelemetryVerificationHistoryResponse,
    TelemetryVerificationRecordResponse,
    TelemetryVerificationStartResponse,
)
from src.services import deployment_service
from src.services.deployment_service import PreparedDeploymentProject
from src.services.deployment_stream_service import create_session, get_session
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import (
    ConflictError,
    DownstreamServiceError,
    EntityNotFoundError,
    ValidationError,
)

ProjectPreparer = Callable[[DigitalTwin, str], Awaitable[PreparedDeploymentProject]]
SessionCreator = Callable[[str, str, str], Awaitable[Any]]
SessionGetter = Callable[[str], Awaitable[Any | None]]
TaskScheduler = Callable[[Awaitable[Any]], Any]
InfrastructureVerifier = Callable[
    [PreparedDeploymentProject, str], Awaitable[dict[str, Any]]
]
logger = logging.getLogger(__name__)
MAX_VERIFICATION_PAYLOAD_BYTES = 128 * 1024
MAX_DEVICE_ID_LENGTH = 128


class DeploymentVerificationService:
    """Coordinates infrastructure and dataflow verification workflows."""

    def __init__(
        self,
        db: Session,
        twin_repository: TwinRepository,
        *,
        project_preparer: ProjectPreparer | None = None,
        session_creator: SessionCreator = create_session,
        session_getter: SessionGetter = get_session,
        task_scheduler: TaskScheduler = asyncio.create_task,
        infrastructure_verifier: InfrastructureVerifier | None = None,
        deployer_client: DeployerClient | None = None,
    ):
        self.db = db
        self.twin_repository = twin_repository
        self.project_preparer = (
            project_preparer or deployment_service.prepare_project_for_deployment
        )
        self.session_creator = session_creator
        self.session_getter = session_getter
        self.task_scheduler = task_scheduler
        self.deployer_client = deployer_client or DeployerClient()
        self.infrastructure_verifier = (
            infrastructure_verifier or self._verify_infrastructure_with_deployer
        )

    async def verify_infrastructure(
        self, twin_id: str, user_id: str, *, test_mode: bool
    ) -> dict[str, Any]:
        """Run structured infrastructure verification for a deployed twin."""
        twin = self._require_deployed_twin(
            twin_id,
            user_id,
            "verify infrastructure",
        )
        if test_mode:
            return self._mock_infrastructure_result()

        twin = self._reload_for_verification(twin_id, user_id)
        prepared_project = await self._prepare_project(
            twin, user_id, "Failed to prepare project"
        )
        provider = prepared_project.provider
        return await self.infrastructure_verifier(prepared_project, provider)

    async def start_dataflow_verification(
        self,
        twin_id: str,
        user_id: str,
        body: dict[str, Any],
        *,
        test_mode: bool,
    ) -> dict[str, Any]:
        """Start dataflow verification and return the SSE session contract."""
        self._require_deployed_twin(twin_id, user_id, "verify data flow")
        payload = self._validate_dataflow_payload(body)
        repository = TelemetryVerificationRepository(self.db)
        if repository.get_active_for_twin(twin_id) is not None:
            raise ConflictError("Telemetry verification already in progress")

        if test_mode:
            session_id = str(uuid.uuid4())
            record = repository.create_running(
                twin_id=twin_id,
                deployment_id=None,
                session_id=session_id,
                device_id=payload["iotDeviceId"],
            )
            session = await self.session_creator(twin_id, session_id, "verify_dataflow")
            repository.mark_completed(
                record,
                status="not_run",
                trace_id=None,
                result=None,
                error_code="TEST_MODE_NOT_RUN",
                error_message="Live telemetry verification was not run in test mode",
            )
            repository.prune_terminal_history(twin_id)
            self.db.commit()
            if session is not None:
                session.on_complete(
                    success=False,
                    message="Live telemetry verification was not run in test mode",
                    error_code="TEST_MODE_NOT_RUN",
                )
            return self._start_response(record)

        twin = self._reload_for_verification(twin_id, user_id)
        deployment = DeploymentRepository(self.db).latest_successful_deploy(twin_id)
        if deployment is None:
            raise ValidationError(
                "Twin has no successful deployment to bind verification evidence to"
            )
        prepared_project = await self._prepare_project(
            twin, user_id, "Failed to prepare project"
        )
        session_id = str(uuid.uuid4())
        record = repository.create_running(
            twin_id=twin_id,
            deployment_id=deployment.id,
            session_id=session_id,
            device_id=payload["iotDeviceId"],
        )
        self.db.commit()
        operation = self.proxy_dataflow_sse(
            verification_id=record.id,
            session_id=session_id,
            prepared_project=prepared_project,
            payload=payload,
        )
        try:
            await self.session_creator(twin_id, session_id, "verify_dataflow")
            self.task_scheduler(operation)
        except Exception as exc:
            close_operation = getattr(operation, "close", None)
            if callable(close_operation):
                close_operation()
            repository.mark_completed(
                record,
                status="fail",
                trace_id=None,
                result=None,
                error_code="VERIFICATION_START_FAILED",
                error_message="Failed to start telemetry verification",
            )
            repository.prune_terminal_history(twin_id)
            self.db.commit()
            raise DownstreamServiceError(
                status_code=500,
                public_detail="Failed to start telemetry verification",
            ) from exc
        return self._start_response(record)

    async def proxy_dataflow_sse(
        self,
        verification_id: str,
        session_id: str,
        prepared_project: PreparedDeploymentProject,
        payload: dict[str, Any],
    ) -> None:
        """Proxy Deployer dataflow SSE messages into the Management SSE session."""
        session = await self.session_getter(session_id)
        if not session:
            self._mark_dataflow_failed(
                verification_id,
                error_code="VERIFICATION_SESSION_MISSING",
                error_message="Telemetry verification session is unavailable",
            )
            return

        try:
            event_name: str | None = None
            terminal: TelemetryVerificationEvidence | None = None
            async for line in self.deployer_client.verify_dataflow(
                prepared_project.resource_name,
                payload,
                prepared_project.operation_token,
            ):
                if not line:
                    event_name = None
                    continue
                if line.startswith("event: "):
                    event_name = line.removeprefix("event: ").strip()
                    continue
                if line.startswith("data: "):
                    message = line[6:]
                    if event_name == "done":
                        if terminal is not None:
                            raise ValueError("Duplicate verification terminal event")
                        terminal = TelemetryVerificationEvidence.model_validate_json(
                            message
                        )
                        message = json.dumps(
                            terminal.model_dump(mode="json", exclude_none=True),
                            separators=(",", ":"),
                        )
                    else:
                        message = redact_secret_like_text(message)
                    await session.push_log(message)
            if terminal is None:
                raise ValueError("Verification terminal event is missing")
            repository = TelemetryVerificationRepository(self.db)
            record = repository.get_by_id(verification_id)
            if record is None:
                raise RuntimeError("Telemetry verification record is unavailable")
            repository.mark_completed(
                record,
                status=terminal.status,
                trace_id=terminal.trace_id,
                result=terminal.model_dump(mode="json", exclude_none=True),
                error_code=(
                    None if terminal.status == "pass" else "TELEMETRY_ROUNDTRIP_FAILED"
                ),
                error_message=(
                    None
                    if terminal.status == "pass"
                    else f"Verification failed at: {terminal.failed_phase}"
                ),
            )
            repository.prune_terminal_history(record.twin_id)
            self.db.commit()
            verification_ok = terminal.status == "pass"
            summary_message = (
                "Telemetry roundtrip verified"
                if verification_ok
                else f"Verification failed at: {terminal.failed_phase}"
            )
            session.on_complete(success=verification_ok, message=summary_message)
        except (PydanticValidationError, ValueError) as exc:
            logger.error(
                "Invalid dataflow verification evidence (%s)", type(exc).__name__
            )
            safe_error = "Deployer returned invalid telemetry verification evidence"
            self._mark_dataflow_failed(
                verification_id,
                error_code="INVALID_VERIFICATION_EVIDENCE",
                error_message=safe_error,
            )
            await session.push_log(
                json.dumps(
                    {
                        "timestamp": "",
                        "message": f"Verification error: {safe_error}",
                        "status": "fail",
                    }
                )
            )
            session.on_complete(
                success=False,
                message=safe_error,
                error_code="INVALID_VERIFICATION_EVIDENCE",
            )
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            safe_error = self._deployer_error_message(exc)
            self._mark_dataflow_failed(
                verification_id,
                error_code="DEPLOYER_VERIFICATION_FAILED",
                error_message=safe_error,
            )
            await session.push_log(
                json.dumps(
                    {
                        "timestamp": "",
                        "message": f"Verification error: {safe_error}",
                        "status": "fail",
                    }
                )
            )
            session.on_complete(
                success=False,
                message=safe_error,
                error_code="DEPLOYER_VERIFICATION_FAILED",
            )
        except Exception as exc:
            logger.error(
                "Unexpected dataflow verification failure (%s)", type(exc).__name__
            )
            safe_error = "Verification failed unexpectedly"
            self._mark_dataflow_failed(
                verification_id,
                error_code="VERIFICATION_FAILED",
                error_message=safe_error,
            )
            await session.push_log(
                json.dumps(
                    {
                        "timestamp": "",
                        "message": f"Verification error: {safe_error}",
                        "status": "fail",
                    }
                )
            )
            session.on_complete(
                success=False,
                message=safe_error,
                error_code="VERIFICATION_FAILED",
            )

    def get_dataflow_verification(
        self,
        twin_id: str,
        user_id: str,
        verification_id: str,
    ) -> TelemetryVerificationRecordResponse:
        """Return one owner-scoped persisted telemetry result."""

        self._require_owned_twin(twin_id, user_id)
        record = TelemetryVerificationRepository(self.db).get_by_id(verification_id)
        if record is None or record.twin_id != twin_id:
            raise EntityNotFoundError("Telemetry verification not found")
        return self._record_response(record)

    def list_dataflow_verifications(
        self,
        twin_id: str,
        user_id: str,
        *,
        limit: int,
    ) -> TelemetryVerificationHistoryResponse:
        """Return bounded newest-first telemetry evidence for one Twin."""

        self._require_owned_twin(twin_id, user_id)
        records = TelemetryVerificationRepository(self.db).list_for_twin(
            twin_id, limit=limit
        )
        return TelemetryVerificationHistoryResponse(
            verifications=[self._record_response(record) for record in records]
        )

    def _require_deployed_twin(
        self, twin_id: str, user_id: str, operation: str
    ) -> DigitalTwin:
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if not twin:
            raise EntityNotFoundError("Twin not found")
        if twin.state != TwinState.DEPLOYED:
            raise ValidationError(
                f"Twin must be deployed to {operation} (current state: {twin.state})"
            )
        return twin

    def _require_owned_twin(self, twin_id: str, user_id: str) -> DigitalTwin:
        twin = self.twin_repository.get_active_for_user(twin_id, user_id)
        if twin is None:
            raise EntityNotFoundError("Twin not found")
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

    async def _prepare_project(
        self,
        twin: DigitalTwin,
        user_id: str,
        message: str,
    ) -> PreparedDeploymentProject:
        try:
            return await self.project_preparer(twin, user_id)
        except DownstreamServiceError as exc:
            safe_detail = redact_secret_like_text(exc.public_detail)
            logger.error(
                "Project preparation for verification failed downstream (%s)",
                exc.status_code,
            )
            raise DownstreamServiceError(
                status_code=exc.status_code,
                public_detail=safe_detail,
            ) from exc
        except Exception as exc:
            logger.error(
                "Project preparation for verification failed (%s)", type(exc).__name__
            )
            raise DownstreamServiceError(
                status_code=500,
                public_detail=message,
            ) from exc

    @staticmethod
    def _validate_dataflow_payload(body: dict[str, Any]) -> dict[str, Any]:
        payload = body.get("payload") if isinstance(body, dict) else None
        if not isinstance(payload, dict):
            raise ValidationError(
                "Request body must contain 'payload' with 'iotDeviceId' field"
            )
        device_id = payload.get("iotDeviceId")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValidationError("payload.iotDeviceId must be a non-empty string")
        device_id = device_id.strip()
        if len(device_id) > MAX_DEVICE_ID_LENGTH:
            raise ValidationError(
                f"payload.iotDeviceId must not exceed {MAX_DEVICE_ID_LENGTH} characters"
            )
        try:
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValidationError("payload must be JSON serializable") from exc
        if len(encoded) > MAX_VERIFICATION_PAYLOAD_BYTES:
            raise ValidationError(
                "payload exceeds the portable cloud message limit of 128 KiB"
            )
        return {**payload, "iotDeviceId": device_id}

    async def _verify_infrastructure_with_deployer(
        self,
        prepared_project: PreparedDeploymentProject,
        provider: str,
    ) -> dict[str, Any]:
        try:
            return await self.deployer_client.verify_infrastructure(
                prepared_project.resource_name,
                provider,
                prepared_project.operation_token,
            )
        except ExternalServiceError as exc:
            raise DownstreamServiceError(
                status_code=exc.upstream_status_code or 502,
                public_detail=f"Deployer API error: {redact_secret_like_text(exc.public_detail)}",
            ) from exc
        except ExternalServiceUnavailable as exc:
            raise DownstreamServiceError(
                status_code=503,
                public_detail=f"Deployer API unavailable: {redact_secret_like_text(exc.message)}",
            ) from exc

    @staticmethod
    def _deployer_error_message(
        exc: ExternalServiceError | ExternalServiceUnavailable,
    ) -> str:
        if isinstance(exc, ExternalServiceUnavailable):
            return "Deployer API unavailable"
        return f"Deployer API error: {redact_secret_like_text(exc.public_detail)}"

    def _mark_dataflow_failed(
        self,
        verification_id: str,
        *,
        error_code: str,
        error_message: str,
    ) -> None:
        self.db.rollback()
        repository = TelemetryVerificationRepository(self.db)
        record = repository.get_by_id(verification_id)
        if record is None:
            logger.error("Telemetry verification record disappeared before completion")
            return
        repository.mark_completed(
            record,
            status="fail",
            trace_id=None,
            result=None,
            error_code=error_code,
            error_message=error_message,
        )
        repository.prune_terminal_history(record.twin_id)
        self.db.commit()

    @staticmethod
    def _start_response(record: TelemetryVerification) -> dict[str, Any]:
        return TelemetryVerificationStartResponse(
            verification_id=record.id,
            session_id=record.session_id,
            sse_url=f"/sse/deploy/{record.session_id}",
            status_url=(f"/twins/{record.twin_id}/verify/dataflow/{record.id}"),
            status=record.status,
        ).model_dump(mode="json")

    @staticmethod
    def _record_response(
        record: TelemetryVerification,
    ) -> TelemetryVerificationRecordResponse:
        result = (
            TelemetryVerificationEvidence.model_validate(record.result)
            if isinstance(record.result, dict)
            else None
        )
        return TelemetryVerificationRecordResponse(
            id=record.id,
            twin_id=record.twin_id,
            deployment_id=record.deployment_id,
            session_id=record.session_id,
            device_id=record.device_id,
            status=record.status,
            trace_id=record.trace_id,
            result=result,
            error_code=record.error_code,
            error_message=record.error_message,
            requested_at=record.requested_at,
            completed_at=record.completed_at,
        )

    @staticmethod
    def _mock_infrastructure_result() -> dict[str, Any]:
        return {
            "checks": [
                {
                    "name": "L0 Setup resources",
                    "status": "pass",
                    "provider": "",
                    "detail": "12 resources found",
                    "layer": "L0",
                },
                {
                    "name": "L0 Glue functions",
                    "status": "pass",
                    "provider": "",
                    "detail": "cold-writer, hot-reader",
                    "layer": "L0",
                },
                {
                    "name": "IoT endpoint",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "endpoint active",
                    "layer": "L1",
                },
                {
                    "name": "IoT devices registered",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "2 device(s)",
                    "layer": "L1",
                },
                {
                    "name": "Functions deployed",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "5 resources",
                    "layer": "L2",
                },
                {
                    "name": "Hot storage",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "deployed",
                    "layer": "L3",
                },
                {
                    "name": "Cold storage",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "deployed",
                    "layer": "L3",
                },
                {
                    "name": "Archive storage",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "deployed",
                    "layer": "L3",
                },
                {
                    "name": "Hot→Cold mover",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "deployed",
                    "layer": "L3",
                },
                {
                    "name": "Cold→Archive mover",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "deployed",
                    "layer": "L3",
                },
                {
                    "name": "TwinMaker workspace",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "deployed",
                    "layer": "L4",
                },
                {
                    "name": "TwinMaker entities",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "2 entities created",
                    "layer": "L4",
                },
                {
                    "name": "ADT twins",
                    "status": "skip",
                    "provider": "",
                    "detail": "L4 not Azure",
                    "layer": "L4",
                },
                {
                    "name": "Grafana workspace",
                    "status": "pass",
                    "provider": "AWS",
                    "detail": "deployed",
                    "layer": "L5",
                },
            ],
            "summary": {
                "pass_count": 13,
                "fail_count": 0,
                "skip_count": 1,
                "total": 14,
                "healthy": True,
            },  # nosec B105
        }
