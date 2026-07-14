"""
Simulator API - IoT device simulation endpoints.

Provides download endpoint for standalone simulator packages and WebSocket
endpoint for real-time simulator interaction.

**Key endpoints:**
- GET /projects/{name}/simulator/{provider}/download: Download standalone package
- WS /projects/{name}/simulator/{provider}/stream: Real-time WebSocket simulation

**Use case:** Testing IoT data ingestion without physical devices.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
import subprocess
import sys
import asyncio
import os
import json
from pathlib import Path
from logger import logger
import src.core.state as state
from api.error_models import ERROR_RESPONSES
from src.core.paths import resolve_project_context_path
from src.core.simulator_package import (
    SimulatorPackageInvalid,
    SimulatorPackageNotFound,
    SimulatorPackageService,
    normalize_simulator_provider,
)


router = APIRouter()

def _normalize_simulator_provider(provider: str) -> str:
    """Return the internal simulator provider directory name."""
    try:
        return normalize_simulator_provider(provider)
    except SimulatorPackageInvalid as exc:
        raise ValueError(str(exc)) from exc


def _resolve_payload_path(project_path: str, internal_provider: str) -> str | None:
    """Resolve simulator payloads with shared path first, legacy path second."""
    candidates = [
        os.path.join(project_path, "iot_device_simulator", "payloads.json"),
        os.path.join(project_path, "iot_device_simulator", internal_provider, "payloads.json"),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None

# ==========================================
# 1. WebSocket Stream
# ==========================================
@router.websocket("/projects/{project_name}/simulator/{provider}/stream")
async def simulator_stream(websocket: WebSocket, project_name: str, provider: str):
    """
    WebSocket endpoint for real-time IoT device simulation.
    
    Connect to stream simulation logs and send commands to the simulator.
    """
    await websocket.accept()
    
    # 1. Validation
    try:
        internal_provider = _normalize_simulator_provider(provider)
    except ValueError as e:
        await websocket.send_json({"type": "error", "data": str(e)})
        await websocket.close()
        return

    # Check Project Existence
    project_path = resolve_project_context_path(project_name)
    if not project_path.exists():
        await websocket.send_json({"type": "error", "data": f"Project '{project_name}' not found."})
        await websocket.close()
        return

    # Check Config - look for device subdirectories
    provider_dir = project_path / "iot_device_simulator" / internal_provider
    if not provider_dir.exists():
        await websocket.send_json({"type": "error", "data": "Simulator config not found. Please deploy L1 first."})
        await websocket.close()
        return
    
    device_dirs = [d.name for d in provider_dir.iterdir() if d.is_dir()]
    if not device_dirs:
        await websocket.send_json({"type": "error", "data": "No device configs found. Please deploy L1 first."})
        await websocket.close()
        return
    
    config_path = provider_dir / device_dirs[0] / "config_generated.json"
    if not config_path.exists():
        await websocket.send_json({"type": "error", "data": "Simulator config not found. Please deploy L1 first."})
        await websocket.close()
        return

    # Check Payloads
    payload_path = _resolve_payload_path(project_path, internal_provider)
    if not payload_path:
        await websocket.send_json({"type": "error", "data": "Payloads file not found. Please upload payloads.json."})
        await websocket.close()
        return

    # 2. Start Subprocess
    script_path = os.path.join(state.get_project_base_path(), "src", "iot_device_simulator", internal_provider, "main.py")
    process = subprocess.Popen(
        [sys.executable, script_path, "--project", project_name],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=0 # Unbuffered
    )

    logger.info(f"Started simulator subprocess for {project_name}/{internal_provider}")

    async def read_stdout():
        try:
            while True:
                # Non-blocking read line?? 
                # Popen.stdout is a synchronous file object. 
                # We need to run it in an executor or use asyncio.create_subprocess_exec (better).
                # But refactoring to asyncio subprocess might be cleaner.
                # Let's try asyncio.to_thread for blocking reads.
                line = await asyncio.to_thread(process.stdout.readline)
                if not line:
                    break
                await websocket.send_json({"type": "log", "data": line.strip()})
        except Exception as e:
            logger.error(f"Error reading simulator stdout: {e}")

    stdout_task = asyncio.create_task(read_stdout())

    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command")
            
            if command:
                if command == "exit":
                    process.stdin.write("exit\n")
                    process.stdin.flush()
                    break
                else:
                    process.stdin.write(f"{command}\n")
                    process.stdin.flush()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        
        stdout_task.cancel()
        logger.info("Simulator subprocess terminated.")


# ==========================================
# 2. Template Utilities
# ==========================================
def _get_template_dir(provider: str) -> str:
    """Returns the path to the templates directory for the given provider."""
    return os.path.join(state.get_project_base_path(), "src", "iot_device_simulator", provider, "templates")


def _load_template(provider: str, template_name: str, variables: dict = None) -> str:
    """
    Loads a template file and substitutes variables.
    
    Args:
        provider: Cloud provider (aws, azure, google).
        template_name: Name of the template file (e.g., 'README.md.template').
        variables: Dictionary of variables to substitute (uses {{key}} syntax).
    
    Returns:
        Template content with variables substituted.
    """
    template_path = os.path.join(_get_template_dir(provider), template_name)
    
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if variables:
        for key, value in variables.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
    
    return content


# ==========================================
# 3. Download Package
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
    }
)
async def download_simulator_package(project_name: str, provider: str):
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
    service = SimulatorPackageService(
        project_path=resolve_project_context_path(project_name),
        source_root=Path(state.get_project_base_path()) / "src" / "iot_device_simulator",
    )
    try:
        package = service.build(project_name=project_name, provider=provider)
    except SimulatorPackageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SimulatorPackageInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        package.content,
        media_type=package.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{package.filename}"',
            "X-Twin2MultiCloud-Utility": "simulator",
            "X-Twin2MultiCloud-Provider": package.provider,
            "X-Twin2MultiCloud-Credential-Class": package.credential_class,
            "Cache-Control": "no-store",
        }
    )
