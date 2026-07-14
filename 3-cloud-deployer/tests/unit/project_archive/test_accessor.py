import io
import zipfile

import pytest

from src.validation.accessors import DirectoryAccessor, ZipFileAccessor


def _accessor(*names: str) -> ZipFileAccessor:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name in names:
            zf.writestr(name, "{}")
    return ZipFileAccessor(zipfile.ZipFile(io.BytesIO(buffer.getvalue())))


def test_project_root_requires_exact_config_filename():
    assert _accessor("project/notconfig.json").get_project_root() == ""


def test_nested_project_root_is_resolved_once():
    assert _accessor("project/config.json").get_project_root() == "project/"


def test_dotted_project_root_is_preserved():
    assert _accessor("project.v1/config.json").get_project_root() == "project.v1/"


def test_multiple_project_roots_are_rejected():
    with pytest.raises(ValueError, match="multiple project roots"):
        _accessor("one/config.json", "two/config.json")


def test_directory_accessor_rejects_file_symlinks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "secret.json"
    outside.write_text("secret")
    (project / "config.json").symlink_to(outside)

    with pytest.raises(ValueError, match="symbolic links"):
        DirectoryAccessor(project)


def test_directory_accessor_rejects_directory_symlinks(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic links"):
        DirectoryAccessor(project)
