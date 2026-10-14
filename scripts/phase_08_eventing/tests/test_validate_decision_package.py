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
        manifest["file_ownership"].append(copy.deepcopy(manifest["file_ownership"][0]))
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("duplicate file ownership path" in error for error in errors)
        )

    def test_planning_collision_check_rejects_an_implemented_new_target(
        self,
    ) -> None:
        errors: list[str] = []

        VALIDATOR.validate_manifest(
            copy.deepcopy(self.artifacts),
            errors,
            require_new_targets_absent=True,
        )

        self.assertIn(
            "new target already exists: contracts/deployment-manifest/v4/schema.json",
            errors,
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

    def test_incomplete_bridge_profile_binding_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["bridge_route_classes"][0]["profile_bindings"].pop()
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("incomplete profile route bindings" in error for error in errors)
        )

    def test_wrong_bridge_profile_component_scope_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        binding = manifest["bridge_route_classes"][0]["profile_bindings"][0]
        binding["source_telemetry_component_ids"] = [
            "deployment.aws.embedded.bridge-kinesis"
        ]
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("has the wrong provider or profile scope" in error for error in errors)
        )

    def test_wrong_same_scope_bridge_component_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        binding = manifest["bridge_route_classes"][0]["profile_bindings"][0]
        binding["source_telemetry_component_ids"] = ["deployment.aws.event.sns-fifo"]
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any(
                "components differ from exact six-layer-eventing@1 binding" in error
                for error in errors
            )
        )

    def test_bridge_source_component_without_adapter_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        component = next(
            row
            for row in manifest["service_components"]
            if row["deployment_component_id"]
            == "deployment.azure.event.event-hubs-standard"
        )
        component["runtime_adapter_ids"].remove("adapter.azure.bridge@1")
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(
            any("does not own the route bridge adapter" in error for error in errors)
        )

    def test_stale_artifact_digest_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["artifact_refs"][0]["digest"] = "sha256:" + ("0" * 64)
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(any("manifest digest mismatch" in error for error in errors))

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

    def test_incomplete_projection_event_registry_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        registry = artifacts["bridge-decision.json"]["envelope_contract"][
            "event_type_registry"
        ]
        registry["profile_extension_event_types"].pop()
        errors: list[str] = []

        VALIDATOR.validate_event_type_registry(artifacts, errors)

        self.assertIn(
            "bridge Twin-projection event registry is incomplete",
            errors,
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

    def test_missing_capability_row_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        matrix = artifacts["provider-capability-matrix.json"]
        matrix["capability_rows"] = [
            row
            for row in matrix["capability_rows"]
            if row["capability_id"] != "capability.direct-edge.cross-cloud-transport"
        ]
        errors: list[str] = []
        VALIDATOR.validate_coverage(artifacts, errors)
        self.assertTrue(
            any("embedded capability coverage mismatch" in error for error in errors)
        )

    def test_bifromq_formula_input_drift_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        ledger = artifacts["formula-and-unit-ledger.json"]
        formula = next(
            row
            for row in ledger["formulas"]
            if row["formula_id"] == "formula.gcp.bifromq-gke"
        )
        formula["inputs"].remove("lb_processing_gib_price")
        errors: list[str] = []
        VALIDATOR.validate_reference_integrity(artifacts, errors)
        self.assertIn(
            "BifroMQ formula input/expression contract mismatch",
            errors,
        )

    def test_incomplete_capacity_allocation_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        matrix = artifacts["provider-capability-matrix.json"]
        matrix["capacity_allocations"].pop()
        errors: list[str] = []
        VALIDATOR.validate_coverage(artifacts, errors)
        self.assertTrue(
            any("capacity allocation coverage mismatch" in error for error in errors)
        )

    def test_missing_aws_outbound_identity_preflight_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        aws = next(
            row for row in manifest["provider_requirements"] if row["provider"] == "aws"
        )
        aws["preflight_gates"].remove("regional_STS_endpoint_for_GetWebIdentityToken")
        errors: list[str] = []
        VALIDATOR.validate_coverage(artifacts, errors)
        self.assertIn(
            "AWS provider outbound identity preflight is incomplete",
            errors,
        )

    def test_rejected_alternative_without_pricing_disposition_is_rejected(
        self,
    ) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        pricing = artifacts["pricing-model-matrix.json"]
        pricing["rejected_member_dimensions"].pop()
        errors: list[str] = []
        VALIDATOR.validate_coverage(artifacts, errors)
        self.assertTrue(
            any(
                "rejected alternative capability/pricing coverage mismatch" in error
                for error in errors
            )
        )

    def test_unresolved_runtime_adapter_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["service_components"][0]["runtime_adapter_ids"] = ["adapter.unknown@1"]
        errors: list[str] = []
        VALIDATOR.validate_manifest(artifacts, errors)
        self.assertTrue(any("unresolved runtime adapter" in error for error in errors))

    def test_unresolved_contract_reference_is_rejected(self) -> None:
        artifacts = copy.deepcopy(self.artifacts)
        manifest = artifacts["implementation-component-manifest.json"]
        manifest["service_components"][0]["contract_refs"] = ["unknown-contract@1"]
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
            row for row in manifest["file_ownership"] if row["path"] != runtime_path
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
