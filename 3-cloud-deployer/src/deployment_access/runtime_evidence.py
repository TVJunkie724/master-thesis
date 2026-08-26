"""Typed, internal proof that selected Layer Access gates completed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class DeploymentAccessRuntimeEvidenceError(ValueError):
    """Raised when provider runtime proof is incomplete or inconsistent."""


OUTPUT_KEYS = {
    ("l4", "aws"): "aws_component_twin_state_output",
    ("l4", "azure"): "azure_component_twin_state_output",
    ("l4", "gcp"): "gcp_component_twin_state_output",
    ("l5", "aws"): "aws_component_visualization_output",
    ("l5", "azure"): "azure_component_visualization_output",
    ("l5", "gcp"): "gcp_component_visualization_output",
}

INTERNAL_EVIDENCE_KEYS = frozenset(
    {
        "resource_ref",
        "access_binding_refs",
        "artifact_refs",
        "content_revision",
        "data_probe_revision",
    }
)
SUPPORTED_DEPLOYMENT_ACCESS_PROFILES = frozenset({("six-layer-eventing", "1")})


@dataclass(frozen=True)
class SurfaceRuntimeEvidence:
    """Secret-free provider proof captured only after every runtime gate passes."""

    layer: str
    provider: str
    resource_ref: str
    access_binding_refs: tuple[str, ...]
    artifact_refs: tuple[str, ...]
    content_revision: str
    data_probe_revision: str


@dataclass(frozen=True)
class DeploymentAccessRuntimeEvidence:
    """Exact L4/L5 proof for one successful active-profile deployment."""

    surfaces: tuple[SurfaceRuntimeEvidence, SurfaceRuntimeEvidence]

    def __post_init__(self) -> None:
        coordinates = [(item.layer, item.provider) for item in self.surfaces]
        if len(coordinates) != 2 or {layer for layer, _provider in coordinates} != {
            "l4",
            "l5",
        }:
            raise DeploymentAccessRuntimeEvidenceError(
                "Runtime evidence must contain exactly one L4 and one L5 surface"
            )
        if any(provider not in {"aws", "azure", "gcp"} for _, provider in coordinates):
            raise DeploymentAccessRuntimeEvidenceError(
                "Runtime evidence contains an unsupported provider"
            )

    def surface(self, layer: str, provider: str) -> SurfaceRuntimeEvidence | None:
        return next(
            (
                item
                for item in self.surfaces
                if item.layer == layer and item.provider == provider
            ),
            None,
        )


def _provider(context: Any, layer: str) -> str:
    value = str(context.config.get_provider_for_layer(layer)).strip().lower()
    normalized = "gcp" if value == "google" else value
    if normalized not in {"aws", "azure", "gcp"}:
        raise DeploymentAccessRuntimeEvidenceError(
            f"Unsupported Layer Access provider {value!r}"
        )
    return normalized


def surface_output_evidence(
    layer: str,
    provider: str,
    outputs: dict[str, Any],
) -> SurfaceRuntimeEvidence:
    """Validate and type one Terraform-internal evidence object."""

    output_key = OUTPUT_KEYS[(layer, provider)]
    bundle = outputs.get(output_key)
    if not isinstance(bundle, dict):
        raise DeploymentAccessRuntimeEvidenceError(
            f"Required Layer Access output {output_key} is absent"
        )
    internal = bundle.get("internal_evidence")
    if not isinstance(internal, dict) or set(internal) != INTERNAL_EVIDENCE_KEYS:
        raise DeploymentAccessRuntimeEvidenceError(
            f"Layer Access output {output_key} has invalid internal evidence"
        )

    def text(key: str) -> str:
        value = internal.get(key)
        if not isinstance(value, str) or not value.strip():
            raise DeploymentAccessRuntimeEvidenceError(
                f"Layer Access internal evidence {key} must be non-empty text"
            )
        return value.strip()

    def references(key: str) -> tuple[str, ...]:
        value = internal.get(key)
        if (
            not isinstance(value, list)
            or not value
            or any(not isinstance(item, str) or not item.strip() for item in value)
        ):
            raise DeploymentAccessRuntimeEvidenceError(
                f"Layer Access internal evidence {key} must contain references"
            )
        normalized = tuple(item.strip() for item in value)
        if len(set(normalized)) != len(normalized):
            raise DeploymentAccessRuntimeEvidenceError(
                f"Layer Access internal evidence {key} contains duplicates"
            )
        return normalized

    return SurfaceRuntimeEvidence(
        layer=layer,
        provider=provider,
        resource_ref=text("resource_ref"),
        access_binding_refs=references("access_binding_refs"),
        artifact_refs=references("artifact_refs"),
        content_revision=text("content_revision"),
        data_probe_revision=text("data_probe_revision"),
    )


def collect_deployment_access_runtime_evidence(
    context: Any,
    outputs: dict[str, Any],
) -> DeploymentAccessRuntimeEvidence | None:
    """Capture ready proof after provider post-deployment gates have succeeded."""

    graph = getattr(context, "resolved_deployment_graph", None)
    profile_ref = getattr(graph, "profile_ref", {}) if graph is not None else {}
    if (
        profile_ref.get("id"),
        str(profile_ref.get("version")),
    ) not in SUPPORTED_DEPLOYMENT_ACCESS_PROFILES:
        return None
    if not isinstance(outputs, dict):
        raise DeploymentAccessRuntimeEvidenceError(
            "Terraform outputs must be an object"
        )
    return DeploymentAccessRuntimeEvidence(
        surfaces=(
            surface_output_evidence("l4", _provider(context, "4"), outputs),
            surface_output_evidence("l5", _provider(context, "5"), outputs),
        )
    )
