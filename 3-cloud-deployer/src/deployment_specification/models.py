"""Immutable validated deployment specification models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ValidatedResolvedDeploymentSpecification:
    """Canonical v1 specification accepted by the Deployer."""

    specification: Mapping[str, Any]
    canonical_json: str
    digest: str
    schema_version: str


@dataclass(frozen=True, slots=True)
class ValidatedDeploymentManifest:
    """Manifest v2 bound to one validated specification and provider path."""

    manifest: Mapping[str, Any]
    specification: ValidatedResolvedDeploymentSpecification
    provider_by_slot: Mapping[str, str]
