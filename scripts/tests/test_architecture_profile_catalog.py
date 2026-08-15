"""Phase 8.3 production-definition and completeness regression tests."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

import pytest

from scripts import sync_architecture_profile_contracts as contract_sync


ROOT = contract_sync.ROOT
sys.path.insert(0, str(ROOT / "3-cloud-deployer"))

from src.architecture_profiles.completeness import (  # noqa: E402
    CatalogCheckError,
    _artifact_digest,
    _verify_artifact_handler,
    check_catalog_completeness,
)
from src.architecture_profiles import completeness as completeness_module  # noqa: E402
from src.architecture_profiles import contracts as deployer_contracts  # noqa: E402
from src.architecture_profiles import registry as registry_module  # noqa: E402


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, document: dict) -> None:
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _mutated_definitions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
) -> None:
    definitions = tmp_path / "definitions"
    shutil.copytree(contract_sync.DEFINITIONS_ROOT, definitions)
    catalog_path = (
        definitions
        / "component-catalogs"
        / "baseline"
        / "1"
        / "catalog.json"
    )
    catalog = _read(catalog_path)
    mutate(catalog)
    catalog["content_digest"] = contract_sync.runtime.calculate_digest(catalog)
    _write(catalog_path, catalog)

    manifest_path = definitions / "manifest.json"
    manifest = _read(manifest_path)
    manifest["definition_digests"]["catalog"] = catalog["content_digest"]
    _write(manifest_path, manifest)
    for fixture_path in (definitions / "fixtures").rglob("*.json"):
        fixture = _read(fixture_path)
        fixture["catalog_ref"]["digest"] = catalog["content_digest"]
        _write(fixture_path, fixture)

    monkeypatch.setattr(completeness_module, "DEFINITIONS_ROOT", definitions)
    monkeypatch.setattr(registry_module, "DEFINITIONS_ROOT", definitions)


def test_production_definitions_are_a_valid_linked_bundle():
    documents = contract_sync.load_definition_documents()
    validated = contract_sync.runtime.validate_bundle(
        documents,
        bundle_root=contract_sync.SOURCE_V1,
    )
    assert len(validated) == 5
    providers = {
        document["provider"]: document
        for document in documents
        if document["schema_version"] == "provider-implementation-profile.v1"
    }
    assert providers["aws"]["supported"] is True
    assert providers["azure"]["supported"] is True
    assert providers["gcp"]["supported"] is False
    assert providers["gcp"]["capability_claims"]["missing_capability_ids"] == [
        "capability.twin-state",
        "capability.visualization",
    ]


def test_completeness_gate_checks_every_repository_binding():
    report = check_catalog_completeness(ROOT)
    assert report["status"] == "complete"
    assert report["profile"]["logical_components"] == 7
    assert report["catalog"] == {
        "id": "baseline-component-catalog",
        "version": "1",
        "digest": report["catalog"]["digest"],
        "deployment_components": 22,
        "edge_implementations": 36,
        "package_artifacts": 50,
        "terraform_resources": 51,
    }
    assert report["fixtures"]["scenario.all-gcp"] == {
        "status": "unsupported",
        "reason_code": "PROFILE_PROVIDER_CAPABILITY_INCOMPLETE",
    }


def test_package_digest_rejects_symlinked_source(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    target = tmp_path / "target.py"
    target.write_text("pass\n", encoding="utf-8")
    (source / "unsafe.py").symlink_to(target)

    with pytest.raises(CatalogCheckError) as raised:
        _artifact_digest(tmp_path, "source")
    assert raised.value.code == "CATALOG_PACKAGE_REFERENCE_INVALID"


def test_package_handler_must_resolve_to_a_real_callable(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("def other():\n    pass\n", encoding="utf-8")

    with pytest.raises(CatalogCheckError) as raised:
        _verify_artifact_handler(
            tmp_path,
            {
                "artifact_id": "artifact.test.missing-handler",
                "repository_source_path": "source",
                "platform_handler": "main.main",
            },
        )
    assert raised.value.code == "CATALOG_PACKAGE_REFERENCE_INVALID"


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (
            lambda catalog: catalog["components"][0]["terraform_binding"][
                "resource_addresses"
            ].__setitem__(0, "unknown_resource.missing"),
            "CATALOG_TERRAFORM_REFERENCE_INVALID",
        ),
        (
            lambda catalog: catalog["components"][0]["formula_refs"].__setitem__(
                0, "unknown_formula"
            ),
            "CATALOG_FORMULA_REFERENCE_INVALID",
        ),
        (
            lambda catalog: catalog["components"][0][
                "deployment_specification_bindings"
            ][0].__setitem__("component_id", "unknown.dimension"),
            "ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE",
        ),
        (
            lambda catalog: catalog["components"][0][
                "required_permission_capabilities"
            ].__setitem__(0, "permission.aws.thesis-demo-v1.unknown"),
            "CATALOG_PERMISSION_REFERENCE_INVALID",
        ),
        (
            lambda catalog: catalog["components"][0]["pricing_model_refs"].__setitem__(
                0, "pricing-intent.unknown"
            ),
            "CATALOG_PRICING_REFERENCE_INVALID",
        ),
        (
            lambda catalog: catalog["package_artifacts"][0].__setitem__(
                "source_digest", f"sha256:{'0' * 64}"
            ),
            "CATALOG_PACKAGE_DIGEST_MISMATCH",
        ),
        (
            lambda catalog: catalog["package_artifacts"][1].__setitem__(
                "repository_source_path",
                catalog["package_artifacts"][0]["repository_source_path"],
            ),
            "CATALOG_DUPLICATE_OWNERSHIP",
        ),
        (
            lambda catalog: catalog["package_artifacts"][0].__setitem__(
                "platform_handler", "missing.main"
            ),
            "CATALOG_PACKAGE_REFERENCE_INVALID",
        ),
    ],
    ids=[
        "terraform",
        "formula",
        "deployment-dimension",
        "permission",
        "pricing",
        "package-digest",
        "duplicate-package-source",
        "handler",
    ],
)
def test_completeness_gate_rejects_repository_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    expected_code: str,
):
    _mutated_definitions(tmp_path, monkeypatch, mutate)

    with pytest.raises(
        (CatalogCheckError, deployer_contracts.ContractError)
    ) as raised:
        check_catalog_completeness(ROOT)
    assert raised.value.code == expected_code


def test_definition_manifest_pins_decision_and_catalog_digests():
    manifest = _read(
        ROOT / "contracts" / "architecture-profiles" / "definitions" / "manifest.json"
    )
    decision = _read(
        ROOT
        / "contracts"
        / "architecture-inventory"
        / "v1"
        / "five-layer-baseline-v1-decision.json"
    )
    catalog = _read(
        ROOT
        / "contracts"
        / "architecture-profiles"
        / "definitions"
        / "component-catalogs"
        / "baseline"
        / "1"
        / "catalog.json"
    )
    inventory = _read(
        ROOT
        / "contracts"
        / "architecture-inventory"
        / "v1"
        / "current-graph.json"
    )
    assert (
        manifest["source_digests"]["baseline_decision"]
        == decision["content_digest"]
    )
    assert manifest["definition_digests"]["catalog"] == catalog["content_digest"]
    assert (
        manifest["source_digests"]["architecture_inventory"]
        == inventory["content_digest"]
    )
    assert set(manifest["source_digests"]["package_builders"]) == {
        "aws",
        "azure",
        "common",
        "gcp",
        "user",
    }


def test_profile_preserves_phase_8_1_slots_and_completeness_rules_exactly():
    profile = _read(
        ROOT
        / "contracts"
        / "architecture-profiles"
        / "definitions"
        / "profiles"
        / "five-layer-baseline"
        / "1"
        / "profile.json"
    )
    decision = _read(
        ROOT
        / "contracts"
        / "architecture-inventory"
        / "v1"
        / "five-layer-baseline-v1-decision.json"
    )

    assert profile["optimization_slot_ids"] == decision["optimization_slots"]
    assert (
        profile["functional_completeness_rules"]
        == decision["functional_completeness_rules"]
    )


def test_catalog_covers_every_phase_8_3_decision_and_deployment_dimension():
    catalog = _read(
        ROOT
        / "contracts"
        / "architecture-profiles"
        / "definitions"
        / "component-catalogs"
        / "baseline"
        / "1"
        / "catalog.json"
    )
    decision = _read(
        ROOT
        / "contracts"
        / "architecture-inventory"
        / "v1"
        / "five-layer-baseline-v1-decision.json"
    )
    dimensions = _read(
        ROOT
        / "contracts"
        / "resolved-deployment-specification"
        / "v1"
        / "deployment-dimensions.json"
    )

    component_decisions = [
        decision_id
        for owner in (*catalog["components"], *catalog["package_artifacts"])
        for decision_id in owner["decision_implementation_ids"]
    ]
    expected_component_decisions = {
        item["target_implementation_id"]
        for item in decision["component_decisions"]
        if item["action"] == "retain"
        and item["implementation_owner_phase"]
        in {"Phase 8.3", "Phase 8.3 after #113"}
    }
    edge_decisions = [
        decision_id
        for edge in catalog["edge_implementations"]
        for decision_id in edge["decision_edge_ids"]
    ]
    activated_phase_8_6_edges = {
        "target.edge.runtime.aws.l4-to-l5",
        "target.edge.runtime.azure.l4-to-l5",
        "target.edge.runtime.mixed.l4-to-l5",
    }
    expected_edge_decisions = {
        item["target_edge_id"]
        for item in decision["edge_decisions"]
        if item["implementation_owner_phase"] == "Phase 8.3"
        or item["target_edge_id"] in activated_phase_8_6_edges
    }
    dimension_bindings = [
        binding["component_id"]
        for component in catalog["components"]
        for binding in component["deployment_specification_bindings"]
    ]

    assert len(component_decisions) == len(set(component_decisions)) == 51
    assert set(component_decisions) == expected_component_decisions
    assert len(edge_decisions) == len(set(edge_decisions)) == 36
    assert set(edge_decisions) == expected_edge_decisions
    assert len(dimension_bindings) == len(set(dimension_bindings)) == 42
    assert set(dimension_bindings) == set(dimensions["components"])


def test_processing_packages_own_the_reviewed_persister_dependency():
    catalog = _read(
        ROOT
        / "contracts"
        / "architecture-profiles"
        / "definitions"
        / "component-catalogs"
        / "baseline"
        / "1"
        / "catalog.json"
    )
    artifacts = {
        artifact["artifact_id"]: artifact
        for artifact in catalog["package_artifacts"]
    }

    for provider in ("aws", "azure", "gcp"):
        processing = artifacts[f"artifact.{provider}.processing"]
        assert processing["dependency_artifact_refs"] == [
            {"id": f"artifact.{provider}.shared-runtime", "version": "1"},
            {"id": f"artifact.{provider}.processing-persister", "version": "1"},
        ]


def test_cross_provider_twin_read_uses_the_hot_storage_side_glue():
    catalog = _read(
        ROOT
        / "contracts"
        / "architecture-profiles"
        / "definitions"
        / "component-catalogs"
        / "baseline"
        / "1"
        / "catalog.json"
    )
    mixed_read_edges = [
        edge
        for edge in catalog["edge_implementations"]
        if ".mixed." in edge["decision_edge_ids"][0]
        and edge["decision_edge_ids"][0].endswith(".l3-hot-to-l4")
    ]

    assert mixed_read_edges
    for edge in mixed_read_edges:
        source_provider = edge["source_output_port_id"].split(".", 2)[1]
        assert edge["glue_component_ids"] == [
            f"deployment.{source_provider}.cross-cloud-glue"
        ]


def test_profile_uses_current_pricing_registry_identifiers():
    profile = _read(
        ROOT
        / "contracts"
        / "architecture-profiles"
        / "definitions"
        / "profiles"
        / "five-layer-baseline"
        / "1"
        / "profile.json"
    )

    assert profile["optimization_bundle"] == {
        "optimization_strategy_id": "cost_minimization_v1",
        "optimization_strategy_version": "1",
        "calculation_strategy_id": "cost_calculation_v2",
        "calculation_strategy_version": "2",
        "formula_set_id": "cost_formula_set_v1",
        "formula_set_version": "1",
        "scoring_strategy_id": "min_total_cost_v1",
        "scoring_strategy_version": "1",
        "pricing_registry_id": "pricing-registry",
        "pricing_registry_versions": ["1"],
        "workload_contract_id": "digital_twin_workload_v1",
        "workload_contract_version": "1",
        "deployment_specification_versions": [
            "resolved-deployment-specification.v1"
        ],
        "compatibility_digest": profile["optimization_bundle"][
            "compatibility_digest"
        ],
    }
