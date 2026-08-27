import pytest

from src.core.project_storage import (
    ProjectStorage,
    ProjectStorageError,
    is_sensitive_project_file,
)


def test_storage_resolves_template_to_canonical_template_root(tmp_path):
    canonical = tmp_path / "templates" / "digital-twin"
    legacy = tmp_path / "upload" / "template"
    canonical.mkdir(parents=True)
    legacy.mkdir(parents=True)

    context = ProjectStorage(project_root=tmp_path).context("template")

    assert context.project_path == canonical
    assert context.is_template is True


def test_storage_resolves_runtime_twins_independently(tmp_path):
    storage = ProjectStorage(project_root=tmp_path)

    assert storage.context("first").project_path == tmp_path / "upload" / "first"
    assert storage.context("second").project_path == tmp_path / "upload" / "second"


@pytest.mark.parametrize("name", ["../outside", "/absolute", "nested/twin"])
def test_storage_rejects_invalid_twin_names(tmp_path, name):
    with pytest.raises(ProjectStorageError, match="Invalid project name"):
        ProjectStorage(project_root=tmp_path).context(name)


def test_sensitive_file_classifier_keeps_examples_non_secret():
    assert is_sensitive_project_file("config_credentials.json") is True
    assert is_sensitive_project_file("nested/service_account.json") is True
    assert is_sensitive_project_file("config_credentials.json.example") is False
    assert is_sensitive_project_file("config.json") is False
