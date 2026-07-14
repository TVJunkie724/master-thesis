"""Aggregate deployer configuration validation without provider fallbacks."""

from __future__ import annotations

import json
import re
from typing import Callable

import src.validator as validator
from src.api.models.complete_validation import (
    DeployerCompleteValidation,
    DeployerValidationResponse,
    ValidationError,
)


PROVIDERS = {"aws", "azure", "gcp"}
OPTIONAL_LAYER_PROVIDERS = PROVIDERS | {"none"}
OPTIMIZATION_FLAGS = {
    "needs3DModel",
    "returnFeedbackToDevice",
    "triggerNotificationWorkflow",
    "useEventChecking",
}
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def validate_complete_configuration(
    config: DeployerCompleteValidation,
) -> DeployerValidationResponse:
    errors: list[ValidationError] = []
    _validate_core(config, errors)

    path = config.cheapest_path or {}
    l2 = _provider(path, "L2", PROVIDERS, errors)
    l4 = _provider(path, "L4", OPTIONAL_LAYER_PROVIDERS, errors)
    l5 = _provider(path, "L5", OPTIONAL_LAYER_PROVIDERS, errors)
    params = _optimization_flags(config.optimizer_params, errors)
    device_ids = _parse_device_ids(config.config_iot_devices)

    _validate_payloads(config.payloads, device_ids, errors)
    _validate_processors(config.processors or {}, device_ids, l2, errors)
    _validate_hierarchy_and_scene(config, l4, params, errors)
    _validate_event_extensions(config, l2, params, errors)
    _validate_user_config(config.user_config, l5, errors)
    return DeployerValidationResponse(valid=not errors, errors=errors)


def _validate_core(
    config: DeployerCompleteValidation,
    errors: list[ValidationError],
) -> None:
    name = config.deployer_digital_twin_name or ""
    if not name.strip():
        _add(errors, "EMPTY_NAME", "deployer_digital_twin_name", "Digital twin name in config.json is required")
    else:
        _call_validator(
            errors,
            "INVALID_NAME",
            "deployer_digital_twin_name",
            validator.validate_digital_twin_name,
            name,
        )
    _required_config(
        errors,
        config.config_events,
        "config_events",
        "config_events.json",
        "MISSING_CONFIG_EVENTS",
        "INVALID_CONFIG_EVENTS",
    )
    _required_config(
        errors,
        config.config_iot_devices,
        "config_iot_devices",
        "config_iot_devices.json",
        "MISSING_CONFIG_IOT_DEVICES",
        "INVALID_CONFIG_IOT_DEVICES",
    )
    if not config.payloads:
        _add(errors, "MISSING_PAYLOADS", "payloads", "payloads.json is required")


def _required_config(
    errors: list[ValidationError],
    content: str | None,
    field: str,
    filename: str,
    missing_code: str,
    invalid_code: str,
) -> None:
    if not content:
        _add(errors, missing_code, field, f"{filename} is required")
        return
    _call_validator(
        errors,
        invalid_code,
        field,
        validator.validate_config_content,
        filename,
        content,
    )


def _provider(
    path: dict,
    layer: str,
    allowed: set[str],
    errors: list[ValidationError],
) -> str | None:
    raw = path.get(layer, path.get(layer.lower()))
    if raw is None or raw == "":
        _add(errors, "MISSING_PROVIDER", f"cheapest_path.{layer}", f"Provider selection for {layer} is required")
        return None
    if not isinstance(raw, str):
        _add(errors, "INVALID_PROVIDER", f"cheapest_path.{layer}", f"Provider selection for {layer} must be a string")
        return None
    normalized = "gcp" if raw.strip().lower() == "google" else raw.strip().lower()
    if normalized not in allowed:
        _add(errors, "INVALID_PROVIDER", f"cheapest_path.{layer}", f"Unsupported provider '{raw}' for {layer}")
        return None
    return normalized


def _optimization_flags(
    params: dict | None,
    errors: list[ValidationError],
) -> dict[str, bool]:
    values = params or {}
    result = {}
    for name in OPTIMIZATION_FLAGS:
        value = values.get(name, False)
        if not isinstance(value, bool):
            _add(errors, "INVALID_OPTIMIZER_FLAG", f"optimizer_params.{name}", f"{name} must be a boolean")
            result[name] = False
        else:
            result[name] = value
    return result


def _parse_device_ids(content: str | None) -> list[str]:
    try:
        decoded = json.loads(content) if content else []
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return sorted(
        {
            item["id"]
            for item in decoded
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]
        }
    )


def _validate_payloads(
    content: str | None,
    device_ids: list[str],
    errors: list[ValidationError],
) -> None:
    if not content:
        return
    valid, validation_errors, _warnings = validator.validate_simulator_payloads(content)
    if not valid:
        for message in validation_errors:
            _add(errors, "INVALID_PAYLOADS", "payloads", message)
        return
    payloads = json.loads(content)
    payload_ids = {
        item.get("iotDeviceId")
        for item in payloads
        if isinstance(item, dict) and item.get("iotDeviceId")
    }
    configured = set(device_ids)
    for device_id in sorted(payload_ids - configured):
        _add(errors, "UNKNOWN_PAYLOAD_DEVICE", "payloads", f"Payload references unknown device '{device_id}'")
    for device_id in sorted(configured - payload_ids):
        _add(errors, "MISSING_DEVICE_PAYLOAD", f"payload:{device_id}", f"At least one simulator payload for device '{device_id}' is required")


