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
        for name in ("cloud-bootstrap-guide.schema.json", "cloud-bootstrap-session.schema.json"):
            schema = json.loads(
                (contract_sync.SOURCE_ROOT / "v1" / name).read_text(encoding="utf-8")
            )
            serialized = json.dumps(schema, sort_keys=True)
            for field in forbidden:
                self.assertNotIn(f'"{field}"', serialized)


if __name__ == "__main__":
    unittest.main()
