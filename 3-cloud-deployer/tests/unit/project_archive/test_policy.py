import io
import stat
import zipfile

import pytest

from src.project_archive import policy


def _archive(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries:
            zf.writestr(name, content)
    return zipfile.ZipFile(io.BytesIO(buffer.getvalue()))


def test_valid_archive_and_double_dot_filename_are_accepted():
    with _archive([("project/config.json", "{}"), ("project/release..md", "ok")]) as zf:
        policy.validate_archive(zf)


@pytest.mark.parametrize(
    "name",
    ["../config.json", "/config.json", "C:/config.json", "dir\\config.json", "."],
)
def test_ambiguous_or_external_paths_are_rejected(name):
    with _archive([(name, "{}")]) as zf:
        with pytest.raises(policy.ArchivePolicyError):
            policy.validate_archive(zf)


def test_duplicate_member_names_are_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("config.json", "one")
        with pytest.warns(UserWarning):
            zf.writestr("config.json", "two")
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as zf:
        with pytest.raises(policy.ArchivePolicyError, match="duplicate"):
            policy.validate_archive(zf)


def test_symbolic_link_entry_is_rejected():
    info = zipfile.ZipInfo("linked-config.json")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(info, "target")
    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as zf:
        with pytest.raises(policy.ArchivePolicyError, match="symbolic"):
            policy.validate_archive(zf)


def test_high_compression_ratio_is_rejected():
    with _archive([("scene.glb", b"0" * (policy.MAX_COMPRESSION_RATIO + 1) * 100)]) as zf:
        with pytest.raises(policy.ArchiveLimitExceeded, match="compression ratio"):
            policy.validate_archive(zf)


def test_member_count_is_bounded(monkeypatch):
    with _archive([("config.json", "{}")]) as zf:
        monkeypatch.setattr(policy, "MAX_MEMBERS", 0)
        with pytest.raises(policy.ArchiveLimitExceeded, match="too many"):
            policy.validate_archive(zf)
