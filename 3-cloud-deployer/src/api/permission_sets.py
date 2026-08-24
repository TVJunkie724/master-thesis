"""Versioned provider permission-set contract for deployment identities."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Literal

ProviderName = Literal["aws", "azure", "gcp"]
PermissionSetStatus = Literal["matched", "missing", "outdated"]

ACTIVE_PERMISSION_SET_VERSION = "thesis-demo-v2"
DEPLOYMENT_PACK_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "cloud-bootstrap"
    / "v1"
    / "deployment-packs"
)
GCP_PHASE8_API_BASELINE_PATH = (
    DEPLOYMENT_PACK_ROOT.parent / "gcp-phase8-api-baseline.json"
)


@dataclass(frozen=True)
class PermissionSetComparison:
    provider: ProviderName
    expected_version: str
    supplied_version: str | None
    status: PermissionSetStatus

    @property
    def matches(self) -> bool:
        return self.status == "matched"


def active_permission_set_version(provider: ProviderName) -> str:
    """Return the active deployment permission-set version for a provider."""
    if provider not in {"aws", "azure", "gcp"}:
        raise ValueError(f"Unsupported provider: {provider}")
    return ACTIVE_PERMISSION_SET_VERSION


def active_deployment_permission_pack(provider: ProviderName) -> dict:
    """Load a defensive copy of the synchronized active provider pack."""

    active_permission_set_version(provider)
    path = DEPLOYMENT_PACK_ROOT / f"{provider}.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Active {provider} deployment permission pack is unavailable"
        ) from exc
    if (
        not isinstance(document, dict)
        or document.get("provider") != provider
        or document.get("permission_set_version") != ACTIVE_PERMISSION_SET_VERSION
        or document.get("status") != "frozen_offline_contract"
    ):
        raise ValueError(f"Active {provider} deployment permission pack is malformed")
    return deepcopy(document)


def deployment_permission_pack_for_version(
    provider: ProviderName,
    supplied_version: str | None,
) -> dict | None:
    """Return the active pack only when the caller explicitly selects it.

    Missing and historical versions retain the legacy checker matrices for
    compatibility; normalized preflight rejects them through the version gate.
    """

    if supplied_version != ACTIVE_PERMISSION_SET_VERSION:
        return None
    return active_deployment_permission_pack(provider)


def active_gcp_phase8_api_baseline() -> dict:
    """Load the synchronized fixed API baseline for active GCP profiles."""

    try:
        document = json.loads(GCP_PHASE8_API_BASELINE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Active GCP Phase 8 API baseline is unavailable") from exc
    if not isinstance(document, dict):
        raise ValueError("Active GCP Phase 8 API baseline is malformed")
    services = document.get("services")
    prerequisites = document.get("bootstrap_prerequisite_services")
    if (
        document.get("schema_version") != "gcp-phase8-api-baseline.v1"
        or document.get("baseline_id") != "gcp.phase8-api-baseline.v1"
        or document.get("provider") != "gcp"
        or document.get("status") != "frozen_offline_contract"
        or document.get("profiles")
        != ["five-layer-baseline@2", "six-layer-eventing@1"]
        or document.get("owner") != "bootstrap.gcp.admin-v3"
        or document.get("target_mode") != "existing_project"
        or document.get("region") != "europe-west1"
        or not isinstance(services, list)
        or any(not isinstance(service, str) for service in services)
        or services != sorted(set(services))
        or not 1 <= len(services) <= 20
        or any(
            re.fullmatch(r"[a-z0-9-]+\.googleapis\.com", service) is None
            for service in services
        )
        or not isinstance(prerequisites, list)
        or prerequisites
        != [
            "cloudresourcemanager.googleapis.com",
            "iam.googleapis.com",
            "serviceusage.googleapis.com",
        ]
        or document.get("retain_enabled") is not True
    ):
        raise ValueError("Active GCP Phase 8 API baseline is malformed")
    return deepcopy(document)


def compare_permission_set_version(
    provider: ProviderName,
    supplied_version: str | None,
) -> PermissionSetComparison:
    """Compare request/CloudConnection metadata with the active baseline."""
    expected = active_permission_set_version(provider)
    if not supplied_version:
        status: PermissionSetStatus = "missing"
    elif supplied_version == expected:
        status = "matched"
    else:
        status = "outdated"
    return PermissionSetComparison(
        provider=provider,
        expected_version=expected,
        supplied_version=supplied_version,
        status=status,
    )
