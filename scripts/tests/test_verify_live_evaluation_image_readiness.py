from __future__ import annotations

import copy

import pytest

from scripts import materialize_live_evaluation_candidate as materializer
from scripts import verify_live_evaluation_image_readiness as verifier


def test_tracked_image_readiness_record_is_valid() -> None:
    record = verifier.verify(verifier.DEFAULT_RECORD, verifier.DEFAULT_SCHEMA)

    assert record["execution_enabled"] is False
    assert record["cloud_mutation_performed"] is False
    assert record["summary"]["static_custom_images_built"] == 7
    assert record["summary"]["registry_publications_performed"] == 0


def test_record_is_bound_to_current_candidate_pack(tmp_path) -> None:
    output = tmp_path / "candidate-pack"
    materializer.materialize_plan(output)
    manifest = verifier._load(output / "candidate-pack-manifest.json")
    record = verifier._load(verifier.DEFAULT_RECORD)

    assert record["candidate_pack_manifest_digest"] == manifest["manifest_digest"]


def test_record_digest_mutation_fails_closed(tmp_path) -> None:
    record = verifier._load(verifier.DEFAULT_RECORD)
    mutated = copy.deepcopy(record)
    mutated["custom_runtime_images"][0]["local_image_id"] = "sha256:" + ("f" * 64)
    path = tmp_path / "mutated.json"
    path.write_text(verifier._canonical_json(mutated), encoding="utf-8")

    with pytest.raises(ValueError, match="record digest mismatch"):
        verifier.verify(path, verifier.DEFAULT_SCHEMA)


def test_pinned_reference_and_resolved_digest_must_match(tmp_path) -> None:
    record = verifier._load(verifier.DEFAULT_RECORD)
    mutated = copy.deepcopy(record)
    mutated["public_runtime_images"][0]["resolved_digest"] = "sha256:" + ("f" * 64)
    mutated["record_digest"] = verifier._digest(
        {key: value for key, value in mutated.items() if key != "record_digest"}
    )
    path = tmp_path / "mutated.json"
    path.write_text(verifier._canonical_json(mutated), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its pinned reference"):
        verifier.verify(path, verifier.DEFAULT_SCHEMA)
