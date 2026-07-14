"""Digital Twin operation API adapters.

This module keeps deployment, verification, log trace, simulator, and export
routes separate from the CRUD/lifecycle adapter in ``twins.py`` while preserving
the public ``/twins`` paths used by Flutter.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.routes.error_models import ERROR_RESPONSES
from src.clients.deployer_client import DeployerClient
from src.config import settings
from src.models.database import get_db
from src.models.twin import TwinState
from src.models.user import User
from src.repositories.twin_repository import TwinRepository
from src.schemas.management_contracts import (
    OperationSessionResponse,
    RedeployReadinessResponse,
)
from src.schemas.deployment_logs import DeploymentLogPageResponse
from src.schemas.deployment_operations import (
    DeploymentHistoryResponse,
    DeploymentOutputsResponse,
    DeploymentStatusResponse,
)
from src.schemas.deployment_readiness import (
    DeploymentPreflightResponse,
    DeploymentReadinessResponse,
)
from src.services.deployment_log_read_service import DeploymentLogReadService
from src.services.deployment_orchestrator import DeploymentOrchestrator
from src.services.deployment_readiness_service import DeploymentReadinessService
from src.services.errors import ExternalServiceError, ExternalServiceUnavailable
from src.services.secret_redaction import redact_secret_like_text
from src.services.service_errors import ConflictError, DownstreamServiceError, EntityNotFoundError, ValidationError
from src.services.twin_export_service import TwinExportService

logger = logging.getLogger(__name__)

TEST_MODE = os.getenv("ENABLE_TEST_ENDPOINTS", "false").lower() == "true"

router = APIRouter(prefix="/twins", tags=["twins"])


def _deployment_orchestrator(db: Session) -> DeploymentOrchestrator:
    """Build the deployment workflow orchestrator for this request."""
    test_deploy_stream_runner = None
    test_destroy_stream_runner = None
    if TEST_MODE:
        from src.api.routes.test_endpoints import _run_test_deploy_stream, _run_test_destroy_stream

        test_deploy_stream_runner = _run_test_deploy_stream
        test_destroy_stream_runner = _run_test_destroy_stream

    return DeploymentOrchestrator.from_session(
        db,
        test_deploy_stream_runner=test_deploy_stream_runner,
        test_destroy_stream_runner=test_destroy_stream_runner,
    )


def _twin_export_service(db: Session) -> TwinExportService:
    """Build the redacted twin export service for this request."""
    return TwinExportService(db=db, twin_repository=TwinRepository(db))


def _deployment_readiness_service(db: Session) -> DeploymentReadinessService:
    """Build the owner-scoped readiness service for one request."""
    return DeploymentReadinessService(
        db,
        max_age=timedelta(
            minutes=settings.DEPLOYMENT_PREFLIGHT_MAX_AGE_MINUTES,
        ),
    )


def _raise_service_http_error(exc: Exception) -> None:
    """Map typed service errors to the existing route-level HTTP contract."""
    if isinstance(exc, EntityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, DownstreamServiceError):
        raise HTTPException(status_code=exc.status_code, detail=exc.public_detail) from exc
    raise exc


@router.get(
    "/{twin_id}/can-redeploy",
    response_model=RedeployReadinessResponse,
    operation_id="checkRedeploymentCooldown",
    summary="Check if twin can be redeployed",
    description=(
        "Checks deployment cooldown readiness, including the GCP Firestore cooldown rule, "
        "before a destroyed twin is redeployed."
    ),
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404], 503: {"description": "Deployer API unavailable"}},
)
async def can_redeploy(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await _deployment_orchestrator(db).can_redeploy(twin_id, current_user.id)
    except (EntityNotFoundError, DownstreamServiceError) as exc:
        _raise_service_http_error(exc)


@router.post(
    "/{twin_id}/deploy",
    response_model=OperationSessionResponse,
    operation_id="deployDigitalTwin",
    summary="Deploy twin infrastructure",
    description=(
        "Starts deployment for a configured, destroyed, or error-state twin and returns the SSE "
        "session contract for real-time deployment logs."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        409: {"description": "Deployment already in progress"},
    },
)
async def deploy_twin(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        _deployment_readiness_service(db).require_ready(
            twin_id,
            current_user.id,
        )
        return await _deployment_orchestrator(db).deploy_twin(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=TEST_MODE,
        )
    except (ConflictError, DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@router.post(
    "/{twin_id}/destroy",
    response_model=OperationSessionResponse,
    operation_id="destroyDigitalTwinInfrastructure",
    summary="Destroy twin infrastructure",
    description=(
        "Starts infrastructure destruction for a deployed or error-state twin and returns the SSE "
        "session contract for real-time destroy logs."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        409: {"description": "Destroy operation already in progress"},
    },
)
async def destroy_twin_infrastructure(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await _deployment_orchestrator(db).destroy_twin(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=TEST_MODE,
        )
    except (ConflictError, DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}/deployment-readiness",
    response_model=DeploymentReadinessResponse,
    operation_id="getDigitalTwinDeploymentReadiness",
    summary="Get cached deployment readiness",
    description=(
        "Returns owner-scoped cached provider readiness for the currently selected "
        "architecture. This read endpoint never contacts a cloud provider."
    ),
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]},
)
async def get_deployment_readiness(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _deployment_readiness_service(db).get_cached(
            twin_id,
            current_user.id,
        )
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.post(
    "/{twin_id}/deployment-preflight",
    response_model=DeploymentPreflightResponse,
    operation_id="runDigitalTwinDeploymentPreflight",
    summary="Run explicit deployment provider preflight",
    description=(
        "Validates only the deployment Cloud Connections required by the stored "
        "provider architecture. It creates no cloud resources and persists only "
        "redacted readiness evidence."
    ),
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]},
)
async def run_deployment_preflight(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await _deployment_readiness_service(db).run_preflight(
            twin_id,
            current_user.id,
        )
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}/deployment-status",
    response_model=DeploymentStatusResponse,
    operation_id="getDigitalTwinDeploymentStatus",
    summary="Get current deployment status",
    description="Returns persisted deployment state, timestamps, latest deployment metadata, and active SSE reconnect data.",
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]},
)
async def get_deployment_status(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from src.services.deployment_stream_service import get_active_sessions_for_twin

    try:
        return await _deployment_orchestrator(db).get_status(
            twin_id=twin_id,
            user_id=current_user.id,
            active_session_provider=get_active_sessions_for_twin,
        )
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}/outputs",
    response_model=DeploymentOutputsResponse,
    operation_id="getDigitalTwinTerraformOutputs",
    summary="Get latest Terraform outputs",
    description="Returns Terraform outputs from the latest successful deploy or test deployment for this twin.",
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]},
)
async def get_deployment_outputs(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _deployment_orchestrator(db).get_outputs(twin_id, current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}/deployments",
    response_model=DeploymentHistoryResponse,
    operation_id="getDigitalTwinDeploymentHistory",
    summary="Get deployment history",
    description="Returns recent deployment and destroy records for audit, troubleshooting, and UI history views.",
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]},
)
async def get_deployment_history(
    twin_id: str,
    limit: int = Query(10, ge=1, le=50, description="Max number of deployments to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return _deployment_orchestrator(db).get_history(twin_id, current_user.id, limit)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}/logs",
    response_model=DeploymentLogPageResponse,
    operation_id="getDigitalTwinDeploymentLogs",
    summary="Get a bounded page of persisted deployment logs",
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404]},
)
async def get_deployment_logs(
    twin_id: str,
    session_id: str | None = Query(default=None),
    after_event_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    twin = TwinRepository(db).get_active_for_user(twin_id, current_user.id)
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    return DeploymentLogReadService(db).get_page(
        twin,
        session_id=session_id,
        after_event_id=after_event_id,
        limit=limit,
    )


@router.post(
    "/{twin_id}/log-trace/start",
    operation_id="startLogTrace",
    summary="Start a deployment log trace",
    description=(
        "Sends or simulates a traceable IoT test message for a deployed twin and returns trace metadata "
        "plus the optional SSE session contract."
    ),
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        429: {"description": "Rate limited"},
        503: {"description": "Deployer API unavailable"},
    },
)
async def start_log_trace(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    twin = TwinRepository(db).get_with_configs_for_user(twin_id, current_user.id)
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")
    if twin.state != TwinState.DEPLOYED:
        raise HTTPException(
            status_code=400,
            detail=f"Twin must be deployed to trace logs (current state: {twin.state})",
        )

    if TEST_MODE:
        from src.services.deployment_stream_service import create_session
        from src.api.routes.test_endpoints import _run_test_log_trace_stream

        providers = ["aws"]
        if twin.optimizer_config:
            oc = twin.optimizer_config
            unique = {p.lower() for p in filter(None, [oc.cheapest_l1, oc.cheapest_l2, oc.cheapest_l3_hot])}
            if unique:
                providers = list(unique)

        trace_id = f"TRACE-{uuid.uuid4().hex[:8].upper()}"
        session_id = str(uuid.uuid4())
        await create_session(twin_id, session_id, operation_type="log_trace")
        asyncio.create_task(
            _run_test_log_trace_stream(
                session_id=session_id,
                twin_id=twin_id,
                trace_id=trace_id,
                providers=providers,
                duration=30,
                should_fail=False,
            )
        )
        return {
            "trace_id": trace_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "l1_provider": providers[0],
            "providers": providers,
            "message": f"Test message sent to {providers[0]} IoT endpoint",
            "session_id": session_id,
            "sse_url": f"/sse/deploy/{session_id}",
        }

    from src.services.deployment_service import prepare_project_for_deployment

    try:
        resource_name = await prepare_project_for_deployment(twin, current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to prepare project for log trace: {str(exc)}") from exc

    try:
        return await DeployerClient().start_log_trace(resource_name)
    except ExternalServiceError as exc:
        detail = redact_secret_like_text(exc.public_detail)
        if exc.upstream_status_code == 429:
            try:
                parsed = json.loads(detail)
                detail = parsed.get("detail", "Rate limited") if isinstance(parsed, dict) else "Rate limited"
            except json.JSONDecodeError:
                detail = "Rate limited"
        raise HTTPException(
            status_code=exc.upstream_status_code or 502,
            detail=detail if exc.upstream_status_code == 429 else f"Deployer API error: {detail}",
        ) from exc
    except ExternalServiceUnavailable as exc:
        raise HTTPException(status_code=503, detail="Deployer API unavailable") from exc


@router.get(
    "/{twin_id}/log-trace/stream/{trace_id}",
    operation_id="streamLogTrace",
    summary="Stream deployment log trace events",
    description="Streams Deployer log trace SSE events for a trace id while preserving the Deployer event format.",
    responses={401: ERROR_RESPONSES[401], 404: ERROR_RESPONSES[404], 503: {"description": "Deployer API unavailable"}},
)
async def stream_log_trace(
    twin_id: str,
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    twin = TwinRepository(db).get_with_configs_for_user(twin_id, current_user.id)
    if not twin:
        raise HTTPException(status_code=404, detail="Twin not found")

    resource_name = twin.name.lower().replace(" ", "-")
    if twin.deployer_config and twin.deployer_config.deployer_digital_twin_name:
        resource_name = twin.deployer_config.deployer_digital_twin_name

    async def event_generator():
        try:
            async for line in DeployerClient().stream_log_trace(resource_name, trace_id):
                yield line if line.endswith("\n") else f"{line}\n"
        except (ExternalServiceError, ExternalServiceUnavailable) as exc:
            safe_error = redact_secret_like_text(str(exc))
            logger.error("Log trace stream error: %s", safe_error)
            yield "event: error\ndata: {\"message\": \"Deployer log trace stream failed\"}\n\n"
        except Exception as exc:
            safe_error = redact_secret_like_text(str(exc))
            logger.error("Log trace stream error: %s", safe_error)
            yield "event: error\ndata: {\"message\": \"Deployer log trace stream failed\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post(
    "/{twin_id}/verify/infrastructure",
    operation_id="verifyInfrastructure",
    summary="Verify deployed infrastructure",
    description="Runs structured infrastructure verification for a deployed twin through the Deployer boundary.",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        503: {"description": "Deployer API unavailable"},
    },
)
async def verify_infrastructure(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await _deployment_orchestrator(db).verify_infrastructure(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=TEST_MODE,
        )
    except (DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@router.post(
    "/{twin_id}/verify/dataflow",
    operation_id="verifyDataFlow",
    summary="Verify deployed data flow",
    description="Starts end-to-end dataflow verification for a deployed twin and returns the SSE session contract.",
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        503: {"description": "Deployer API unavailable"},
    },
)
async def verify_dataflow(
    twin_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return await _deployment_orchestrator(db).start_dataflow_verification(
            twin_id=twin_id,
            user_id=current_user.id,
            body=body,
            test_mode=TEST_MODE,
        )
    except (DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)


@router.get(
    "/{twin_id}/simulator/download",
    operation_id="downloadIoTSimulator",
    summary="Download IoT simulator package",
    description="Downloads a ready-to-run simulator archive for the optimized L1 provider of a deployed twin.",
    tags=["twins"],
    responses={
        400: ERROR_RESPONSES[400],
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
        502: {"description": "Failed to connect to Deployer"},
    },
)
async def download_simulator(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        archive = await _deployment_orchestrator(db).download_simulator(
            twin_id=twin_id,
            user_id=current_user.id,
            test_mode=TEST_MODE,
        )
    except (DownstreamServiceError, EntityNotFoundError, ValidationError) as exc:
        _raise_service_http_error(exc)

    return StreamingResponse(
        archive.content,
        media_type=archive.media_type,
        headers={"Content-Disposition": f"attachment; filename={archive.filename}"},
    )


@router.get(
    "/{twin_id}/export",
    operation_id="exportTwinConfiguration",
    summary="Export redacted twin configuration",
    description="Downloads a ZIP archive containing the twin configuration and generated deployer inputs with credentials redacted.",
    responses={
        200: {"description": "ZIP file", "content": {"application/zip": {}}},
        401: ERROR_RESPONSES[401],
        404: ERROR_RESPONSES[404],
    },
)
async def export_twin_configuration(
    twin_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        archive = _twin_export_service(db).export_twin(twin_id=twin_id, user_id=current_user.id)
    except EntityNotFoundError as exc:
        _raise_service_http_error(exc)

    return StreamingResponse(
        archive.content,
        media_type=archive.media_type,
        headers={"Content-Disposition": f'attachment; filename="{archive.filename}"'},
    )
