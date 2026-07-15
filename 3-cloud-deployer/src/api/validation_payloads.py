"""IoT simulator payload validation endpoints."""

import json

from fastapi import APIRouter, File, HTTPException, UploadFile

import src.validator as validator
from src.api.error_handling import internal_server_error, safe_error_detail
from src.api.error_models import ERROR_RESPONSES
from src.api.upload_limits import MAX_VALIDATION_UPLOAD_BYTES, read_upload_bounded

router = APIRouter()

# ==========================================
# 5. Simulator Payload Validation
# ==========================================
@router.post(
    "/validate/simulator/payloads",
    operation_id="validateSimulatorPayloads",
    tags=["Validation"],
    summary="Validate simulator payloads",
    description=(
        "**Purpose:** Validates the structure of a payloads.json file for IoT simulation.\n\n"
        "**When to call:** Before running the IoT simulator to verify payload format.\n\n"
        "**Required fields:** Each payload must have an iotDeviceId matching config_iot_devices.json."
    ),
    responses={
        200: {"description": "Payloads structure is valid"},
        413: ERROR_RESPONSES[413],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_simulator_payloads(
    file: UploadFile = File(..., description="payloads.json file to validate")
):
    """
    Validates the structure of a payloads.json file.
    
    **Minimal example:**
    ```json
    [
        {
            "iotDeviceId": "device-1",
            "temperature": 25.5,
            "humidity": 60
        },
        {
            "iotDeviceId": "device-2",
            "pressure": 1013.25
        }
    ]
    ```
    
    **Required fields per payload:**
    - `iotDeviceId`: String identifier matching a device in config_iot_devices.json
    """
    try:
        content = await read_upload_bounded(
            file,
            max_bytes=MAX_VALIDATION_UPLOAD_BYTES,
        )
        content_str = content.decode('utf-8')
        
        is_valid, errors, warnings = validator.validate_simulator_payloads(content_str)
        
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_server_error("Validate simulator payloads", exc) from exc

@router.post(
    "/validate/payloads-with-devices",
    operation_id="validatePayloadsWithDevices",
    tags=["Validation"],
    summary="Cross-validate payloads against devices",
    description=(
        "**Purpose:** Validates that all iotDeviceId values in payloads.json exist in config_iot_devices.json.\n\n"
        "**When to call:** To ensure payload device IDs match configured devices before simulation.\n\n"
        "**Response:** Returns valid=true if all device IDs match, or list of mismatches."
    ),
    responses={
        200: {"description": "All payload device IDs exist in devices config"},
        400: ERROR_RESPONSES[400],
        413: ERROR_RESPONSES[413],
        500: ERROR_RESPONSES[500],
    }
)
async def validate_payloads_with_devices(
    payloads_file: UploadFile = File(..., description="payloads.json file"),
    devices_file: UploadFile = File(..., description="config_iot_devices.json file")
):
    """
    Validates payloads.json against config_iot_devices.json.
    
    **payloads.json example:**
    ```json
    [{"iotDeviceId": "device-1", "temperature": 25.5}]
    ```
    
    **config_iot_devices.json example:**
    ```json
    [{"id": "device-1", "properties": ["temperature", "humidity"]}]
    ```
    
    **Checks:**
    - All `iotDeviceId` values in payloads exist as `id` in devices config
    - Payload structure is valid
    """
    try:
        payloads_content = await read_upload_bounded(
            payloads_file,
            max_bytes=MAX_VALIDATION_UPLOAD_BYTES,
        )
        devices_content = await read_upload_bounded(
            devices_file,
            max_bytes=MAX_VALIDATION_UPLOAD_BYTES,
        )
        
        payloads_str = payloads_content.decode('utf-8')
        devices_str = devices_content.decode('utf-8')
        
        # Parse both files
        try:
            payloads = json.loads(payloads_str)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON in payloads file: {safe_error_detail(exc)}",
            ) from exc
        
        try:
            devices = json.loads(devices_str)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON in devices file: {safe_error_detail(exc)}",
            ) from exc
        
        errors = []
        warnings = []
        
        # Get valid device IDs from config
        if not isinstance(devices, list):
            raise HTTPException(status_code=400, detail="config_iot_devices.json must be a JSON array")
        
        valid_device_ids = {d.get("id") for d in devices if isinstance(d, dict) and "id" in d}
        
        if not isinstance(payloads, list):
            raise HTTPException(status_code=400, detail="payloads.json must be a JSON array")
        
        # Check each payload
        for idx, payload in enumerate(payloads):
            if not isinstance(payload, dict):
                errors.append(f"Item at index {idx} is not a JSON object")
                continue
            
            device_id = payload.get("iotDeviceId")
            if not device_id:
                errors.append(f"Item at index {idx} missing required 'iotDeviceId'")
            elif device_id not in valid_device_ids:
                errors.append(f"Item at index {idx}: iotDeviceId '{device_id}' not found in config_iot_devices.json")
        
        if not payloads:
            warnings.append("Payloads list is empty")
        
        is_valid = len(errors) == 0
        
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "devices_found": list(valid_device_ids)
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise internal_server_error("Cross-validate simulator payloads", exc) from exc

