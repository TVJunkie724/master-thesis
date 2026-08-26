"""Six-layer Eventing optimizer, capacity, and placement coverage."""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path

import pytest

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.six_layer_optimizer import PROVIDER_REGIONS
from backend.architecture_profiles.six_layer_costing import (
    evaluate_six_layer_costs,
)
from backend.architecture_profiles.six_layer_pricing import (
    SixLayerCatalogCostLedgerResolver,
)
from backend.architecture_profiles.six_layer_workload import (
    CONTRACT_ROOT as WORKLOAD_ROOT,
    resolve_six_layer_workload,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.architecture_profiles.six_layer_optimizer import (
    SIX_LAYER_KEYS,
    optimize_six_layer_eventing_v1,
)
from backend.architecture_profiles.strategy import build_resolution_context
from backend.architecture_profiles.five_layer_strategy import (
    build_default_strategy_registry,
)
from backend.deployment_specification.six_layer_builder import (
    SIX_LAYER_LOGICAL_COMPONENTS,
    build_six_layer_eventing_v1_deployment_specification,
)


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
BASELINE_ROOT = (
    Path(__file__).resolve().parents[3] / "json" / "pricing_catalog_baselines"
)
EVENT_SERVICES = {
    "aws": {
        "aws.kinesis-data-streams",
        "aws.sns-fifo",
        "aws.sqs-fifo",
        "aws.lambda-event-worker",
        "aws.s3-event-failure-store",
        "aws.cloudwatch",
    },
    "azure-small": {
        "azure.event-hubs-standard-small-medium",
        "azure.service-bus-standard",
        "azure.functions-flex-event-worker",
        "azure.monitor",
        "azure.log-analytics-shared-workspace",
    },
    "azure-large": {
        "azure.event-hubs-dedicated-large",
        "azure.service-bus-standard",
        "azure.functions-flex-event-worker",
        "azure.monitor",
        "azure.log-analytics-shared-workspace",
    },
    "gcp-small": {
        "gcp.pubsub-separated-event-layer-topics",
        "gcp.cloud-run-event-service-small-medium",
        "gcp.cloud-logging",
        "gcp.cloud-monitoring",
    },
    "gcp-large": {
        "gcp.pubsub-separated-event-layer-topics",
        "gcp.cloud-run-event-service-small-medium",
        "gcp.cloud-run-worker-pool-fixed-large",
        "gcp.cloud-logging",
        "gcp.cloud-monitoring",
    },
}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _registry() -> ArchitectureProfileRegistry:
    return ArchitectureProfileRegistry(
        profile_id="six-layer-eventing",
        profile_version="1",
    )


def _profile_ref(registry: ArchitectureProfileRegistry) -> dict[str, str]:
    return {
        "profileId": registry.profile["profile_id"],
        "profileVersion": registry.profile["profile_version"],
        "contentDigest": registry.profile["content_digest"],
    }


def _extension_bindings() -> list[dict[str, str]]:
    return [
        {
            "slotId": "processor.telemetry",
            "slotVersion": "1",
            "artifactId": "artifact.user.processor.example",
            "artifactDigest": "sha256:" + ("1" * 64),
            "configurationDigest": "sha256:" + ("2" * 64),
        }
    ]


def _workload(size: str):
    return _read(WORKLOAD_ROOT / "fixtures" / "valid" / f"core-{size}.json")


def _resolved_workload(size: str):
    return resolve_six_layer_workload(_workload(size))


def _pricing():
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
            "currency": "USD",
        }
    return pricing, evidence


def _rds(provider: str, size: str):
    registry = _registry()
    assignment = {logical: provider for logical in SIX_LAYER_LOGICAL_COMPONENTS}
    return build_six_layer_eventing_v1_deployment_specification(
        calculation_run_id=RUN_ID,
        assignment=assignment,
        resolved_workload=_resolved_workload(size),
        architecture_profile_ref={
            "id": registry.profile["profile_id"],
            "version": registry.profile["profile_version"],
            "digest": registry.profile["content_digest"],
        },
        component_catalog_ref={
            "id": registry.catalog["catalog_id"],
            "version": registry.catalog["catalog_version"],
            "digest": registry.catalog["content_digest"],
        },
        workload_contract_digest=registry.profile["workload_contract_ref"]["digest"],
        pricing_evidence_digests={provider: "sha256:" + ("a" * 64)},
        definition_lifecycle_statuses={
            "profile": "active",
            "catalog": "active",
            f"provider:{provider}": "active",
        },
    )


