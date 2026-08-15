"""Aggregate deployer configuration validation without provider fallbacks."""

from __future__ import annotations

import ipaddress
import json
import math
import re
from typing import Callable

import src.validator as validator
from src.api.models.complete_validation import (
    DeployerArchitectureProfileRef,
    DeployerCompleteValidation,
    DeployerValidationResponse,
    ValidationError,
)
from src.architecture_profiles.registry import ArchitectureProfileRegistry
from src.provider_capabilities import (
    selections_from_cheapest_path,
    validate_provider_selections,
)
from src.core.executable_topology import (
    UnsupportedErrorHandlingTopologyError,
    ensure_executable_optimization_topology,
)


PROVIDERS = {"aws", "azure", "gcp"}
OPTIONAL_LAYER_PROVIDERS = PROVIDERS | {"none"}
OPTIMIZATION_FLAGS = {
    "needs3DModel",
    "integrateErrorHandling",
    "returnFeedbackToDevice",
    "triggerNotificationWorkflow",
    "useEventChecking",
}
FIVE_LAYER_V2 = ("five-layer-baseline", "2")
SIX_LAYER_EVENTING_V1 = ("six-layer-eventing", "1")
PHASE_8_COMPARISON_PROFILES = {FIVE_LAYER_V2, SIX_LAYER_EVENTING_V1}
V2_FORBIDDEN_OPTIMIZER_FIELDS = {
    "allowGcpSelfHostedL4",
    "allowGcpSelfHostedL5",
    "amountOfActiveEditors",
    "amountOfActiveViewers",
    "apiCallsPerDashboardRefresh",
    "average3DModelSizeInMB",
    "dashboardRefreshesPerHour",
    "entityCount",
    "eventTriggerRate",
    "eventsPerMessage",
    "integrateErrorHandling",
    "needs3DModel",
    "numberOfEventActions",
    "orchestrationActionsPerMessage",
    "returnFeedbackToDevice",
    "triggerNotificationWorkflow",
    "useEventChecking",
}
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
V2_CONDITION_PATTERN = re.compile(r"^\s*(\S+)\s*(<=|>=|==|!=|<|>)\s*(\S+)\s*$")
V2_TYPED_OPERAND_PATTERN = re.compile(
    r"^(?:DOUBLE|INTEGER|STRING|BOOLEAN)\([^()\r\n]*\)$"
)


def validate_complete_configuration(
    config: DeployerCompleteValidation,
) -> DeployerValidationResponse:
    errors: list[ValidationError] = []
    _validate_core(config, errors)
    profile = _validate_architecture_profile_ref(
        config.architecture_profile_ref,
        errors,
    )

    path = config.cheapest_path or {}
    _validate_path_capabilities(path, errors, profile)
    l2 = _provider(path, "L2", PROVIDERS, errors)
    l4 = _provider(path, "L4", OPTIONAL_LAYER_PROVIDERS, errors)
    l5 = _provider(path, "L5", OPTIONAL_LAYER_PROVIDERS, errors)
    params = _optimization_flags(config.optimizer_params, errors)
    _validate_profile_optimizer_fields(
        profile,
        config.optimizer_params,
        errors,
    )
    device_ids = _parse_device_ids(config.config_iot_devices)

    _validate_payloads(config.payloads, device_ids, errors)
    _validate_processors(config.processors or {}, device_ids, l2, profile, errors)
    _validate_hierarchy_and_scene(config, l4, params, profile, errors)
    _validate_event_extensions(config, l2, params, profile, errors)
    _validate_user_config(config.user_config, l4, l5, profile, errors)
    return DeployerValidationResponse(valid=not errors, errors=errors)


def _validate_architecture_profile_ref(
    reference: DeployerArchitectureProfileRef | None,
    errors: list[ValidationError],
) -> tuple[str, str] | None:
    if reference is None:
        return None
    identity = (reference.id, reference.version)
    if identity not in {
        ("five-layer-baseline", "1"),
        *PHASE_8_COMPARISON_PROFILES,
    }:
        _add(
            errors,
            "ARCH_PROFILE_UNAVAILABLE",
            "architecture_profile_ref",
            f"Architecture profile {reference.id}@{reference.version} is unavailable",
        )
        return None
    expected = ArchitectureProfileRegistry(
        profile_id=reference.id,
        profile_version=reference.version,
    ).profile["content_digest"]
    if reference.digest != expected:
        _add(
            errors,
            "ARCH_PROFILE_DIGEST_MISMATCH",
            "architecture_profile_ref.digest",
            "Architecture profile digest does not match the pinned repository profile",
        )
    return identity


