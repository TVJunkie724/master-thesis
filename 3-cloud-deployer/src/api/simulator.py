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
import zipfile
import io
import datetime
from logger import logger
import src.core.state as state
from api.error_models import ERROR_RESPONSES


router = APIRouter()

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
    if provider not in ("aws", "azure"):
        await websocket.send_json({"type": "error", "data": f"Provider '{provider}' not supported. Supported: aws, azure."})
        await websocket.close()
        return

    # Check Project Existence
    project_path = os.path.join(state.get_project_upload_path(), project_name)
    if not os.path.exists(project_path):
        await websocket.send_json({"type": "error", "data": f"Project '{project_name}' not found."})
        await websocket.close()
        return

    # Check Config - look for device subdirectories
    provider_dir = os.path.join(project_path, "iot_device_simulator", provider)
    if not os.path.exists(provider_dir):
        await websocket.send_json({"type": "error", "data": "Simulator config not found. Please deploy L1 first."})
        await websocket.close()
        return
    
    device_dirs = [d for d in os.listdir(provider_dir) if os.path.isdir(os.path.join(provider_dir, d))]
    if not device_dirs:
        await websocket.send_json({"type": "error", "data": "No device configs found. Please deploy L1 first."})
        await websocket.close()
        return
    
    config_path = os.path.join(provider_dir, device_dirs[0], "config_generated.json")
    if not os.path.exists(config_path):
        await websocket.send_json({"type": "error", "data": "Simulator config not found. Please deploy L1 first."})
        await websocket.close()
        return

    # Check Payloads
    payload_path = os.path.join(project_path, "iot_device_simulator", provider, "payloads.json")
    if not os.path.exists(payload_path):
        await websocket.send_json({"type": "error", "data": "Payloads file not found. Please upload payloads.json."})
        await websocket.close()
        return

    # 2. Start Subprocess
    script_path = os.path.join(state.get_project_base_path(), "src", "iot_device_simulator", provider, "main.py")
    process = subprocess.Popen(
        [sys.executable, script_path, "--project", project_name],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=0 # Unbuffered
    )

    logger.info(f"Started simulator subprocess for {project_name}/{provider}")

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
    # Normalize 'gcp' to 'google' internally
    internal_provider = "google" if provider == "gcp" else provider
    
    if internal_provider not in ("aws", "azure", "google"):
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' not supported. Supported: aws, azure, gcp.")

    provider_dir = os.path.join(state.get_project_upload_path(), project_name, "iot_device_simulator", internal_provider)
    src_dir = os.path.join(state.get_project_base_path(), "src", "iot_device_simulator", internal_provider)
    
    # Payloads are stored at iot_device_simulator level (shared across devices)
    payload_path = os.path.join(state.get_project_upload_path(), project_name, "iot_device_simulator", "payloads.json")

    # Find all device subdirectories
    if not os.path.exists(provider_dir):
        raise HTTPException(status_code=404, detail="Simulator config not found. Deploy L1 first.")
    
    device_dirs = [d for d in os.listdir(provider_dir) if os.path.isdir(os.path.join(provider_dir, d))]
    if not device_dirs:
        raise HTTPException(status_code=404, detail="No device configs found. Deploy L1 first.")
    
    # Load all device configs
    device_configs = {}
    for device_id in device_dirs:
        config_path = os.path.join(provider_dir, device_id, "config_generated.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                device_configs[device_id] = json.load(f)
    
    if not device_configs:
        raise HTTPException(status_code=404, detail="No valid device configs found. Deploy L1 first.")
    
    # Use first device as default
    first_device_id = list(device_configs.keys())[0]
    first_config = device_configs[first_device_id]
    
    # AWS-specific: validate certificates exist for all devices
    auth_dir = None
    if internal_provider == "aws":
        auth_dir = os.path.join(state.get_project_upload_path(), project_name, "iot_devices_auth")
        for device_id in device_configs:
            device_cert_dir = os.path.join(auth_dir, device_id)
            if not os.path.exists(device_cert_dir):
                raise HTTPException(status_code=404, detail=f"Certificates for device '{device_id}' not found.")

    # GCP-specific: validate service account key exists
    sa_key_path = None
    if internal_provider == "google":
        sa_key_path = first_config.get("service_account_key_path", "")
        if not (sa_key_path and os.path.exists(sa_key_path)):
            # Check fallback location
            sa_key_path = os.path.join(state.get_project_upload_path(), project_name, "service_account.json")
            if not os.path.exists(sa_key_path):
                raise HTTPException(status_code=404, detail="GCP service account key not found. Configure GCP credentials first.")

    # Create Zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        # 1. Default config.json at root (first device, for backward compatibility)
        default_config = first_config.copy()
        if internal_provider == "aws":
            default_config["cert_path"] = f"configs/{first_device_id}/certificate.pem.crt"
            default_config["key_path"] = f"configs/{first_device_id}/private.pem.key"
            default_config["root_ca_path"] = "AmazonRootCA1.pem"
        elif internal_provider == "google":
            default_config["service_account_key_path"] = "service_account.json"
        default_config["payload_path"] = "payloads.json"
        zip_file.writestr("config.json", json.dumps(default_config, indent=2))
        
        # 2. Per-device configs in configs/{device_id}/ directories
        for device_id, device_config in device_configs.items():
            sim_config = device_config.copy()
            if internal_provider == "aws":
                sim_config["cert_path"] = f"configs/{device_id}/certificate.pem.crt"
                sim_config["key_path"] = f"configs/{device_id}/private.pem.key"
                sim_config["root_ca_path"] = "../AmazonRootCA1.pem"
            elif internal_provider == "google":
                sim_config["service_account_key_path"] = "../service_account.json"
            sim_config["payload_path"] = "../payloads.json"
            zip_file.writestr(f"configs/{device_id}/config.json", json.dumps(sim_config, indent=2))
            
            # AWS: include device certificates
            if internal_provider == "aws" and auth_dir:
                device_cert_dir = os.path.join(auth_dir, device_id)
                for f in ["certificate.pem.crt", "private.pem.key"]:
                    fp = os.path.join(device_cert_dir, f)
                    if os.path.exists(fp):
                        zip_file.write(fp, f"configs/{device_id}/{f}")

        # 3. Payloads
        if os.path.exists(payload_path):
            zip_file.write(payload_path, "payloads.json")
        else:
            zip_file.writestr("payloads.json", "[]")

        # 4. AWS-specific: Root CA (shared)
        if internal_provider == "aws":
            root_ca_path = os.path.join(src_dir, "AmazonRootCA1.pem")
            if os.path.exists(root_ca_path):
                zip_file.write(root_ca_path, "AmazonRootCA1.pem")

        # 4b. GCP-specific: Service Account Key (shared)
        if internal_provider == "google" and sa_key_path:
            if os.path.exists(sa_key_path):
                zip_file.write(sa_key_path, "service_account.json")

        # 5. Source Code
        for f in ["main.py", "transmission.py", "globals.py"]:
            fp = os.path.join(src_dir, f)
            if os.path.exists(fp):
                zip_file.write(fp, f"src/{f}")
        
        # 6. Generated Files from Templates
        device_list = list(device_configs.keys())
        template_vars = {
            "project_name": project_name,
            "provider": provider,
            "device_id": first_device_id,  # Default device
            "device_ids": ", ".join(device_list),
            "device_count": len(device_list),
            "endpoint": first_config.get("endpoint", ""),
            "project_id": first_config.get("project_id", ""),
            "topic_name": first_config.get("topic_name", ""),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # README.md (with variable substitution)
        zip_file.writestr("README.md", _load_template(internal_provider, "README.md.template", template_vars))
        
        # requirements.txt (static)
        zip_file.writestr("requirements.txt", _load_template(internal_provider, "requirements.txt"))
        
        # Dockerfile (static)
        zip_file.writestr("Dockerfile", _load_template(internal_provider, "Dockerfile"))
        
        # docker-compose.yml (with variable substitution)
        zip_file.writestr("docker-compose.yml", _load_template(internal_provider, "docker-compose.yml.template", template_vars))


    zip_buffer.seek(0)
    
    filename = f"simulator_package_{project_name}_{provider}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
