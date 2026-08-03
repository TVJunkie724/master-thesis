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
    """Deployment manifest bound to validated immutable execution contracts."""

    manifest: Mapping[str, Any]
    specification: ValidatedResolvedDeploymentSpecification
    provider_by_slot: Mapping[str, str]
    manifest_version: str
    architecture: Mapping[str, Any] | None = None
