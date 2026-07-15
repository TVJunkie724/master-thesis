import json
import stat

import pytest

from src.core.project_storage import (
    ProjectFileAccessDenied,
    ProjectStorage,
    ProjectStorageError,
)


def test_storage_resolves_template_to_canonical_template_root(tmp_path):
    canonical = tmp_path / "templates" / "digital-twin"
    legacy = tmp_path / "upload" / "template"
    canonical.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (canonical / "config.json").write_text(json.dumps({"source": "canonical"}))
    (legacy / "legacy-only.json").write_text(json.dumps({"source": "legacy"}))

    storage = ProjectStorage(project_root=tmp_path)

    assert storage.context("template").project_path == canonical
    assert storage.read_json("template", "config.json") == {"source": "canonical"}
    with pytest.raises(FileNotFoundError):
        storage.read_json("template", "legacy-only.json")


def test_storage_resolves_runtime_projects_independently(tmp_path):
    first = tmp_path / "upload" / "first"
    second = tmp_path / "upload" / "second"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    (first / "config.json").write_text(json.dumps({"name": "first"}))
    (second / "config.json").write_text(json.dumps({"name": "second"}))

    storage = ProjectStorage(project_root=tmp_path)

    assert storage.read_json("first", "config.json") == {"name": "first"}
    assert storage.read_json("second", "config.json") == {"name": "second"}


def test_storage_file_tree_hides_sensitive_credentials_but_keeps_examples(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config.json").write_text("{}")
    (project / "config_credentials.json").write_text('{"aws": "secret"}')
    (project / "config_credentials.json.example").write_text("{}")

    tree = ProjectStorage(project_root=tmp_path).file_tree("factory")

    names = {item["name"] for item in tree}
    assert "config.json" in names
    assert "config_credentials.json.example" in names
    assert "config_credentials.json" not in names


def test_storage_blocks_sensitive_file_content_reads(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (project / "config_credentials.json").write_text('{"aws": "secret"}')

    storage = ProjectStorage(project_root=tmp_path)

    with pytest.raises(ProjectFileAccessDenied):
        storage.file_content("factory", "config_credentials.json")


def test_storage_blocks_path_traversal_and_absolute_paths(tmp_path):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    (tmp_path / "outside.json").write_text("{}")

    storage = ProjectStorage(project_root=tmp_path)

    with pytest.raises(ProjectStorageError, match="Traversal"):
        storage.file_content("factory", "../outside.json")
    with pytest.raises(ProjectStorageError, match="Absolute"):
        storage.file_content("factory", "/tmp/outside.json")


def test_storage_write_rejects_template_project(tmp_path):
    template = tmp_path / "templates" / "digital-twin"
    template.mkdir(parents=True)

    storage = ProjectStorage(project_root=tmp_path)

    with pytest.raises(ProjectStorageError, match="template"):
        storage.write_text("template", "state_machines/aws_step_function.json", "{}")


@pytest.mark.parametrize("writer", ["text", "json"])
def test_storage_writes_sensitive_files_with_owner_only_permissions(tmp_path, writer):
    project = tmp_path / "upload" / "factory"
    project.mkdir(parents=True)
    storage = ProjectStorage(project_root=tmp_path)

    if writer == "text":
        result = storage.write_text(
            "factory",
            "config_credentials.json",
            '{"secret":"value"}',
        )
    else:
        result = storage.write_json(
            "factory",
            "gcp_credentials.json",
            {"private_key": "value"},
        )

    assert stat.S_IMODE(result.stat().st_mode) == 0o600
