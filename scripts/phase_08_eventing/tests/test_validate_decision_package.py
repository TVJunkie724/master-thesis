from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "validate_decision_package.py"
SPEC = importlib.util.spec_from_file_location(
    "phase_08_validate_decision_package",
    SCRIPT_PATH,
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {SCRIPT_PATH}")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class DecisionPackageValidationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.artifacts = VALIDATOR.load_artifacts()

    def test_current_package_has_no_findings(self) -> None:
        self.assertEqual(VALIDATOR.validate(strict=True), [])

    def test_duplicate_file_ownership_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["file_ownership"].append(
            copy.deepcopy(manifest["file_ownership"][0])
        )
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("duplicate file ownership path" in error for error in errors)
        )

    def test_incomplete_bridge_route_matrix_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["bridge_route_classes"].pop()
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("manifest bridge route mismatch" in error for error in errors)
        )

    def test_stale_artifact_digest_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["artifact_refs"][0]["digest"] = "sha256:" + ("0" * 64)
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("manifest digest mismatch" in error for error in errors)
        )

    def test_domain_edge_drift_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["logical_edges"][0]["consumer_component_ids"] = [
            "component.historical-persistence"
        ]
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("consumers differ from domain contract" in error for error in errors)
        )

    def test_incomplete_scenario_pair_matrix_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        results = artifacts["scenario-cost-results.json"]
        results["scenarios"][0]["directed_pair_bridge_results"].pop()
        errors: list[str] = []
        VALIDATOR.validate_coverage(artifacts, errors)
        self.assertTrue(
            any("incomplete directed-pair results" in error for error in errors)
        )

    def test_unresolved_runtime_adapter_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["service_components"][0]["runtime_adapter_ids"] = [
            "adapter.unknown@1"
        ]
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(any("unresolved runtime adapter" in error for error in errors))

    def test_unresolved_contract_reference_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["service_components"][0]["contract_refs"] = [
            "unknown-contract@1"
        ]
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("unresolved contract reference" in error for error in errors)
        )

    def test_runtime_source_without_file_owner_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        runtime_path = manifest["runtime_adapters"][0]["source_path"]
        manifest["file_ownership"] = [
            row
            for row in manifest["file_ownership"]
            if row["path"] != runtime_path
        ]
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("implementation path has no file owner" in error for error in errors)
        )

    def test_secret_like_field_is_rejected(self) -> None:
        errors: list[str] = []
        VALIDATOR.validate_secrets(
            "fixture.json",
            {"client_secret": "must-not-exist"},
            errors,
        )
        self.assertEqual(
            errors,
            ["fixture.json:client_secret: secret-like field name"],
        )


if __name__ == "__main__":
    unittest.main()
