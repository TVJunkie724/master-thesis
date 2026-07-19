"""Canonical fixture helpers for Phase 8 Management architecture tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.services.architecture_contract_service import (
    calculate_digest,
    calculate_resolution_id,
)
from src.services.resolved_deployment_specification_service import (
    calculate_digest as calculate_deployment_digest,
)
from tests.pricing_catalog_test_data import catalog_context
from tests.resolved_deployment_specification_test_data import (
    SLOT_ORDER,
    _component,
    _fixture_contract,
    build_resolved_deployment_specification,
)


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "contracts"
    / "generated"
    / "architecture-profiles"
    / "v1"
    / "fixtures"
    / "valid"
)


def _read(name: str) -> dict:
    return json.loads((CONTRACT_ROOT / name).read_text("utf-8"))


def linked_architecture_fixture_documents() -> tuple[dict, ...]:
    return (
        _read("five-layer-baseline-profile.json"),
        _read("aws-baseline-provider-profile.json"),
        _read("azure-baseline-provider-profile.json"),
        _read("baseline-component-catalog.json"),
    )


def _single_provider_architecture(
    architecture: dict,
    *,
    provider: str,
) -> tuple[dict, dict]:
    profile, aws_profile, azure_profile, catalog = (
        linked_architecture_fixture_documents()
    )
    provider_profile = {
        "aws": aws_profile,
        "azure": azure_profile,
    }[provider]
    mappings = {
        item["component_id"]: item
        for item in provider_profile["component_mappings"]
    }
    catalog_components = {
        item["deployment_component_id"]: item
        for item in catalog["components"]
    }
    template_assignments = {
        item["logical_component_id"]: item
        for item in architecture["component_assignments"]
    }
    assignments = []
    for logical in profile["components"]:
        logical_id = logical["component_id"]
        mapping = mappings[logical_id]
        component = catalog_components[
            mapping["deployment_component_candidates"][0]
        ]
        assignment = copy.deepcopy(template_assignments[logical_id])
        assignment.update(
            {
                "capability_evidence": mapping[
                    "provided_capability_ids"
                ],
                "deployment_component_id": component[
                    "deployment_component_id"
                ],
                "deployment_component_version": component[
                    "component_version"
                ],
                "deployment_specification_component_ids": mapping[
                    "deployment_specification_component_ids"
                ],
                "formula_refs": mapping["formula_refs"],
                "pricing_model_refs": component["pricing_model_refs"],
                "provider": provider,
                "provider_implementation_profile_ref": {
                    "id": provider_profile[
                        "implementation_profile_id"
                    ],
                    "version": provider_profile[
                        "implementation_profile_version"
                    ],
                    "digest": provider_profile["content_digest"],
                },
                "region": mapping["supported_region_ids"][0].split(
                    ".",
                    2,
                )[-1],
                "service_id": component["service_id"],
            }
        )
        assignments.append(assignment)

    edge_mappings = {
        item["edge_id"]: item
        for item in provider_profile["edge_mappings"]
    }
    catalog_edges = {
        item["edge_implementation_id"]: item
        for item in catalog["edge_implementations"]
    }
    template_edges = {
        item["edge_id"]: item for item in architecture["resolved_edges"]
    }
    edges = []
    for logical in profile["edges"]:
        logical_id = logical["edge_id"]
        mapping = edge_mappings[logical_id]
        catalog_edge = catalog_edges[mapping["edge_implementation_id"]]
        edge = copy.deepcopy(template_edges[logical_id])
        edge.update(
            {
                "delivery_semantics": catalog_edge[
                    "delivery_requirements"
                ],
                "destination_port_id": mapping[
                    "catalog_input_port_id"
                ],
                "edge_implementation_id": mapping[
                    "edge_implementation_id"
                ],
                "formula_refs": catalog_edge["formula_refs"],
                "mechanism": mapping["mechanism"],
                "observability_contract_ref": catalog_edge[
                    "observability_contract_ref"
                ],
                "source_port_id": mapping["catalog_output_port_id"],
                "transfer_evidence_refs": [
                    f"evidence.{provider}.transfer"
                ],
                "transfer_route_class": mapping[
                    "transfer_route_class"
                ],
                "trust_contract_ref": catalog_edge[
                    "trust_contract_ref"
                ],
            }
        )
        edges.append(edge)

    architecture["component_assignments"] = assignments
    architecture["resolved_edges"] = edges
    architecture["provider_profile_refs"] = [
        {
            "id": provider_profile["implementation_profile_id"],
            "version": provider_profile[
                "implementation_profile_version"
            ],
            "digest": provider_profile["content_digest"],
            "provider": provider,
        }
    ]
    architecture["pricing_evidence_refs"] = [
        item
        for item in architecture["pricing_evidence_refs"]
        if item["provider"] == provider
    ]
    architecture["resolution_id"] = calculate_resolution_id(architecture)
    return architecture, provider_profile


def calculation_result_and_contracts(
    provider: str | None = None,
) -> tuple[dict, dict, dict]:
    if provider not in {None, "aws", "azure"}:
        raise ValueError("provider must be aws, azure, or None")
    context = catalog_context()
    selected = {
        "l1": provider or "aws",
        "l2": provider or "azure",
        "l3_hot": provider or "azure",
        "l3_cool": provider or "azure",
        "l3_archive": provider or "azure",
        "l4": provider or "azure",
        "l5": provider or "azure",
    }
    result = {
        "optimization_profile_id": "cost_minimization_v1",
        "calculation_strategy_id": "cost_calculation_v2",
        "optimizationProfile": {
            "profile_version": "1",
            "pricing_registry_version": "2026.07.17",
            "scoring_strategy_id": "min_total_cost_v1",
        },
        "calculationStrategy": {
            "formula_set_id": "cost_formula_set_v1",
            "workload_contract_id": "digital_twin_workload_v1",
        },
        "calculationResult": {
            "L1": selected["l1"].upper(),
            "L2": selected["l2"].upper(),
            "L3": {
                "Hot": selected["l3_hot"].upper(),
                "Cool": selected["l3_cool"].upper(),
                "Archive": selected["l3_archive"].upper(),
            },
            "L4": selected["l4"].upper(),
            "L5": selected["l5"].upper(),
        },
        "pricingCatalogs": context.to_http_dict(),
    }
    specification = build_resolved_deployment_specification(
        result,
        calculation_run_id=RUN_ID,
        pricing_catalogs=result["pricingCatalogs"],
    )
    architecture = copy.deepcopy(
        _read("mixed-baseline-resolved-architecture.json")
    )
    if provider is not None:
        architecture, provider_profile = _single_provider_architecture(
            architecture,
            provider=provider,
        )
        required_component_ids = {
            component_id
            for mapping in provider_profile["component_mappings"]
            for component_id in mapping[
                "deployment_specification_component_ids"
            ]
        }
    else:
        required_component_ids = {
            component_id
            for assignment in architecture["component_assignments"]
            for component_id in assignment[
                "deployment_specification_component_ids"
            ]
        }
    existing_component_ids = {
        item["component_id"] for item in specification["components"]
    }
    registry = _fixture_contract()
    specification["components"].extend(
        _component(
            component_id,
            registry=registry,
            pricing_catalogs=result["pricingCatalogs"],
            formula_set_id=result["calculationStrategy"]["formula_set_id"],
            workload_contract_id=result["calculationStrategy"][
                "workload_contract_id"
            ],
        )
        for component_id in sorted(
            required_component_ids - existing_component_ids
        )
    )
    components_by_id = {
        item["component_id"]: item for item in specification["components"]
    }
    ordered_component_ids = []
    for slot_id in SLOT_ORDER:
        requirement = registry["slot_requirements"][slot_id][
            selected[
                {
                    "l1_ingestion": "l1",
                    "l2_processing": "l2",
                    "l3_hot_storage": "l3_hot",
                    "l3_cool_storage": "l3_cool",
                    "l3_archive_storage": "l3_archive",
                    "l4_twin_state": "l4",
                    "l5_visualization": "l5",
                }[slot_id]
            ]
        ]
        ordered_component_ids.extend(requirement["required_components"])
        ordered_component_ids.extend(
            component_id
            for component_id in requirement["optional_components"]
            if component_id in components_by_id
        )
    ordered_component_ids.extend(
        item["component_id"]
        for item in specification["components"]
        if item["slot_id"] in {"transition_runtime", "cross_cloud_glue"}
    )
    specification["components"] = [
        components_by_id[component_id]
        for component_id in ordered_component_ids
    ]
    specification["digest"] = calculate_deployment_digest(specification)
    architecture["extension_bindings"][0]["configuration_digest"] = (
        "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
    )
    architecture["deployment_specification_ref"]["digest"] = specification[
        "digest"
    ]
    architecture["content_digest"] = calculate_digest(architecture)
    return result, specification, architecture
