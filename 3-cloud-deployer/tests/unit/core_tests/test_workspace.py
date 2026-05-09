"""Tests for ephemeral deployment workspaces."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.workspace import create_ephemeral_workspace, ephemeral_workspace


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
