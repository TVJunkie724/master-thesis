"""HTTP transport for bounded, secret-safe cloud log tracing."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from src.api.error_models import ERROR_RESPONSES
from logger import logger
from src.core.observability import redact_sensitive
from src.core.exceptions import DeploymentError
from src.core.paths import resolve_project_context_path
from src.log_tracing.registry import (
    TraceExpired,
    TraceNotFound,
    TraceOwnershipError,
    TraceRateLimited,
    TraceRegistry,
)
from src.log_tracing.service import (
    LogTraceService,
    generate_trace_id as generate_trace_id,
    providers_to_query,
)

RATE_LIMIT_SECONDS = 30
TRACE_TIMEOUT_SECONDS = 90
TRACE_LIFETIME_SECONDS = 120
POLL_INTERVAL_SECONDS = 2

trace_registry = TraceRegistry(
    cooldown=timedelta(seconds=RATE_LIMIT_SECONDS),
    lifetime=timedelta(seconds=TRACE_LIFETIME_SECONDS),
)
trace_service = LogTraceService(
    trace_registry,
    timeout_seconds=TRACE_TIMEOUT_SECONDS,
    poll_interval_seconds=POLL_INTERVAL_SECONDS,
)

router = APIRouter(prefix="/logs", tags=["Logs"])


def get_providers_to_query(project_name: str) -> set[str]:
    from src.core.config_loader import ProjectConfigLoader

    bundle = ProjectConfigLoader().load_bundle(project_name)
    return providers_to_query(bundle.config.providers)


def _require_project(project_name: str) -> None:
    if not resolve_project_context_path(project_name).is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found",
        )


@router.post(
    "/trace/start",
    operation_id="startLogTrace",
    summary="Send one traceable IoT test message",
    responses={
        200: {"description": "Trace started"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
        429: {"description": "Trace cooldown active"},
        500: ERROR_RESPONSES[500],
    },
)
async def start_log_trace(
    project_name: str = Query(..., min_length=1, max_length=128),
):
    _require_project(project_name)
    try:
        return await asyncio.to_thread(trace_service.start, project_name)
    except TraceRateLimited as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited. Wait {exc.retry_after} seconds.",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except (DeploymentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=redact_sensitive(exc)) from exc
    except Exception as exc:
        logger.error("Failed to start log trace: %s", redact_sensitive(exc))
        raise HTTPException(
            status_code=500,
            detail="Failed to send test message. Check simulator configuration.",
        ) from exc


@router.get(
    "/trace/stream/{trace_id}",
    operation_id="streamLogTrace",
    summary="Stream trace-correlated logs from configured providers",
    responses={
        200: {"description": "SSE stream with log, error, heartbeat, and done events"},
        403: {"description": "Trace belongs to another project"},
        404: ERROR_RESPONSES[404],
        410: {"description": "Trace expired"},
    },
)
async def stream_log_trace(
    trace_id: str,
    project_name: str = Query(..., min_length=1, max_length=128),
):
    _require_project(project_name)
    try:
        trace_service.validate(trace_id, project_name)
    except TraceOwnershipError as exc:
        raise HTTPException(
            status_code=403,
            detail="Trace ID does not belong to this project",
        ) from exc
    except TraceExpired as exc:
        raise HTTPException(status_code=410, detail="Trace has expired") from exc
    except TraceNotFound as exc:
        raise HTTPException(status_code=404, detail="Unknown trace ID") from exc
    return EventSourceResponse(trace_service.stream(trace_id, project_name))
