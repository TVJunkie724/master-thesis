"""Tests for ephemeral deployment workspaces."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.observability import OperationContext
from src.core.workspace import (
    create_ephemeral_workspace,
    deployment_workspace,
    ephemeral_workspace,
    sync_runtime_outputs,
)


def _context(project_path: Path, project_name: str = "factory") -> SimpleNamespace:
    return SimpleNamespace(project_name=project_name, project_path=project_path)


def test_create_ephemeral_workspace_copies_project_files(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")
    (project / "deployment_manifest.json").write_text('{"manifest_version": "1.0"}')
    (project / "terraform").mkdir()
    (project / "terraform" / "terraform.tfstate").write_text("{}")

    workspace = create_ephemeral_workspace(
        _context(project),
        workspace_root=tmp_path / "workspaces",
    )

    try:
        assert workspace.project_name == "factory"
        assert workspace.source_path == project.resolve()
        assert workspace.workspace_path != project.resolve()
        assert (workspace.workspace_path / "config.json").read_text() == "{}"
        assert (workspace.workspace_path / "deployment_manifest.json").exists()
        assert workspace.terraform_dir == workspace.workspace_path / "terraform"
        assert workspace.state_path == workspace.workspace_path / "terraform" / "terraform.tfstate"
    finally:
        workspace.cleanup()

    assert not workspace.workspace_path.exists()


def test_create_ephemeral_workspace_excludes_internal_artifacts(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")
    (project / "versions").mkdir()
    (project / "versions" / "archive.zip").write_text("old")
    (project / ".build").mkdir()
    (project / ".build" / "bundle.zip").write_text("cache")
    (project / "terraform").mkdir()
    (project / "terraform" / "terraform.tfstate").write_text("{}")
    (project / "terraform" / ".terraform").mkdir()
    (project / "terraform" / ".terraform" / "provider-cache").write_text("cache")
    (project / "__pycache__").mkdir()
    (project / "__pycache__" / "module.pyc").write_bytes(b"pyc")
    (project / ".DS_Store").write_text("mac")

    workspace = create_ephemeral_workspace(
        _context(project),
        workspace_root=tmp_path / "workspaces",
    )

    try:
        assert (workspace.workspace_path / "config.json").exists()
        assert (workspace.workspace_path / "terraform" / "terraform.tfstate").exists()
        assert not (workspace.workspace_path / "terraform" / ".terraform").exists()
        assert not (workspace.workspace_path / "versions").exists()
        assert not (workspace.workspace_path / ".build").exists()
        assert not (workspace.workspace_path / "__pycache__").exists()
        assert not (workspace.workspace_path / ".DS_Store").exists()
    finally:
        workspace.cleanup()


def test_ephemeral_workspace_context_manager_cleans_up(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")

    with ephemeral_workspace(_context(project), workspace_root=tmp_path / "workspaces") as workspace:
        workspace_path = workspace.workspace_path
        assert workspace_path.exists()

    assert not workspace_path.exists()


def test_sync_runtime_outputs_copies_only_durable_allowlisted_outputs(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")

    workspace = create_ephemeral_workspace(
        _context(project),
        workspace_root=tmp_path / "workspaces",
    )

    try:
        (workspace.workspace_path / "terraform").mkdir(exist_ok=True)
        (workspace.workspace_path / "terraform" / "terraform.tfstate").write_text("state")
        (workspace.workspace_path / "terraform" / "terraform.tfstate.backup").write_text("backup")
        (workspace.workspace_path / "terraform" / "generated.tfvars.json").write_text("secret")

        auth_dir = workspace.workspace_path / "iot_devices_auth" / "device-1"
        auth_dir.mkdir(parents=True)
        (auth_dir / "certificate.pem.crt").write_text("cert")

        simulator_dir = workspace.workspace_path / "iot_device_simulator" / "aws" / "device-1"
        simulator_dir.mkdir(parents=True)
        (simulator_dir / "config_generated.json").write_text("{}")
        (simulator_dir / "payloads.json").write_text("[]")

        build_dir = workspace.workspace_path / ".build" / "aws"
        build_dir.mkdir(parents=True)
        (build_dir / "processor.zip").write_text("zip")
        metadata_dir = workspace.workspace_path / ".build" / "metadata"
        metadata_dir.mkdir(parents=True)
        metadata_payload = '{"schema_version": 2, "artifact_hash": "sha256:abc"}'
        (metadata_dir / "processor.aws.json").write_text(metadata_payload)

        sync_runtime_outputs(workspace)
    finally:
        workspace.cleanup()

    assert (project / "terraform" / "terraform.tfstate").read_text() == "state"
    assert (project / "terraform" / "terraform.tfstate.backup").read_text() == "backup"
    assert (project / "iot_devices_auth" / "device-1" / "certificate.pem.crt").read_text() == "cert"
    assert (project / "iot_device_simulator" / "aws" / "device-1" / "config_generated.json").read_text() == "{}"
    assert (project / "terraform" / "terraform.tfstate").stat().st_mode & 0o777 == 0o600
    assert (project / "terraform" / "terraform.tfstate.backup").stat().st_mode & 0o777 == 0o600
    assert (project / "iot_devices_auth").stat().st_mode & 0o777 == 0o700
    assert (project / "iot_devices_auth" / "device-1").stat().st_mode & 0o777 == 0o700
    assert (
        project / "iot_devices_auth" / "device-1" / "certificate.pem.crt"
    ).stat().st_mode & 0o777 == 0o600
    assert (
        project
        / "iot_device_simulator"
        / "aws"
        / "device-1"
        / "config_generated.json"
    ).stat().st_mode & 0o777 == 0o600
    assert not (project / "terraform" / "generated.tfvars.json").exists()
    assert not (project / "iot_device_simulator" / "aws" / "device-1" / "payloads.json").exists()
    assert (project / ".build" / "metadata" / "processor.aws.json").read_text() == metadata_payload
    assert not (project / ".build" / "aws").exists()


def test_deployment_workspace_uses_runtime_project_path_and_syncs_outputs(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")
    context = _context(project)

    with deployment_workspace(context, workspace_root=tmp_path / "workspaces") as (runtime_context, workspace):
        workspace_path = workspace.workspace_path
        assert runtime_context.project_path == workspace_path
        assert context.project_path == project
        (workspace_path / "terraform").mkdir(exist_ok=True)
        (workspace_path / "terraform" / "terraform.tfstate").write_text("state")

    assert not workspace_path.exists()
    assert (project / "terraform" / "terraform.tfstate").read_text() == "state"


def test_deployment_workspace_logs_prepare_phase_with_operation_context(tmp_path, caplog):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")
    operation_context = OperationContext.create(
        operation="deploy",
        project_name="factory",
        provider="aws",
        operation_id="op-123",
    )

    with caplog.at_level("INFO", logger="src.core.workspace"):
        with deployment_workspace(
            _context(project),
            workspace_root=tmp_path / "workspaces",
            operation_context=operation_context,
        ) as (_runtime_context, workspace):
            workspace_path = workspace.workspace_path

    assert not workspace_path.exists()
    assert "Deployment phase started: workspace_prepare" in caplog.text
    assert "Deployment phase completed: workspace_prepare" in caplog.text
    assert "op-123" in [getattr(record, "operation_id", None) for record in caplog.records]


def test_sync_runtime_outputs_rejects_symlinked_destination(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")

    workspace = create_ephemeral_workspace(
        _context(project),
        workspace_root=tmp_path / "workspaces",
    )

    try:
        external_state = tmp_path / "outside.tfstate"
        external_state.write_text("outside")
        (project / "terraform").mkdir()
        (project / "terraform" / "terraform.tfstate").symlink_to(external_state)

        (workspace.workspace_path / "terraform").mkdir(exist_ok=True)
        (workspace.workspace_path / "terraform" / "terraform.tfstate").write_text("state")

        with pytest.raises(ValueError, match="outside the source project|symlinked runtime output destination"):
            sync_runtime_outputs(workspace)
    finally:
        workspace.cleanup()

    assert external_state.read_text() == "outside"


def test_create_ephemeral_workspace_rejects_symlinks(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")
    external_secret = tmp_path / "secret.txt"
    external_secret.write_text("secret")
    (project / "linked-secret.txt").symlink_to(external_secret)

    with pytest.raises(ValueError, match="project contains symlinks"):
        create_ephemeral_workspace(
            _context(project),
            workspace_root=tmp_path / "workspaces",
        )


def test_create_ephemeral_workspace_rejects_workspace_root_inside_source(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")

    with pytest.raises(ValueError, match="must not be inside the source project"):
        create_ephemeral_workspace(
            _context(project),
            workspace_root=project / ".tmp-workspaces",
        )

    assert not (project / ".tmp-workspaces").exists()


def test_create_ephemeral_workspace_rejects_symlink_workspace_root(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")
    actual_root = tmp_path / "actual-workspaces"
    actual_root.mkdir()
    linked_root = tmp_path / "linked-workspaces"
    linked_root.symlink_to(actual_root, target_is_directory=True)

    with pytest.raises(ValueError, match="workspace root must not be a symlink"):
        create_ephemeral_workspace(
            _context(project),
            workspace_root=linked_root,
        )


def test_create_ephemeral_workspace_rejects_missing_project_path(tmp_path):
    with pytest.raises(ValueError, match="project path does not exist"):
        create_ephemeral_workspace(
            _context(tmp_path / "missing"),
            workspace_root=tmp_path / "workspaces",
        )
