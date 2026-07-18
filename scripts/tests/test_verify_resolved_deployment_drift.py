"""Tests for the credential-free deployment drift gate orchestrator."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import verify_resolved_deployment_drift as verification


class DeploymentDriftVerificationTests(unittest.TestCase):
    def test_rejects_e2e_and_cloud_overlay_modes(self) -> None:
        unsafe_environments = (
            {"RUN_E2E_TESTS": "1"},
            {"THESIS_WITH_CREDENTIALS": "true"},
            {"THESIS_CLOUD_CREDENTIAL_OVERLAY": "yes"},
            {"WITH_CREDENTIALS": "on"},
            {"COMPOSE_FILE": "compose.yaml:compose.cloud.local.yaml"},
        )

        for environment in unsafe_environments:
            with self.subTest(environment=environment):
                with self.assertRaises(
                    verification.VerificationConfigurationError
                ):
                    verification.validate_safety(environment)

    def test_sanitized_environment_removes_provider_credentials(self) -> None:
        environment = {
            "PATH": os.environ["PATH"],
            "AWS_ACCESS_KEY_ID": "not-used",
            "ARM_CLIENT_SECRET": "not-used",
            "AZURE_CLIENT_ID": "not-used",
            "GCP_SERVICE_ACCOUNT_JSON": "not-used",
            "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/not-used.json",
            "TF_VAR_cloud_secret": "not-used",
            "RUN_E2E_TESTS": "false",
        }
        runtime_secrets = Path("/tmp/runtime-secrets")

        result = verification.sanitized_environment(
            environment,
            runtime_secrets_dir=runtime_secrets,
        )

        self.assertEqual(result["PATH"], environment["PATH"])
        self.assertEqual(result["RUN_E2E_TESTS"], "0")
        self.assertEqual(
            result["THESIS_RUNTIME_SECRETS_DIR"],
            str(runtime_secrets),
        )
        self.assertTrue(result["AWS_EC2_METADATA_DISABLED"])
        self.assertNotIn("AWS_ACCESS_KEY_ID", result)
        self.assertNotIn("ARM_CLIENT_SECRET", result)
        self.assertNotIn("AZURE_CLIENT_ID", result)
        self.assertNotIn("GCP_SERVICE_ACCOUNT_JSON", result)
        self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS", result)
        self.assertNotIn("TF_VAR_cloud_secret", result)

    def test_ephemeral_runtime_secrets_are_private_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            directory = Path(temporary_root) / "runtime"

            verification.create_ephemeral_runtime_secrets(directory)

            self.assertEqual(
                stat.S_IMODE(directory.stat().st_mode),
                0o700,
            )
            jwt_secret = (directory / "JWT_SECRET_KEY").read_text(
                encoding="utf-8"
            ).strip()
            encryption_key = (directory / "ENCRYPTION_KEY").read_text(
                encoding="utf-8"
            ).strip()
            self.assertGreaterEqual(len(jwt_secret), 64)
            self.assertEqual(len(encryption_key), 44)
            self.assertNotEqual(jwt_secret, encryption_key)
            for path in directory.iterdir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_focused_stages_cover_every_cross_stack_boundary(self) -> None:
        stages = verification.focused_stages("contract-test")
        names = [stage.name for stage in stages]
        rendered = "\n".join(" ".join(stage.command) for stage in stages)

        self.assertEqual(
            names,
            [
                "Compose model",
                "Verification images",
                "Canonical contract and root tests",
                "Optimizer formula-to-selection drift",
                "Management persistence-to-manifest drift",
                "Deployer tfvars and Terraform drift",
            ],
        )
        self.assertIn(
            "tests/unit/calculation_v2/test_deployment_drift_matrix.py",
            rendered,
        )
        self.assertIn("tests/test_deployment_drift_matrix.py", rendered)
        self.assertIn(
            "tests/unit/terraform/test_native_mock_plans.py",
            rendered,
        )
        self.assertNotIn("flutter build", rendered)
        self.assertNotIn("tests/e2e", rendered)
        self.assertNotIn("compose.cloud.local", rendered)

    @unittest.skipUnless(hasattr(os, "getuid"), "POSIX identity required")
    def test_management_stages_use_host_owner_for_private_secrets(self) -> None:
        expected_user = f"{os.getuid()}:{os.getgid()}"
        stages = (
            *verification.focused_stages("contract-test"),
            *verification.full_stages("contract-test"),
        )
        management_commands = [
            stage.command
            for stage in stages
            if "management-api" in stage.command
            and stage.name != "Verification images"
        ]

        self.assertEqual(len(management_commands), 2)
        for command in management_commands:
            with self.subTest(command=command):
                user_index = command.index("--user")
                self.assertEqual(command[user_index + 1], expected_user)

    def test_full_stages_add_safe_project_and_documentation_gates(self) -> None:
        stages = verification.full_stages("contract-test")
        names = [stage.name for stage in stages]
        rendered = "\n".join(" ".join(stage.command) for stage in stages)

        self.assertEqual(
            names,
            [
                "Documentation image",
                "Optimizer full quality gate",
                "Management API full quality gate",
                "Deployer full quality gate",
                "Flutter full quality gate",
                "Documentation strict build",
                "Repository static checks",
            ],
        )
        self.assertIn("--ignore=tests/e2e", rendered)
        self.assertIn("thesis.sh test frontend", rendered)
        self.assertIn("mkdocs build --strict", rendered)
        self.assertNotIn("terraform apply", rendered)

    @patch.object(verification.subprocess, "run")
    def test_stage_runner_stops_at_first_failure(self, run_mock) -> None:
        run_mock.side_effect = (
            subprocess.CompletedProcess(("first",), 0),
            subprocess.CompletedProcess(("second",), 7),
        )
        stages = (
            verification.Stage("first", ("first",)),
            verification.Stage("second", ("second",)),
            verification.Stage("third", ("third",)),
        )

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verification.run_stages(
                stages,
                environment={"PATH": os.environ["PATH"]},
            )

        self.assertEqual(result, 7)
        self.assertEqual(run_mock.call_count, 2)

    @patch.object(verification.subprocess, "run")
    def test_cleanup_removes_only_isolated_compose_resources(
        self,
        run_mock,
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(("docker",), 0)

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verification.cleanup_compose_project(
                "contract-test",
                environment={"PATH": os.environ["PATH"]},
            )

        self.assertEqual(result, 0)
        command = run_mock.call_args.args[0]
        self.assertIn("contract-test", command)
        self.assertIn("docs", command)
        self.assertEqual(command[-3:], ("down", "--volumes", "--remove-orphans"))

    @patch.object(verification.subprocess, "run")
    def test_stage_runner_reports_command_start_failure(self, run_mock) -> None:
        run_mock.side_effect = FileNotFoundError("docker")

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verification.run_stages(
                (verification.Stage("missing", ("docker", "version")),),
                environment={"PATH": os.environ["PATH"]},
            )

        self.assertEqual(result, 127)

    @patch.object(verification.subprocess, "run")
    def test_cleanup_reports_command_start_failure(self, run_mock) -> None:
        run_mock.side_effect = FileNotFoundError("docker")

        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = verification.cleanup_compose_project(
                "contract-test",
                environment={"PATH": os.environ["PATH"]},
            )

        self.assertEqual(result, 127)


if __name__ == "__main__":
    unittest.main()
