"""Canonical deployment specification fixtures for Deployer tests."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v1"
)
DEFAULT_PACKAGE_FILES = [
    "config.json",
    "config_iot_devices.json",
    "config_events.json",
    "config_credentials.json",
    "config_providers.json",
]


def load_specification(
    fixture_name: str = "all-aws.json",
    *,
    validity: str = "valid",
) -> dict[str, Any]:
    payload = json.loads(
        (CONTRACT_ROOT / "fixtures" / validity / fixture_name).read_text("utf-8")
    )
    return payload.get("specification", payload)


def provider_config_for_specification(
    specification: dict[str, Any],
) -> dict[str, str]:
    registry = json.loads(
        (CONTRACT_ROOT / "deployment-dimensions.json").read_text("utf-8")
    )
    providers: dict[str, str] = {}
    for slot_id, slot in registry["slots"].items():
        deployer_key = slot["deployer_key"]
        if deployer_key is None:
            continue
        component = next(
            (
                item
                for item in specification.get("components", [])
                if item.get("slot_id") == slot_id
            ),
            None,
        )
        providers[deployer_key] = (
            component.get("provider", "aws")
            if isinstance(component, dict)
            else "aws"
        )
    return providers


def deployment_manifest(
    specification: dict[str, Any] | None = None,
    *,
    providers: dict[str, str] | None = None,
    package_files: list[str] | None = None,
    resource_name: str = "factory",
) -> dict[str, Any]:
    specification = deepcopy(specification or load_specification())
    provider_config = providers or provider_config_for_specification(specification)
    return {
        "manifest_version": "2.0",
        "producer": "test",
        "package": {
            "format": "deployer-project-zip",
            "files": list(package_files or DEFAULT_PACKAGE_FILES),
            "required_files": list(DEFAULT_PACKAGE_FILES),
            "secret_bearing_files": ["config_credentials.json"],
        },
        "twin": {"resource_name": resource_name},
        "providers": dict(provider_config),
        "calculation_run_id": specification["calculation_run_id"],
        "resolved_deployment_specification_digest": specification["digest"],
        "resolved_deployment_specification": specification,
        "credentials": {
            "providers": sorted(set(provider_config.values())),
            "sources": {
                provider: "cloud_connection"
                for provider in sorted(set(provider_config.values()))
            },
            "contains_secret_payloads": False,
        },
    }
