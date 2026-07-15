"""Request validation and SSE transport for data-flow verification."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
import time
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from logger import logger
from src.core.config_loader import ProjectConfigLoader
from src.core.exceptions import DeploymentError
from src.core.observability import redact_sensitive
from src.core.paths import resolve_project_context_path
from src.iot_device_simulator.sender import send_test_message
from src.runtime_outputs import load_terraform_outputs
from src.verification.contracts import VerificationContext
from src.verification.events import display_timestamp, sse_event
from src.verification.orchestrator import DataFlowVerificationOrchestrator
from src.api.operation_context import operation_project_path

router = APIRouter(tags=["Verification"])

MAX_VERIFICATION_PAYLOAD_BYTES = 128 * 1024
MAX_DEVICE_ID_LENGTH = 128


class _StreamProgress:
    """Retain terminal phase states for an honest emergency summary."""

    def __init__(self) -> None:
        self.phases: dict[int, tuple[str, str]] = {}

    def observe(self, event: str) -> None:
        lines = event.splitlines()
        if not lines or lines[0] != "event: phase":
            return
        data_line = next(
            (line for line in lines if line.startswith("data: ")),
            None,
        )
        if data_line is None:
            return
        data = json.loads(data_line.removeprefix("data: "))
        self.phases[data["phase"]] = (data["name"], data["status"])

    def failure_summary(self) -> dict:
        running = next(
            (
                (phase, name)
                for phase, (name, status) in sorted(self.phases.items())
                if status == "running"
            ),
            None,
        )
        failed = next(
            (
                (phase, name)
                for phase, (name, status) in sorted(self.phases.items())
                if status == "fail"
            ),
            None,
        )
        statuses = [status for _, status in self.phases.values()]
        failed_phase = (
            f"Phase {running[0]} - {running[1]}"
            if running
            else (
                f"Phase {failed[0]} - {failed[1]}" if failed else "Verification runtime"
            )
        )
        return {
            "pass_count": statuses.count("pass"),
            "fail_count": statuses.count("fail") + (1 if running else 0),
            "skip_count": statuses.count("skip"),
            "failed_phase": failed_phase,
        }


class DataFlowRequest(BaseModel):
    payload: dict

    @field_validator("payload")
    @classmethod
    def validate_payload(cls, payload: dict) -> dict:
        device_id = payload.get("iotDeviceId")
        if not isinstance(device_id, str) or not device_id.strip():
            raise ValueError("payload.iotDeviceId must be a non-empty string")
        if len(device_id) > MAX_DEVICE_ID_LENGTH:
            raise ValueError(
                f"payload.iotDeviceId must not exceed {MAX_DEVICE_ID_LENGTH} characters"
            )
        try:
            size = len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("payload must be JSON serializable") from exc
        if size > MAX_VERIFICATION_PAYLOAD_BYTES:
            raise ValueError(
                "payload exceeds the portable cloud message limit of 128 KiB"
            )
        return {**payload, "iotDeviceId": device_id.strip()}


def _load_verification_context(
    project_name: str,
    project_path=None,
) -> VerificationContext:
    project_path = project_path or resolve_project_context_path(project_name)
    if not project_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found",
        )

    try:
        bundle = ProjectConfigLoader().load_bundle_from_path(
            project_name,
            project_path,
        )
        terraform_outputs = load_terraform_outputs(project_name, project_path)
    except (DeploymentError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Project configuration is invalid: {redact_sensitive(exc)}",
        ) from exc

    config = bundle.config
    if not config.providers.get("layer_1_provider"):
        raise HTTPException(status_code=400, detail="L1 provider not configured")

    return VerificationContext(
        project_name=project_name,
        project_path=project_path,
        providers=config.providers,
        terraform_outputs=terraform_outputs,
        optimization=config.optimization,
        credentials=bundle.credentials,
        events=config.events,
    )


async def _safe_event_stream(
    orchestrator: DataFlowVerificationOrchestrator,
    payload: dict,
) -> AsyncIterator[str]:
    started = time.monotonic()
    progress = _StreamProgress()
    try:
        async for event in orchestrator.stream(payload):
            progress.observe(event)
            yield event
    except Exception as exc:
        logger.error(
            f"Data-flow verification failed unexpectedly: {redact_sensitive(exc)}"
        )
        yield sse_event(
            "log",
            {
                "timestamp": display_timestamp(),
                "message": "Verification stopped because of an internal error",
                "status": "fail",
            },
        )
        summary = progress.failure_summary()
        if summary["fail_count"] == 0:
            summary["fail_count"] = 1
        yield sse_event(
            "done",
            {
                **summary,
                "total_time": round(time.monotonic() - started, 1),
                "hints": [],
            },
        )


@router.post(
    "/dataflow/verify",
    operation_id="verifyDataFlow",
    summary="Verify deployed data flow with trace-correlated evidence",
    description=(
        "Sends one bounded test message and streams phase results for message "
        "delivery, hot storage, digital-twin readiness, and event flow."
    ),
    responses={
        200: {"description": "SSE stream with verification results"},
        400: {"description": "Invalid or incomplete project configuration"},
        404: {"description": "Project not found"},
        422: {"description": "Invalid verification payload"},
    },
)
async def verify_data_flow(
    body: DataFlowRequest,
    operation_token: Annotated[str, Header(alias="X-Operation-Package", min_length=1)],
    project_name: str = Query(
        ...,
        min_length=1,
        max_length=128,
        description="Digital twin project name",
    ),
) -> StreamingResponse:
    package_scope = operation_project_path(project_name, operation_token)
    package_entered = False
    try:
        project_path = package_scope.__enter__()
        package_entered = True
        context = _load_verification_context(project_name, project_path)
        orchestrator = DataFlowVerificationOrchestrator(
            context,
            send_test_message,
        )
    except Exception as exc:
        if package_entered:
            package_scope.__exit__(type(exc), exc, exc.__traceback__)
        raise

    async def operation_stream():
        try:
            async for event in _safe_event_stream(orchestrator, body.payload):
                yield event
        except BaseException as exc:
            package_scope.__exit__(type(exc), exc, exc.__traceback__)
            raise
        else:
            package_scope.__exit__(None, None, None)

    return StreamingResponse(
        operation_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "X-Accel-Buffering": "no",
        },
    )