def _validate_profile_optimizer_fields(
    profile: tuple[str, str] | None,
    params: dict | None,
    errors: list[ValidationError],
) -> None:
    if profile not in PHASE_8_COMPARISON_PROFILES or not isinstance(params, dict):
        return
    for field in sorted(V2_FORBIDDEN_OPTIMIZER_FIELDS & params.keys()):
        _add(
            errors,
            "FORBIDDEN_PROFILE_FIELD",
            f"optimizer_params.{field}",
            f"{field} is not part of the selected Phase 8 comparison profile",
        )


def _validate_path_capabilities(
    path: dict,
    errors: list[ValidationError],
    profile: tuple[str, str] | None,
) -> None:
    try:
        violations = validate_provider_selections(
            selections_from_cheapest_path(path),
            architecture_profile=profile,
        )
    except ValueError as exc:
        _add(errors, "INVALID_PROVIDER", "cheapest_path", str(exc))
        return
    for violation in violations:
        _add(
            errors,
            "CAPABILITY_UNAVAILABLE",
            f"cheapest_path.{violation.layer}",
            (
                f"{violation.provider.upper()} {violation.layer} is "
                f"{violation.availability.value}: {violation.reason} "
                f"({violation.reason_code})"
            ),
        )


def _validate_core(
    config: DeployerCompleteValidation,
    errors: list[ValidationError],
) -> None:
    name = config.deployer_digital_twin_name or ""
    if not name.strip():
        _add(
            errors,
            "EMPTY_NAME",
            "deployer_digital_twin_name",
            "Digital twin name in config.json is required",
        )
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
        _add(
            errors,
            "MISSING_PROVIDER",
            f"cheapest_path.{layer}",
            f"Provider selection for {layer} is required",
        )
        return None
    if not isinstance(raw, str):
        _add(
            errors,
            "INVALID_PROVIDER",
            f"cheapest_path.{layer}",
            f"Provider selection for {layer} must be a string",
        )
        return None
    normalized = "gcp" if raw.strip().lower() == "google" else raw.strip().lower()
    if normalized not in allowed:
        _add(
            errors,
            "INVALID_PROVIDER",
            f"cheapest_path.{layer}",
            f"Unsupported provider '{raw}' for {layer}",
        )
        return None
    return normalized


def _optimization_flags(
    params: dict | None,
    errors: list[ValidationError],
) -> dict[str, bool]:
    values = params or {}
    result = {}
    try:
        ensure_executable_optimization_topology(values)
    except UnsupportedErrorHandlingTopologyError as exc:
        _add(
            errors,
            exc.code,
            f"optimizer_params.{exc.field}",
            exc.message,
        )
    for name in OPTIMIZATION_FLAGS:
        value = values.get(name, False)
        if not isinstance(value, bool):
            _add(
                errors,
                "INVALID_OPTIMIZER_FLAG",
                f"optimizer_params.{name}",
                f"{name} must be a boolean",
            )
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
        _add(
            errors,
            "UNKNOWN_PAYLOAD_DEVICE",
            "payloads",
            f"Payload references unknown device '{device_id}'",
        )
    for device_id in sorted(configured - payload_ids):
        _add(
            errors,
            "MISSING_DEVICE_PAYLOAD",
            f"payload:{device_id}",
            f"At least one simulator payload for device '{device_id}' is required",
        )


def _validate_processors(
    processors: dict[str, str],
    device_ids: list[str],
    provider: str | None,
    profile: tuple[str, str] | None,
    errors: list[ValidationError],
) -> None:
    if profile in PHASE_8_COMPARISON_PROFILES:
        for device_id in sorted(processors):
            _add(
                errors,
                "UNEXPECTED_PROCESSOR",
                f"processor:{device_id}",
                (
                    f"{profile[0]}@{profile[1]} provides the bounded telemetry "
                    "processor as a profile-owned runtime component"
                ),
            )
        return
    configured = set(device_ids)
    for device_id in sorted(configured - processors.keys()):
        _add(
            errors,
            "MISSING_PROCESSOR",
            f"processor:{device_id}",
            f"Processor for device '{device_id}' is required",
        )
    for device_id in sorted(processors.keys() - configured):
        _add(
            errors,
            "UNEXPECTED_PROCESSOR",
            f"processor:{device_id}",
            f"Processor has no configured device '{device_id}'",
        )
    if provider is None:
        return
    for device_id in sorted(configured & processors.keys()):
        _validate_function(
            errors,
            "INVALID_PROCESSOR",
            f"processor:{device_id}",
            f"Processor for '{device_id}'",
            provider,
            processors[device_id],
        )


