"""Focused code-backed extractor coverage."""

from __future__ import annotations

from collections import Counter

import hcl2

from architecture_inventory.extractors import (
    ALLOWLISTED_ANCHORS,
    _parse_terraform_root,
    extract_artifact_sources,
    extract_deployment_contract,
    extract_optimizer_shape,
    extract_static_functions,
    extract_terraform_objects,
    verify_allowlisted_anchors,
)
from src.function_registry import STATIC_FUNCTIONS


def test_function_registry_extraction_is_complete():
    extracted = extract_static_functions()

    assert [item["name"] for item in extracted] == [
        item.name for item in STATIC_FUNCTIONS
    ]
    assert sum(len(item["providers"]) for item in extracted) == 54


def test_committed_provider_handlers_and_user_templates_are_discovered(
    repository_root,
):
    extracted = extract_artifact_sources(repository_root)
    missing = {item["source_key"] for item in extracted if not item["exists"]}

    assert missing == {
        "static:aws:event-feedback",
        "static:azure:event-feedback",
        "static:gcp:event-feedback",
    }
    assert (
        sum(item["source_key"].startswith("user-template:") for item in extracted) == 6
    )


def test_live_terraform_inventory_contains_every_current_object_kind():
    counts = Counter(item["kind"] for item in extract_terraform_objects())

    assert counts["resource"] > 0
    assert counts["data"] > 0
    assert counts["output"] > 0
    assert counts["variable"] > 0
    assert counts["local"] > 0


def test_hcl_parser_collects_module_blocks_without_regex(tmp_path):
    (tmp_path / "fixture.tf").write_text(
        """
variable "name" { type = string }
locals { value = var.name }
data "external" "example" { program = ["true"] }
resource "null_resource" "example" {}
module "child" { source = "./child" }
output "name" { value = var.name }
""".strip(),
        encoding="utf-8",
    )

    extracted = _parse_terraform_root(tmp_path, hcl2)

    assert {item["kind"] for item in extracted} == {
        "resource",
        "data",
        "output",
        "module",
        "variable",
        "local",
    }


def test_optimizer_and_deployment_contract_reconcile(repository_root):
    optimizer = extract_optimizer_shape(repository_root)
    deployment = extract_deployment_contract(repository_root)

    assert optimizer["layer_order"] == [
        "L1",
        "L2",
        "L3_hot",
        "L3_cool",
        "L3_archive",
        "L4",
        "L5",
    ]
    assert len(optimizer["segment_ids"]) == 6
    assert len(deployment["components"]) == 42
    assert set(deployment["slot_requirements"]) >= {
        "l1_ingestion",
        "l2_processing",
        "l3_hot_storage",
        "l3_cool_storage",
        "l3_archive_storage",
        "l4_twin_state",
        "l5_visualization",
    }


def test_fixed_field_consumer_allowlist_is_complete(repository_root):
    verified = verify_allowlisted_anchors(repository_root)

    assert len(verified) == sum(len(entry["anchors"]) for entry in ALLOWLISTED_ANCHORS)
    assert len({entry["path"] for entry in ALLOWLISTED_ANCHORS}) == 20
    assert all(entry["owner"] for entry in ALLOWLISTED_ANCHORS)
    assert all(entry["rationale"] for entry in ALLOWLISTED_ANCHORS)
    assert all(entry["expiry_phase"] for entry in ALLOWLISTED_ANCHORS)
