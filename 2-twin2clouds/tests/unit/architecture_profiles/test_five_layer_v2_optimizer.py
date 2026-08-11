"""Closed-world Five-layer v2 optimization orchestration coverage."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.five_layer_v2_costing import (
    CONTRACT_ROOT as RDS_ROOT,
    FORMULA_REF,
    expected_route_owners,
    selection_digest,
)
from backend.architecture_profiles.five_layer_v2_optimizer import (
    optimize_five_layer_v2,
)
from backend.architecture_profiles.five_layer_v2_pricing import (
    build_five_layer_v2_catalog_cost_ledger_resolver,
)
from backend.architecture_profiles.five_layer_v2_workload import (
    CONTRACT_ROOT as WORKLOAD_ROOT,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
EVIDENCE = {
    "aws": {
        "id": "pricing-evidence.aws.test-v2",
        "version": "1",
        "digest": "sha256:" + ("a" * 64),
        "provider": "aws",
        "currency": "USD",
    },
    "azure": {
        "id": "pricing-evidence.azure.test-v2",
        "version": "1",
        "digest": "sha256:" + ("b" * 64),
        "provider": "azure",
        "currency": "USD",
    },
}
BASELINE_ROOT = (
    Path(__file__).resolve().parents[3] / "json" / "pricing_catalog_baselines"
)


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _request():
    registry = ArchitectureProfileRegistry(profile_version="2")
    return registry, {
        "calculation_run_id": RUN_ID,
        "architecture_profile": {
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        "extension_bindings": [
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
        "workload": _read(WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json"),
        "pricing_evidence_refs": EVIDENCE,
        "providers": ("aws", "azure"),
        "registry": registry,
    }


def _published_pricing(*, currency: str = "USD"):
    manifest = _read(BASELINE_ROOT / "baseline.json")
    pricing = {}
    evidence = {}
    for provider, reference in manifest["catalogs"].items():
        snapshot = _read(
            BASELINE_ROOT
            / provider
            / reference["pricing_region"]
            / "snapshots"
            / f"{reference['snapshot_id']}.json"
        )
        pricing[provider] = snapshot["pricing"]
        evidence[provider] = {
            "id": reference["snapshot_id"],
            "version": "1",
            "digest": reference["content_digest"],
            "provider": provider,
            "currency": currency,
        }
    return pricing, evidence


def _ledger(specification, assignment, workload, *, omit_azure=False):
    registry = _read(RDS_ROOT / "component-capacity-registry.json")
    components = {item["component_id"]: item for item in registry["components"]}
    evidence = {
        item["provider"]: item["digest"]
        for item in specification["optimization_context"]["pricing_evidence_refs"]
    }
    component_costs = []
    for selection in specification["component_selections"]:
        if omit_azure and selection["provider"] == "azure":
            continue
        component = components[selection["implementation_component_id"]]
        component_costs.append(
            {
                "component_id": selection["implementation_component_id"],
                "cost_owner_id": component["pricing_owner_id"],
                "selection_digest": selection_digest(selection),
                "formula_reference": FORMULA_REF,
                "pricing_evidence_digest": evidence[selection["provider"]],
                "monthly_amount": "1" if selection["provider"] == "aws" else "2",
            }
        )
    route_costs = []
    for route in expected_route_owners(assignment, workload):
        route_costs.append(
            {
                "cost_owner_id": route.cost_owner_id,
                "route_class": route.route_class,
                "pair": route.pair,
                "domain_flow_ids": list(route.domain_flow_ids),
                "workload_digest": route.workload_digest,
                "formula_reference": FORMULA_REF,
                "pricing_evidence_digests": {
                    "source": evidence[route.source_provider],
                    "destination": evidence[route.destination_provider],
                },
                "monthly_amount": str(10 * len(route.allocation_item_ids)),
                "allocations": [
                    {"item_id": item_id, "monthly_amount": "10"}
                    for item_id in route.allocation_item_ids
                ],
            }
        )
    return {
        "schema_version": "five-layer-v2-cost-ledger.v1",
        "currency": "USD",
        "component_costs": component_costs,
        "route_costs": route_costs,
    }


def test_optimizer_costs_all_64_two_provider_candidates_and_selects_aws():
    _, request = _request()

    result = optimize_five_layer_v2(
        **request,
        cost_ledger_resolver=_ledger,
    )

    assert result.enumerated_candidate_count == 64
    assert result.costed_candidate_count == 64
    assert result.rejected_by_error_code == ()
    assert {
        assignment["provider"]
        for assignment in result.resolved_architecture["component_assignments"]
    } == {"aws"}
    assert result.resolved_architecture["cost_summary"]["monthly_total"] == "19"
    assert result.cost_ledger["schema_version"] == ("five-layer-v2-cost-ledger.v1")
    assert len(result.cost_ledger["component_costs"]) == len(
        result.deployment_specification["component_selections"]
    )
    assert result.cost_ledger["route_costs"] == []


def test_optimizer_rejects_incomplete_provider_price_coverage_per_candidate():
    _, request = _request()

    result = optimize_five_layer_v2(
        **request,
        cost_ledger_resolver=lambda specification, assignment, workload: _ledger(
            specification,
            assignment,
            workload,
            omit_azure=True,
        ),
    )

    assert result.enumerated_candidate_count == 64
    assert result.costed_candidate_count == 1
    assert dict(result.rejected_by_error_code) == {"ARCH_PRICING_EVIDENCE_MISSING": 63}


def test_optimizer_requires_exactly_one_production_or_test_pricing_source():
    _, request = _request()

    with pytest.raises(ArchitectureResolutionError) as missing:
        optimize_five_layer_v2(**request)
    with pytest.raises(ArchitectureResolutionError) as ambiguous:
        optimize_five_layer_v2(
            **request,
            cost_ledger_resolver=_ledger,
            pricing_by_provider={},
        )

    assert missing.value.code == "ARCH_PRICING_EVIDENCE_MISSING"
    assert ambiguous.value.code == "ARCH_PRICING_EVIDENCE_MISSING"


def test_optimizer_reports_bounded_diagnostics_when_every_candidate_is_rejected():
    _, request = _request()

    def reject_pricing(*_args):
        raise ArchitectureResolutionError(
            "ARCH_PRICING_EVIDENCE_MISSING",
            "pricing",
            "test rejection",
        )

    with pytest.raises(ArchitectureResolutionError) as raised:
        optimize_five_layer_v2(
            **request,
            cost_ledger_resolver=reject_pricing,
        )

    assert raised.value.code == "ARCH_NO_ADMISSIBLE_CANDIDATE"
    assert raised.value.safe_diagnostics() == {
        "enumeratedCandidateCount": 64,
        "admissibleCandidateCount": 0,
        "rejectedCandidateCount": 64,
        "rejectedByErrorCode": {"ARCH_PRICING_EVIDENCE_MISSING": 64},
        "representativeCandidateIds": list(
            raised.value.diagnostics.representative_candidate_ids
        ),
    }
    assert len(raised.value.diagnostics.representative_candidate_ids) == 25


@pytest.mark.parametrize("provider", ("aws", "azure", "gcp"))
@pytest.mark.parametrize("size", ("small", "medium", "large"))
def test_published_rate_cards_cost_every_single_cloud_scenario(provider, size):
    registry, request = _request()
    pricing, evidence = _published_pricing()
    request.update(
        workload=_read(WORKLOAD_ROOT / "fixtures" / "valid" / f"core-{size}.json"),
        pricing_evidence_refs=evidence,
        providers=(provider,),
        registry=registry,
    )

    result = optimize_five_layer_v2(
        **request,
        pricing_by_provider=pricing,
    )

    assert result.enumerated_candidate_count == 1
    assert result.costed_candidate_count == 1
    assert result.rejected_by_error_code == ()
    assert result.cost_evaluation.monthly_total > 0


@pytest.mark.parametrize("size", ("small", "medium", "large"))
def test_published_rate_cards_cost_all_729_multicloud_candidates(size):
    registry, request = _request()
    pricing, evidence = _published_pricing()
    workload = _read(WORKLOAD_ROOT / "fixtures" / "valid" / f"core-{size}.json")
    audited_ledgers = []
    catalog_resolver = build_five_layer_v2_catalog_cost_ledger_resolver(pricing)

    def audited_resolver(specification, assignment, resolved_workload):
        ledger = catalog_resolver(specification, assignment, resolved_workload)
        audited_ledgers.append(ledger)
        return ledger

    request.update(
        workload=workload,
        pricing_evidence_refs=evidence,
        providers=("aws", "azure", "gcp"),
        registry=registry,
    )

    result = optimize_five_layer_v2(
        **request,
        cost_ledger_resolver=audited_resolver,
    )

    assert result.enumerated_candidate_count == 729
    assert result.costed_candidate_count == 729
    assert result.rejected_by_error_code == ()
    assert len(audited_ledgers) == 729
    assert all(
        sum(
            (
                Decimal(item["monthly_amount"])
                for item in ledger["component_costs"] + ledger["route_costs"]
            ),
            Decimal(0),
        )
        > 0
        for ledger in audited_ledgers
    )
    route_shapes = {
        (item["route_class"], item["pair"])
        for ledger in audited_ledgers
        for item in ledger["route_costs"]
    }
    assert route_shapes == {
        (route_class, f"{source}->{destination}")
        for route_class in (
            "domain_event_cross_cloud",
            "twin_projection_cross_cloud",
            "storage_hot_to_cool_cross_cloud",
            "storage_cool_to_archive_cross_cloud",
        )
        for source in ("aws", "azure", "gcp")
        for destination in ("aws", "azure", "gcp")
        if source != destination
    }
    critical_transport_ids = {
        "aws.kinesis-only-for-reviewed-remote-telemetry-edge",
        "aws.sns-fifo-only-for-reviewed-remote-control-edge",
        "azure.event-hubs-only-for-reviewed-remote-telemetry-edge",
        "gcp.pubsub-separated-embedded-topics",
    }
    assert all(
        Decimal(item["monthly_amount"]) > 0
        for ledger in audited_ledgers
        for item in ledger["component_costs"]
        if item["component_id"] in critical_transport_ids
    )


def test_published_eur_rate_cards_cost_all_729_multicloud_candidates():
    registry, request = _request()
    pricing, evidence = _published_pricing(currency="EUR")
    workload = _read(WORKLOAD_ROOT / "fixtures" / "valid" / "core-small.json")
    workload["currency"] = "EUR"
    request.update(
        workload=workload,
        pricing_evidence_refs=evidence,
        providers=("aws", "azure", "gcp"),
        registry=registry,
    )

    result = optimize_five_layer_v2(
        **request,
        pricing_by_provider=pricing,
    )

    assert result.enumerated_candidate_count == 729
    assert result.costed_candidate_count == 729
    assert result.rejected_by_error_code == ()
    assert result.cost_evaluation.currency == "EUR"
    assert result.cost_evaluation.monthly_total > 0