def _validate_hierarchy_and_scene(config, l4, params, profile, errors) -> None:
    if profile in PHASE_8_COMPARISON_PROFILES:
        profile_label = f"{profile[0]}@{profile[1]}"
        for field, present in (
            ("hierarchy", bool(config.hierarchy)),
            ("scene_config", bool(config.scene_config)),
            ("scene_glb", config.scene_glb_uploaded),
        ):
            if present:
                _add(
                    errors,
                    "FORBIDDEN_PROFILE_FIELD",
                    field,
                    (
                        f"{profile_label} derives its bounded L4 seed from the "
                        "configured PoC devices and does not accept manual hierarchy "
                        "or scene artifacts"
                    ),
                )
        return
    if l4 not in {"aws", "azure"}:
        return
    if not config.hierarchy:
        _add(
            errors,
            "MISSING_HIERARCHY",
            "hierarchy",
            f"Hierarchy JSON is required for L4 provider ({l4.upper()})",
        )
    else:
        function = (
            validator.validate_aws_hierarchy_content
            if l4 == "aws"
            else validator.validate_azure_hierarchy_content
        )
        _call_validator(
            errors, "INVALID_HIERARCHY", "hierarchy", function, config.hierarchy
        )
    if not params["needs3DModel"]:
        return
    if not config.scene_config:
        _add(
            errors,
            "MISSING_SCENE_CONFIG",
            "scene_config",
            "Scene config is required for 3D visualization",
        )
    else:
        _call_validator(
            errors,
            "INVALID_SCENE_CONFIG",
            "scene_config",
            validator.validate_scene_config_content,
            l4,
            config.scene_config,
            config.hierarchy,
        )
    if not config.scene_glb_uploaded:
        _add(
            errors,
            "MISSING_SCENE_GLB",
            "scene_glb",
            "Scene GLB file must be uploaded for 3D visualization",
        )


def _validate_event_extensions(config, l2, params, profile, errors) -> None:
    if profile in PHASE_8_COMPARISON_PROFILES:
        _validate_mandatory_v2_event_extensions(config, l2, profile, errors)
        return
    if params["returnFeedbackToDevice"]:
        if not config.event_feedback:
            _add(
                errors,
                "MISSING_EVENT_FEEDBACK",
                "event_feedback",
                "Event feedback function is required (returnFeedbackToDevice=true)",
            )
        elif l2:
            _validate_function(
                errors,
                "INVALID_EVENT_FEEDBACK",
                "event_feedback",
                "Event feedback",
                l2,
                config.event_feedback,
            )
    if params["useEventChecking"]:
        expected = set(_parse_action_names(config.config_events))
        actions = config.event_actions or {}
        for name in sorted(expected - actions.keys()):
            _add(
                errors,
                "MISSING_EVENT_ACTION",
                f"event_action:{name}",
                f"Event action function '{name}' is required",
            )
        for name in sorted(actions.keys() - expected):
            _add(
                errors,
                "UNEXPECTED_EVENT_ACTION",
                f"event_action:{name}",
                f"Event action '{name}' is not referenced by config_events.json",
            )
        if l2:
            for name in sorted(expected & actions.keys()):
                _validate_function(
                    errors,
                    "INVALID_EVENT_ACTION",
                    f"event_action:{name}",
                    f"Event action '{name}'",
                    l2,
                    actions[name],
                )
    if params["triggerNotificationWorkflow"]:
        if not config.state_machine:
            _add(
                errors,
                "MISSING_STATE_MACHINE",
                "state_machine",
                "State machine is required (triggerNotificationWorkflow=true)",
            )
        elif l2:
            _call_validator(
                errors,
                "INVALID_STATE_MACHINE",
                "state_machine",
                validator.validate_state_machine_content,
                _state_machine_filename(l2),
                config.state_machine,
            )


