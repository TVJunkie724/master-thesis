"""Aggregate validation contract for deployable Twin configurations."""

import json

from fastapi import APIRouter
from pydantic import BaseModel, Field

import src.validator as validator

router = APIRouter()

# 11. Complete Deployer Config Validation
# ==========================================

class ValidationError(BaseModel):
    """Structured validation error with error code for localization."""
    code: str
    field: str
    message: str


class DeployerCompleteValidation(BaseModel):
    """Input model for complete deployer config validation."""
    # Core configs
    deployer_digital_twin_name: str | None = None
    config_events: str | None = None          # JSON content
    config_iot_devices: str | None = None     # JSON content
    payloads: str | None = None               # JSON content
    
    # Functions
    processors: dict[str, str] | None = None  # {device_id: code}
    event_feedback: str | None = None         # code
    event_actions: dict[str, str] | None = None  # {name: code}
    
    # L4 assets
    hierarchy: str | None = None              # JSON content
    scene_config: str | None = None           # JSON content
    scene_glb_uploaded: bool = False
    
    # L2 state machine
    state_machine: str | None = None          # JSON/YAML content
    
    # L5 user config
    user_config: str | None = None            # JSON content
    
    # Context from optimizer
    optimizer_params: dict | None = None
    cheapest_path: dict[str, str | dict] | None = None


class DeployerValidationResponse(BaseModel):
    """Validation response with all errors."""
    valid: bool
    errors: list[ValidationError] = Field(default_factory=list)


def _parse_device_ids(config_iot_devices: str | None) -> list[str]:
    """Extract device IDs from config_iot_devices JSON."""
    if not config_iot_devices:
        return []
    try:
        devices = json.loads(config_iot_devices)
        if isinstance(devices, list):
            return [d.get("id") for d in devices if isinstance(d, dict) and d.get("id")]
    except json.JSONDecodeError:
        pass
    return []


def _parse_action_names(config_events: str | None) -> list[str]:
    """Extract action functionNames from config_events JSON.
    
    For workflow actions (step_function, logic_app, workflow), extracts both
    functionName and functionNameB since they represent chained functions.
    """
    if not config_events:
        return []
    try:
        events = json.loads(config_events)
        if isinstance(events, list):
            names = []
            for event in events:
                if isinstance(event, dict):
                    action = event.get("action", {})
                    if isinstance(action, dict):
                        if action.get("functionName"):
                            names.append(action["functionName"])
                        if action.get("functionNameB"):
                            names.append(action["functionNameB"])
            return names
    except json.JSONDecodeError:
        pass
    return []


def _get_state_machine_filename(provider: str) -> str:
    """Get state machine filename for provider."""
    provider = provider.lower()
    if provider == "azure":
        return "azure_logic_app.json"
    elif provider == "gcp" or provider == "google":
        return "google_cloud_workflow.yaml"
    else:  # aws is default
        return "aws_step_function.json"


def _validate_payload_device_coverage(
    payloads_content: str,
    device_ids: list[str],
) -> list[ValidationError]:
    """Validate payload structure and require coverage for every configured device."""
    valid, validation_errors, _warnings = validator.validate_simulator_payloads(
        payloads_content
    )
    if not valid:
        return [
            ValidationError(
                code="INVALID_PAYLOADS",
                field="payloads",
                message=message,
            )
            for message in validation_errors
        ]

    payloads = json.loads(payloads_content)
    payload_device_ids = {
        payload.get("iotDeviceId")
        for payload in payloads
        if isinstance(payload, dict) and payload.get("iotDeviceId")
    }
    configured_device_ids = set(device_ids)
    errors = [
        ValidationError(
            code="UNKNOWN_PAYLOAD_DEVICE",
            field="payloads",
            message=f"Payload references unknown device '{device_id}'",
        )
        for device_id in sorted(payload_device_ids - configured_device_ids)
    ]
    errors.extend(
        ValidationError(
            code="MISSING_DEVICE_PAYLOAD",
            field=f"payload:{device_id}",
            message=f"At least one simulator payload for device '{device_id}' is required",
        )
        for device_id in sorted(configured_device_ids - payload_device_ids)
    )
    return errors