def _cross_cloud_rds(size: str):
    return _placement_rds(
        size,
        ingestion="aws",
        eventing="azure",
        processing="gcp",
    )


def _placement_rds(
    size: str,
    *,
    ingestion: str,
    eventing: str,
    processing: str,
    hot_storage: str | None = None,
):
    registry = _registry()
    hot_storage = hot_storage or processing
    assignment = {
        "component.ingestion": ingestion,
        "component.eventing": eventing,
        "component.processing": processing,
        "component.hot-storage": hot_storage,
        "component.cool-storage": hot_storage,
        "component.archive-storage": hot_storage,
        "component.twin-state": processing,
        "component.visualization": hot_storage,
    }
    specification = build_six_layer_eventing_v1_deployment_specification(
        calculation_run_id=RUN_ID,
        assignment=assignment,
        resolved_workload=_resolved_workload(size),
        architecture_profile_ref={
            "id": registry.profile["profile_id"],
            "version": registry.profile["profile_version"],
            "digest": registry.profile["content_digest"],
        },
        component_catalog_ref={
            "id": registry.catalog["catalog_id"],
            "version": registry.catalog["catalog_version"],
            "digest": registry.catalog["content_digest"],
        },
        workload_contract_digest=registry.profile["workload_contract_ref"]["digest"],
        pricing_evidence_digests={
            provider: "sha256:" + marker * 64
            for provider, marker in {"aws": "a", "azure": "b", "gcp": "c"}.items()
            if provider in set(assignment.values())
        },
        definition_lifecycle_statuses={
            "profile": "active",
            "catalog": "active",
            "provider:aws": "active",
            "provider:azure": "active",
            "provider:gcp": "active",
        },
    )
    return assignment, specification


def test_registry_and_strategy_enumerate_only_colocated_l3_hot_l5_candidates():
    registry = _registry()
    context = build_resolution_context(
        registry=registry,
        calculation_run_id=RUN_ID,
        architecture_profile=_profile_ref(registry),
        extension_bindings=_extension_bindings(),
        resolution_status="offline_contract_fixture",
    ).with_execution_inputs(
        layer_options={layer: (("AWS", 0), ("Azure", 0)) for layer in SIX_LAYER_KEYS},
        provider_regions=PROVIDER_REGIONS,
    )
    strategy = build_default_strategy_registry(context).resolve(context.profile)
    candidates = strategy.enumerate_candidates(context)

    assert len(candidates) == 128
    assert all(
        candidate.component("component.hot-storage").provider
        == candidate.component("component.visualization").provider
        for candidate in candidates
    )
    assert {
        candidate.component("component.eventing").provider for candidate in candidates
    } == {"aws", "azure"}


@pytest.mark.parametrize("provider", ("aws", "azure", "gcp"))
@pytest.mark.parametrize("size", ("small", "medium", "large"))
def test_single_cloud_selects_exact_event_bundle_and_no_bridge(provider, size):
    specification = _rds(provider, size)
    event_components = {
        item["implementation_component_id"]
        for item in specification["component_selections"]
        if item["logical_component_id"] == "component.eventing"
    }
    expected_key = (
        provider
        if provider == "aws"
        else f"{provider}-{'large' if size == 'large' else 'small'}"
    )

    assert event_components == EVENT_SERVICES[expected_key]
    assert not any("only-for-reviewed-remote" in item for item in event_components)
    if provider == "gcp" and size == "large":
        worker = next(
            item
            for item in specification["component_selections"]
            if item["implementation_component_id"]
            == "gcp.cloud-run-worker-pool-fixed-large"
        )
        dimensions = {
            item["dimension_id"].rsplit(".", 1)[-1]: item["value"]
            for item in worker["dimensions"]
        }
        assert dimensions == {
            "resource_count": 126,
            "requests": 0,
            "vcpu_seconds": "331128000",
            "memory_gib_seconds": "165564000",
        }
        assert (
            "gate.live-capacity.gcp.cloud-run-worker-pool-preview"
            in specification["readiness"]["blocking_gate_ids"]
        )


