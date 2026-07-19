"""Non-ranking capability projection for Phase 8.3 provider definitions."""

from __future__ import annotations

from dataclasses import dataclass

from .registry import ArchitectureProfileRegistry


@dataclass(frozen=True)
class CapabilityReport:
    provider: str
    supported: bool
    mapped_component_ids: tuple[str, ...]
    mapped_edge_ids: tuple[str, ...]
    provided_capability_ids: tuple[str, ...]
    missing_capability_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


def resolve_provider_capabilities(
    provider: str,
    *,
    registry: ArchitectureProfileRegistry | None = None,
) -> CapabilityReport:
    """Return declared evidence only; ranking remains owned by Phase 8.5."""
    profile = (registry or ArchitectureProfileRegistry()).provider(provider)
    claims = profile["capability_claims"]
    return CapabilityReport(
        provider=provider,
        supported=bool(profile["supported"]),
        mapped_component_ids=tuple(
            item["component_id"] for item in profile["component_mappings"]
        ),
        mapped_edge_ids=tuple(item["edge_id"] for item in profile["edge_mappings"]),
        provided_capability_ids=tuple(claims["provided_capability_ids"]),
        missing_capability_ids=tuple(claims["missing_capability_ids"]),
        reason_codes=tuple(
            item["reason_code"] for item in profile["unsupported_reasons"]
        ),
    )
