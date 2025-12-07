# Refactor & Integrate IoT Device Simulator

## Goal Description
Refactor the `iot_device_simulator` to be **project-adaptable**, **multi-cloud ready**, and **integrated** with both the CLI and REST API (WebSockets) for the Flutter frontend.

This plan addresses the following key requirements:
1.  **Decouple User-Adaptable Data from System Logic**: The user only needs to provide payloads (`payloads.json`). All other configuration (endpoint, certificates) is generated automatically during deployment.
2.  **Multi-Cloud Readiness**: Structure the source code and upload assets with provider-specific subdirectories (`/aws/`, `/azure/`).
3.  **API Integration**: Expose simulator control via WebSockets for real-time log streaming and command execution.
4.  **CLI Integration**: Allow running the simulator interactively from the main CLI.

---

## Technical Background & Reasoning

### Certificate Types Explained (AWS IoT Core)
When connecting a device to AWS IoT Core using MQTT over TLS, **two types of certificates** are involved:

| Certificate Type | Purpose | Unique Per... | How Obtained | Our Strategy |
|---|---|---|---|---|
| **Root CA (Server Auth)** | The device uses this to verify it's talking to the *real* AWS IoT endpoint. | **Globally Static**. Amazon provides a single set of Root CAs for all accounts/regions. | Downloaded from [Amazon Trust Services](https://www.amazontrust.com/repository/AmazonRootCA1.pem). | **Bundle in `src/`**. No user action needed. |
| **Device Certificate (Client Auth)** | AWS IoT uses this to verify the *device* is authorized. | **Unique per device/thing**. Each registered "Thing" gets its own certificate and private key. | Generated via `aws iot create-keys-and-certificate` (Boto3 or CLI). | **Generated during `deploy_l1`**. Already implemented. |

