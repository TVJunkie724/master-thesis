"""Behavioral tests for complete-path and pooled transfer optimization."""

from decimal import Decimal

import pytest

from backend.calculation_v2.components.types import Provider
from backend.calculation_v2.path_optimizer import (
    build_baseline_edge_workloads,
    build_transfer_pricing_context,
    evaluate_complete_paths,
)
from backend.pricing_registry import load_pricing_registry
from tests.unit.pricing.transfer_fixtures import (
    canonical_transfer_catalog,
    pricing_catalog_context_for,
)


def _pricing() -> dict:
    return {
        provider: {"transfer": canonical_transfer_catalog(provider)}
        for provider in ("aws", "azure", "gcp")
    }


def _derived(*, telemetry_bytes: Decimal, query_count: Decimal = Decimal(0)):
    return {
        "total_messages_per_month": telemetry_bytes / Decimal(1024),
        "msg_size_kb": Decimal(1),
        "data_size_per_month_gb": telemetry_bytes / (Decimal(1024) ** 3),
        "queries_per_month": query_count,
        "average_digital_twin_query_response_size_kb": Decimal("1.5"),
    }


def _options(
    *,
    l1=(("AWS", 0.0),),
    l2=(("AWS", 0.0),),
    l3_hot=(("AWS", 0.0),),
    l3_cool=(("AWS", 0.0),),
    l3_archive=(("AWS", 0.0),),
    l4=(("AWS", 0.0),),
    l5=(("AWS", 0.0),),
):
    return {
        "L1": l1,
        "L2": l2,
        "L3_hot": l3_hot,
        "L3_cool": l3_cool,
        "L3_archive": l3_archive,
        "L4": l4,
        "L5": l5,
    }


def _evaluate(layer_options, derived):
    pricing = _pricing()
    return evaluate_complete_paths(
        layer_options=layer_options,
        derived=derived,
        pricing=pricing,
        pricing_catalog_context=pricing_catalog_context_for(pricing),
        pricing_registry=load_pricing_registry(),
        glue_cost_resolver=lambda _provider, _invocations: Decimal(0),
    )


def test_complete_path_cost_can_override_independent_layer_minima():
    evaluation_set = _evaluate(
        _options(
            l1=(("AWS", 0.0), ("Azure", 100.0)),
            l2=(("AWS", 1.0), ("Azure", 0.0)),
        ),
        _derived(telemetry_bytes=Decimal(200_000_000_000)),
    )

    winner = min(
        evaluation_set.evaluations,
        key=lambda item: (item.total_cost, item.candidate_id),
    )

    assert winner.provider_for("L1") == Provider.AWS
    assert winner.provider_for("L2") == Provider.AWS
    assert winner.total_cost == Decimal(1)
    assert evaluation_set.enumerated_path_count == 4


def test_source_provider_free_allowance_is_consumed_once_across_edges():
    evaluation_set = _evaluate(
        _options(
            l1=(("AWS", 0.0),),
            l2=(("Azure", 0.0),),
            l3_hot=(("AWS", 0.0),),
            l3_cool=(("Azure", 0.0),),
            l3_archive=(("Azure", 0.0),),
            l4=(("AWS", 0.0),),
            l5=(("AWS", 0.0),),
        ),
        _derived(telemetry_bytes=Decimal(75_000_000_000)),
    )

    winner = evaluation_set.evaluations[0]
    aws_charges = [
        charge
        for charge in winner.transfer_charges
        if charge.route.source.provider == Provider.AWS
        and charge.route.destination.provider != Provider.AWS
    ]

    assert [charge.route.segment_id for charge in aws_charges] == [
        "L1_to_L2",
        "L3_hot_to_L3_cool",
    ]
    assert [charge.egress_cost for charge in aws_charges] == [
        Decimal(0),
        Decimal("4.50"),
    ]
    assert sum(
        (charge.egress_cost for charge in aws_charges),
        Decimal(0),
    ) == Decimal("4.50")


def test_same_provider_path_keeps_all_six_zero_cost_routes_visible():
    evaluation_set = _evaluate(
        _options(),
        _derived(
            telemetry_bytes=Decimal(1_000_000_000),
            query_count=Decimal(12),
        ),
    )

    context = build_transfer_pricing_context(evaluation_set.evaluations[0])

    assert [route["segmentId"] for route in context["routes"]] == [
        "L1_to_L2",
        "L2_to_L3_hot",
        "L3_hot_to_L3_cool",
        "L3_cool_to_L3_archive",
        "L3_hot_to_L4",
        "L4_to_L5",
    ]
    assert context["pools"] == []
    assert all(route["routeClass"] == "same_provider_same_region" for route in context["routes"])
    assert all(route["totalCost"] == 0 for route in context["routes"])


def test_query_response_edges_use_declared_kib_response_size():
    workloads = build_baseline_edge_workloads(
        _derived(
            telemetry_bytes=Decimal(1_000_000),
            query_count=Decimal(12),
        )
    )
    query_edges = {
        workload.segment_id: workload
        for workload in workloads
        if workload.segment_id in {"L3_hot_to_L4", "L4_to_L5"}
    }

    assert set(query_edges) == {"L3_hot_to_L4", "L4_to_L5"}
    assert {
        workload.volume_bytes for workload in query_edges.values()
    } == {Decimal(12) * Decimal("1.5") * Decimal(1024)}
    assert all(
        "1024 bytes" in " ".join(workload.assumptions)
        for workload in query_edges.values()
    )


def test_layer_options_are_canonical_and_reject_duplicate_providers():
    pricing = _pricing()
    common = {
        "derived": _derived(telemetry_bytes=Decimal(0)),
        "pricing": pricing,
        "pricing_catalog_context": pricing_catalog_context_for(pricing),
        "pricing_registry": load_pricing_registry(),
        "glue_cost_resolver": lambda _provider, _invocations: Decimal(0),
    }
    reordered = _options(
        l1=(("GCP", 0.0), ("AWS", 0.0), ("Azure", 0.0)),
    )

    evaluation_set = evaluate_complete_paths(
        layer_options=reordered,
        **common,
    )

    assert [
        evaluation.candidate_id.split("|", maxsplit=1)[0]
        for evaluation in evaluation_set.evaluations
    ] == ["aws", "azure", "gcp"]

    duplicate = _options(l1=(("AWS", 0.0), ("AWS", 1.0)))
    with pytest.raises(ValueError, match="Duplicate provider option"):
        evaluate_complete_paths(layer_options=duplicate, **common)
