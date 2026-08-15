"""Semantic checker regression tests."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from architecture_inventory.canonical import source_tree_digest
from architecture_inventory.checker import (
    InventoryCheckError,
    _check_ids_and_references,
    _check_source_reconciliation,
    _secret_material_findings,
    extract_diagram_manifest,
)


def _inventory(repository_root):
    return json.loads(
        (
            repository_root / "contracts/architecture-inventory/v1/current-graph.json"
        ).read_text(encoding="utf-8")
    )


def test_referential_integrity_accepts_committed_inventory(repository_root):
    _check_ids_and_references(_inventory(repository_root))


def test_duplicate_global_id_is_rejected(repository_root):
    inventory = _inventory(repository_root)
    inventory["edges"].append(deepcopy(inventory["edges"][0]))

    with pytest.raises(InventoryCheckError, match="DUPLICATE_ID"):
        _check_ids_and_references(inventory)


def test_broken_implementation_reference_is_rejected(repository_root):
    inventory = _inventory(repository_root)
    inventory["edges"][0]["destination_implementation_id"] = "implementation.missing"

    with pytest.raises(InventoryCheckError, match="REFERENCE_UNRESOLVED"):
        _check_ids_and_references(inventory)


def test_missing_source_matrix_row_is_rejected(repository_root):
    inventory = _inventory(repository_root)
    inventory["edges"] = [
        item
        for item in inventory["edges"]
        if item["edge_id"] != "edge.runtime.aws.l1-to-l2"
    ]

    with pytest.raises(InventoryCheckError, match="SOURCE_ENTITY_UNMAPPED"):
        _check_source_reconciliation(repository_root, inventory)


def test_stale_matrix_row_is_rejected(repository_root):
    inventory = _inventory(repository_root)
    stale = deepcopy(inventory["components"][0])
    stale["implementation_id"] = "implementation.aws.stale"
    stale["component_id"] = "component.aws.stale"
    inventory["components"].append(stale)

    with pytest.raises(InventoryCheckError, match="MATRIX_ENTITY_STALE"):
        _check_source_reconciliation(repository_root, inventory)


def test_source_tree_digest_tracks_relevant_but_not_irrelevant_files(tmp_path):
    audited = tmp_path / "audited"
    audited.mkdir()
    relevant = audited / "source.py"
    relevant.write_text("one", encoding="utf-8")
    irrelevant = tmp_path / "outside.py"
    irrelevant.write_text("one", encoding="utf-8")
    original = source_tree_digest(tmp_path, ["audited"])

    irrelevant.write_text("two", encoding="utf-8")
    assert source_tree_digest(tmp_path, ["audited"]) == original
    relevant.write_text("two", encoding="utf-8")
    assert source_tree_digest(tmp_path, ["audited"]) != original


def test_diagram_manifest_extraction_is_deterministic():
    text = """before
<!-- architecture-inventory-diagram-ids:
edge.runtime.aws.l1-to-l2
responsibility.l1.ingestion
-->
after"""

    assert extract_diagram_manifest(text) == {
        "edge.runtime.aws.l1-to-l2",
        "responsibility.l1.ingestion",
    }


@pytest.mark.parametrize(
    "forbidden",
    [
        "config_credentials.json",
        "terraform.tfstate",
        "AWS_ACCESS_KEY_ID=not-a-real-value",
        "-----BEGIN PRIVATE KEY-----",
    ],
)
def test_secret_like_material_is_rejected(repository_root, forbidden):
    inventory = _inventory(repository_root)
    inventory["fixed_assumptions"][0]["convention"] = forbidden

    assert _secret_material_findings(inventory)
