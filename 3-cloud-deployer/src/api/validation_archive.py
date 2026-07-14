"""Project archive validation endpoints."""

from fastapi import APIRouter, File, HTTPException, UploadFile

import src.validator as validator
from src.api.error_models import ERROR_RESPONSES
from logger import logger
from src.api.upload_limits import read_upload_bounded
from src.core.observability import redact_sensitive
from src.project_archive.policy import MAX_COMPRESSED_ARCHIVE_BYTES
from src.project_archive.policy import ArchiveLimitExceeded, ArchivePolicyError

router = APIRouter()

# ==========================================
# 1. Zip Validation
# ==========================================
@router.post(
    "/validate/zip",
    operation_id="validateProjectZip",
    tags=["Validation"],
    summary="Validate project zip file",
    description=(
        "**Purpose:** Validates a project zip file without extracting, checking structure and security.\\n\\n"
        "**When to call:** Before uploading a project to verify it meets all requirements.\\n\\n"
        "**Checks performed:** Zip integrity, Zip Slip path traversal, required files, schema validation."
    ),
    responses={
        200: {"description": "Project zip is valid"},
        400: ERROR_RESPONSES[400],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_zip(file: UploadFile = File(..., description="Project zip file to validate")):
    """
    Validates a project zip file without extracting it.
    
    **Minimal valid project structure:**
    ```
    project.zip
    ├── config.json                    (required)
    ├── config_iot_devices.json        (required)
    ├── config_events.json             (required)
    ├── config_providers.json          (required)
    ├── config_optimization.json       (required)
    ├── config_credentials.json        (required)
    │
    ├── twin_hierarchy/                (required)
    │   ├── aws_hierarchy.json         (required if layer_4_provider=aws)
    │   └── azure_hierarchy.json       (required if layer_4_provider=azure)
    │
    ├── state_machines/                (optional - required if triggerNotificationWorkflow=true)
    │   ├── aws_step_function.json     (if layer_2_provider=aws)
    │   ├── azure_logic_app.json       (if layer_2_provider=azure)
    │   └── google_cloud_workflow.yaml (if layer_2_provider=google)
    │
    ├── lambda_functions/              (if layer_2_provider=aws)
    │   ├── processors/
    │   │   └── default_processor/
    │   │       └── process.py
    │   ├── event_actions/             (optional - required if useEventChecking=true)
    │   │   └── <action_name>/
    │   │       └── lambda_function.py
    │   └── event-feedback/            (optional - required if returnFeedbackToDevice=true)
    │       └── lambda_function.py
    │
    ├── azure_functions/               (if layer_2_provider=azure)
    │   ├── processors/
    │   │   └── default_processor/
    │   │       └── function_app.py
    │   └── event_actions/             (optional - required if useEventChecking=true)
    │       └── <action_name>/
    │           └── function_app.py
    │
    ├── cloud_functions/               (if layer_2_provider=google)
    │   ├── processors/
    │   │   └── default_processor/
    │   │       └── main.py
    │   └── event_actions/             (optional - required if useEventChecking=true)
    │       └── <action_name>/
    │           └── main.py
    │
    └── iot_device_simulator/          (optional - for testing IoT data flow)
        └── payloads.json
    ```
    
    **Dependency triggers (in config_optimization.json):**
    - `useEventChecking=true` → requires event_actions/ folder
    - `returnFeedbackToDevice=true` → requires event-feedback/ folder (AWS only)
    - `triggerNotificationWorkflow=true` → requires state_machines/ folder
    
    **Checks performed:**
    - Zip integrity and path traversal safety (Zip Slip)
    - Presence of all required configuration files
    - Content schema validation for all config files
    - Dependency checks based on optimization flags
    """
    try:
        content = await read_upload_bounded(
            file,
            max_bytes=MAX_COMPRESSED_ARCHIVE_BYTES,
        )
        validator.validate_project_zip(content)
        return {"message": "Project zip is valid and secure."}
    except ArchiveLimitExceeded as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except ArchivePolicyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Validation error: %s", redact_sensitive(e))
        raise HTTPException(status_code=500, detail="Internal validation error. Check server logs.")
