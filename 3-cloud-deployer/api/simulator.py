from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
import subprocess
import sys
import asyncio
import globals
import os
import json
import zipfile
import io
import datetime
from logger import logger

router = APIRouter()

# ==========================================
# 1. WebSocket Stream
# ==========================================
@router.websocket("/projects/{project_name}/simulator/{provider}/stream")
async def simulator_stream(websocket: WebSocket, project_name: str, provider: str):
    await websocket.accept()
    
    # 1. Validation
    if provider != "aws":
        await websocket.send_json({"type": "error", "data": f"Provider '{provider}' not supported."})
        await websocket.close()
        return

    # Check Project Existence
    project_path = os.path.join(globals.project_path(), "upload", project_name)
    if not os.path.exists(project_path):
        await websocket.send_json({"type": "error", "data": f"Project '{project_name}' not found."})
        await websocket.close()
        return

    # Check Config
    config_path = os.path.join(project_path, "iot_device_simulator", provider, "config_generated.json")
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
    script_path = os.path.join(globals.project_path(), "src", "iot_device_simulator", provider, "main.py")
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
# 2. Download Package
# ==========================================
@router.get("/projects/{project_name}/simulator/{provider}/download")
async def download_simulator_package(project_name: str, provider: str):
    if provider != "aws":
        raise HTTPException(status_code=400, detail=f"Provider '{provider}' not supported.")

    base_dir = os.path.join(globals.project_path(), "upload", project_name, "iot_device_simulator", provider)
    auth_dir = os.path.join(globals.project_path(), "upload", project_name, "iot_devices_auth")
    src_dir = os.path.join(globals.project_path(), "src", "iot_device_simulator", provider)
    root_ca_path = os.path.join(src_dir, "AmazonRootCA1.pem")
    config_path = os.path.join(base_dir, "config_generated.json")
    payload_path = os.path.join(base_dir, "payloads.json")

    # Validation
    if not os.path.exists(config_path):
        raise HTTPException(status_code=404, detail="Simulator config not found. Deploy L1 first.")
    
    # Load config to get device ID
    with open(config_path, 'r') as f:
        config_data = json.load(f)
    device_id = config_data.get("device_id")
    endpoint = config_data.get("endpoint")

    device_cert_dir = os.path.join(auth_dir, device_id)
    if not os.path.exists(device_cert_dir):
        raise HTTPException(status_code=404, detail=f"Certificates for device '{device_id}' not found.")

    # Create Zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        
        # 1. Config (Transformed)
        sim_config = config_data.copy()
        sim_config["cert_path"] = f"certificates/{device_id}/certificate.pem.crt"
        sim_config["key_path"] = f"certificates/{device_id}/private.pem.key"
        sim_config["root_ca_path"] = "AmazonRootCA1.pem"
        sim_config["payload_path"] = "payloads.json"
        zip_file.writestr("config.json", json.dumps(sim_config, indent=2))

        # 2. Payloads
        if os.path.exists(payload_path):
            zip_file.write(payload_path, "payloads.json")
        else:
            zip_file.writestr("payloads.json", "[]") # Empty array if missing (?) Plan said invalid if missing.

        # 3. Root CA
        if os.path.exists(root_ca_path):
            zip_file.write(root_ca_path, "AmazonRootCA1.pem")

        # 4. Certificates
        for f in ["certificate.pem.crt", "private.pem.key"]:
             fp = os.path.join(device_cert_dir, f)
             if os.path.exists(fp):
                 zip_file.write(fp, f"certificates/{device_id}/{f}")

        # 5. Source Code
        for f in ["main.py", "transmission.py", "globals.py"]:
            fp = os.path.join(src_dir, f)
            if os.path.exists(fp):
                zip_file.write(fp, f"src/{f}")
        
        # 6. README.md
        readme_content = f"""# IoT Device Simulator Package

**Project**: {project_name}
**Provider**: {provider}
**Device ID**: {device_id}
**Endpoint**: {endpoint}
**Generated**: {datetime.datetime.now().isoformat()}

## Prerequisites
- Python 3.9+
- pip
- Docker (optional)

## Setup
1. Extract this zip file.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Option 1: Python
Run the simulator:
```bash
python src/main.py
```

### Option 2: Docker
Build and run:
```bash
docker-compose up --build
```
Or manually:
```bash
docker build -t iot-simulator .
docker run -it iot-simulator
```

### Available Commands
- `send` - Send the next payload from payloads.json to AWS IoT Core.
- `help` - Show available commands.
- `exit` - Exit the simulator.

## File Structure
- `config.json` - Simulator configuration.
- `payloads.json` - Payload data.
- `AmazonRootCA1.pem` - AWS Root CA.
- `certificates/` - Device certificates.
- `src/` - Simulator Python code.
"""
        zip_file.writestr("README.md", readme_content)

        # 7. requirements.txt
        zip_file.writestr("requirements.txt", "AWSIoTPythonSDK>=1.4.9\n")

        # 8. Dockerfile
        dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run main.py
CMD ["python", "src/main.py"]
"""
        zip_file.writestr("Dockerfile", dockerfile_content)

        # 9. docker-compose.yml
        compose_content = f"""version: '3.8'

services:
  simulator:
    build: .
    container_name: iot_simulator_{device_id}
    stdin_open: true   # Keep stdin open for interactive commands
    tty: true          # Allocate a pseudo-TTY
    restart: unless-stopped
"""
        zip_file.writestr("docker-compose.yml", compose_content)

    zip_buffer.seek(0)
    
    filename = f"simulator_package_{project_name}_{provider}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
