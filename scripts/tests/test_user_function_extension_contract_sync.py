"""Regression tests for user-function extension contract synchronization."""

from __future__ import annotations

import copy
import json
import unittest

from scripts import sync_user_function_extension_contracts as contract_sync


class UserFunctionExtensionContractSyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = contract_sync._load_runtime()
        cls.root = contract_sync.SOURCE_ROOT / "v1"
        cls.source_files = {
            path.relative_to(cls.root / "examples" / "source" / "valid").as_posix():
            path.read_text(encoding="utf-8")
            for path in (cls.root / "examples" / "source" / "valid").iterdir()
            if path.is_file()
        }
        cls.archive = cls.runtime.deterministic_source_zip(cls.source_files)

    def test_source_and_generated_copies_are_valid_and_identical(self) -> None:
        expected = contract_sync.validate_source()
        self.assertEqual(contract_sync.check(), expected)
        for target in contract_sync.TARGETS:
            self.assertEqual(
                (target / ".contract-sha256").read_text(
                    encoding="utf-8"
                ).strip(),
                expected,
            )

    def test_only_registered_payload_and_schema_projection_objects_are_open(
        self,
    ) -> None:
        findings = []
        for path in sorted(self.root.glob("*.schema.json")):
            schema = contract_sync._load_json(path)

            def walk(value: object, location: str = "$") -> None:
                if isinstance(value, dict):
                    if (
                        value.get("type") == "object"
                        and value.get("additionalProperties") is not False
                    ):
                        findings.append(f"{path.name}:{location}")
                    for field, child in value.items():
                        walk(child, f"{location}.{field}")
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        walk(child, f"{location}[{index}]")

            walk(schema)
        self.assertEqual(
            set(findings),
            {
                (
                    "artifact-manifest.schema.json:"
                    "$.properties.configuration"
                ),
                (
                    "extension-slot.schema.json:"
                    "$.$defs.json_schema_contract.properties.properties"
                ),
                (
                    "extension-slot.schema.json:"
                    "$.$defs.configuration_schema_contract.allOf[1]"
                ),
                (
                    "extension-slot.schema.json:"
                    "$.$defs.configuration_schema_contract.allOf[1]."
                    "properties.properties"
                ),
                (
                    "extension-slot.schema.json:"
                    "$.$defs.configuration_field_schema.allOf[1]"
                ),
                "runtime-envelope.schema.json:$.$defs.base",
                (
                    "runtime-envelope.schema.json:"
                    "$.$defs.input.allOf[1].properties.payload"
                ),
                (
                    "runtime-envelope.schema.json:"
                    "$.$defs.success.allOf[1].properties.payload"
                ),
            },
        )

    def test_required_invalid_fixtures_fail_with_stable_codes(self) -> None:
        expected = {
            "digest-tamper.json": "EXTENSION_SCHEMA_INVALID",
            "platform-field.json": "EXTENSION_SCHEMA_INVALID",
            "runtime-secret-reference.json": "EXTENSION_SCHEMA_INVALID",
            "secret-configuration.json": "EXTENSION_SECRET_MATERIAL_DETECTED",
            "unauthorized-capability.json": "EXTENSION_CAPABILITY_UNAUTHORIZED",
            "unknown-version.json": "EXTENSION_RUNTIME_UNSUPPORTED",
        }
        invalid_root = self.root / "examples" / "invalid"
        self.assertEqual(
            {path.name for path in invalid_root.glob("*.json")},
            set(expected),
        )
        for filename, error_code in expected.items():
            document = contract_sync._load_json(invalid_root / filename)
            with self.subTest(filename=filename):
                with self.assertRaises(
                    self.runtime.ExtensionContractError
                ) as raised:
                    if filename == "digest-tamper.json":
                        self.runtime.validate_artifact_manifest(document)
                    elif filename == "runtime-secret-reference.json":
                        self.runtime.validate_runtime_envelope(document)
                    else:
                        self.runtime.validate_source_archive(
                            metadata=document,
                            archive_bytes=self.archive,
                            created_by=(
                                "00000000-0000-4000-8000-000000000001"
                            ),
                        )
                self.assertEqual(raised.exception.code, error_code)
                self.assertNotIn("def process", str(raised.exception))

    def test_manifest_digest_mutation_fails_closed(self) -> None:
        manifest = contract_sync._load_json(
            self.root / "examples" / "valid-artifact.json"
        )
        mutated_files = dict(self.source_files)
        mutated_files["process.py"] += "\nVALUE = 2\n"
        with self.assertRaises(
            self.runtime.ExtensionContractError
        ) as raised:
            self.runtime.validate_artifact_manifest(
                copy.deepcopy(manifest),
                files=mutated_files,
            )
        self.assertEqual(raised.exception.code, "EXTENSION_SCHEMA_INVALID")

    def test_contract_json_contains_no_secret_reference_surface(self) -> None:
        serialized = json.dumps(
            {
                path.relative_to(self.root).as_posix(): path.read_text(
                    encoding="utf-8"
                )
                for path in self.root.rglob("*.json")
            },
            sort_keys=True,
        ).lower()
        self.assertNotIn('"secret_references"', serialized)
        self.assertNotIn('"credentials"', serialized)


if __name__ == "__main__":
    unittest.main()
