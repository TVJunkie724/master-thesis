"""The research slice must not weaken the complete architecture contracts."""

import hashlib
import json
import re

import pytest

from scripts import prepare_core_evaluation as core


@pytest.mark.parametrize("scenario", core.SCENARIOS)
def test_core_inputs_are_deterministic_incomplete_and_access_free(scenario):
    result = core.materialize(scenario)
    assert result == core.materialize(scenario)
    digest = result.pop("content_digest")
    assert (
        digest
        == "sha256:"
        + hashlib.sha256(
            json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    assert result["execution_enabled"] is False
    assert result["full_architecture_evidence"] is False
    assert result["budget_cap_usd"] is None
    assert result["maximum_runtime_minutes"] is None
    assert len(result["assignments"]) == 6
    assert not any(
        "twin-state" in key or "visualization" in key for key in result["assignments"]
    )
    values = result["tfvars"]
    assert re.fullmatch(r"[a-z][a-z0-9-]{1,20}", values["digital_twin_name"])
    assert values["evaluation_scope"] == "core"
    assert values["layer_4_provider"] == values["layer_5_provider"] == ""
    assert not any(
        marker in key
        for key in values["resolved_component_dimensions"]
        for marker in (
            "twinmaker",
            "digital-twins",
            "bounded-twin",
            "twin-explorer",
            "layer-access",
            "grafana",
        )
    )
    assert not any(key.endswith("_image") for key in values)
    assert not any(
        marker in key
        for key in values
        for marker in ("secret", "credential", "password")
    )


def test_core_matrix_retains_all_three_local_and_six_directed_cases():
    pairs = list(core.SCENARIOS.values())
    assert len(pairs) == 9
    assert sum(source == target for source, target in pairs) == 3
    for name, (source, target) in core.SCENARIOS.items():
        result = core.materialize(name)
        routes = result["tfvars"]["resolved_cross_cloud_routes"]
        if source == target:
            assert routes == result["identity_pairs"] == []
        else:
            assert len(routes) == 3
            assert sorted(result["identity_pairs"]) == sorted(
                [[source, target], [target, source]]
            )
            assert {r["logical_edge_id"] for r in routes} == {
                "edge.ingestion-to-eventing",
                "edge.eventing-to-ingestion",
            }
            assert any(
                "device.command.requested.v1" in r["event_types"] for r in routes
            )
            assert not any(
                event.startswith("twin.") for r in routes for event in r["event_types"]
            )


def test_core_sizing_rejects_full_assignment_and_larger_workload():
    result = core.materialize("core-small-local-gcp")
    small = core.resolve_six_layer_workload(json.loads(core.WORKLOAD_PATH.read_text()))
    with pytest.raises(ValueError):
        core.small_core_evaluation_dimensions(
            {**result["assignments"], "component.twin-state": "gcp"}, small
        )
    medium = core.resolve_six_layer_workload(
        json.loads(core.WORKLOAD_PATH.with_name("core-medium.json").read_text())
    )
    with pytest.raises(ValueError, match="only Small"):
        core.small_core_evaluation_dimensions(result["assignments"], medium)
