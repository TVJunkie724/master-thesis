"""Phase 8.1 five-layer target-decision regression tests."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from architecture_inventory.baseline import (
    BaselineDecisionError,
    _check_bindings,
    _check_component_consistency,
    _check_coverage,
    _check_digest,
    _check_evidence_paths,
    _check_enums,
    _check_eventing_scope,
    _check_proofs,
    _check_provider_bundles,
    _check_scenarios,
    _check_sensitive_material,
    _check_source_digest,
    _check_targets,
    check_baseline_decision,
)
from architecture_inventory.canonical import pretty_json


def _load(repository_root, name):
    return json.loads(
        (
            repository_root / "contracts/architecture-inventory/v1" / name
        ).read_text(encoding="utf-8")
    )


@pytest.fixture
def inventory(repository_root):
    return _load(repository_root, "current-graph.json")


@pytest.fixture
def decision(repository_root):
    return _load(repository_root, "five-layer-baseline-v1-decision.json")


def test_valid_complete_decision(repository_root, inventory):
    counts = check_baseline_decision(
        repository_root,
        inventory,
        lambda _schema_path, _instance: None,
    )

    assert counts == {
        "baseline_component_decisions": 114,
        "baseline_edge_decisions": 90,
        "baseline_provider_candidates": 4,
        "baseline_scenarios": 6,
    }


def test_every_missing_component_decision_is_rejected(inventory, decision):
    for index, component in enumerate(decision["component_decisions"]):
        mutated = deepcopy(decision)
        del mutated["component_decisions"][index]

        with pytest.raises(
            BaselineDecisionError, match="COMPONENT_DECISION_MISSING"
        ) as error:
            _check_coverage(inventory, mutated)

        assert any(
            component["current_implementation_id"] in finding
            for finding in error.value.findings
        )


def test_every_missing_edge_decision_is_rejected(inventory, decision):
    for index, edge in enumerate(decision["edge_decisions"]):
        mutated = deepcopy(decision)
        del mutated["edge_decisions"][index]

        with pytest.raises(
            BaselineDecisionError, match="EDGE_DECISION_MISSING"
        ) as error:
            _check_coverage(inventory, mutated)

        assert any(
            edge["current_edge_id"] in finding
            for finding in error.value.findings
        )


def test_invalid_component_action_is_rejected(decision):
    decision["component_decisions"][0]["action"] = "invent"

    with pytest.raises(BaselineDecisionError, match="FUNCTIONAL_PROOF_MISSING"):
        _check_enums(decision)


def test_invalid_edge_mechanism_is_rejected(decision):
    decision["edge_decisions"][0]["mechanism"] = "implicit_call"

    with pytest.raises(BaselineDecisionError, match="FUNCTIONAL_PROOF_MISSING"):
        _check_enums(decision)


def test_component_logical_mapping_must_match_inventory(inventory, decision):
    decision["component_decisions"][0][
        "current_logical_component_id"
    ] = "component.wrong"

    with pytest.raises(
        BaselineDecisionError, match="TARGET_REFERENCE_UNRESOLVED"
    ):
        _check_component_consistency(inventory, decision)


def test_component_provider_mapping_must_match_inventory(inventory, decision):
    decision["component_decisions"][0]["provider_applicability"] = ["platform"]

    with pytest.raises(
        BaselineDecisionError, match="TARGET_REFERENCE_UNRESOLVED"
    ):
        _check_component_consistency(inventory, decision)


def test_unqualified_logical_component_divergence_is_rejected(
    inventory, decision
):
    component_id = "component.function.dispatcher"
    variants = [
        item
        for item in decision["component_decisions"]
        if item["current_logical_component_id"] == component_id
    ]
    variants[0]["target_responsibility_id"] = "responsibility.processing"

    with pytest.raises(
        BaselineDecisionError, match="TARGET_REFERENCE_UNRESOLVED"
    ):
        _check_component_consistency(inventory, decision)


def test_edge_target_must_match_its_component_decisions(inventory, decision):
    edge = next(
        item for item in decision["edge_decisions"] if item["mechanism"] != "remove"
    )
    edge["source_target_implementation_id"] = (
        decision["component_decisions"][-1]["target_implementation_id"]
    )

    with pytest.raises(
        BaselineDecisionError, match="TARGET_REFERENCE_UNRESOLVED"
    ):
        _check_targets(inventory, decision)


def test_removed_edge_cannot_keep_target_binding(inventory, decision):
    edge = next(
        item for item in decision["edge_decisions"] if item["mechanism"] == "remove"
    )
    edge["target_edge_id"] = "target.edge.stale"
    edge["resource_binding_source"] = "platform_binding"

    with pytest.raises(
        BaselineDecisionError, match="TARGET_REFERENCE_UNRESOLVED"
    ):
        _check_targets(inventory, decision)


@pytest.mark.parametrize("action", ["internalize", "replace", "remove"])
@pytest.mark.parametrize("proof_field", ["functional_proof", "cost_proof"])
def test_non_retain_action_without_proof_is_rejected(
    decision, action, proof_field
):
    component = decision["component_decisions"][0]
    component["action"] = action
    component[proof_field] = ""

    with pytest.raises(BaselineDecisionError, match="FUNCTIONAL_PROOF_MISSING"):
        _check_proofs(decision)


def test_stale_source_inventory_digest_is_rejected(inventory, decision):
    decision["source_inventory_digest"] = "sha256:" + ("0" * 64)

    with pytest.raises(BaselineDecisionError, match="SOURCE_INVENTORY_STALE"):
        _check_source_digest(inventory, decision)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mandatory_capabilities", []),
        ("implementation_component_bundle", []),
    ],
)
def test_incomplete_provider_capability_or_bundle_is_rejected(
    decision, field, value
):
    decision["provider_admissibility"][0][field] = value

    with pytest.raises(
        BaselineDecisionError, match="PROVIDER_BUNDLE_INCOMPLETE"
    ):
        _check_provider_bundles(decision)


@pytest.mark.parametrize(
    "field,value",
    [
        ("deployment_support_status", "incomplete"),
        ("evidence_support_status", "incomplete"),
        ("formula_evidence_complete", False),
        ("pricing_evidence_complete", False),
        ("missing_functionality", ["missing"]),
    ],
)
def test_supported_provider_with_evidence_gap_is_rejected(
    decision, field, value
):
    candidate = decision["provider_admissibility"][0]
    candidate.update(
        {
            "deployment_support_status": "complete",
            "evidence_support_status": "complete",
            "formula_evidence_complete": True,
            "pricing_evidence_complete": True,
            "missing_functionality": [],
            "status": "supported",
        }
    )
    candidate[field] = value

    with pytest.raises(
        BaselineDecisionError, match="PROVIDER_BUNDLE_INCOMPLETE"
    ):
        _check_provider_bundles(decision)


@pytest.mark.parametrize(
    "binding",
    [
        "constructed_name",
        "derived_name",
        "string_convention",
        "suffix_lookup",
        "none",
    ],
)
def test_implicit_or_duplicated_resource_binding_is_rejected(decision, binding):
    edge = next(
        item for item in decision["edge_decisions"] if item["mechanism"] != "remove"
    )
    edge["resource_binding_source"] = binding

    with pytest.raises(
        BaselineDecisionError, match="RESOURCE_BINDING_IMPLICIT"
    ):
        _check_bindings(decision)


def test_eventing_responsibility_is_rejected(decision):
    decision["required_responsibilities"][0][
        "responsibility_id"
    ] = "responsibility.eventing"

    with pytest.raises(BaselineDecisionError, match="EVENTING_SCOPE_LEAK"):
        _check_eventing_scope(decision)


def test_secret_like_material_is_rejected(decision):
    decision["compatibility_rules"][0]["rule"] = (
        "AWS_ACCESS_KEY_ID=not-a-real-value"
    )

    with pytest.raises(BaselineDecisionError, match="FUNCTIONAL_PROOF_MISSING"):
        _check_sensitive_material(decision)


def test_missing_or_escaping_evidence_path_is_rejected(
    repository_root, decision
):
    decision["component_decisions"][0]["decision_evidence"] = [
        "../outside.md#anchor"
    ]

    with pytest.raises(BaselineDecisionError, match="FUNCTIONAL_PROOF_MISSING"):
        _check_evidence_paths(repository_root, decision)


def test_retained_optional_event_path_is_rejected(decision):
    component = next(
        item
        for item in decision["component_decisions"]
        if ".event-checker" in item["current_implementation_id"]
    )
    component["action"] = "retain"

    with pytest.raises(BaselineDecisionError, match="EVENTING_SCOPE_LEAK"):
        _check_eventing_scope(decision)


def test_digest_mutation_is_rejected(decision):
    decision["compatibility_rules"][0]["rule"] += " mutation"

    with pytest.raises(BaselineDecisionError, match="DECISION_DIGEST_MISMATCH"):
        _check_digest(pretty_json(decision), decision)


def test_unsupported_scenario_must_remain_visible(inventory, decision):
    decision["required_scenarios"] = [
        item
        for item in decision["required_scenarios"]
        if item["scenario_id"] != "scenario.all-gcp"
    ]

    with pytest.raises(
        BaselineDecisionError, match="PROVIDER_BUNDLE_INCOMPLETE"
    ):
        _check_scenarios(inventory, decision)


def test_unsupported_scenario_requires_stable_reason(inventory, decision):
    scenario = next(
        item
        for item in decision["required_scenarios"]
        if item["status"] == "unsupported"
    )
    scenario["reason_code"] = ""

    with pytest.raises(
        BaselineDecisionError, match="PROVIDER_BUNDLE_INCOMPLETE"
    ):
        _check_scenarios(inventory, decision)
