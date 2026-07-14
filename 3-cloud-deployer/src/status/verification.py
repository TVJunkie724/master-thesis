"""Structured L0-L5 infrastructure verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from src.core.factory import create_context
from src.core.observability import redact_sensitive
from src.status.metadata import check_function_artifacts
from src.status.sdk import check_sdk_managed
from src.status.terraform import check_terraform_state

CheckStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class InfrastructureCheck:
    name: str
    status: CheckStatus
    provider: str = ""
    detail: str = ""
    layer: str = ""


def _check(
    name: str,
    status: CheckStatus,
    provider: str = "",
    detail: str = "",
    layer: str = "",
) -> InfrastructureCheck:
    return InfrastructureCheck(
        name=name,
        status=status,
        provider=provider.upper(),
        detail=redact_sensitive(detail),
        layer=layer,
    )


def _state_check(
    state: dict,
    path: tuple[str, ...],
    *,
    name: str,
    provider: str,
    layer: str,
) -> InfrastructureCheck:
    if not provider or provider == "none":
        return _check(name, "skip", provider, "Layer not configured", layer)
    if state.get("status") == "error":
        return _check(name, "skip", provider, "Terraform state unavailable", layer)
    current = state
    for key in path:
        current = current.get(key, {})
    if current.get("deployed"):
        return _check(
            name,
            "pass",
            provider,
            f"{len(current.get('resources', []))} state resource(s)",
            layer,
        )
    return _check(name, "fail", provider, "Not found in Terraform state", layer)


def _sdk_check(
    component: dict,
    *,
    name: str,
    layer: str,
    skip_when_unconfigured: bool = True,
) -> InfrastructureCheck:
    status = component.get("status")
    provider = component.get("provider", "")
    if status == "deployed":
        return _check(name, "pass", provider, "Provider API confirmed", layer)
    if status == "not_configured" and skip_when_unconfigured:
        return _check(name, "skip", provider, "Layer not configured", layer)
    return _check(
        name,
        "fail",
        provider,
        component.get("message") or "Provider API did not confirm resource",
        layer,
    )


def verify_infrastructure(project_name: str, provider: str | None = None) -> dict:
    """Combine independent local-state, metadata, and provider evidence."""
    del provider  # Layer ownership comes from the canonical project config.
    checks: list[InfrastructureCheck] = []
    state = check_terraform_state(project_name)
    if state.get("status") == "error":
        checks.append(
            _check(
                "Terraform state",
                "fail",
                detail=state.get("error", "State check failed"),
                layer="L0",
            )
        )
    elif state.get("status") == "not_deployed":
        checks.append(
            _check("Terraform state", "fail", detail="No deployment state", layer="L0")
        )
    else:
        checks.append(
            _check(
                "Terraform state",
                "pass",
                detail=f"{state.get('total_resources', 0)} resources",
                layer="L0",
            )
        )

    try:
        context = create_context(project_name)
        config = context.config
    except Exception as exc:
        checks.append(
            _check(
                "Project configuration",
                "fail",
                detail=redact_sensitive(exc),
                layer="L0",
            )
        )
        return _result(checks)

    providers = config.providers
    sdk = check_sdk_managed(project_name, context=context)
    checks.extend(
        [
            _state_check(
                state,
                ("l1",),
                name="IoT infrastructure",
                provider=providers.get("layer_1_provider", ""),
                layer="L1",
            ),
            _sdk_check(
                sdk.get("iot_devices", {}),
                name="IoT devices",
                layer="L1",
            )
            if config.iot_devices
            else _check(
                "IoT devices",
                "skip",
                providers.get("layer_1_provider", ""),
                "No devices configured",
                "L1",
            ),
            _state_check(
                state,
                ("l2",),
                name="Processing infrastructure",
                provider=providers.get("layer_2_provider", ""),
                layer="L2",
            ),
            _state_check(
                state,
                ("l3", "hot"),
                name="Hot storage",
                provider=providers.get("layer_3_hot_provider", ""),
                layer="L3",
            ),
            _state_check(
                state,
                ("l3", "cold"),
                name="Cold storage",
                provider=providers.get("layer_3_cold_provider", ""),
                layer="L3",
            ),
            _state_check(
                state,
                ("l3", "archive"),
                name="Archive storage",
                provider=providers.get("layer_3_archive_provider", ""),
                layer="L3",
            ),
            _state_check(
                state,
                ("l4",),
                name="Digital twin infrastructure",
                provider=providers.get("layer_4_provider", ""),
                layer="L4",
            ),
            _sdk_check(
                sdk.get("twin_management", {}),
                name="Digital twin resources",
                layer="L4",
            ),
            _state_check(
                state,
                ("l5",),
                name="Visualization infrastructure",
                provider=providers.get("layer_5_provider", ""),
                layer="L5",
            ),
            _sdk_check(
                sdk.get("visualization", {}),
                name="Visualization workspace",
                layer="L5",
            ),
        ]
    )

    metadata = check_function_artifacts(project_name)
    if metadata["functions"]:
        deployed = sum(
            1 for item in metadata["functions"].values() if item["deployed"]
        )
        total = len(metadata["functions"])
        checks.append(
            _check(
                "User functions",
                "pass" if deployed == total else "fail",
                providers.get("layer_2_provider", ""),
                f"{deployed}/{total} current packages deployed",
                "L2",
            )
        )
    return _result(checks)


def _result(checks: list[InfrastructureCheck]) -> dict:
    payload = [asdict(check) for check in checks]
    passed = sum(check.status == "pass" for check in checks)
    failed = sum(check.status == "fail" for check in checks)
    skipped = sum(check.status == "skip" for check in checks)
    return {
        "checks": payload,
        "summary": {
            "pass_count": passed,
            "fail_count": failed,
            "skip_count": skipped,
            "total": len(checks),
            "healthy": failed == 0,
        },
    }