def _validate_mandatory_v2_event_extensions(config, l2, profile, errors) -> None:
    del l2
    profile_label = f"{profile[0]}@{profile[1]}"
    _validate_v2_rules(config.config_events, profile_label, errors)
    for name in sorted((config.event_actions or {}).keys()):
        _add(
            errors,
            "UNEXPECTED_EVENT_ACTION",
            f"event_action:{name}",
            (
                f"{profile_label} treats functionName/functionNameB as "
                "logical action IDs and uses its fixed synthetic PoC action and "
                "notification boundaries"
            ),
        )
    if config.event_feedback:
        _add(
            errors,
            "UNEXPECTED_EVENT_FEEDBACK",
            "event_feedback",
            (
                f"{profile_label} uses its provider-owned device command "
                "adapter instead of an uploaded event feedback function"
            ),
        )
    if config.state_machine:
        _add(
            errors,
            "UNEXPECTED_STATE_MACHINE",
            "state_machine",
            (
                f"{profile_label} uses its fixed provider workflow instead "
                "of an uploaded state machine"
            ),
        )


def _validate_v2_rules(content: str | None, profile_label: str, errors) -> None:
    try:
        rules = json.loads(content) if content else []
    except json.JSONDecodeError:
        return
    if not isinstance(rules, list):
        return
    if not 1 <= len(rules) <= 100:
        _add(
            errors,
            "INVALID_V2_RULE_SET",
            "config_events",
            f"{profile_label} requires between 1 and 100 typed rules",
        )
        return
    seen_rule_ids = set()
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        condition = rule.get("condition")
        match = (
            V2_CONDITION_PATTERN.fullmatch(condition)
            if isinstance(condition, str)
            else None
        )
        operands = (match.group(1), match.group(3)) if match else ()
        typed_operands = [
            operand
            for operand in operands
            if V2_TYPED_OPERAND_PATTERN.fullmatch(operand)
        ]
        if (
            not match
            or not typed_operands
            or not all(_valid_v2_typed_operand(operand) for operand in typed_operands)
        ):
            _add(
                errors,
                "INVALID_V2_TYPED_RULE",
                f"config_events[{index}].condition",
                (
                    f"{profile_label} conditions require the bounded "
                    "typed operand syntax DOUBLE(...), INTEGER(...), STRING(...), "
                    "or BOOLEAN(...)"
                ),
            )
        rule_id = rule.get("rule_id")
        if rule_id is None:
            continue
        if not isinstance(rule_id, str) or not rule_id or rule_id in seen_rule_ids:
            _add(
                errors,
                "INVALID_V2_RULE_ID",
                f"config_events[{index}].rule_id",
                f"{profile_label} explicit rule IDs must be non-empty and unique",
            )
        else:
            seen_rule_ids.add(rule_id)


def _valid_v2_typed_operand(token: str) -> bool:
    kind, raw = token.split("(", 1)
    raw = raw[:-1]
    try:
        if kind == "DOUBLE":
            return math.isfinite(float(raw))
        if kind == "INTEGER":
            int(raw)
            return True
    except ValueError:
        return False
    if kind == "BOOLEAN":
        return raw.lower() in {"true", "false"}
    return kind == "STRING"


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


