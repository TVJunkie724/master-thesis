"""Status API regression tests."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.api import status


def test_check_code_hashes_does_not_treat_built_package_as_deployed(tmp_path):
    project = tmp_path / "upload" / "factory"
    metadata_dir = project / ".build" / "metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "processor.aws.json").write_text(
        """{
  "function": "processor",
  "provider": "aws",
  "zip_hash": "sha256:abc",
  "last_built": "2026-05-10T21:00:00Z"
}"""
    )

    with patch.object(status, "_get_upload_dir", return_value=str(project)):
        result = status.check_code_hashes("factory")

    assert result == {
        "status": "built",
        "functions": {
            "processor": {
                "deployed": False,
                "state": "built",
                "provider": "aws",
                "hash": "sha256:abc",
                "last_updated": "2026-05-10T21:00:00Z",
            }
        },
    }


def test_check_code_hashes_requires_deployed_hash_to_match_current_build(tmp_path):
    project = tmp_path / "upload" / "factory"
    metadata_dir = project / ".build" / "metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "processor.aws.json").write_text(
        """{
  "function": "processor",
  "provider": "aws",
  "zip_hash": "sha256:current",
  "deployed_zip_hash": "sha256:current",
  "last_built": "2026-05-10T21:00:00Z",
  "last_deployed": "2026-05-10T21:01:00Z"
}"""
    )

    with patch.object(status, "_get_upload_dir", return_value=str(project)):
        result = status.check_code_hashes("factory")

    assert result["status"] == "deployed"
    assert result["functions"]["processor"] == {
        "deployed": True,
        "state": "deployed",
        "provider": "aws",
        "hash": "sha256:current",
        "last_updated": "2026-05-10T21:01:00Z",
    }


def test_drift_detection_uses_transient_tfvars_without_persisting_secrets(tmp_path):
    project = tmp_path / "upload" / "factory"
    (project / "terraform").mkdir(parents=True)
    completed = SimpleNamespace(returncode=0, stdout="", stderr="")

    with (
        patch.object(status, "_get_upload_dir", return_value=str(project)),
        patch.object(status, "generate_tfvars") as mock_generate_tfvars,
        patch.object(status, "_run_terraform_command", return_value=completed) as mock_run_terraform,
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
        patch.object(status, "_get_upload_dir", return_value=str(project)),
        patch.object(status, "generate_tfvars"),
        patch.object(status, "_run_terraform_command", return_value=completed),
    ):
        result = status.check_terraform_drift("factory")

    assert result["status"] == "drift_detected"
    assert "sensitive-value" not in result["details"]
    assert "<redacted>" in result["details"]


def test_status_command_adapter_allows_only_read_only_contracts(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    state_result = SimpleNamespace(returncode=0, stdout="resource", stderr="")

    with (
        patch.object(status, "_get_upload_dir", return_value=str(project)),
        patch.object(status.TerraformRunner, "state_list", return_value=state_result) as state_list,
    ):
        assert status._run_terraform_command(["state", "list"], "factory") is state_result
        with pytest.raises(ValueError, match="Unsupported"):
            status._run_terraform_command(["destroy", "-auto-approve"], "factory")

    state_list.assert_called_once_with()
