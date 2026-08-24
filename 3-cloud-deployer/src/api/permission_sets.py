"""Versioned provider permission-set contract for deployment identities."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
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
        raise ValueError(
            f"Active {provider} deployment permission pack is malformed"
        )
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
