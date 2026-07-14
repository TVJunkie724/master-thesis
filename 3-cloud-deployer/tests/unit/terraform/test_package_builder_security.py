"""Security invariants shared by provider package builders."""

import json
import os

import pytest

from src.core.deterministic_zip import atomic_zip_archive, write_zip_bytes
from src.providers.terraform.package_builder import (
    _create_lambda_zip,
    _save_user_hash_metadata,
)


def test_package_builder_rejects_symbolic_link_sources(tmp_path):
    source = tmp_path / "source"
    shared = tmp_path / "shared"
    source.mkdir()
    shared.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    (source / "linked.txt").symlink_to(outside)

    with pytest.raises(ValueError, match="Symbolic links"):
        _create_lambda_zip(source, shared, tmp_path / "function.zip")


def test_package_bytes_are_reproducible_across_source_mtime_changes(tmp_path):
    source = tmp_path / "source"
    shared = tmp_path / "shared"
    source.mkdir()
    shared.mkdir()
    handler = source / "lambda_function.py"
    handler.write_text("def lambda_handler(event, context):\n    return event\n")

    first_path = tmp_path / "first.zip"
    second_path = tmp_path / "second.zip"
    _create_lambda_zip(source, shared, first_path)
    os.utime(handler, (handler.stat().st_atime, handler.stat().st_mtime + 3600))
    _create_lambda_zip(source, shared, second_path)

    assert first_path.read_bytes() == second_path.read_bytes()


def test_atomic_archive_keeps_previous_artifact_when_build_fails(tmp_path):
    target = tmp_path / "function.zip"
    target.write_bytes(b"previous")

    with pytest.raises(RuntimeError, match="build failed"):
        with atomic_zip_archive(target) as archive:
            write_zip_bytes(archive, "handler.py", b"partial")
            raise RuntimeError("build failed")

    assert target.read_bytes() == b"previous"
    assert not target.with_suffix(".zip.tmp").exists()


@pytest.mark.parametrize(
    ("function_name", "provider"),
    [("../escape", "aws"), ("processor", "../escape")],
)
def test_package_metadata_rejects_unsafe_components(tmp_path, function_name, provider):
    with pytest.raises(ValueError, match="Invalid"):
        _save_user_hash_metadata(tmp_path, function_name, provider, "sha256:value")


def test_package_metadata_is_atomic_and_uses_utc_timestamp(tmp_path):
    _save_user_hash_metadata(tmp_path, "processor", "aws", "sha256:value")

    metadata_path = tmp_path / ".build" / "metadata" / "processor.aws.json"
    metadata = json.loads(metadata_path.read_text())
    assert metadata["last_built"].endswith("Z")
    assert not metadata_path.with_suffix(".json.tmp").exists()
