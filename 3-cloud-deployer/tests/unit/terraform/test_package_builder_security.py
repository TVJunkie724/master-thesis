"""Security invariants shared by provider package builders."""

import json
import os

import pytest

from src.core.deterministic_zip import atomic_zip_archive, write_zip_bytes
from src.providers.terraform.package_builder import (
    _create_lambda_zip,
    _reconcile_user_hash_metadata,
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


def test_unchanged_package_preserves_deployment_evidence(tmp_path):
    _save_user_hash_metadata(tmp_path, "processor", "aws", "sha256:value")
    metadata_path = tmp_path / ".build" / "metadata" / "processor.aws.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["deployed_zip_hash"] = "sha256:value"
    metadata["last_deployed"] = "2026-07-14T10:00:00Z"
    metadata_path.write_text(json.dumps(metadata))

    _save_user_hash_metadata(tmp_path, "processor", "aws", "sha256:value")

    rebuilt = json.loads(metadata_path.read_text())
    assert rebuilt["deployed_zip_hash"] == "sha256:value"
    assert rebuilt["last_deployed"] == "2026-07-14T10:00:00Z"


def test_changed_package_invalidates_deployment_evidence(tmp_path):
    _save_user_hash_metadata(tmp_path, "processor", "aws", "sha256:old")
    metadata_path = tmp_path / ".build" / "metadata" / "processor.aws.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["deployed_zip_hash"] = "sha256:old"
    metadata["last_deployed"] = "2026-07-14T10:00:00Z"
    metadata_path.write_text(json.dumps(metadata))

    _save_user_hash_metadata(tmp_path, "processor", "aws", "sha256:new")

    rebuilt = json.loads(metadata_path.read_text())
    assert "deployed_zip_hash" not in rebuilt
    assert "last_deployed" not in rebuilt


def test_metadata_reconciliation_removes_stale_and_previous_provider_entries(tmp_path):
    _save_user_hash_metadata(tmp_path, "active", "aws", "sha256:active")
    _save_user_hash_metadata(tmp_path, "stale", "aws", "sha256:stale")
    _save_user_hash_metadata(tmp_path, "other", "azure", "sha256:other")

    _reconcile_user_hash_metadata(tmp_path, "aws", {"active"})

    metadata_dir = tmp_path / ".build" / "metadata"
    assert (metadata_dir / "active.aws.json").exists()
    assert not (metadata_dir / "stale.aws.json").exists()
    assert not (metadata_dir / "other.azure.json").exists()
