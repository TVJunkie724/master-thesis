"""Contract tests for host-neutral behavior in the root Bash entrypoint."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "thesis.sh"


class ThesisEntrypointTests(unittest.TestCase):
    def run_bash(
        self,
        expression: str,
        *,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        merged_environment = os.environ.copy()
        merged_environment.update(environment or {})
        return subprocess.run(
            ["bash", "-c", f'source "{SCRIPT}"; {expression}'],
            cwd=ROOT,
            env=merged_environment,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_resolves_all_supported_desktop_hosts(self) -> None:
        cases = {
            "Darwin": "macos",
            "Linux": "linux",
            "MINGW64_NT-10.0": "windows",
            "MSYS_NT-10.0": "windows",
            "CYGWIN_NT-10.0": "windows",
        }

        for host, expected in cases.items():
            with self.subTest(host=host):
                result = self.run_bash(f'resolve_host_desktop_device "{host}"')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

    def test_unknown_host_fails_without_macos_fallback(self) -> None:
        result = self.run_bash('resolve_host_desktop_device "FreeBSD"')

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("Unsupported host 'FreeBSD'", result.stderr)
        self.assertIn("THESIS_FLUTTER_DEVICE", result.stderr)

    def test_explicit_device_override_wins(self) -> None:
        result = self.run_bash(
            'ensure_flutter_device; printf "%s" "$FLUTTER_DEVICE"',
            environment={
                "THESIS_FLUTTER_DEVICE": "chrome",
                "THESIS_HOST_OS_OVERRIDE": "FreeBSD",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "chrome")

    def test_implicit_device_uses_detected_host(self) -> None:
        result = self.run_bash(
            'ensure_flutter_device; printf "%s" "$FLUTTER_DEVICE"',
            environment={
                "THESIS_FLUTTER_DEVICE": "",
                "THESIS_HOST_OS_OVERRIDE": "MSYS_NT-10.0",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "windows")

    def test_explicit_python_three_command_is_validated_and_preserved(self) -> None:
        result = self.run_bash(
            'ensure_python_command; printf "%s" "$PYTHON_COMMAND"',
            environment={"THESIS_PYTHON_COMMAND": sys.executable},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, sys.executable)

    def test_deployment_contract_forwards_focused_mode(self) -> None:
        result = self.run_bash(
            "main test deployment-contract --focused",
            environment={"THESIS_PYTHON_COMMAND": "echo"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "scripts/verify_resolved_deployment_drift.py --focused",
            result.stdout,
        )

    def test_deployment_contract_rejects_unknown_options(self) -> None:
        result = self.run_bash(
            "main test deployment-contract --live",
            environment={"THESIS_PYTHON_COMMAND": "echo"},
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn(
            "test deployment-contract accepts only --focused",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
