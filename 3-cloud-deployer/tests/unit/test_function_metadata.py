"""Security and consistency tests for function artifact evidence."""

import json

import pytest

from src.function_metadata import (
    hash_bytes,
    load_function_metadata,
    mark_function_deployed,
    metadata_path,
    record_function_build,
)


def test_deployment_evidence_rejects_superseded_artifact(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    first_hash = hash_bytes(b"first")
    second_hash = hash_bytes(b"second")
    target = record_function_build(
        project,
        "processor-sensor-1",
        "aws",
        hash_bytes(b"source-one"),
        first_hash,
    )
    record_function_build(
        project,
        "processor-sensor-1",
        "aws",
        hash_bytes(b"source-two"),
        second_hash,
    )

    assert not mark_function_deployed(
        target,
        expected_artifact_hash=first_hash,
    )
    metadata = load_function_metadata(target)
    assert metadata is not None
    assert metadata["artifact_hash"] == second_hash
    assert "deployed_artifact_hash" not in metadata


def test_metadata_path_canonicalizes_google_provider(tmp_path):
    assert metadata_path(tmp_path, "processor", "google").name == "processor.gcp.json"


def test_metadata_write_rejects_symlinked_build_directory(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / ".build").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        record_function_build(
            project,
            "processor",
            "aws",
            hash_bytes(b"source"),
            hash_bytes(b"artifact"),
        )


def test_metadata_loader_rejects_legacy_or_malformed_evidence(tmp_path):
    target = tmp_path / "metadata.json"
    target.write_text(json.dumps({"zip_hash": hash_bytes(b"legacy")}))
    assert load_function_metadata(target) is None

    target.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "function": "processor",
                "provider": "aws",
                "source_hash": "not-a-hash",
                "artifact_hash": hash_bytes(b"artifact"),
                "last_built": "2026-01-01T00:00:00Z",
            }
        )
    )
    assert load_function_metadata(target) is None
