"""Credential-free Terraform mock plans for resolved deployment selections."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from src.providers.terraform.package_builders.aws_six_layer import (
    build_aws_six_layer_domain_app,
)
from src.providers.terraform.package_builders.aws_eventing import (
    build_aws_eventing_app,
)
from src.providers.terraform.package_builders.azure_six_layer import (
    build_azure_six_layer_graph_apps,
)


TERRAFORM_SOURCE = Path(__file__).resolve().parents[3] / "src" / "terraform"
CREDENTIAL_ENV_PREFIXES = (
    "ARM_",
    "AWS_",
    "AZURE_",
    "CLOUDSDK_",
    "GOOGLE_",
)


pytestmark = pytest.mark.skipif(
    shutil.which("terraform") is None,
    reason="Terraform CLI is required for credential-free native mock plans",
)


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

    build_aws_six_layer_domain_app(project_path)
    build_aws_eventing_app(project_path)
    build_azure_six_layer_graph_apps(
        project_path,
        ("six-layer-domain", "six-layer-eventing"),
    )

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

    assert "Success! 8 passed, 0 failed." in result.stdout
    assert not list(tmp_path.rglob("*.tfstate"))
    assert not list(tmp_path.rglob("*.tfplan"))


def test_gcp_six_layer_workflow_reports_one_terminal_outcome_to_domain_consumer():
    terraform_source = (TERRAFORM_SOURCE / "gcp_six_layer.tf").read_text(
        encoding="utf-8"
    )

    assert 'schema_version   = "workflow-outcome.v1"' in terraform_source
    assert '{ outcome_status = "SUCCEEDED" }' in terraform_source
    assert '{ outcome_status = "FAILED" }' in terraform_source
    assert (
        'google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["domain"].uri'
        in terraform_source
    )


def test_disabled_azure_platform_user_assignments_remain_provider_valid():
    user_source = (TERRAFORM_SOURCE / "azure_user.tf").read_text(encoding="utf-8")
    grafana_source = (TERRAFORM_SOURCE / "azure_grafana.tf").read_text(
        encoding="utf-8"
    )
    twins_source = (TERRAFORM_SOURCE / "azure_twins.tf").read_text(
        encoding="utf-8"
    )

    assert "platform_user_role_principal_id = coalesce(" in user_source
    assert '"00000000-0000-0000-0000-000000000000"' in user_source
    assert (
        grafana_source.count(
            "principal_id = local.platform_user_role_principal_id"
        )
        == 1
    )
    assert (
        twins_source.count(
            "principal_id = local.platform_user_role_principal_id"
        )
        == 2
    )


def test_aws_six_layer_storage_mover_uses_only_digest_input_and_exact_task_dimension():
    terraform_source = (TERRAFORM_SOURCE / "aws_six_layer.tf").read_text(
        encoding="utf-8"
    )

    assert "image     = var.aws_six_layer_storage_mover_image" in terraform_source
    assert (
        '"dimension.aws.aws.ecs-fargate-storage-mover.task_count"' in terraform_source
    )
    assert ":storage-mover-v1" not in terraform_source


def test_azure_six_layer_storage_mover_uses_digest_and_explicit_exact_task_jobs():
    terraform_source = (TERRAFORM_SOURCE / "azure_six_layer.tf").read_text(
        encoding="utf-8"
    )

    assert "image  = var.azure_six_layer_storage_mover_image" in terraform_source
    assert (
        '"dimension.azure.azure.container-apps-scheduled-storage-job.task_count"'
        in terraform_source
    )
    assert (
        'resource "azurerm_container_app_job" '
        '"azure_azure_container_apps_scheduled_storage_job"' in terraform_source
    )
    assert (
        "for_each                     = local.azure_six_layer_storage_schedule_tasks"
        in terraform_source
    )
    assert "parallelism              = 1" in terraform_source
    assert (
        "contains([1, 4, 30], local.azure_six_layer_storage_task_count)"
        in terraform_source
    )
    assert ":latest" not in terraform_source