@pytest.mark.parametrize("provider", ("aws", "azure", "gcp"))
def test_real_single_cloud_optimizer_prices_complete_profile(provider):
    pricing, evidence = _pricing()
    registry = _registry()
    result = optimize_six_layer_eventing_v1(
        calculation_run_id=RUN_ID,
        architecture_profile=_profile_ref(registry),
        extension_bindings=_extension_bindings(),
        workload=_workload("small"),
        pricing_evidence_refs={provider: evidence[provider]},
        pricing_by_provider={provider: pricing[provider]},
        providers=(provider,),
        registry=registry,
    )

    assert result.enumerated_candidate_count == 1
    assert result.costed_candidate_count == 1
    assert result.cost_evaluation.monthly_total > 0
    assert result.cost_ledger["route_costs"] == []
    assert len(result.resolved_architecture["component_assignments"]) == 8
    event_edges = [
        item
        for item in result.resolved_architecture["resolved_edges"]
        if "eventing" in item["edge_id"]
    ]
    assert len(event_edges) == 5
    assert {item["mechanism"] for item in event_edges} == {"provider_native_trigger"}
    assert {item["transfer_route_class"] for item in event_edges} == {
        "same_provider_same_region"
    }


def test_optimizer_rejects_cheapest_candidate_when_resolution_is_not_materializable():
    pricing, evidence = _pricing()
    registry = _registry()
    base_resolver = SixLayerCatalogCostLedgerResolver(pricing)
    invalid_assignment = {
        "component.ingestion": "aws",
        "component.processing": "aws",
        "component.hot-storage": "aws",
        "component.cool-storage": "azure",
        "component.archive-storage": "azure",
        "component.twin-state": "azure",
        "component.visualization": "aws",
        "component.eventing": "gcp",
    }

    def prefer_unmaterializable_candidate(specification, assignment, workload):
        ledger = copy.deepcopy(
            base_resolver.resolve(specification, assignment, workload)
        )
        if assignment != invalid_assignment:
            quote = ledger["component_costs"][0]
            quote["monthly_amount"] = str(
                Decimal(quote["monthly_amount"]) + Decimal("1000000000")
            )
        return ledger

    result = optimize_six_layer_eventing_v1(
        calculation_run_id=RUN_ID,
        architecture_profile=_profile_ref(registry),
        extension_bindings=_extension_bindings(),
        workload=_workload("small"),
        pricing_evidence_refs=evidence,
        cost_ledger_resolver=prefer_unmaterializable_candidate,
        registry=registry,
    )

    assert result.winning_candidate_id != "aws|aws|aws|azure|azure|azure|aws|gcp"
    assert result.costed_candidate_count < result.enumerated_candidate_count
    assert dict(result.rejected_by_error_code)["ARCH_RESOLUTION_BUILD_FAILED"] > 0


def test_optimizer_materializes_source_owned_event_bridges_in_rta():
    pricing, evidence = _pricing()
    registry = _registry()
    base_resolver = SixLayerCatalogCostLedgerResolver(
        {provider: pricing[provider] for provider in ("aws", "azure")}
    )

    def force_cross_event(specification, assignment, workload):
        ledger = copy.deepcopy(
            base_resolver.resolve(specification, assignment, workload)
        )
        target = (
            assignment["component.ingestion"] == "aws"
            and assignment["component.eventing"] == "azure"
            and assignment["component.processing"] == "aws"
        )
        if not target:
            quote = ledger["component_costs"][0]
            quote["monthly_amount"] = str(
                Decimal(quote["monthly_amount"]) + Decimal("1000000000")
            )
        return ledger

    result = optimize_six_layer_eventing_v1(
        calculation_run_id=RUN_ID,
        architecture_profile=_profile_ref(registry),
        extension_bindings=_extension_bindings(),
        workload=_workload("small"),
        pricing_evidence_refs={
            provider: evidence[provider] for provider in ("aws", "azure")
        },
        cost_ledger_resolver=force_cross_event,
        providers=("aws", "azure"),
        registry=registry,
    )

    assignment = {
        item["logical_component_id"]: item["provider"]
        for item in result.resolved_architecture["component_assignments"]
    }
    event_edges = {
        item["edge_id"]: item
        for item in result.resolved_architecture["resolved_edges"]
        if "eventing" in item["edge_id"]
    }

    assert assignment["component.ingestion"] == "aws"
    assert assignment["component.eventing"] == "azure"
    assert assignment["component.processing"] == "aws"
    assert set(event_edges) == {
        "edge.ingestion-to-eventing",
        "edge.eventing-to-processing",
        "edge.processing-to-eventing",
        "edge.eventing-to-ingestion",
        "edge.eventing-to-hot-storage",
    }
    assert {item["mechanism"] for item in event_edges.values()} == {
        "cross_provider_adapter"
    }


