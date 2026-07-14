"""Status API regression tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from src.api import status
from src.status import metadata as metadata_status
from src.status import terraform as terraform_status


SOURCE_HASH = "sha256:" + "a" * 64
ARTIFACT_HASH = "sha256:" + "b" * 64


def test_request_validation_normalizes_google_alias(tmp_path):
    with patch.object(
        status,
        "resolve_project_context_path",
        return_value=tmp_path,
    ):
        assert status._validate_request("factory", "google") == "gcp"


def test_request_validation_rejects_missing_project(tmp_path):
    missing = tmp_path / "missing"
    with (
        patch.object(
            status,
            "resolve_project_context_path",
            return_value=missing,
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        status._validate_request("factory", "aws")

    assert exc_info.value.status_code == 404


def test_function_artifacts_do_not_treat_built_package_as_deployed(tmp_path):
    project = tmp_path / "upload" / "factory"
    metadata_dir = project / ".build" / "metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "processor.aws.json").write_text(
        """{
  "function": "processor",
  "provider": "aws",
  "schema_version": 2,
  "source_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "artifact_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "last_built": "2026-05-10T21:00:00Z"
}"""
    )

    with patch.object(
        metadata_status,
        "resolve_project_context_path",
        return_value=project,
    ):
        result = status.check_function_artifacts("factory")

    assert result == {
        "status": "built",
        "functions": {
            "processor": {
                "deployed": False,
                "state": "built",
                "provider": "aws",
                "hash": ARTIFACT_HASH,
                "source_hash": SOURCE_HASH,
                "last_updated": "2026-05-10T21:00:00Z",
            }
        },
    }


def test_function_artifacts_require_deployed_hash_to_match_current_build(tmp_path):
    project = tmp_path / "upload" / "factory"
    metadata_dir = project / ".build" / "metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "processor.aws.json").write_text(
        """{
  "function": "processor",
  "provider": "aws",
  "schema_version": 2,
  "source_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "artifact_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "deployed_artifact_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "last_built": "2026-05-10T21:00:00Z",
  "last_deployed": "2026-05-10T21:01:00Z"
}"""
    )

    with patch.object(
        metadata_status,
        "resolve_project_context_path",
        return_value=project,
    ):
        result = status.check_function_artifacts("factory")

    assert result["status"] == "deployed"
    assert result["functions"]["processor"] == {
        "deployed": True,
        "state": "deployed",
        "provider": "aws",
        "hash": ARTIFACT_HASH,
        "source_hash": SOURCE_HASH,
        "last_updated": "2026-05-10T21:01:00Z",
    }


def test_hash_metadata_does_not_follow_directory_symlink(tmp_path):
    project = tmp_path / "upload" / "factory"
    outside = tmp_path / "outside"
    outside.mkdir(parents=True)
    (outside / "secret.json").write_text(
        '{"function":"leak","artifact_hash":"sha256:secret"}'
    )
    (project / ".build").mkdir(parents=True)
    (project / ".build" / "metadata").symlink_to(outside, target_is_directory=True)

    with patch.object(
        metadata_status,
        "resolve_project_context_path",
        return_value=project,
    ):
        result = metadata_status.check_function_artifacts("factory")

    assert result == {"status": "no_deployments", "functions": {}}


def test_duplicate_function_metadata_keeps_both_artifacts(tmp_path):
    project = tmp_path / "upload" / "factory"
    metadata_dir = project / ".build" / "metadata"
    metadata_dir.mkdir(parents=True)
    for provider in ("aws", "azure"):
        (metadata_dir / f"processor.{provider}.json").write_text(
            "{"
            '"schema_version":2,'
            '"function":"processor",'
            f'"provider":"{provider}",'
            f'"source_hash":"{SOURCE_HASH}",'
            f'"artifact_hash":"{ARTIFACT_HASH}",'
            '"last_built":"2026-05-10T21:00:00Z"'
            "}"
        )

    with patch.object(
        metadata_status,
        "resolve_project_context_path",
        return_value=project,
    ):
        result = metadata_status.check_function_artifacts("factory")

    assert set(result["functions"]) == {"processor", "processor@azure"}


def test_drift_detection_uses_transient_tfvars_without_persisting_secrets(tmp_path):
    project = tmp_path / "upload" / "factory"
    (project / "terraform").mkdir(parents=True)
    completed = SimpleNamespace(returncode=0, stdout="", stderr="")

    with (
        patch.object(
            terraform_status,
            "resolve_project_context_path",
            return_value=project,
        ),
        patch.object(terraform_status, "generate_tfvars") as mock_generate_tfvars,
        patch.object(
            terraform_status,
            "run_terraform_status_command",
            return_value=completed,
        ) as mock_run_terraform,
    ):
        result = status.check_terraform_drift("factory")

    generated_path = Path(mock_generate_tfvars.call_args.args[1])
    command_args = mock_run_terraform.call_args.args[0]

    assert result == {
        "status": "no_drift",
        "message": "Infrastructure matches Terraform state",
    }
    assert mock_generate_tfvars.call_args.args[0] == str(project)
    assert generated_path.name == "generated.tfvars.json"
    assert project not in generated_path.parents
    assert not generated_path.exists()
    assert f"-var-file={generated_path}" in command_args
    assert not (project / "terraform" / "generated.tfvars.json").exists()


def test_drift_detection_redacts_terraform_diagnostics(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    completed = SimpleNamespace(
        returncode=2,
        stdout="azure_client_secret=sensitive-value",
        stderr="",
    )

    with (
        patch.object(
            terraform_status,
            "resolve_project_context_path",
            return_value=project,
        ),
        patch.object(terraform_status, "generate_tfvars"),
        patch.object(
            terraform_status,
            "run_terraform_status_command",
            return_value=completed,
        ),
    ):
        result = status.check_terraform_drift("factory")

    assert result["status"] == "drift_detected"
    assert result["details"] == "Terraform refresh-only plan reported changes"


def test_status_command_adapter_allows_only_read_only_contracts(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    state_result = SimpleNamespace(returncode=0, stdout="resource", stderr="")

    with (
        patch.object(
            terraform_status,
            "resolve_project_context_path",
            return_value=project,
        ),
        patch.object(
            terraform_status.TerraformRunner,
            "state_list",
            return_value=state_result,
        ) as state_list,
    ):
        assert terraform_status.run_terraform_status_command(
            ["state", "list"],
            "factory",
        ) is state_result
        with pytest.raises(ValueError, match="Unsupported"):
            terraform_status.run_terraform_status_command(
                ["destroy", "-auto-approve"],
                "factory",
            )

    state_list.assert_called_once_with()


def test_state_command_failure_is_not_reported_as_not_deployed(monkeypatch):
    completed = SimpleNamespace(
        returncode=1,
        stdout="",
        stderr="api_key=sensitive-value",
    )
    monkeypatch.setattr(
        terraform_status,
        "run_terraform_status_command",
        lambda *args: completed,
    )

    result = terraform_status.check_terraform_state("factory")

    assert result["status"] == "error"
    assert result["total_resources"] == 0
    assert result["error"] == "Terraform state list failed"


def test_state_resources_are_classified_by_canonical_addresses(monkeypatch):
    completed = SimpleNamespace(
        returncode=0,
        stdout="\n".join(
            [
                "aws_iot_thing.l1_device[0]",
                "aws_lambda_function.l2_persister[0]",
                "aws_dynamodb_table.l3_hot[0]",
                "aws_glacier_vault.l3_archive[0]",
                "aws_iottwinmaker_workspace.l4_workspace[0]",
            ]
        ),
        stderr="",
    )
    monkeypatch.setattr(
        terraform_status,
        "run_terraform_status_command",
        lambda *args: completed,
    )

    result = terraform_status.check_terraform_state("factory")

    assert result["status"] == "deployed"
    assert result["l1"]["deployed"] is True
    assert result["l2"]["deployed"] is True
    assert result["l3"]["hot"]["deployed"] is True
    assert result["l3"]["cold"]["deployed"] is False
    assert result["l4"]["deployed"] is True
