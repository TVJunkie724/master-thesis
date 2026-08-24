"""Regression tests for guided cloud-bootstrap contract synchronization."""

from __future__ import annotations

import json
import unittest

from jsonschema import Draft202012Validator, FormatChecker

from scripts import sync_cloud_bootstrap_contracts as contract_sync


class CloudBootstrapContractSyncTests(unittest.TestCase):
    def test_source_and_generated_copies_are_valid_and_identical(self) -> None:
        expected = contract_sync.validate_source()
        self.assertEqual(contract_sync.check(), expected)
        for target in contract_sync.TARGETS:
            self.assertEqual(
                (target / ".contract-sha256").read_text(encoding="utf-8").strip(),
                expected,
            )

    def test_every_schema_is_draft_2020_12_valid(self) -> None:
        for path in sorted((contract_sync.SOURCE_ROOT / "v1").glob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema, format_checker=FormatChecker())

    def test_response_contracts_expose_no_secret_value_fields(self) -> None:
        forbidden = {
            "secret_access_key",
            "session_token",
            "client_secret",
            "private_key",
            "service_account_json",
            "credential_payload",
        }
        for name in (
            "cloud-bootstrap-guide.schema.json",
            "cloud-bootstrap-session.schema.json",
        ):
            schema = json.loads(
                (contract_sync.SOURCE_ROOT / "v1" / name).read_text(encoding="utf-8")
            )
            serialized = json.dumps(schema, sort_keys=True)
            for field in forbidden:
                self.assertNotIn(f'"{field}"', serialized)

    def test_gcp_api_baseline_is_bounded_and_owned_by_active_authority(self) -> None:
        baseline = json.loads(
            (
                contract_sync.SOURCE_ROOT / "v1" / "gcp-phase8-api-baseline.json"
            ).read_text(encoding="utf-8")
        )
        authority = json.loads(
            contract_sync.AUTHORITY_PACK_SOURCES[
                "v1/authority-packs/gcp.json"
            ].read_text(encoding="utf-8")
        )
        permissions = {
            permission
            for group in authority["permission_groups"]
            for permission in group["permissions"]
        }

        self.assertEqual(baseline["owner"], "bootstrap.gcp.admin-v3")
        self.assertEqual(authority["contract_id"], baseline["owner"])
        self.assertEqual(authority["target_modes"], ["existing_project"])
        self.assertEqual(len(baseline["services"]), 19)
        self.assertLessEqual(len(baseline["services"]), 20)
        self.assertIn("serviceusage.services.enable", permissions)
        self.assertIn("serviceusage.operations.get", permissions)

    def test_gcp_guide_contract_rejects_organization_target(self) -> None:
        guide = json.loads(
            (
                contract_sync.SOURCE_ROOT
                / "v1"
                / "fixtures"
                / "valid"
                / "aws-guide.json"
            ).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (
                contract_sync.SOURCE_ROOT
                / "v1"
                / "gcp-phase8-api-baseline.json"
            ).read_text(encoding="utf-8")
        )
        guide.update(
            provider="gcp",
            target={
                "provider": "gcp",
                "mode": "organization",
                "bootstrap_project_id": "thesis-admin-project",
                "organization_id": "123456789",
                "billing_account_id": "ABCDEF-123456-ABCDEF",
                "region": "europe-west1",
            },
            api_baseline={
                "id": baseline["baseline_id"],
                "digest": "sha256:" + ("a" * 64),
                "services": baseline["services"],
                "retain_enabled": True,
                "mutation_summary": baseline["mutation_summary"],
                "limitations": baseline["limitations"],
                "artifact_url": "https://example.com/gcp/api-baseline",
            },
        )
        schema = json.loads(
            (
                contract_sync.SOURCE_ROOT
                / "v1"
                / "cloud-bootstrap-guide.schema.json"
            ).read_text(encoding="utf-8")
        )

        errors = list(Draft202012Validator(schema).iter_errors(guide))

        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