def test_catalog_covers_all_six_directed_provider_pairs_for_every_event_edge():
    registry = _registry()
    event_edges = {
        "edge.ingestion-to-eventing",
        "edge.eventing-to-processing",
        "edge.processing-to-eventing",
        "edge.eventing-to-ingestion",
        "edge.eventing-to-hot-storage",
    }
    implementations = [
        item
        for item in registry.catalog["edge_implementations"]
        if item["logical_edge_ids"][0] in event_edges
        and item["transfer_route_class"] == "cross_provider"
    ]

    assert len(implementations) == 30
    assert {
        tuple(
            item["edge_implementation_id"]
            .removeprefix("edge-implementation.")
            .split(".", 1)[0]
            .split("-to-", 1)
        )
        for item in implementations
    } == {
        (source, destination)
        for source in ("aws", "azure", "gcp")
        for destination in ("aws", "azure", "gcp")
        if source != destination
    }
    assert all(
        item["mechanism"] == "cross_provider_adapter" for item in implementations
    )
    assert all(item["glue_component_ids"] for item in implementations)


@pytest.mark.parametrize(
    ("size", "expected"),
    (
        (
            "small",
            {
                "edge.ingestion-to-eventing": ("100351", "512897536"),
                "edge.processing-to-eventing": ("102855", "517513216"),
                "edge.eventing-to-processing": ("202955", "1029896704"),
                "edge.eventing-to-hot-storage": ("202955", "1029896704"),
                "edge.eventing-to-ingestion": ("251", "514048"),
            },
        ),
        (
            "medium",
            {
                "edge.ingestion-to-eventing": ("10175375", "176730176000"),
                "edge.processing-to-eventing": ("10429125", "177197888000"),
                "edge.eventing-to-processing": ("20579125", "353876096000"),
                "edge.eventing-to-hot-storage": ("20579125", "353876096000"),
                "edge.eventing-to-ingestion": ("25375", "51968000"),
            },
        ),
        (
            "large",
            {
                "edge.ingestion-to-eventing": ("103257500", "6856075520000"),
                "edge.processing-to-eventing": ("105832500", "6860821760000"),
                "edge.eventing-to-processing": ("208832500", "13716369920000"),
                "edge.eventing-to-hot-storage": (
                    "208832500",
                    "13716369920000",
                ),
                "edge.eventing-to-ingestion": ("257500", "527360000"),
            },
        ),
    ),
)
def test_cross_cloud_event_routes_use_exact_frozen_channel_quantities(size, expected):
    pricing, _evidence = _pricing()
    assignment, specification = _cross_cloud_rds(size)

    ledger = SixLayerCatalogCostLedgerResolver(pricing).resolve(
        specification,
        assignment,
        _resolved_workload(size),
    )
    evaluate_six_layer_costs(
        specification=specification,
        assignment=assignment,
        resolved_workload=_resolved_workload(size),
        cost_ledger=ledger,
    )

    quantities_by_edge = {
        allocation["item_id"]: item["normalized_quantities"]
        for item in ledger["route_costs"]
        if item["route_class"] == "domain_event_cross_cloud"
        for allocation in item["allocations"]
    }
    assert quantities_by_edge == {
        edge_id: {
            "source_runtime": operations,
            "destination_operations": operations,
            "cross_cloud_egress_bytes": transfer_bytes,
        }
        for edge_id, (operations, transfer_bytes) in expected.items()
    }


def test_independent_remote_hot_storage_selects_its_event_landing_bundle():
    pricing, _evidence = _pricing()
    assignment, specification = _placement_rds(
        "small",
        ingestion="aws",
        eventing="aws",
        processing="aws",
        hot_storage="azure",
    )

    selected = {
        item["implementation_component_id"]
        for item in specification["component_selections"]
    }
    assert {
        "azure.event-hubs-only-for-reviewed-remote-telemetry-edge",
        "azure.service-bus-standard",
        "aws.lambda-event-adapter",
    }.issubset(selected)

    ledger = SixLayerCatalogCostLedgerResolver(pricing).resolve(
        specification,
        assignment,
        _resolved_workload("small"),
    )
    event_to_hot_route = next(
        route
        for route in ledger["route_costs"]
        if any(
            allocation["item_id"] == "edge.eventing-to-hot-storage"
            for allocation in route["allocations"]
        )
    )
    assert event_to_hot_route["pair"] == "aws->azure"
    assert "topology_cost_registry_digest" in event_to_hot_route
    landing_costs = {
        item["component_id"]: Decimal(item["monthly_amount"])
        for item in ledger["component_costs"]
        if item["component_id"]
        in {
            "azure.event-hubs-only-for-reviewed-remote-telemetry-edge",
            "azure.service-bus-standard",
        }
    }
    assert set(landing_costs) == {
        "azure.event-hubs-only-for-reviewed-remote-telemetry-edge",
        "azure.service-bus-standard",
    }
    assert all(amount > 0 for amount in landing_costs.values())


