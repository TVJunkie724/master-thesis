"""Credential-free Terraform mock plans for resolved deployment selections."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

from src.providers.terraform.package_builder import build_all_packages


TERRAFORM_SOURCE = Path(__file__).resolve().parents[3] / "src" / "terraform"
CREDENTIAL_ENV_PREFIXES = (
    "ARM_",
    "AWS_",
    "AZURE_",
    "CLOUDSDK_",
    "GOOGLE_",
)


def _providers(
    *,
    l1: str,
    l2: str,
    hot: str,
    cool: str,
    archive: str,
    l4: str,
    l5: str,
) -> dict[str, str]:
    return {
        "layer_1_provider": l1,
        "layer_2_provider": l2,
        "layer_3_hot_provider": hot,
        "layer_3_cold_provider": cool,
        "layer_3_archive_provider": archive,
        "layer_4_provider": l4,
        "layer_5_provider": l5,
    }


def _write_minimal_project(project_path: Path) -> None:
    payloads = {
        "config.json": {"digital_twin_name": "drift-test"},
        "config_events.json": [],
        "config_iot_devices.json": [],
        "config_optimization.json": {
            "inputParamsUsed": {
                "needs3DModel": False,
                "returnFeedbackToDevice": False,
                "triggerNotificationWorkflow": False,
                "useEventChecking": False,
            }
        },
    }
    for name, payload in payloads.items():
        (project_path / name).write_text(
            json.dumps(payload),
            encoding="utf-8",
        )


def _run_terraform(
    terraform_dir: Path,
    *arguments: str,
    plugin_cache: Path,
) -> subprocess.CompletedProcess[str]:
    sanitized_environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(CREDENTIAL_ENV_PREFIXES)
    }
    environment = {
        **sanitized_environment,
        "AWS_EC2_METADATA_DISABLED": "true",
        "CHECKPOINT_DISABLE": "1",
        "TF_IN_AUTOMATION": "1",
        "TF_INPUT": "0",
        "TF_PLUGIN_CACHE_DIR": str(plugin_cache),
    }
    result = subprocess.run(
        [
            "terraform",
            f"-chdir={terraform_dir}",
            *arguments,
            "-no-color",
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, (
        f"terraform {' '.join(arguments)} failed\n"
        f"stdout:\n{result.stdout[-4000:]}\n"
        f"stderr:\n{result.stderr[-4000:]}"
    )
    return result


def test_native_mock_plans_bind_resolved_selections_without_credentials(
    tmp_path,
):
    terraform_dir = tmp_path / "terraform"
    project_path = tmp_path / "project"
    plugin_cache = tmp_path / "plugin-cache"
    shutil.copytree(
        TERRAFORM_SOURCE,
        terraform_dir,
        ignore=shutil.ignore_patterns(".terraform", "*.tfstate*"),
    )
    project_path.mkdir()
    plugin_cache.mkdir()
    _write_minimal_project(project_path)

    all_aws = _providers(
        l1="aws",
        l2="aws",
        hot="aws",
        cool="aws",
        archive="aws",
        l4="aws",
        l5="aws",
    )
    gcp_storage = _providers(
        l1="aws",
        l2="aws",
        hot="google",
        cool="google",
        archive="google",
        l4="aws",
        l5="aws",
    )
    build_all_packages(terraform_dir, project_path, all_aws)
    build_all_packages(terraform_dir, project_path, gcp_storage)

    _run_terraform(
        terraform_dir,
        "init",
        "-backend=false",
        "-lockfile=readonly",
        plugin_cache=plugin_cache,
    )
    _run_terraform(
        terraform_dir,
        "validate",
        plugin_cache=plugin_cache,
    )
    result = _run_terraform(
        terraform_dir,
        "test",
        f"-var=project_path={project_path}",
        plugin_cache=plugin_cache,
    )

    assert "3 passed, 0 failed" in result.stdout
    assert not list(tmp_path.rglob("*.tfstate"))
    assert not list(tmp_path.rglob("*.tfplan"))