def _validate_processors(
    processors: dict[str, str],
    device_ids: list[str],
    provider: str | None,
    errors: list[ValidationError],
) -> None:
    configured = set(device_ids)
    for device_id in sorted(configured - processors.keys()):
        _add(errors, "MISSING_PROCESSOR", f"processor:{device_id}", f"Processor for device '{device_id}' is required")
    for device_id in sorted(processors.keys() - configured):
        _add(errors, "UNEXPECTED_PROCESSOR", f"processor:{device_id}", f"Processor has no configured device '{device_id}'")
    if provider is None:
        return
    for device_id in sorted(configured & processors.keys()):
        _validate_function(errors, "INVALID_PROCESSOR", f"processor:{device_id}", f"Processor for '{device_id}'", provider, processors[device_id])


def _validate_hierarchy_and_scene(config, l4, params, errors) -> None:
    if l4 not in {"aws", "azure"}:
        return
    if not config.hierarchy:
        _add(errors, "MISSING_HIERARCHY", "hierarchy", f"Hierarchy JSON is required for L4 provider ({l4.upper()})")
    else:
        function = validator.validate_aws_hierarchy_content if l4 == "aws" else validator.validate_azure_hierarchy_content
        _call_validator(errors, "INVALID_HIERARCHY", "hierarchy", function, config.hierarchy)
    if not params["needs3DModel"]:
        return
    if not config.scene_config:
        _add(errors, "MISSING_SCENE_CONFIG", "scene_config", "Scene config is required for 3D visualization")
    else:
        _call_validator(errors, "INVALID_SCENE_CONFIG", "scene_config", validator.validate_scene_config_content, l4, config.scene_config, config.hierarchy)
    if not config.scene_glb_uploaded:
        _add(errors, "MISSING_SCENE_GLB", "scene_glb", "Scene GLB file must be uploaded for 3D visualization")


def _validate_event_extensions(config, l2, params, errors) -> None:
    if params["returnFeedbackToDevice"]:
        if not config.event_feedback:
            _add(errors, "MISSING_EVENT_FEEDBACK", "event_feedback", "Event feedback function is required (returnFeedbackToDevice=true)")
        elif l2:
            _validate_function(errors, "INVALID_EVENT_FEEDBACK", "event_feedback", "Event feedback", l2, config.event_feedback)
    if params["useEventChecking"]:
        expected = set(_parse_action_names(config.config_events))
        actions = config.event_actions or {}
        for name in sorted(expected - actions.keys()):
            _add(errors, "MISSING_EVENT_ACTION", f"event_action:{name}", f"Event action function '{name}' is required")
        for name in sorted(actions.keys() - expected):
            _add(errors, "UNEXPECTED_EVENT_ACTION", f"event_action:{name}", f"Event action '{name}' is not referenced by config_events.json")
        if l2:
            for name in sorted(expected & actions.keys()):
                _validate_function(errors, "INVALID_EVENT_ACTION", f"event_action:{name}", f"Event action '{name}'", l2, actions[name])
    if params["triggerNotificationWorkflow"]:
        if not config.state_machine:
            _add(errors, "MISSING_STATE_MACHINE", "state_machine", "State machine is required (triggerNotificationWorkflow=true)")
        elif l2:
            _call_validator(errors, "INVALID_STATE_MACHINE", "state_machine", validator.validate_state_machine_content, _state_machine_filename(l2), config.state_machine)


def _parse_action_names(content: str | None) -> list[str]:
    try:
        events = json.loads(content) if content else []
    except json.JSONDecodeError:
        return []
    names = set()
    if isinstance(events, list):
        for event in events:
            action = event.get("action") if isinstance(event, dict) else None
            if not isinstance(action, dict):
                continue
            names.update(
                value
                for key in ("functionName", "functionNameB")
                if isinstance((value := action.get(key)), str) and value
            )
    return sorted(names)


def _validate_user_config(content, l5, errors) -> None:
    if l5 not in {"aws", "azure"}:
        return
    if not content:
        _add(errors, "MISSING_USER_CONFIG", "user_config", f"User config is required for L5 provider ({l5.upper()})")
        return
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        _add(errors, "INVALID_USER_CONFIG", "user_config", "config_user.json must contain valid JSON")
        return
    if not isinstance(value, dict):
        _add(errors, "INVALID_USER_CONFIG", "user_config", "config_user.json must be a JSON object")
        return
    email = value.get("admin_email", "")
    if not isinstance(email, str):
        _add(errors, "INVALID_USER_CONFIG", "user_config", "admin_email must be a string")
    elif email and not EMAIL_PATTERN.fullmatch(email):
        _add(errors, "INVALID_USER_CONFIG", "user_config", "admin_email must be a valid email address")
    elif email and l5 == "azure" and not email.split("@", 1)[1].lower().endswith(".onmicrosoft.com"):
        _add(errors, "INVALID_USER_CONFIG", "user_config", "Azure admin_email must use the tenant onmicrosoft.com domain")


def _validate_function(errors, code, field, label, provider, content) -> None:
    function = {
        "aws": validator.validate_python_code_aws,
        "azure": validator.validate_python_code_azure,
        "gcp": validator.validate_python_code_google,
    }[provider]
    _call_validator(errors, code, field, function, content, prefix=f"{label}: ")


def _state_machine_filename(provider: str) -> str:
    return {"aws": "aws_step_function.json", "azure": "azure_logic_app.json", "gcp": "google_cloud_workflow.yaml"}[provider]


def _call_validator(errors, code, field, function: Callable, *args, prefix="") -> None:
    try:
        function(*args)
    except ValueError as exc:
        _add(errors, code, field, f"{prefix}{exc}")


def _add(errors, code, field, message) -> None:
    errors.append(ValidationError(code=code, field=field, message=message))
