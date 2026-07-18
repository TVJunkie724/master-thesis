"""Regression tests for the cross-project deployment contract synchronizer."""

from __future__ import annotations

import copy
import unittest

from scripts import sync_resolved_deployment_contract as contract_sync


class ResolvedDeploymentContractSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = contract_sync._read_json(
            contract_sync.SOURCE_V1 / "schema.json"
        )
        cls.registry = contract_sync._read_json(
            contract_sync.SOURCE_V1 / "deployment-dimensions.json"
        )
        cls.matrix_schema = contract_sync._read_json(
            contract_sync.SOURCE_V1 / "verification-matrix.schema.json"
        )
        cls.matrix = contract_sync._read_json(
            contract_sync.SOURCE_V1 / "verification-matrix.json"
        )

    def validate(self, matrix: dict[str, object]) -> None:
        contract_sync._validate_verification_matrix(
            matrix,
            self.matrix_schema,
            self.registry,
        )

    def test_canonical_source_and_generated_copies_are_valid(self) -> None:
        contract_sync.validate_source()
        contract_sync.check_synchronized()

    def test_matrix_covers_every_deployable_component_and_target(self) -> None:
        registry_targets = {
            component_id: {
                definition["terraform_target"]
                for definition in component["dimensions"].values()
                if definition["classification"] == "deployable_selection"
            }
            for component_id, component in self.registry["components"].items()
            if any(
                definition["classification"] == "deployable_selection"
                for definition in component["dimensions"].values()
            )
        }
        matrix_targets = {
            component_id: set(targets)
            for component_id, targets in self.matrix[
                "expected_targets_by_component"
            ].items()
        }

        self.assertEqual(matrix_targets, registry_targets)

    def test_missing_component_target_is_rejected(self) -> None:
        matrix = copy.deepcopy(self.matrix)
        del matrix["expected_targets_by_component"]["l3_archive.gcp.cloud_storage"]

        with self.assertRaisesRegex(
            RuntimeError,
            "do not cover deployable components exactly",
        ):
            self.validate(matrix)

    def test_unsupported_target_value_is_rejected(self) -> None:
        matrix = copy.deepcopy(self.matrix)
        matrix["expected_targets_by_component"]["l3_archive.aws.s3"][
            "aws_l3_archive_storage_class"
        ] = "STANDARD"

        with self.assertRaisesRegex(RuntimeError, "unsupported value"):
            self.validate(matrix)

    def test_invalid_azure_sku_capacity_combination_is_rejected(self) -> None:
        matrix = copy.deepcopy(self.matrix)
        free_case = matrix["azure_iot_hub_cases"][0]
        free_case["expected_capacity"] = 2

        with self.assertRaisesRegex(RuntimeError, "violates registry constraints"):
            self.validate(matrix)

    def test_wrong_transition_source_owner_is_rejected(self) -> None:
        matrix = copy.deepcopy(self.matrix)
        matrix["storage_transitions"][0]["runtime_component_by_source"]["gcp"] = (
            "transition.l3_hot_to_l3_cool.aws.runtime"
        )

        with self.assertRaisesRegex(RuntimeError, "differs from policy"):
            self.validate(matrix)

    def test_wrong_glue_receiver_owner_is_rejected(self) -> None:
        matrix = copy.deepcopy(self.matrix)
        matrix["glue_component_by_receiver"]["azure"] = "glue.aws.lambda"

        with self.assertRaisesRegex(RuntimeError, "differs from registry policy"):
            self.validate(matrix)

    def test_unknown_fixture_is_rejected(self) -> None:
        matrix = copy.deepcopy(self.matrix)
        matrix["representative_paths"][0]["fixture"] = "missing.json"

        with self.assertRaisesRegex(RuntimeError, "unknown fixture"):
            self.validate(matrix)

    def test_fixture_provider_drift_is_rejected(self) -> None:
        matrix = copy.deepcopy(self.matrix)
        matrix["representative_paths"][0]["providers"]["l2_processing"] = "azure"

        with self.assertRaisesRegex(RuntimeError, "differs from its fixture"):
            self.validate(matrix)

    def test_conflicting_shared_terraform_target_is_rejected(self) -> None:
        matrix = copy.deepcopy(self.matrix)
        registry = copy.deepcopy(self.registry)
        matrix["expected_targets_by_component"][
            "transition.l3_hot_to_l3_cool.azure.runtime"
        ]["azure_l3_function_plan_sku"] = "Y2"
        plan_dimension = registry["components"][
            "transition.l3_hot_to_l3_cool.azure.runtime"
        ]["dimensions"]["azure.functions.plan_sku"]
        plan_dimension["allowed_values"] = ["Y1", "Y2"]

        with self.assertRaisesRegex(RuntimeError, "contradictory values"):
            contract_sync._validate_verification_matrix(
                matrix,
                self.matrix_schema,
                registry,
            )


if __name__ == "__main__":
    unittest.main()
