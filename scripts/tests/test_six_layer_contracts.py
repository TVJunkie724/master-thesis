from __future__ import annotations

import copy
import re
import pytest

from jsonschema import Draft202012Validator, FormatChecker

from scripts import refresh_six_layer_contract_digests as refresh
from scripts import sync_six_layer_contracts as contracts


def _linked_documents():
    return [
        contracts._read(contracts.PROFILE_PATH),
        contracts._read(contracts.CATALOG_PATH),
        *(contracts._read(contracts._provider_path(p)) for p in contracts.PROVIDERS),
    ]


def test_gcp_exclusion_is_explicit_not_silently_incomplete():
    profile = contracts._read(contracts._provider_path("gcp"))
    assert set(profile["excluded_component_ids"]) == {
        "component.twin-state",
        "component.visualization",
    }
    assert "component.hot-storage" in {
        item["component_id"] for item in profile["component_mappings"]
    }
    del profile["excluded_component_ids"]
    profile["content_digest"] = contracts.RUNTIME.calculate_digest(profile)
    with pytest.raises(
        contracts.RUNTIME.ContractError, match="supported logical components"
    ):
        contracts.RUNTIME.validate_document(
            profile,
            bundle_root=contracts.ARCH_V2,
            linked_documents=_linked_documents(),
        )


def test_other_provider_cannot_claim_gcp_scope_exception():
    profile = contracts._read(contracts._provider_path("aws"))
    profile["excluded_component_ids"] = [
        "component.twin-state",
        "component.visualization",
    ]
    profile["content_digest"] = contracts.RUNTIME.calculate_digest(profile)
    with pytest.raises(contracts.RUNTIME.ContractError, match="GCP"):
        contracts.RUNTIME.validate_document(
            profile,
            bundle_root=contracts.ARCH_V2,
            linked_documents=_linked_documents(),
        )


def test_empty_visualization_fixture_cannot_be_relabelled_publishable():
    architecture = contracts._read(contracts.RTA_PATH)
    assert (
        next(
            item
            for item in architecture["component_assignments"]
            if item["logical_component_id"] == "component.visualization"
        )["deployment_specification_component_ids"]
        == []
    )
    architecture["resolution_status"] = "publishable"
    architecture["resolution_id"] = contracts.RUNTIME.calculate_resolution_id(
        architecture
    )
    architecture["content_digest"] = contracts.RUNTIME.calculate_digest(architecture)
    with pytest.raises(
        contracts.RUNTIME.ContractError, match="Only offline pending visualization"
    ):
        contracts.RUNTIME.validate_document(
            architecture,
            bundle_root=contracts.ARCH_V2,
            linked_documents=_linked_documents(),
        )


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
