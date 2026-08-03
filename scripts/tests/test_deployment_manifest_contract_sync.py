"""Regression tests for DeploymentManifest v3 synchronization."""

from __future__ import annotations

import copy
import sys
from types import ModuleType

from jsonschema import Draft202012Validator, FormatChecker

from scripts import generate_deployment_manifest_fixtures as fixture_generator
from scripts import sync_deployment_manifest_contract as contract_sync


def test_source_and_generated_copies_are_valid_and_identical():
    assert contract_sync.check() == contract_sync.validate_source()


def test_every_top_level_field_is_required():
    schema = contract_sync._read_json(contract_sync.SCHEMA_PATH)
    fixture = contract_sync._read_json(
        contract_sync.VALID_ROOT / "mixed-providers.json"
    )
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    for field in schema["required"]:
        mutated = copy.deepcopy(fixture)
        del mutated[field]
        assert list(validator.iter_errors(mutated)), field


def test_secret_payload_declaration_is_rejected():
    schema = contract_sync._read_json(contract_sync.SCHEMA_PATH)
    fixture = contract_sync._read_json(
        contract_sync.VALID_ROOT / "all-aws.json"
    )
    fixture["credentials"]["contains_secret_payloads"] = True

    assert list(
        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).iter_errors(fixture)
    )


def test_fixture_price_penalty_also_closes_zero_price_tiers():
    values = {"freeTier": {"price": 0}, "paidTier": {"price": 0.25}}

    fixture_generator._scale_price_fields(values, 1_000_000)

    assert values["freeTier"]["price"] == 1_000_000
    assert values["paidTier"]["price"] == 250_000


def test_generated_scenario_assignments_match_fixture_names():
    expected = {
        "all-aws": {"aws"},
        "all-azure": {"azure"},
        "mixed": {"aws", "azure"},
    }

    local_tests = ModuleType("tests")
    local_tests.__path__ = [str(fixture_generator.OPTIMIZER_ROOT / "tests")]
    sys.path.insert(0, str(fixture_generator.OPTIMIZER_ROOT))
    sys.modules["tests"] = local_tests
    try:
        for scenario, providers in expected.items():
            result = fixture_generator._resolved_result(scenario)
            assignments = result["resolvedTwinArchitecture"][
                "component_assignments"
            ]

            assert {item["provider"] for item in assignments} == providers
    finally:
        sys.modules.pop("tests", None)
        sys.path.remove(str(fixture_generator.OPTIMIZER_ROOT))
