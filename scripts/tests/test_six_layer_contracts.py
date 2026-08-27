from __future__ import annotations

import copy
import re

from jsonschema import Draft202012Validator, FormatChecker

from scripts import refresh_six_layer_contract_digests as refresh
from scripts import sync_six_layer_contracts as contracts


def test_standalone_six_layer_contract_bundle_is_valid() -> None:
    contracts.validate_source()


def test_six_layer_is_the_only_shared_profile() -> None:
    profile_root = contracts.DEFINITIONS / "profiles"
    assert sorted(path.name for path in profile_root.iterdir()) == [
        "six-layer-eventing"
    ]


def test_six_layer_manifest_has_no_inheritance() -> None:
    manifest = contracts._read(contracts.DEFINITION_MANIFEST_PATH)
    assert not any(key.startswith("inherited_") for key in manifest)


def test_optimizer_runtime_pin_matches_six_layer_manifest() -> None:
    manifest = contracts._read(contracts.DEFINITION_MANIFEST_PATH)
    source = refresh.OPTIMIZER_ORCHESTRATOR_PATH.read_text(encoding="utf-8")
    match = re.search(
        r'EVENTING_MANIFEST_DIGEST\s*=\s*\(\s*"(sha256:[0-9a-f]{64})"\s*\)',
        source,
    )
    assert match is not None
    assert match.group(1) == manifest["content_digest"]


def test_manifest_v4_requires_every_top_level_field() -> None:
    schema = contracts._read(contracts.MANIFEST_V4 / "schema.json")
    fixture = contracts._read(contracts.DEPLOYMENT_MANIFEST_PATH)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    for field in schema["required"]:
        mutated = copy.deepcopy(fixture)
        del mutated[field]
        assert list(validator.iter_errors(mutated)), field


def test_manifest_v4_embeds_only_current_six_layer_contracts() -> None:
    manifest = contracts._read(contracts.DEPLOYMENT_MANIFEST_PATH)

    assert manifest["manifest_version"] == "4.0"
    assert (
        manifest["resolved_twin_architecture"]["schema_version"]
        == "resolved-twin-architecture.v2"
    )
    assert (
        manifest["resolved_deployment_specification"]["schema_version"]
        == "resolved-deployment-specification.v2"
    )


def test_manifest_v4_rejects_secret_payload_declaration() -> None:
    schema = contracts._read(contracts.MANIFEST_V4 / "schema.json")
    fixture = contracts._read(contracts.DEPLOYMENT_MANIFEST_PATH)
    fixture["credentials"]["contains_secret_payloads"] = True

    errors = Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).iter_errors(fixture)
    assert list(errors)
