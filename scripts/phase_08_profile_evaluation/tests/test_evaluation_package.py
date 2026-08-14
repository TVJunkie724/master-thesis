from __future__ import annotations

import copy
from decimal import Decimal
import json
import shutil

import pytest

from scripts.phase_08_profile_evaluation.generate import semantic_digest
from scripts.phase_08_profile_evaluation.validate import (
    DEFAULT_PACKAGE,
    SCHEMA_DIRECTORY,
    validate_cost,
    validate_package,
    validate_rejections_and_research_mapping,
    validate_schema,
)
from scripts.phase_08_profile_evaluation.verify_runtime_images import (
    SERVICE_NAMES,
    compare_digests,
    configured_digests,
)


def read(name: str) -> dict:
    return json.loads((DEFAULT_PACKAGE / name).read_text(encoding="utf-8"))


def test_committed_package_is_valid():
    validate_package(DEFAULT_PACKAGE)


def test_strict_schema_rejects_unknown_top_level_field():
    manifest = read("evaluation-manifest.json")
    manifest["unexpected"] = True
    with pytest.raises(AssertionError):
        validate_schema(
            manifest,
            SCHEMA_DIRECTORY / "evaluation-manifest.schema.json",
        )


def test_rejection_schema_forbids_a_publishable_total():
    rejections = read("rejections.json")
    rejections["rejections"][0]["monthly_total"] = "0"
    with pytest.raises(AssertionError):
        validate_schema(rejections, SCHEMA_DIRECTORY / "rejections.schema.json")


def test_functional_before_cost_order_is_immutable():
    functional = read("functional-matrix.json")
    functional["evaluation_order"] = [
        "estimated_cost",
        "functional_completeness",
        "theoretical_capacity",
    ]
    with pytest.raises(AssertionError):
        validate_schema(
            functional,
            SCHEMA_DIRECTORY / "functional-matrix.schema.json",
        )


def test_cost_recomputation_rejects_tampered_total():
    result = read("cost-results/six-layer-v1-small.json")
    cost = copy.deepcopy(result["optimizer_result"]["winner"]["cost"])
    cost["monthly_total"] = str(Decimal(cost["monthly_total"]) + 1)
    with pytest.raises(AssertionError):
        validate_cost(cost)


def test_paired_digest_changes_when_event_workload_changes():
    manifest = read("scenario-manifest.json")
    scenario = manifest["paired_scenarios"][0]
    original = scenario["paired_workload_digest"]
    mutated = copy.deepcopy(scenario["eventing_workload"])
    mutated["retry_share"] = mutated["retry_share"] + 0.001
    assert (
        semantic_digest({"core": scenario["core_workload"], "eventing": mutated})
        != original
    )


def test_all_directed_pairs_and_single_cloud_cases_are_present():
    expected_pairs = {
        f"{source}->{destination}"
        for source in ("aws", "azure", "gcp")
        for destination in ("aws", "azure", "gcp")
        if source != destination
    }
    for size in ("small", "medium", "large"):
        result = read(f"cost-results/six-layer-v1-{size}.json")
        assert {
            item["directed_pair"] for item in result["directed_event_pair_results"]
        } == expected_pairs
        for profile in ("five-layer-v2", "six-layer-v1"):
            profile_result = read(f"cost-results/{profile}-{size}.json")
            assert (
                sum(
                    item["placement_class"] == "single_cloud"
                    for item in profile_result["online_placement_results"]
                )
                == 3
            )
            for placement in profile_result["online_placement_results"]:
                if placement["placement_class"] == "single_cloud":
                    assert Decimal(placement["cost"]["category_totals"]["bridge"]) == 0
                    assert (
                        Decimal(placement["cost"]["category_totals"]["transfer"]) == 0
                    )


def test_cross_profile_delta_never_becomes_a_global_winner():
    deltas = read("architecture-deltas.json")
    assert deltas["cross_profile_optimizer_winner_selected"] is False
    assert all(
        row["inherited_l1_l5_assignment"] == row["six_layer_inherited_l1_l5_assignment"]
        for row in deltas["matched_context_cost_deltas"]
    )


def test_research_question_source_digest_rejects_drift(tmp_path):
    package = tmp_path / "evidence"
    shutil.copytree(DEFAULT_PACKAGE, package)
    mapping_path = package / "rq-mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping["research_question_source"]["digest"] = "sha256:" + ("0" * 64)
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")

    with pytest.raises(AssertionError):
        validate_rejections_and_research_mapping(package)


def test_runtime_image_config_covers_every_evaluation_service():
    assert set(configured_digests()) == set(SERVICE_NAMES)


def test_runtime_image_digest_drift_is_rejected():
    expected = {"optimizer": "sha256:" + ("1" * 64)}
    actual = {"optimizer": "sha256:" + ("2" * 64)}
    with pytest.raises(AssertionError):
        compare_digests(expected, actual)
