#!/usr/bin/env python3
"""Run the credential-free Resolved Deployment Specification drift gate."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "compose.yaml"
DEFAULT_PROJECT = "master-thesis-deployment-contract"
TRUTHY = frozenset({"1", "true", "yes", "on"})
CREDENTIAL_ENV_PREFIXES = (
    "ARM_",
    "AWS_",
    "AZURE_",
    "CLOUDSDK_",
    "GCP_",
    "GOOGLE_",
    "TF_VAR_",
)
CREDENTIAL_ENV_KEYS = frozenset(
    {
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
        "AZURE_TENANT_ID",
        "GOOGLE_APPLICATION_CREDENTIALS",
    }
)
OVERLAY_ENV_KEYS = (
    "THESIS_WITH_CREDENTIALS",
    "THESIS_CLOUD_CREDENTIAL_OVERLAY",
    "WITH_CREDENTIALS",
)


class VerificationConfigurationError(RuntimeError):
    """Raised when the requested gate could permit provider-side effects."""


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    cwd: Path = ROOT


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in TRUTHY


def validate_safety(environment: Mapping[str, str]) -> None:
    """Reject explicit live/E2E modes before starting any subprocess."""

    if _is_truthy(environment.get("RUN_E2E_TESTS")):
        raise VerificationConfigurationError(
            "RUN_E2E_TESTS must be disabled for the deployment contract gate."
        )
    for key in OVERLAY_ENV_KEYS:
        if _is_truthy(environment.get(key)):
            raise VerificationConfigurationError(
                f"{key} enables a credential overlay and is forbidden."
            )

    compose_files = environment.get("COMPOSE_FILE", "")
    if "compose.cloud.local" in compose_files:
        raise VerificationConfigurationError(
            "COMPOSE_FILE must not include compose.cloud.local.yaml."
        )


def sanitized_environment(
    environment: Mapping[str, str],
    *,
    runtime_secrets_dir: Path,
) -> dict[str, str]:
    """Return an environment without provider credentials or live-test flags."""

    sanitized = {
        key: value
        for key, value in environment.items()
        if key not in CREDENTIAL_ENV_KEYS
        and not key.startswith(CREDENTIAL_ENV_PREFIXES)
    }
    sanitized.update(
        {
            "RUN_E2E_TESTS": "0",
            "THESIS_RUNTIME_SECRETS_DIR": str(runtime_secrets_dir),
            "TF_IN_AUTOMATION": "1",
            "TF_INPUT": "0",
            "AWS_EC2_METADATA_DISABLED": "true",
            "CHECKPOINT_DISABLE": "1",
        }
    )
    return sanitized


def create_ephemeral_runtime_secrets(directory: Path) -> None:
    """Create non-cloud application secrets required by the Compose model."""

    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    values = {
        "JWT_SECRET_KEY": secrets.token_urlsafe(64),
        "ENCRYPTION_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(
            "ascii"
        ),
    }
    for filename, value in values.items():
        path = directory / filename
        path.write_text(f"{value}\n", encoding="utf-8")
        path.chmod(0o600)


def _compose_prefix(project: str) -> tuple[str, ...]:
    return (
        "docker",
        "compose",
        "-p",
        project,
        "-f",
        str(COMPOSE_FILE),
    )


def _compose_run(
    project: str,
    service: str,
    *command: str,
    root_mount: bool = False,
    environment: Sequence[str] = (),
    user: str | None = None,
) -> tuple[str, ...]:
    result = [
        *_compose_prefix(project),
        "run",
        "--rm",
        "--no-deps",
        "-T",
    ]
    if user is not None:
        result.extend(("--user", user))
    if root_mount:
        result.extend(("-v", f"{ROOT}:/workspace:ro", "-w", "/workspace"))
    for value in environment:
        result.extend(("-e", value))
    result.append(service)
    result.extend(command)
    return tuple(result)


def _host_user_spec() -> str | None:
    """Return the POSIX host identity that owns private ephemeral secrets."""

    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return None
    return f"{getuid()}:{getgid()}"


def focused_stages(project: str) -> tuple[Stage, ...]:
    """Return the deterministic cross-stack drift stages."""

    return (
        Stage(
            "Compose model",
            (*_compose_prefix(project), "config", "--quiet"),
        ),
        Stage(
            "Verification images",
            (
                *_compose_prefix(project),
                "build",
                "2twin2clouds",
                "3cloud-deployer",
                "management-api",
            ),
        ),
        Stage(
            "Canonical contract and root tests",
            _compose_run(
                project,
                "3cloud-deployer",
                "sh",
                "-lc",
                (
                    "python scripts/sync_resolved_deployment_contract.py --check "
                    "&& python -m unittest "
                    "scripts.tests.test_resolved_deployment_contract_sync "
                    "scripts.tests.test_verify_resolved_deployment_drift "
                    "scripts.tests.test_thesis_entrypoint"
                ),
                root_mount=True,
            ),
        ),
        Stage(
            "Optimizer formula-to-selection drift",
            _compose_run(
                project,
                "2twin2clouds",
                "python",
                "-m",
                "pytest",
                "-q",
                "tests/unit/calculation_v2/test_deployment_drift_matrix.py",
                "tests/unit/test_resolved_deployment_contract.py",
                environment=(
                    "PRICING_CATALOG_STORE_ROOT=/tmp/pricing-catalogs",
                ),
            ),
        ),
        Stage(
            "Management persistence-to-manifest drift",
            _compose_run(
                project,
                "management-api",
                "python",
                "-m",
                "pytest",
                "-q",
                "tests/test_deployment_drift_matrix.py",
                "tests/test_resolved_deployment_contract.py",
                "tests/test_resolved_deployment_specification_service.py",
                environment=(
                    "APP_ENV=test",
                    "DEBUG=false",
                    "DATABASE_URL=sqlite:////tmp/deployment-contract.db",
                    "UPLOAD_DIR=/tmp/deployment-contract-uploads",
                    "SEED_DATA=false",
                    "ENABLE_TEST_ENDPOINTS=false",
                ),
                user=_host_user_spec(),
            ),
        ),
        Stage(
            "Deployer tfvars and Terraform drift",
            _compose_run(
                project,
                "3cloud-deployer",
                "sh",
                "-lc",
                (
                    "terraform fmt -check -recursive src/terraform "
                    "&& python -m pytest -q "
                    "tests/unit/deployment_specification/"
                    "test_deployment_drift_matrix.py "
                    "tests/unit/terraform/test_deployment_target_bindings.py "
                    "tests/unit/terraform/test_native_mock_plans.py "
                    "tests/unit/test_resolved_deployment_contract.py"
                ),
                environment=(
                    "DEPLOYER_RUNTIME_STATE_ROOT=/tmp/deployment-contract-state",
                ),
            ),
        ),
    )


def full_stages(project: str) -> tuple[Stage, ...]:
    """Return all safe quality gates after the focused drift stages."""

    return (
        Stage(
            "Documentation image",
            (
                *_compose_prefix(project),
                "--profile",
                "docs",
                "build",
                "docs",
            ),
        ),
        Stage(
            "Optimizer full quality gate",
            _compose_run(
                project,
                "2twin2clouds",
                "sh",
                "-lc",
                (
                    "python -m pytest tests -q "
                    "&& ruff check api backend rest_api.py tests "
                    "&& python -m bandit -q -r api backend rest_api.py "
                    "&& python -m compileall -q api backend rest_api.py "
                    "&& python -m pip check"
                ),
                environment=(
                    "PRICING_CATALOG_STORE_ROOT=/tmp/pricing-catalogs",
                ),
            ),
        ),
        Stage(
            "Management API full quality gate",
            _compose_run(
                project,
                "management-api",
                "sh",
                "-lc",
                (
                    "python -m pytest tests --ignore=tests/e2e -q "
                    "&& ruff check src migrations scripts tests "
                    "&& python -m bandit -q -r src migrations scripts "
                    "&& python -m compileall -q src migrations scripts "
                    "&& python -m pip check"
                ),
                environment=(
                    "APP_ENV=test",
                    "DEBUG=false",
                    "DATABASE_URL=sqlite:////tmp/deployment-contract-full.db",
                    "UPLOAD_DIR=/tmp/deployment-contract-full-uploads",
                    "SEED_DATA=false",
                    "ENABLE_TEST_ENDPOINTS=false",
                ),
                user=_host_user_spec(),
            ),
        ),
        Stage(
            "Deployer full quality gate",
            _compose_run(
                project,
                "3cloud-deployer",
                "./run_tests.sh",
                environment=(
                    "DEPLOYER_RUNTIME_STATE_ROOT=/tmp/deployment-contract-state",
                ),
            ),
        ),
        Stage(
            "Flutter full quality gate",
            ("bash", str(ROOT / "thesis.sh"), "test", "frontend"),
        ),
        Stage(
            "Documentation strict build",
            (
                *_compose_prefix(project),
                "--profile",
                "docs",
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "docs",
                "mkdocs",
                "build",
                "--strict",
            ),
        ),
        Stage(
            "Repository static checks",
            (
                "sh",
                "-lc",
                (
                    "bash -n thesis.sh "
                    "&& python3 scripts/check_flutter_architecture.py "
                    "&& git diff --check"
                ),
            ),
        ),
    )


def run_stages(
    stages: Sequence[Stage],
    *,
    environment: Mapping[str, str],
) -> int:
    """Run stages in order and stop at the first failure."""

    started = time.monotonic()
    total = len(stages)
    for index, stage in enumerate(stages, start=1):
        stage_started = time.monotonic()
        rendered = shlex.join(stage.command)
        print(f"\n[{index}/{total}] {stage.name}", flush=True)
        print(f"  $ {rendered}", flush=True)
        try:
            result = subprocess.run(
                stage.command,
                cwd=stage.cwd,
                env=dict(environment),
                check=False,
            )
        except OSError as exc:
            elapsed = time.monotonic() - stage_started
            print(
                f"FAILED: {stage.name} could not start after {elapsed:.1f}s\n"
                f"Command: {rendered}\n"
                f"Reason: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return 127
        elapsed = time.monotonic() - stage_started
        if result.returncode != 0:
            print(
                f"FAILED: {stage.name} after {elapsed:.1f}s\n"
                f"Command: {rendered}",
                file=sys.stderr,
                flush=True,
            )
            return result.returncode
        print(f"PASS: {stage.name} ({elapsed:.1f}s)", flush=True)

    elapsed = time.monotonic() - started
    print(
        f"\nResolved deployment drift gate passed in {elapsed:.1f}s.",
        flush=True,
    )
    return 0


def cleanup_compose_project(
    project: str,
    *,
    environment: Mapping[str, str],
) -> int:
    """Remove only the isolated gate network, containers, and data volumes."""

    command = (
        *_compose_prefix(project),
        "--profile",
        "docs",
        "down",
        "--volumes",
        "--remove-orphans",
    )
    print("\n[CLEANUP] Isolated verification resources", flush=True)
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=dict(environment),
            check=False,
        )
    except OSError as exc:
        print(
            f"FAILED: verification cleanup\n"
            f"Command: {shlex.join(command)}\n"
            f"Reason: {exc}",
            file=sys.stderr,
            flush=True,
        )
        return 127
    if result.returncode != 0:
        print(
            f"FAILED: verification cleanup\nCommand: {shlex.join(command)}",
            file=sys.stderr,
            flush=True,
        )
    else:
        print("PASS: verification cleanup", flush=True)
    return result.returncode


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--focused",
        action="store_true",
        help="Run only cross-stack contract and Terraform drift tests.",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = parse_args(arguments)
    try:
        validate_safety(os.environ)
    except VerificationConfigurationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    project = os.environ.get(
        "THESIS_CONTRACT_COMPOSE_PROJECT",
        DEFAULT_PROJECT,
    )
    with tempfile.TemporaryDirectory(
        prefix="twin2multicloud-deployment-contract-"
    ) as temporary_root:
        runtime_secrets_dir = Path(temporary_root) / "runtime-secrets"
        create_ephemeral_runtime_secrets(runtime_secrets_dir)
        environment = sanitized_environment(
            os.environ,
            runtime_secrets_dir=runtime_secrets_dir,
        )
        stages = [*focused_stages(project)]
        if not args.focused:
            stages.extend(full_stages(project))
        result = 1
        try:
            result = run_stages(stages, environment=environment)
        finally:
            cleanup_result = cleanup_compose_project(
                project,
                environment=environment,
            )
        return result if result != 0 else cleanup_result


if __name__ == "__main__":
    raise SystemExit(main())
