"""Five-layer v2 workload, placement, and functional-completeness gates."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.architecture_profiles.diagnostics import ArchitectureResolutionError
from backend.architecture_profiles.five_layer_v2_strategy import (
    FiveLayerV2CandidateStrategy,
)
from backend.architecture_profiles.five_layer_strategy import (
    build_default_strategy_registry,
)
from backend.architecture_profiles.five_layer_v2_workload import (
    CONTRACT_ROOT,
    resolve_five_layer_v2_workload,
)
from backend.architecture_profiles.registry import ArchitectureProfileRegistry
from backend.architecture_profiles.strategy import build_resolution_context


RUN_ID = "018f0f5e-7b5e-7b2d-9f0b-7f66c2a88a01"
LAYER_KEYS = (
    "L1",
    "L2",
    "L3_hot",
    "L3_cool",
    "L3_archive",
    "L4",
    "L5",
)


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _context(*, resolution_status: str = "offline_contract_fixture"):
    registry = ArchitectureProfileRegistry(profile_version="2")
    context = build_resolution_context(
        registry=registry,
        calculation_run_id=RUN_ID,
        architecture_profile={
            "profileId": registry.profile["profile_id"],
            "profileVersion": registry.profile["profile_version"],
            "contentDigest": registry.profile["content_digest"],
        },
        extension_bindings=[
            {
                "slotId": "processor.telemetry",
                "slotVersion": "1",
                "artifactId": "artifact.user.processor.example",
                "artifactDigest": "sha256:" + ("1" * 64),
                "configurationDigest": "sha256:" + ("2" * 64),
            }
        ],
        resolution_status=resolution_status,
    )
    return registry, context.with_execution_inputs(
        layer_options={
            layer: (("AWS", 1), ("Azure", 1), ("GCP", 1))
            for layer in LAYER_KEYS
        },
        provider_regions={
            "aws": "eu-central-1",
            "azure": "westeurope",
            "gcp": "europe-west1",
        },
    )


@pytest.mark.parametrize("size", ("small", "medium", "large"))
def test_workload_resolves_only_immutable_core_eventing_pairs(size):
    workload = _read(
        CONTRACT_ROOT / "fixtures" / "valid" / f"core-{size}.json"
    )

    resolved = resolve_five_layer_v2_workload(workload)

    assert resolved.size == size
    assert resolved.eventing_scenario_ref["id"] == f"eventing-{size}-v1"
    assert resolved.eventing_scenario["bounded_synthetic_scenario"] is True


def test_workload_currency_is_independent_of_the_frozen_scenario_identity():
    workload = _read(CONTRACT_ROOT / "fixtures" / "valid" / "core-small.json")
    workload["currency"] = "EUR"

    resolved = resolve_five_layer_v2_workload(workload)

    assert resolved.size == "small"
    assert resolved.workload["currency"] == "EUR"
    assert resolved.eventing_scenario_ref["id"] == "eventing-small-v1"


@pytest.mark.parametrize(
    ("mutation", "path"),
    (
        (
            lambda value: value.update({"useEventChecking": True}),
            "$",
        ),
        (
            lambda value: value.update({"monthlyViewerSeats": 999}),
            "workload",
        ),
        (
            lambda value: value.update(
                {"eventingScenarioId": "eventing-medium-v1"}
            ),
            "workload",
        ),
    ),
)
def test_workload_rejects_retired_custom_or_mismatched_inputs(mutation, path):
    workload = copy.deepcopy(
        _read(CONTRACT_ROOT / "fixtures" / "valid" / "core-small.json")
    )
    mutation(workload)

    with pytest.raises(ArchitectureResolutionError) as raised:
        resolve_five_layer_v2_workload(workload)

    assert raised.value.code == "ARCH_WORKLOAD_INCOMPATIBLE"
    assert raised.value.field == path


def test_publishable_resolution_rejects_draft_profile():
    with pytest.raises(ArchitectureResolutionError) as raised:
        _context(resolution_status="publishable")

    assert raised.value.code == "ARCH_PROFILE_NOT_FOUND"


def test_offline_resolution_enumerates_all_729_admissible_assignments():
    registry, context = _context()
    strategy = FiveLayerV2CandidateStrategy(registry.profile)
    strategy.validate_request(context)

    candidates = strategy.enumerate_candidates(context)
    complete = tuple(
        strategy.validate_functional_completeness(candidate, context)
        for candidate in candidates
    )

    assert len(candidates) == 729
    assert len(complete) == 729
    assert all(
        candidate.candidate.component("component.hot-storage").provider
        == candidate.candidate.component("component.visualization").provider
        for candidate in complete
    )
    assert all(len(candidate.edges) == 8 for candidate in complete)
    assert {
        edge.logical_edge["edge_id"]
        for edge in complete[0].edges
    } >= {
        "edge.hot-storage-to-visualization",
        "edge.hot-storage-to-twin-state",
        "edge.ingestion-to-hot-storage",
        "edge.processing-to-ingestion",
    }
    assert all(
        edge.logical_edge["edge_id"] != "edge.twin-state-to-visualization"
        for edge in complete[0].edges
    )


def test_v2_registry_is_explicit_and_does_not_change_v1_default():
    historical = ArchitectureProfileRegistry()
    current = ArchitectureProfileRegistry(profile_version="2")

    assert historical.profile["profile_version"] == "1"
    assert historical.catalog["catalog_id"] == "baseline-component-catalog"
    assert current.profile["profile_version"] == "2"
    assert current.catalog["catalog_id"] == "complete-service-component-catalog"


def test_strategy_registry_dispatches_exact_v2_bundle():
    _, context = _context()

    strategy = build_default_strategy_registry(context).resolve(context.profile)

    assert isinstance(strategy, FiveLayerV2CandidateStrategy)