**Source**: [AWS Docs - Server Authentication](https://docs.aws.amazon.com/iot/latest/developerguide/server-authentication.html), [AWS Docs - Create Client Certificates](https://docs.aws.amazon.com/iot/latest/developerguide/device-certs-create.html)

### Current Deployer Behavior (Already Implemented)
Looking at `src/aws/iot_deployer_aws.py::create_iot_thing()`:
*   It calls `aws_iot_client.create_keys_and_certificate(setAsActive=True)`.
*   It saves the generated `certificate.pem.crt`, `private.pem.key`, and `public.pem.key` to `upload/{project}/iot_devices_auth/{iot_device_id}/`.
*   It creates and attaches an IoT Policy.

**Conclusion**: Device certificates are already handled. No changes needed for cert generation.

### Why `iot_devices_auth` is in `upload/` (Current State) - Discussion
The current implementation saves certificates to `upload/{project}/iot_devices_auth/`. The user asks:
> *"Why would the iot_devices_auth directory be in the upload folder (logically user accessible)? The user does not need to see the certificates does he? Why not have the iot_devices_auth in /src?"*

**Analysis**:
*   **`/src`**: Contains **system code**, not runtime data. Certificates are **project-specific runtime artifacts**.
*   **`upload/{project}/`**: Contains **project-specific data**. Certificates belong here logically because they are generated *per project* and *per device*.
*   **User Access**: While users don't *need* to edit certs, they may need to:
    1.  **Back them up**: If re-deploying elsewhere.
    2.  **Distribute to real devices**: In a real scenario, the generated certs would be installed on physical devices.
    3.  **Inspect for debugging**: If connection fails, users may need to verify cert paths.
*   **Proposed Change (Optional)**: If strict isolation is desired, certs could be saved to a dedicated directory like `runtime/{project}/secrets/`. However, this adds complexity. For now, keeping them in `upload/{project}/iot_devices_auth/` is acceptable as it's already implemented and logically grouped with project data.

> [!NOTE]
> **Decision**: Keep `iot_devices_auth` in `upload/{project}/` (current behavior). This is a generated-at-runtime directory, not user-uploaded, but it's project-specific and the user *may* need access for debugging or real device provisioning. The simulator will read from this location.

### Topic Name Derivation
The MQTT topic is **NOT hardcoded** in the template project. It is **derived** from the `digital_twin_name` in `config.json`:
```
Topic = {digital_twin_name}/iot-data
Example: "digital-twin/iot-data"
```
**Source**: `src/aws/init_values_deployer_aws.py` (line 16):
```python
topic = globals.config["digital_twin_name"] + "/iot-data"
```
*   The IoT Rule (`layer_1_iot.py`) subscribes to this topic.
*   The simulator must publish to this topic.

**Conclusion**: The generated `config_generated.json` will derive the topic from `config.json` at deployment time. There is no hardcoding.

### Payload Structure Requirements
Based on code analysis (`dispatcher/lambda_function.py`, `transmission.py`), payloads **MUST** contain:
*   `iotDeviceId` (string, **required**): Identifies which device sent the data. Must match an `id` in `config_iot_devices.json`.
*   `time` (string, optional): ISO8601 timestamp. If empty, the simulator fills it automatically.
*   Additional properties (e.g., `temperature`, `pressure`): User-defined, matching properties in `config_iot_devices.json`.

**Validation Requirements for `payloads.json`**:
1.  Must be a valid JSON array.
2.  Each object in the array must have an `iotDeviceId` key.
3.  Each `iotDeviceId` value should ideally exist in `config_iot_devices.json` (warning if not).

---

## User Review Required

> [!IMPORTANT]
> **Payloads Only**: The `payloads.json` file is the **only** user-editable file related to the simulator. It defines the data the simulated device will send.
> **Location**: `upload/{project}/iot_device_simulator/aws/payloads.json` (previously in `src/`).

> [!NOTE]
> **Root CA (`AmazonRootCA1.pem`)**: This is a **global, static, public** file from Amazon Trust Services. It is the **same for all AWS accounts, all regions, and all projects**. It will be **bundled within the source code** (`src/iot_device_simulator/aws/AmazonRootCA1.pem`) and is **not** something the user needs to interact with. No API endpoint for upload is needed, and it does not belong in `upload/`.

> [!NOTE]
> **Device Certificates**: These are **unique per IoT device** (per "Thing" in AWS). They are **already generated and saved** by `create_iot_thing()` during `deploy_l1` to `upload/{project}/iot_devices_auth/{device_id}/`. The simulator will read them from there. **No new generation or upload endpoint is needed**. The location in `upload/` is intentional for project isolation and potential user access for debugging/distribution.

> [!IMPORTANT]
> **Config Clarification**:
> *   `upload/template/config.json` (Main Digital Twin config - name, storage days, etc.) is **unchanged**.
> *   `src/iot_device_simulator/config.json` (Simulator config) will be **renamed to `config.json.example`** and kept for reference. It will not be used at runtime.
> *   `upload/{project}/iot_device_simulator/aws/config_generated.json` is a **new** file, **generated at deployment time**. The user does not need to edit or upload this. Correct: there will no longer be a `config.json` file read at runtime, only `config_generated.json`.

---

## Proposed Changes

### 1. Directory Structure

#### Source Code (`src/`)
```text
src/iot_device_simulator/
├── __init__.py              # [NEW] Python package marker (empty file)
├── aws/
│   ├── __init__.py          # [NEW] Python package marker (empty file)
│   ├── main.py              # Entry point (moved from src/src/)
│   ├── transmission.py      # MQTT logic (moved from src/src/)
│   ├── globals.py           # Config loading (moved from src/src/)
│   └── AmazonRootCA1.pem    # Static Root CA (moved from parent)
├── azure/ (Future - Placeholder structure)
│   ├── __init__.py          # [NEW] Python package marker (empty file)
│   └── .gitkeep
├── google/ (Future - Placeholder structure)
│   ├── __init__.py          # [NEW] Python package marker (empty file)
│   └── .gitkeep
└── config.json.example      # Renamed from config.json, kept for reference
```
**Reasoning**: Provider-specific code is isolated. The Root CA is bundled with the AWS-specific code where it logically belongs. `__init__.py` files are required for Python to recognize these directories as importable packages.

#### Upload Template (`upload/template/`)
```text
upload/template/iot_device_simulator/
└── aws/
    └── payloads.json        # User-defined payload data (moved from src/)
```
**Reasoning**: Only the user-adaptable data lives in `upload/`. The auto-generated config will also be written here after deployment.

---

### 2. Deployer Changes

#### [MODIFY] `src/aws/iot_deployer_aws.py`
**Task**: Generate Simulator Runtime Configuration after device creation.
*   **Location**: At the end of `create_iot_thing()`.
*   **Action**: Call a new helper function `_generate_simulator_config(iot_device)`.
*   **New Function `_generate_simulator_config(iot_device)`**:
    ```python
    def _generate_simulator_config(iot_device):
        """
        Generates config_generated.json for the IoT device simulator.
        Called after device certificate creation.
        
        This file contains all runtime information the simulator needs:
        - AWS IoT endpoint (fetched dynamically)
        - MQTT topic (derived from digital_twin_name)
        - Paths to device certificates (relative to config file location)
        - Path to Root CA (bundled in src/)
        - Path to payloads.json (same directory as config)
        """
        import globals
        import os
        import json
        import util
        
        # 1. Fetch IoT Endpoint (dynamically via Boto3)
        endpoint_response = globals_aws.aws_iot_client.describe_endpoint(endpointType='iot:Data-ATS')
        endpoint = endpoint_response['endpointAddress']
        
        # 2. Derive topic from digital_twin_name
        topic = globals.config["digital_twin_name"] + "/iot-data"
        
        # 3. Paths
        device_id = iot_device['id']
        
        # Resolve Root CA path (bundled in src)
        # This is an absolute path since it's in the system code, not project data
        root_ca_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "iot_device_simulator", "aws", "AmazonRootCA1.pem"
        ))
        
        config_data = {
            "endpoint": endpoint,
            "topic": topic,
            "device_id": device_id,
            # Relative paths from config file location (upload/{project}/iot_device_simulator/aws/)
            "cert_path": f"../../iot_devices_auth/{device_id}/certificate.pem.crt",
            "key_path": f"../../iot_devices_auth/{device_id}/private.pem.key",
            "root_ca_path": root_ca_path,  # Absolute path to bundled Root CA
            "payload_path": "payloads.json"  # Same directory as config_generated.json
        }
        
        # 4. Write to upload/{project}/iot_device_simulator/aws/
        sim_dir = os.path.join(util.get_path_in_project(), "iot_device_simulator", "aws")
        os.makedirs(sim_dir, exist_ok=True)
        config_path = os.path.join(sim_dir, "config_generated.json")
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2)
        logger.info(f"Generated simulator config: {config_path}")
    ```

**Note on `payload_path`**: This is a **relative path**. When the simulator loads the config, it will resolve `payload_path` relative to the directory containing `config_generated.json`. So if the config is at `upload/template/iot_device_simulator/aws/config_generated.json`, then `payload_path = "payloads.json"` resolves to `upload/template/iot_device_simulator/aws/payloads.json`. This is correct.

---

### 3. Simulator Script Changes

#### [MODIFY] `src/iot_device_simulator/aws/main.py`
*   Accept CLI argument `--project <name>`.
*   Load `upload/{project}/iot_device_simulator/aws/config_generated.json`.
*   Resolve paths for certs and payloads relative to the config file.
*   Resolve `root_ca_path` as given (absolute path).

#### [MODIFY] `src/iot_device_simulator/aws/globals.py`
*   `initialize_config(project_name)`:
    *   Build path: `upload/{project}/iot_device_simulator/aws/config_generated.json`.
    *   Load config.
    *   Resolve `cert_path`, `key_path`, `payload_path` relative to config file's directory.
    *   Store resolved paths in a global `config` dict.

#### [MODIFY] `src/iot_device_simulator/aws/transmission.py`
*   Use `globals.config` for all paths (no hardcoded relatives).
*   `cert_path`, `key_path`, `payload_path` are resolved by `globals.py`.

---

### 4. API Integration

#### [MODIFY] `rest_api.py`
**Task**: Register the new simulator router.
*   **Location**: Import section (line ~16) and router includes (line ~60).
*   **Changes**:
    ```python
    # Add import (after existing api imports)
    from api import projects, validation, deployment, status, info, aws_gateway, simulator
    
    # Add router include (after existing includes)
    app.include_router(simulator.router)
    ```

#### [NEW] `api/simulator.py`
*   **Endpoint**: `WebSocket /projects/{project_name}/simulator/{provider}/stream`
*   **On Connect**:
    1.  **Validate `project_name` exists**: Check `upload/{project}` directory.
    2.  **Validate `provider` is supported**: Currently only `aws`.
    3.  **Check Deployment Health (Pre-flight Checks)**:
        *   `config_generated.json` exists?
            *   If not: Error "Simulator config not found. Please deploy L1 first."
        *   `iot_devices_auth/{device_id}/` exists with cert files?
            *   If not: Error "Device certificates not found. Please deploy L1 first."
        *   `payloads.json` exists?
            *   If not: Error "Payloads file not found. Please upload payloads.json first."
        *   `payloads.json` is valid JSON array with `iotDeviceId` keys?
            *   If not: Error with validation details.
    4.  **Start Subprocess**: `python src/iot_device_simulator/aws/main.py --project {project_name}`.
    5.  **Async Loop**:
        *   Read `stdout`/`stderr` from subprocess -> Send to WS client as `{"type": "log", "data": "..."}`.
        *   Read WS client messages -> Write to subprocess `stdin`:
            *   `{"command": "send"}` -> writes `send\n` to stdin.
            *   `{"command": "help"}` -> writes `help\n` to stdin.
            *   `{"command": "exit"}` -> writes `exit\n` to stdin.
*   **On Disconnect**: Terminate subprocess.

#### [NEW] Download Simulator Package Endpoint
*   **Endpoint**: `GET /projects/{project_name}/simulator/{provider}/download`
*   **Purpose**: Allow users to download a **complete, standalone simulator package** that can be run on an external machine, real IoT device, or shared with a team member.
*   **Response**: A zip file containing the **full simulator** (code + config + certs + Docker):
    ```text
    simulator_package_{project_name}_{provider}.zip
    ├── README.md                 # Setup and usage guide (auto-generated)
    ├── requirements.txt          # Python dependencies (e.g., AWSIoTPythonSDK)
    ├── Dockerfile                # Docker setup (auto-generated)
    ├── docker-compose.yml        # Docker Compose for easy startup
    ├── config.json               # Copy of config_generated.json (renamed for clarity)
    ├── payloads.json             # User's payload definitions
    ├── AmazonRootCA1.pem         # Root CA certificate
    ├── certificates/
    │   └── {device_id}/
    │       ├── certificate.pem.crt
    │       └── private.pem.key
    └── src/                      # Simulator Python code
        ├── main.py               # Entry point
        ├── transmission.py       # MQTT logic
        └── globals.py            # Config loading
    ```
*   **Logic**:
    1.  **Validate**: Project exists, provider is supported, `config_generated.json` exists.
    2.  **Gather Files**:
        *   `upload/{project}/iot_device_simulator/{provider}/config_generated.json` -> `config.json`
        *   `upload/{project}/iot_device_simulator/{provider}/payloads.json` -> `payloads.json`
        *   `src/iot_device_simulator/{provider}/AmazonRootCA1.pem` -> `AmazonRootCA1.pem`
        *   `src/iot_device_simulator/{provider}/*.py` -> `src/*.py` (all Python files)
        *   `upload/{project}/iot_devices_auth/{device_id}/*` -> `certificates/{device_id}/*`
            *   The `device_id` is read from `config_generated.json`.
    3.  **Transform config.json Paths for Standalone Use**:
        *   The original `config_generated.json` has paths relative to the project's upload directory.
        *   For standalone use, paths must be relative to the zip's root.
        *   **Transformation**:
            ```python
            # Original (from config_generated.json):
            "cert_path": "../../iot_devices_auth/{id}/certificate.pem.crt"
            "key_path": "../../iot_devices_auth/{id}/private.pem.key"
            "root_ca_path": "/absolute/path/to/AmazonRootCA1.pem"
            "payload_path": "payloads.json"
            
            # Transformed (for standalone zip):
            "cert_path": "certificates/{id}/certificate.pem.crt"
            "key_path": "certificates/{id}/private.pem.key"
            "root_ca_path": "AmazonRootCA1.pem"
            "payload_path": "payloads.json"  # Unchanged (already relative)
            ```
    4.  **Generate README.md**: Create a dynamically generated guide (see template below).
    5.  **Generate requirements.txt**: Include `AWSIoTPythonSDK` (for AWS provider).
    6.  **Generate Dockerfile**: Create a Docker setup that starts the simulator.
    7.  **Generate docker-compose.yml**: For easy `docker-compose up` startup.
    8.  **Create Zip**: Use `zipfile` module to create an in-memory zip.
    9.  **Return**: `StreamingResponse` with `Content-Disposition: attachment; filename=simulator_package_{project}_{provider}.zip`.
*   **Use Case**: User wants to run the simulator on an external machine, real IoT device, or share the config with a team member.

**README.md Template (Generated Dynamically)**:
```markdown
# IoT Device Simulator Package

**Project**: {project_name}
**Provider**: {provider}
**Device ID**: {device_id}
**Endpoint**: {endpoint}
**Generated**: {timestamp}

## Prerequisites
- Python 3.9+
- pip

## Setup
1. Extract this zip file.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Run the simulator:
```bash
python src/main.py
```

### Available Commands
- `send` - Send the next payload from payloads.json to AWS IoT Core.
- `help` - Show available commands.
- `exit` - Exit the simulator.

## File Structure
- `config.json` - Simulator configuration (endpoint, topic, paths).
- `payloads.json` - Payload data to send (edit this to change what data is sent).
- `AmazonRootCA1.pem` - AWS Root CA certificate (do not modify).
- `certificates/` - Device certificates (do not modify).
- `src/` - Simulator Python code.

## Notes
- The simulator will cycle through payloads in `payloads.json`.
- Each payload must have an `iotDeviceId` field matching the device.
- Timestamps (`time` field) are auto-filled if empty.
```

**Dockerfile Template (Generated Dynamically)**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy all files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run simulator interactively
CMD ["python", "src/main.py"]
```

**docker-compose.yml Template (Generated Dynamically)**:
```yaml
version: '3.8'

services:
  simulator:
    build: .
    container_name: iot_simulator_{device_id}
    stdin_open: true   # Keep stdin open for interactive commands
    tty: true          # Allocate a pseudo-TTY
    restart: unless-stopped
```

**Usage with Docker** (included in README.md):
```bash
# Option 1: Run with Docker
docker build -t iot-simulator .
docker run -it iot-simulator

# Option 2: Run with Docker Compose
docker-compose up --build
```

> [!NOTE]
> **Security Consideration**: This endpoint exposes private keys. It should be protected in production environments. For now (development/thesis scope), it's acceptable. Future: Add authentication or require explicit user confirmation.

#### Deployment State Caching (Future Vision)
> [!NOTE]
> **Current Approach**: For this initial implementation, deployment health checks (file existence) are performed **at WebSocket connect time**. This is a simple, stateless approach that works for the current scope.
>
> **Future Improvement (Flutter Frontend Phase)**: When the Flutter frontend is implemented with its management database, deployment state can be **cached in the database**:
> *   **On Deploy**: Write deployment status (L1 deployed, L2 deployed, etc.) to the database.
> *   **On Simulator Start**: Query the database for deployment status instead of checking files.
> *   **Benefits**: Faster checks, richer state tracking (e.g., "L1 deployed at 2025-12-07 21:00 UTC"), offline state awareness.
>
> This is **out of scope** for this implementation plan. The file-based checks are sufficient for now and will be replaced when the database is introduced.

---

### 5. CLI Integration

#### [MODIFY] `src/main.py`
*   **New Command**: `simulate <provider> [project_name]`
    *   Example: `simulate aws` (uses active project) or `simulate aws my_project`.
*   **Logic**:
    1.  Resolve `project_name` (default to `globals.CURRENT_PROJECT`).
    2.  **Pre-flight Checks** (same as API):
        *   Check `config_generated.json` exists.
        *   Check `payloads.json` exists.
    3.  Run `subprocess.call(["python", "src/iot_device_simulator/aws/main.py", "--project", project_name])`.
    4.  This is **blocking**. The main CLI loop pauses until the simulator subprocess exits (user types `exit`).
*   **Help Menu Update**: Add `simulate` command description.

---

### 6. Validation

#### [MODIFY] `src/validator.py`
*   **New Function**: `validate_simulator_payloads(content_str, project_name=None)`:
    *   Parse `content_str` as JSON.
    *   **Check 1**: Valid JSON.
    *   **Check 2**: Is a list (array).
    *   **Check 3**: Each object has `iotDeviceId` key.
    *   **Check 4 (Warning, optional)**: If `project_name` is provided, load `config_iot_devices.json` and check each `iotDeviceId` exists. Return warnings for mismatches.
    *   Returns `(is_valid: bool, errors: list[str], warnings: list[str])`.

---

### 7. API for Payloads (Validation & Upload Endpoints)

Following the pattern in `api/validation.py`, we add dedicated validation endpoints:

#### [ADD to `api/validation.py`]
**Validation Endpoints for Simulator Payloads**:

1.  **`POST /validate/simulator/payloads`** (Validate uploaded content, no project context):
    *   **Input**: Binary/base64 JSON content.
    *   **Logic**: Call `validator.validate_simulator_payloads(content)` without project context.
    *   **Returns**: `{"valid": true, "errors": [], "warnings": []}` or 400 with errors.
    *   **Use Case**: User wants to validate a `payloads.json` file before uploading to a specific project.

2.  **`POST /validate/simulator/payloads/{project_name}`** (Validate uploaded content with project context):
    *   **Input**: Binary/base64 JSON content.
    *   **Logic**: Call `validator.validate_simulator_payloads(content, project_name=project_name)`.
    *   **Returns**: `{"valid": true, "errors": [], "warnings": ["iotDeviceId 'x' not found in config_iot_devices.json"]}` or 400.
    *   **Use Case**: User wants to validate content AND check device IDs against a specific project's configuration.

3.  **`GET /projects/{project_name}/simulator/{provider}/payloads/validate`** (Validate existing file in project):
    *   **Input**: None (reads from disk).
    *   **Logic**: Load `upload/{project}/iot_device_simulator/{provider}/payloads.json`, validate using `validate_simulator_payloads(content, project_name)`.
    *   **Returns**: `{"valid": true, "errors": [], "warnings": []}` or 400.
    *   **Use Case**: User wants to validate the currently saved `payloads.json` in a project.

#### [ADD to `api/projects.py`]
**Upload Endpoint**:

*   **`PUT /projects/{project_name}/simulator/{provider}/payloads`**:
    *   **Input**: Binary/base64 JSON content.
    *   **Logic**:
        1.  Call `validator.validate_simulator_payloads(content, project_name=project_name)`.
        2.  If `errors`: Return 400 with error details.
        3.  If `warnings`: Log them, include in response, but proceed.
        4.  Save to `upload/{project}/iot_device_simulator/{provider}/payloads.json`.
    *   **Returns**: `{"message": "Payloads uploaded successfully.", "warnings": [...]}` or 400.

---

## Files to Move/Delete/Rename

| Action | Source | Destination | Reason |
|---|---|---|---|
| MOVE | `src/iot_device_simulator/src/main.py` | `src/iot_device_simulator/aws/main.py` | Multi-cloud structure |
| MOVE | `src/iot_device_simulator/src/transmission.py` | `src/iot_device_simulator/aws/transmission.py` | Multi-cloud structure |
| MOVE | `src/iot_device_simulator/src/globals.py` | `src/iot_device_simulator/aws/globals.py` | Multi-cloud structure |
| MOVE | `src/iot_device_simulator/AmazonRootCA1.pem` | `src/iot_device_simulator/aws/AmazonRootCA1.pem` | Bundled with AWS code |
| MOVE | `src/iot_device_simulator/payloads.json` | `upload/template/iot_device_simulator/aws/payloads.json` | User adaptable |
| RENAME | `src/iot_device_simulator/config.json` | `src/iot_device_simulator/config.json.example` | Kept for reference only |
| CREATE | N/A | `src/iot_device_simulator/__init__.py` | Python package marker (empty file) |
| CREATE | N/A | `src/iot_device_simulator/aws/__init__.py` | Python package marker (empty file) |
| CREATE | N/A | `src/iot_device_simulator/azure/__init__.py` | Python package marker (empty file) |
| CREATE | N/A | `src/iot_device_simulator/google/__init__.py` | Python package marker (empty file) |
| CREATE | N/A | `src/iot_device_simulator/azure/.gitkeep` | Placeholder for future Azure implementation |
| CREATE | N/A | `src/iot_device_simulator/google/.gitkeep` | Placeholder for future Google implementation |
| DELETE | `src/iot_device_simulator/src/` (empty after moves) | N/A | Cleanup empty directory |

---

## Verification Plan

### Automated Tests (`tests/`)

1.  **Config Generation Test** (`tests/unit/test_simulator_config_generation.py`):
    *   Mock `boto3` IoT client (`describe_endpoint`).
    *   Call `_generate_simulator_config({"id": "test_device"})`.
    *   Assert `upload/.../config_generated.json` is created with correct keys (`endpoint`, `topic`, `cert_path`, `key_path`, `root_ca_path`, `payload_path`).
    *   Assert `topic` is derived from `digital_twin_name`.
    *   **Run**: `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 pytest tests/unit/test_simulator_config_generation.py -v`

2.  **Payload Validator Test** (`tests/unit/test_validator_simulator.py`):
    *   Test `validate_simulator_payloads` with:
        *   Valid list with `iotDeviceId` -> Pass, no errors.
        *   Invalid JSON -> Fail with error.
        *   Not a list (e.g., dict) -> Fail with error.
        *   Missing `iotDeviceId` -> Fail with error.
        *   `iotDeviceId` not in `config_iot_devices.json` -> Pass with warning.
    *   **Run**: `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 pytest tests/unit/test_validator_simulator.py -v`

3.  **Payload Validation API Test** (`tests/api/test_simulator_validation.py`):
    *   Test `POST /validate/simulator/payloads` with valid/invalid content.
    *   Test `GET /projects/{project_name}/simulator/{provider}/payloads/validate` with existing file.
    *   **Run**: `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 pytest tests/api/test_simulator_validation.py -v`

4.  **WebSocket API Test** (`tests/api/test_simulator_ws.py`):
    *   Use `TestClient` with WebSocket support.
    *   **Test 1 (Config Missing)**: Connect without `config_generated.json` -> Expect error message.
    *   **Test 2 (Payloads Missing)**: Connect without `payloads.json` -> Expect error message.
    *   **Test 3 (Happy Path)**: Create mock `config_generated.json` and `payloads.json`, connect, send `{"command": "help"}`, verify response contains "Available commands".
    *   **Run**: `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 pytest tests/api/test_simulator_ws.py -v`

### Manual Verification

1.  **CLI Flow**:
    1.  Start Docker container: `docker-compose up -d`.
    2.  Run CLI: `docker exec -it -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python src/main.py`.
    3.  Type `deploy aws` (Must have AWS creds configured).
    4.  After deployment, type `simulate aws`.
    5.  Expected: Simulator starts, shows "Welcome to the IoT Device Simulator...".
    6.  Type `help`. Expected: Shows available commands.
    7.  Type `send`. Expected: "Message sent!" (if AWS endpoint is reachable).
    8.  Type `exit`. Expected: Returns to main CLI.

2.  **API Flow (Postman or similar WebSocket client)**:
    1.  Ensure API is running: `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 uvicorn rest_api:app --host 0.0.0.0 --port 8000`.
    2.  Connect to `ws://localhost:8000/projects/template/simulator/aws/stream`.
    3.  Expected: Logs stream in showing "Welcome to...".
    4.  Send `{"command": "help"}`.
    5.  Expected: Logs stream shows help menu.
    6.  Disconnect.

3.  **Validation Endpoints (curl/Postman)**:
    1.  `POST /validate/simulator/payloads` with valid JSON array -> 200.
    2.  `POST /validate/simulator/payloads` with invalid JSON -> 400.
    3.  `GET /projects/template/simulator/aws/payloads/validate` -> 200 (assuming payloads.json exists in template).
