from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from scripts.check_flutter_architecture import audit, main


class FlutterArchitectureCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def write(self, relative: str, content: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def findings(self) -> list[tuple[str, str, int]]:
        return [(item.rule_id, item.path, item.line) for item in audit(self.root)]

    def test_clean_layered_fixture_passes(self) -> None:
        self.write(
            "twin2multicloud_flutter/lib/screens/home.dart",
            "import 'package:flutter/material.dart';\nclass Home {}\n",
        )
        self.assertEqual(self.findings(), [])

    def test_credential_labels_and_model_fields_are_not_secret_values(self) -> None:
        self.write(
            "twin2multicloud_flutter/lib/widgets/credential_form.dart",
            "const label = 'Client secret';\nconst field = 'private_key_id';\n",
        )
        self.assertEqual(self.findings(), [])

    def test_direct_provider_service_url_fails(self) -> None:
        self.write(
            "twin2multicloud_flutter/lib/services/bad.dart",
            "const endpoint = 'http://localhost:5003/calculate';\n",
        )
        self.assertEqual(
            self.findings(),
            [
                (
                    "FLUTTER-DIRECT-SERVICE",
                    "twin2multicloud_flutter/lib/services/bad.dart",
                    1,
                )
            ],
        )

    def test_presentation_http_import_and_symbol_fail(self) -> None:
        self.write(
            "twin2multicloud_flutter/lib/screens/bad.dart",
            "import 'package:dio/dio.dart';\nApiService? service;\n",
        )
        rules = [rule for rule, _, _ in self.findings()]
        self.assertEqual(rules, ["FLUTTER-PRESENTATION-HTTP"] * 2)

    def test_secret_output_is_redacted(self) -> None:
        secret = "sk-thisMustNeverAppearInOutput123456"
        self.write(
            "twin2multicloud_flutter/lib/demo/fixture.dart",
            f"const token = '{secret}';\n",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--root", str(self.root)])
        self.assertEqual(result, 1)
        self.assertIn("FLUTTER-SECRET-LITERAL", output.getvalue())
        self.assertNotIn(secret, output.getvalue())

    def test_multiline_private_key_is_redacted(self) -> None:
        self.write(
            "twin2multicloud_flutter/assets/demo/credential_fixture.json",
            '{"private_key":"-----BEGIN PRIVATE KEY-----\\nunsafe\\n"}',
        )
        rendered = "\n".join(item.render() for item in audit(self.root))
        self.assertIn("FLUTTER-SECRET-LITERAL", rendered)
        self.assertNotIn("unsafe", rendered)

    def test_diagnostic_reports_exact_line(self) -> None:
        self.write(
            "twin2multicloud_flutter/lib/core/bad.dart",
            "void run() {\n  debugPrint('unsafe');\n}\n",
        )
        self.assertEqual(
            self.findings(),
            [
                (
                    "FLUTTER-DIAGNOSTIC",
                    "twin2multicloud_flutter/lib/core/bad.dart",
                    2,
                )
            ],
        )

    def test_missing_optional_directories_do_not_fail(self) -> None:
        self.assertEqual(self.findings(), [])

    def test_non_utf8_source_fails_closed_without_content(self) -> None:
        path = self.root / "twin2multicloud_flutter/lib/screens/binary.dart"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\xff\xfeprivate")
        rendered = "\n".join(item.render() for item in audit(self.root))
        self.assertIn("FLUTTER-SOURCE-READ", rendered)
        self.assertIn("twin2multicloud_flutter/lib/screens/binary.dart:1", rendered)
        self.assertNotIn("private", rendered)

    def test_absolute_credential_path_fails_but_filename_label_passes(self) -> None:
        self.write(
            "twin2multicloud_flutter/lib/widgets/file_help.dart",
            "const expected = 'config_credentials.json';\n"
            "const unsafe = '/Users/example/secrets/google-credentials.json';\n",
        )
        self.assertEqual(
            self.findings(),
            [
                (
                    "FLUTTER-SECRET-LITERAL",
                    "twin2multicloud_flutter/lib/widgets/file_help.dart",
                    2,
                )
            ],
        )

    def test_demo_config_rejects_runtime_keys(self) -> None:
        self.write(
            "twin2multicloud_flutter/config/demo.json",
            '{"API_BASE_URL":"http://localhost:5005"}',
        )
        self.assertEqual(
            self.findings(),
            [
                (
                    "FLUTTER-RUNTIME-CONFIG",
                    "twin2multicloud_flutter/config/demo.json",
                    1,
                ),
            ],
        )

    def test_runtime_keys_are_owned_only_by_explicit_profile_sources(self) -> None:
        self.write(
            "twin2multicloud_flutter/lib/config/app_runtime.dart",
            "const key = 'DEV_AUTH_TOKEN';\n",
        )
        self.write(
            "twin2multicloud_flutter/config/production.example.json",
            '{"APP_MODE":"production","API_BASE_URL":"https://api.example"}',
        )
        self.write(
            "twin2multicloud_flutter/lib/services/defaults.dart",
            "const unsafe = 'DEV_AUTH_TOKEN';\n",
        )

        self.assertEqual(
            self.findings(),
            [
                (
                    "FLUTTER-RUNTIME-CONFIG",
                    "twin2multicloud_flutter/lib/services/defaults.dart",
                    1,
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