def _validate_user_config(content, l4, l5, profile, errors) -> None:
    phase8 = profile in PHASE_8_COMPARISON_PROFILES
    if not phase8 and l5 not in {"aws", "azure"}:
        return
    if not content:
        _add(
            errors,
            "MISSING_USER_CONFIG",
            "user_config",
            (
                "Phase 8 comparison profiles require the platform identity used "
                "for usable L4/L5 access"
                if phase8
                else f"User config is required for L5 provider ({l5.upper()})"
            ),
        )
        return
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        _add(
            errors,
            "INVALID_USER_CONFIG",
            "user_config",
            "config_user.json must contain valid JSON",
        )
        return
    if not isinstance(value, dict):
        _add(
            errors,
            "INVALID_USER_CONFIG",
            "user_config",
            "config_user.json must be a JSON object",
        )
        return
    email = value.get("admin_email", "")
    if not isinstance(email, str):
        _add(
            errors, "INVALID_USER_CONFIG", "user_config", "admin_email must be a string"
        )
    elif email and not EMAIL_PATTERN.fullmatch(email):
        _add(
            errors,
            "INVALID_USER_CONFIG",
            "user_config",
            "admin_email must be a valid email address",
        )
    elif (
        email
        and not phase8
        and l5 == "azure"
        and not email.split("@", 1)[1].lower().endswith(".onmicrosoft.com")
    ):
        _add(
            errors,
            "INVALID_USER_CONFIG",
            "user_config",
            "Azure admin_email must use the tenant onmicrosoft.com domain",
        )
    if not phase8:
        aws_intent = value.get("aws_layer_access_principal_intent", "existing")
        if aws_intent not in {"existing", "invite_builtin"}:
            _add(
                errors,
                "INVALID_USER_CONFIG",
                "user_config.aws_layer_access_principal_intent",
                "aws_layer_access_principal_intent must be existing or invite_builtin",
            )
        return

    for field in ("admin_email", "admin_first_name", "admin_last_name"):
        field_value = value.get(field)
        if not isinstance(field_value, str) or not field_value.strip():
            _add(
                errors,
                "INVALID_USER_CONFIG",
                f"user_config.{field}",
                f"{field} must be a non-empty string for Phase 8 L4/L5 access",
            )

    selected = {provider for provider in (l4, l5) if provider in PROVIDERS}
    if "aws" in selected:
        aws_intent = value.get("aws_layer_access_principal_intent")
        if aws_intent not in {"existing", "invite_builtin"}:
            _add(
                errors,
                "INVALID_USER_CONFIG",
                "user_config.aws_layer_access_principal_intent",
                "AWS L4/L5 requires explicit existing or invite_builtin principal intent",
            )

    if "azure" in selected:
        object_id = value.get("azure_principal_object_id")
        if not isinstance(object_id, str) or not UUID_PATTERN.fullmatch(object_id):
            _add(
                errors,
                "INVALID_USER_CONFIG",
                "user_config.azure_principal_object_id",
                "Azure L4/L5 requires an existing Entra principal object ID UUID",
            )
        label = value.get("azure_principal_label")
        if not isinstance(label, str) or not label.strip():
            _add(
                errors,
                "INVALID_USER_CONFIG",
                "user_config.azure_principal_label",
                "Azure L4/L5 requires a non-empty Entra principal label or UPN",
            )

    if l5 == "gcp":
        cidrs = value.get("gcp_grafana_source_cidrs")
        if not isinstance(cidrs, list) or not cidrs:
            _add(
                errors,
                "INVALID_USER_CONFIG",
                "user_config.gcp_grafana_source_cidrs",
                "GCP L5 requires at least one bounded Grafana source CIDR",
            )
        elif not all(_valid_bounded_cidr(cidr) for cidr in cidrs):
            _add(
                errors,
                "INVALID_USER_CONFIG",
                "user_config.gcp_grafana_source_cidrs",
                "GCP Grafana source CIDRs must be valid and must not be wildcard routes",
            )


def _valid_bounded_cidr(value: object) -> bool:
    if not isinstance(value, str) or value in {"0.0.0.0/0", "::/0"}:
        return False
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError:
        return False
    return True


def validate_phase8_user_config_content(
    content: str,
    *,
    l4_provider: str | None,
    l5_provider: str | None,
    profile: tuple[str, str],
) -> None:
    """Validate one user-config editor payload with its trusted profile context."""
    if profile not in PHASE_8_COMPARISON_PROFILES:
        raise ValueError("Architecture profile is not an active Phase 8 profile")
    errors: list[ValidationError] = []
    _validate_user_config(content, l4_provider, l5_provider, profile, errors)
    if errors:
        raise ValueError(
            "; ".join(f"{error.field}: {error.message}" for error in errors)
        )


def _validate_function(errors, code, field, label, provider, content) -> None:
    function = {
        "aws": validator.validate_python_code_aws,
        "azure": validator.validate_python_code_azure,
        "gcp": validator.validate_python_code_google,
    }[provider]
    _call_validator(errors, code, field, function, content, prefix=f"{label}: ")


def _state_machine_filename(provider: str) -> str:
    return {
        "aws": "aws_step_function.json",
        "azure": "azure_logic_app.json",
        "gcp": "google_cloud_workflow.yaml",
    }[provider]


def _call_validator(errors, code, field, function: Callable, *args, prefix="") -> None:
    try:
        function(*args)
    except ValueError as exc:
        _add(errors, code, field, f"{prefix}{exc}")


def _add(errors, code, field, message) -> None:
    errors.append(ValidationError(code=code, field=field, message=message))