def test_cost_evaluation_rejects_a_tampered_topology_registry_binding():
    pricing, _evidence = _pricing()
    assignment, specification = _cross_cloud_rds("small")
    workload = _resolved_workload("small")
    ledger = SixLayerCatalogCostLedgerResolver(pricing).resolve(
        specification,
        assignment,
        workload,
    )
    event_quote = next(
        item
        for item in ledger["component_costs"]
        if "topology_cost_registry_digest" in item
    )
    event_quote["topology_cost_registry_digest"] = "sha256:" + "0" * 64

    with pytest.raises(ArchitectureResolutionError) as raised:
        evaluate_six_layer_costs(
            specification=specification,
            assignment=assignment,
            resolved_workload=workload,
            cost_ledger=ledger,
        )

    assert raised.value.code == "ARCH_PRICING_EVIDENCE_MISSING"


def test_all_243_event_topologies_reconcile_to_the_frozen_cost_registry():
    pricing, _evidence = _pricing()
    registry = _read(
        Path(__file__).resolve().parents[3]
        / "backend"
        / "contracts"
        / "generated"
        / "architecture-profiles"
        / "definitions"
        / "six-layer-eventing-v1-cost-registry.json"
    )

    for scenario in registry["scenarios"]:
        size = scenario["scenario_id"].removeprefix("eventing-").removesuffix("-v1")
        for placement in scenario["placements"]:
            assignment, specification = _placement_rds(
                size,
                ingestion=placement["ingestion_provider"],
                eventing=placement["eventing_provider"],
                processing=placement["processing_provider"],
                hot_storage=placement["hot_storage_provider"],
            )
            ledger = SixLayerCatalogCostLedgerResolver(pricing).resolve(
                specification,
                assignment,
                _resolved_workload(size),
            )
            worker_selections = [
                item
                for item in specification["component_selections"]
                if item["implementation_component_id"]
                == "gcp.cloud-run-worker-pool-fixed-large"
            ]
            expected_worker_count = 0
            if size == "large":
                if placement["eventing_provider"] == "gcp":
                    local_subscription_count = 2
                    if placement["processing_provider"] == "gcp":
                        local_subscription_count += 2
                    if placement["hot_storage_provider"] == "gcp":
                        local_subscription_count += 2
                    bridge_channels = set()
                    if placement["processing_provider"] != "gcp":
                        bridge_channels.update(
                            {"telemetry.received.v1", "telemetry.processed.v1"}
                        )
                    if placement["hot_storage_provider"] != "gcp":
                        bridge_channels.add("telemetry.processed.v1")
                    expected_worker_count = 21 * (
                        local_subscription_count + len(bridge_channels)
                    )
                else:
                    bridge_channels = set()
                    if placement["ingestion_provider"] == "gcp":
                        bridge_channels.add("telemetry.received.v1")
                    if placement["processing_provider"] == "gcp":
                        bridge_channels.add("telemetry.processed.v1")
                    expected_worker_count = 21 * len(bridge_channels)
            assert len(worker_selections) == (1 if expected_worker_count else 0)
            if worker_selections:
                dimensions = {
                    item["dimension_id"].rsplit(".", 1)[-1]: item["value"]
                    for item in worker_selections[0]["dimensions"]
                }
                assert dimensions["resource_count"] == expected_worker_count
                assert dimensions["vcpu_seconds"] == str(
                    expected_worker_count * 2628000
                )
                assert dimensions["memory_gib_seconds"] == str(
                    expected_worker_count * 1314000
                )
            frozen_quotes = [
                item
                for item in ledger["component_costs"] + ledger["route_costs"]
                if item.get("topology_cost_registry_digest")
                == registry["content_digest"]
            ]

            assert sum(
                (Decimal(item["monthly_amount"]) for item in frozen_quotes),
                Decimal(0),
            ) == Decimal(placement["event_scope_total_usd"])
