"""Read-only Phase 8.3 profile/catalog summaries for future Management APIs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.services.architecture_contract_service import ArchitectureContractService


DEFINITIONS_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "definitions"
)


class ProviderProfileSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    supported: bool
    component_mappings: int
    edge_mappings: int
    missing_capability_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]


class ArchitectureCatalogSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str
    profile_version: str
    profile_digest: str
    responsibility_count: int
    logical_component_count: int
    logical_edge_count: int
    optimization_slot_count: int
    functional_completeness_rule_count: int
    extension_slot_ids: tuple[str, ...]
    catalog_id: str
    catalog_version: str
    catalog_digest: str
    deployment_component_count: int
    edge_implementation_count: int
    package_artifact_count: int
    providers: tuple[ProviderProfileSummary, ...]
    runtime_activation: str = "dark-read-only"


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Architecture definition must contain an object")
    return payload


class ArchitectureCatalogReadService:
    """Expose a typed internal projection without routes or persistence."""

    @staticmethod
    def read_summary() -> ArchitectureCatalogSummary:
        profile = _read(
            DEFINITIONS_ROOT
            / "profiles"
            / "five-layer-baseline"
            / "1"
            / "profile.json"
        )
        catalog = _read(
            DEFINITIONS_ROOT
            / "component-catalogs"
            / "baseline"
            / "1"
            / "catalog.json"
        )
        providers = tuple(
            _read(
                DEFINITIONS_ROOT
                / "provider-implementations"
                / "five-layer-baseline"
                / "1"
                / provider
                / "1.json"
            )
            for provider in ("aws", "azure", "gcp")
        )
        documents = (profile, *providers, catalog)
        ArchitectureContractService.read_bundle(documents)
        summaries = tuple(
            ProviderProfileSummary(
                provider=document["provider"],
                supported=document["supported"],
                component_mappings=len(document["component_mappings"]),
                edge_mappings=len(document["edge_mappings"]),
                missing_capability_ids=tuple(
                    document["capability_claims"]["missing_capability_ids"]
                ),
                reason_codes=tuple(
                    reason["reason_code"]
                    for reason in document["unsupported_reasons"]
                ),
            )
            for document in providers
        )
        return ArchitectureCatalogSummary(
            profile_id=profile["profile_id"],
            profile_version=profile["profile_version"],
            profile_digest=profile["content_digest"],
            responsibility_count=len(profile["responsibilities"]),
            logical_component_count=len(profile["components"]),
            logical_edge_count=len(profile["edges"]),
            optimization_slot_count=len(profile["optimization_slot_ids"]),
            functional_completeness_rule_count=len(
                profile["functional_completeness_rules"]
            ),
            extension_slot_ids=tuple(
                slot["slot_id"] for slot in profile["extension_slots"]
            ),
            catalog_id=catalog["catalog_id"],
            catalog_version=catalog["catalog_version"],
            catalog_digest=catalog["content_digest"],
            deployment_component_count=len(catalog["components"]),
            edge_implementation_count=len(catalog["edge_implementations"]),
            package_artifact_count=len(catalog["package_artifacts"]),
            providers=summaries,
        )