@router.post(
    "/validate/deployer-complete",
    operation_id="validateDeployerComplete",
    response_model=DeployerValidationResponse,
    tags=["Validation"],
    summary="Validate complete deployer configuration",
    description="""
Validates ALL deployer configuration files and functions for state transition to 'configured'.

**Checks performed (reuses existing validators):**
- `deployer_digital_twin_name`: Non-empty, valid format (alphanumeric, hyphen, underscore, max 15 chars)
- `config_events`, `config_iot_devices`: Required, schema validation
- `payloads`: Required
- `processors`: One per device in config_iot_devices, code validation
- `hierarchy`: Required if L4 = AWS or Azure, schema validation
- `scene_config`, `scene_glb`: Required if needs3DModel = true and L4 = AWS/Azure
- `event_feedback`: Required if returnFeedbackToDevice = true
- `event_actions`: One per action functionName in config_events (if useEventChecking = true)
- `state_machine`: Required if triggerNotificationWorkflow = true
- `user_config`: Required if L5 = AWS or Azure

**Returns all errors, not just the first one.**
"""
)
async def validate_deployer_complete(
    config: DeployerCompleteValidation
) -> DeployerValidationResponse:
    """
    Validates complete deployer configuration for state transition.
    
    Reuses existing validators from validator.py.
    Returns all validation errors aggregated.
    """
    errors: list[ValidationError] = []
    
    # === CORE CONFIGS (always required) ===
    
    # Digital twin name
    name = config.deployer_digital_twin_name or ""
    if not name.strip():
        errors.append(ValidationError(
            code="EMPTY_NAME",
            field="deployer_digital_twin_name",
            message="Digital twin name in config.json is required"
        ))
    else:
        try:
            validator.validate_digital_twin_name(name)
        except ValueError as e:
            errors.append(ValidationError(
                code="INVALID_NAME",
                field="deployer_digital_twin_name",
                message=str(e)
            ))
    
    # Config events
    if not config.config_events:
        errors.append(ValidationError(
            code="MISSING_CONFIG_EVENTS",
            field="config_events",
            message="config_events.json is required"
        ))
    else:
        try:
            validator.validate_config_content("config_events.json", config.config_events)
        except ValueError as e:
            errors.append(ValidationError(
                code="INVALID_CONFIG_EVENTS",
                field="config_events",
                message=str(e)
            ))
    
    # Config IoT devices
    if not config.config_iot_devices:
        errors.append(ValidationError(
            code="MISSING_CONFIG_IOT_DEVICES",
            field="config_iot_devices",
            message="config_iot_devices.json is required"
        ))
    else:
        try:
            validator.validate_config_content("config_iot_devices.json", config.config_iot_devices)
        except ValueError as e:
            errors.append(ValidationError(
                code="INVALID_CONFIG_IOT_DEVICES",
                field="config_iot_devices",
                message=str(e)
            ))
    
    # Payloads
    if not config.payloads:
        errors.append(ValidationError(
            code="MISSING_PAYLOADS",
            field="payloads",
            message="payloads.json is required"
        ))
    
    # === PROCESSORS AND PAYLOADS (per device) ===
    device_ids = _parse_device_ids(config.config_iot_devices)
    if config.payloads:
        errors.extend(_validate_payload_device_coverage(config.payloads, device_ids))
    processors = config.processors or {}
    l2_provider = (config.cheapest_path or {}).get("L2", "aws").lower()
    
    for device_id in device_ids:
        code = processors.get(device_id)
        if not code:
            errors.append(ValidationError(
                code="MISSING_PROCESSOR",
                field=f"processor:{device_id}",
                message=f"Processor for device '{device_id}' is required"
            ))
        else:
            try:
                if l2_provider == "azure":
                    validator.validate_python_code_azure(code)
                elif l2_provider == "gcp" or l2_provider == "google":
                    validator.validate_python_code_google(code)
                else:  # aws is default
                    validator.validate_python_code_aws(code)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_PROCESSOR",
                    field=f"processor:{device_id}",
                    message=f"Processor for '{device_id}': {str(e)}"
                ))
    
    # === CONDITIONAL VALIDATION ===
    params = config.optimizer_params or {}
    path = config.cheapest_path or {}
    l4 = path.get("L4", "").upper()
    l5 = path.get("L5", "").upper()
    
    # Hierarchy (L4 = AWS/Azure)
    if l4 in ("AWS", "AZURE"):
        if not config.hierarchy:
            errors.append(ValidationError(
                code="MISSING_HIERARCHY",
                field="hierarchy",
                message=f"Hierarchy JSON is required for L4 provider ({l4})"
            ))
        else:
            try:
                if l4 == "AWS":
                    validator.validate_aws_hierarchy_content(config.hierarchy)
                else:
                    validator.validate_azure_hierarchy_content(config.hierarchy)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_HIERARCHY",
                    field="hierarchy",
                    message=str(e)
                ))
    
    # Scene config (L4 = AWS/Azure + needs3DModel)
    if l4 in ("AWS", "AZURE") and params.get("needs3DModel"):
        if not config.scene_config:
            errors.append(ValidationError(
                code="MISSING_SCENE_CONFIG",
                field="scene_config",
                message="Scene config is required for 3D visualization"
            ))
        else:
            try:
                validator.validate_scene_config_content(l4.lower(), config.scene_config, config.hierarchy)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_SCENE_CONFIG",
                    field="scene_config",
                    message=str(e)
                ))
        
        if not config.scene_glb_uploaded:
            errors.append(ValidationError(
                code="MISSING_SCENE_GLB",
                field="scene_glb",
                message="Scene GLB file must be uploaded for 3D visualization"
            ))
    
    # Event feedback (returnFeedbackToDevice = true)
    if params.get("returnFeedbackToDevice"):
        if not config.event_feedback:
            errors.append(ValidationError(
                code="MISSING_EVENT_FEEDBACK",
                field="event_feedback",
                message="Event feedback function is required (returnFeedbackToDevice=true)"
            ))
        else:
            try:
                if l2_provider == "azure":
                    validator.validate_python_code_azure(config.event_feedback)
                elif l2_provider == "gcp" or l2_provider == "google":
                    validator.validate_python_code_google(config.event_feedback)
                else:
                    validator.validate_python_code_aws(config.event_feedback)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_EVENT_FEEDBACK",
                    field="event_feedback",
                    message=f"Event feedback: {str(e)}"
                ))
    
    # Event actions (useEventChecking = true)
    if params.get("useEventChecking"):
        action_names = _parse_action_names(config.config_events)
        actions = config.event_actions or {}
        for action_name in action_names:
            code = actions.get(action_name)
            if not code:
                errors.append(ValidationError(
                    code="MISSING_EVENT_ACTION",
                    field=f"event_action:{action_name}",
                    message=f"Event action function '{action_name}' is required"
                ))
            else:
                try:
                    if l2_provider == "azure":
                        validator.validate_python_code_azure(code)
                    elif l2_provider == "gcp" or l2_provider == "google":
                        validator.validate_python_code_google(code)
                    else:
                        validator.validate_python_code_aws(code)
                except ValueError as e:
                    errors.append(ValidationError(
                        code="INVALID_EVENT_ACTION",
                        field=f"event_action:{action_name}",
                        message=f"Event action '{action_name}': {str(e)}"
                    ))
    
    # State machine (triggerNotificationWorkflow = true)
    if params.get("triggerNotificationWorkflow"):
        if not config.state_machine:
            errors.append(ValidationError(
                code="MISSING_STATE_MACHINE",
                field="state_machine",
                message="State machine is required (triggerNotificationWorkflow=true)"
            ))
        else:
            try:
                filename = _get_state_machine_filename(l2_provider)
                validator.validate_state_machine_content(filename, config.state_machine)
            except ValueError as e:
                errors.append(ValidationError(
                    code="INVALID_STATE_MACHINE",
                    field="state_machine",
                    message=str(e)
                ))
    
    # User config (L5 = AWS/Azure)
    if l5 in ("AWS", "AZURE"):
        if not config.user_config:
            errors.append(ValidationError(
                code="MISSING_USER_CONFIG",
                field="user_config",
                message=f"User config is required for L5 provider ({l5})"
            ))
    
    return DeployerValidationResponse(
        valid=len(errors) == 0,
        errors=errors
    )


