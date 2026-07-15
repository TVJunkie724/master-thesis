"""
Simulator API - IoT device simulation endpoints.

Provides download endpoint for standalone simulator packages and WebSocket
endpoint for real-time simulator interaction.

**Key endpoints:**
- GET /projects/{name}/simulator/{provider}/download: Download standalone package
- WS /projects/{name}/simulator/{provider}/stream: Real-time WebSocket simulation

**Use case:** Testing IoT data ingestion without physical devices.
"""

from fastapi import APIRouter, Header, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import Annotated
from logger import logger
import src.core.state as state
from src.api.error_handling import safe_error_detail
from src.api.error_models import ERROR_RESPONSES
from src.core.simulator_package import (
    SimulatorPackageInvalid,
    SimulatorPackageNotFound,
    SimulatorPackageService,
    normalize_simulator_provider,
)
from src.simulator.session import (
    SimulatorSessionBusy,
    SimulatorSessionError,
    SimulatorSessionInvalid,
    SimulatorSessionNotFound,
    SimulatorSessionRunner,
    resolve_simulator_session,
    session_registry,
)
from src.core.observability import redact_sensitive
from src.api.operation_context import operation_project_path


router = APIRouter()


async def _send_websocket_error(websocket: WebSocket, message: str) -> None:
    """Send a stable error event when the peer is still connected."""
    try:
        await websocket.send_json({"type": "error", "data": message})
    except (RuntimeError, WebSocketDisconnect):
        pass


def _normalize_simulator_provider(provider: str) -> str:
    """Return the internal simulator provider directory name."""
    try:
        return normalize_simulator_provider(provider)
    except SimulatorPackageInvalid as exc:
        raise ValueError(str(exc)) from exc


# ==========================================
# 1. WebSocket Stream
# ==========================================
@router.websocket("/projects/{project_name}/simulator/{provider}/stream")
async def simulator_stream(
    websocket: WebSocket,
    project_name: str,
    provider: str,
    device_id: str | None = None,
):
    """
    WebSocket endpoint for real-time IoT device simulation.

    Connect to stream simulation logs and send commands to the simulator.
    """
    await websocket.accept()

    try:
        spec = resolve_simulator_session(
            project_name=project_name,
            provider=provider,
            device_id=device_id,
            repository_root=Path(state.get_project_base_path()),
        )
        async with session_registry.claim(spec.key):
            logger.info(
                "Started simulator session for %s/%s/%s",
                project_name,
                spec.public_provider,
                spec.device_id,
            )
            await SimulatorSessionRunner(spec).run(websocket)
    except WebSocketDisconnect:
        logger.info("Simulator WebSocket disconnected")
    except (
        SimulatorSessionNotFound,
        SimulatorSessionInvalid,
        SimulatorSessionBusy,
    ) as exc:
        await _send_websocket_error(websocket, str(exc))
    except TimeoutError:
        await _send_websocket_error(websocket, "Simulator session timed out.")
    except SimulatorSessionError as exc:
        logger.error("Simulator session failed: %s", exc)
        await _send_websocket_error(websocket, "Simulator session failed.")
    except Exception as exc:
        logger.error(
            "Unexpected simulator session failure (%s): %s",
            type(exc).__name__,
            redact_sensitive(exc),
        )
        await _send_websocket_error(websocket, "Simulator session failed.")
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass


# ==========================================
# 2. Download Package
# ==========================================
@router.get(
    "/projects/{project_name}/simulator/{provider}/download",
    operation_id="downloadSimulatorPackage",
    tags=["Projects"],
    summary="Download standalone IoT simulator package as ZIP",
    description=(
        "**Purpose:** Download a self-contained IoT device simulator for local/Docker use.\n\n"
        "**Package contents:**\n"
        "- config.json, payloads.json\n"
        "- src/: Simulator Python code\n"
        "- certificates/ or service_account.json (provider-specific)\n"
        "- Dockerfile & docker-compose.yml\n"
        "- README.md with setup instructions"
    ),
    responses={
        200: {"description": "Simulator zip package"},
        400: ERROR_RESPONSES[400],
        404: ERROR_RESPONSES[404],
    },
)
async def download_simulator_package(
    project_name: str,
    provider: str,
    operation_token: Annotated[str, Header(alias="X-Operation-Package", min_length=1)],
):
    """
    Download a standalone IoT device simulator package as a ZIP file.

    **Package contents:**
    - config.json: Simulator configuration
    - payloads.json: IoT device payloads
    - src/: Simulator source code
    - certificates/: Device certificates (AWS only)
    - service_account.json: Service account key (GCP only)
    - Dockerfile & docker-compose.yml: Container setup
    - README.md: Usage instructions
    """
    try:
        with operation_project_path(project_name, operation_token) as project_path:
            service = SimulatorPackageService(
                project_path=project_path,
                source_root=Path(state.get_project_base_path())
                / "src"
                / "iot_device_simulator",
            )
            package = service.build(project_name=project_name, provider=provider)
    except SimulatorPackageNotFound as exc:
        raise HTTPException(status_code=404, detail=safe_error_detail(exc)) from exc
    except SimulatorPackageInvalid as exc:
        raise HTTPException(status_code=400, detail=safe_error_detail(exc)) from exc

    return StreamingResponse(
        package.content,
        media_type=package.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{package.filename}"',
            "X-Twin2MultiCloud-Utility": "simulator",
            "X-Twin2MultiCloud-Provider": package.provider,
            "X-Twin2MultiCloud-Credential-Class": package.credential_class,
            "Cache-Control": "no-store",
        },
    )
