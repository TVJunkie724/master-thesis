"""Deterministic resolved-deployment fixtures for Management API tests."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "contracts"
    / "generated"
    / "resolved-deployment-specification"
    / "v1"
)
SLOT_ORDER = (
    "l1_ingestion",
    "l2_processing",
    "l3_hot_storage",
    "l3_cool_storage",
    "l3_archive_storage",
    "l4_twin_state",
    "l5_visualization",
)
RESULT_PATH = {
    "l1_ingestion": ("L1",),
    "l2_processing": ("L2",),
    "l3_hot_storage": ("L3", "Hot"),
    "l3_cool_storage": ("L3", "Cool"),
    "l3_archive_storage": ("L3", "Archive"),
    "l4_twin_state": ("L4",),
    "l5_visualization": ("L5",),
}


def build_resolved_deployment_specification(
    result: dict,
    *,
    calculation_run_id: str,
    pricing_catalogs: dict,
) -> dict:
    registry = _fixture_contract()
    profile = result["optimizationProfile"]
    strategy = result["calculationStrategy"]
    provider_by_slot = {
        slot_id: _nested(result["calculationResult"], path).lower()
        for slot_id, path in RESULT_PATH.items()
    }
    components = []
    for slot_id in SLOT_ORDER:
        provider = provider_by_slot[slot_id]
        requirement = registry["slot_requirements"][slot_id][provider]
        for component_id in requirement["required_components"]:
            components.append(
                _component(
                    component_id,
                    registry=registry,
                    pricing_catalogs=pricing_catalogs,
                    formula_set_id=strategy["formula_set_id"],
                    workload_contract_id=strategy["workload_contract_id"],
                )
            )

    glue_by_provider = registry["cross_cloud_glue_policy"][
        "component_by_provider"
    ]
    required_glue = set()
    for boundary in registry["cross_cloud_glue_policy"]["boundaries"]:
        source = provider_by_slot[boundary["source_slot"]]
        target = provider_by_slot[boundary["target_slot"]]
        if source != target:
            required_glue.add(provider_by_slot[boundary["receiver_slot"]])
    for provider in ("aws", "azure", "gcp"):
        if provider in required_glue:
            components.append(
                _component(
                    glue_by_provider[provider],
                    registry=registry,
                    pricing_catalogs=pricing_catalogs,
                    formula_set_id=strategy["formula_set_id"],
                    workload_contract_id=strategy["workload_contract_id"],
                )
            )

    specification = {
        "schema_version": "resolved-deployment-specification.v1",
        "calculation_run_id": calculation_run_id,
        "architecture_profile": {
            "profile_id": "five-layer-baseline",
            "profile_version": "1",
        },
        "optimization_context": {
            "optimization_profile_id": result["optimization_profile_id"],
            "optimization_profile_version": profile["profile_version"],
            "calculation_strategy_id": result["calculation_strategy_id"],
            "formula_set_id": strategy["formula_set_id"],
            "workload_contract_id": strategy["workload_contract_id"],
            "pricing_registry_version": profile["pricing_registry_version"],
            "catalog_references": {
                provider: {
                    "snapshot_id": reference["snapshotId"],
                    "pricing_region": reference["pricingRegion"],
                    "content_digest": reference["contentDigest"],
                }
                for provider, reference in pricing_catalogs["catalogs"].items()
            },
        },
        "currency": "USD",
        "components": components,
    }
    specification["digest"] = _digest(specification)
    return specification


@lru_cache(maxsize=1)
def _fixture_contract() -> dict:
    return json.loads(
        (CONTRACT_ROOT / "deployment-dimensions.json").read_text("utf-8")
    )


def _component(
    component_id: str,
    *,
    registry: dict,
    pricing_catalogs: dict,
    formula_set_id: str,
    workload_contract_id: str,
) -> dict:
    definition = registry["components"][component_id]
    provider = definition["provider"]
    dimensions = []
    for dimension_id, dimension_definition in definition["dimensions"].items():
        value = _dimension_value(dimension_definition)
        resolution = registry["dimension_resolution"][dimension_id]
        if dimension_definition["classification"] == "account_scope":
            evidence_reference = f"provider_context:{provider}"
        elif resolution == "baseline_invariant":
            evidence_reference = (
                f"deployment_registry:{registry['registry_version']}"
            )
        elif resolution == "formula_input":
            evidence_reference = (
                f"workload_contract:{workload_contract_id}"
            )
        else:
            snapshot_id = pricing_catalogs["catalogs"][provider][
                "snapshotId"
            ]
            evidence_reference = f"catalog:{snapshot_id}"
        dimension = {
            "dimension_id": dimension_id,
            "classification": dimension_definition["classification"],
            "value": value,
            "formula_reference": f"formula_set:{formula_set_id}",
            "evidence_reference": evidence_reference,
        }
        unit = registry["dimension_units"].get(dimension_id)
        if unit is not None:
            dimension["unit"] = unit
        terraform_target = dimension_definition.get("terraform_target")
        if terraform_target is not None:
            dimension["terraform_target"] = terraform_target
        dimensions.append(dimension)
    return {
        "component_id": component_id,
        "slot_id": definition["slot_id"],
        "provider": provider,
        "service_id": definition["service_id"],
        "required": True,
        "dimensions": dimensions,
    }


def _dimension_value(definition: dict):
    allowed = definition.get("allowed_values")
    if allowed:
        return allowed[0]
    if "minimum" in definition:
        return definition["minimum"]
    value_type = definition["value_type"]
    if value_type == "boolean":
        return False
    if value_type == "integer":
        return 0
    return "test"


def _nested(value: dict, path: tuple[str, ...]) -> str:
    current = value
    for key in path:
        current = current[key]
    return str(current)


def _digest(specification: dict) -> str:
    encoded = json.dumps(
        specification,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
