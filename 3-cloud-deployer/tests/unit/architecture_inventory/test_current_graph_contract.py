"""JSON Schema and canonical inventory contract tests."""

from __future__ import annotations

from copy import deepcopy
import json

from jsonschema import Draft202012Validator, FormatChecker
import pytest

from architecture_inventory.canonical import content_digest, pretty_json


def _load(repository_root):
    schema = json.loads(
        (
            repository_root
            / "contracts/architecture-inventory/v1/current-graph.schema.json"
        ).read_text(encoding="utf-8")
    )
    inventory = json.loads(
        (
            repository_root / "contracts/architecture-inventory/v1/current-graph.json"
        ).read_text(encoding="utf-8")
    )
    return schema, inventory


def _validator(schema):
    return Draft202012Validator(schema, format_checker=FormatChecker())


def test_committed_inventory_is_valid_and_canonical(repository_root):
    schema, inventory = _load(repository_root)

    assert list(_validator(schema).iter_errors(inventory)) == []
    assert content_digest(inventory) == inventory["content_digest"]
    assert (
        repository_root / "contracts/architecture-inventory/v1/current-graph.json"
    ).read_text(encoding="utf-8") == pretty_json(inventory)


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "inventory_id",
        "source_commit",
        "audited_source_paths",
        "audited_source_tree_digest",
        "generated_at",
        "paper_model_references",
        "responsibilities",
        "components",
        "artifacts",
        "terraform_objects",
        "edges",
        "cost_owners",
        "trust_boundaries",
        "fixed_assumptions",
        "unresolved_findings",
        "content_digest",
    ],
)
def test_every_top_level_field_is_required(repository_root, field):
    schema, inventory = _load(repository_root)
    mutated = deepcopy(inventory)
    del mutated[field]

    assert list(_validator(schema).iter_errors(mutated))


def test_additional_properties_are_rejected(repository_root):
    schema, inventory = _load(repository_root)
    mutated = deepcopy(inventory)
    mutated["unexpected"] = True

    assert list(_validator(schema).iter_errors(mutated))


@pytest.mark.parametrize(
    "field",
    [
        "responsibilities",
        "components",
        "artifacts",
        "terraform_objects",
        "edges",
        "cost_owners",
        "trust_boundaries",
        "fixed_assumptions",
        "unresolved_findings",
    ],
)
def test_top_level_entity_arrays_are_unique(repository_root, field):
    schema, inventory = _load(repository_root)
    mutated = deepcopy(inventory)
    mutated[field].append(deepcopy(mutated[field][0]))

    assert list(_validator(schema).iter_errors(mutated))


def test_every_nested_record_field_is_required_and_closed(repository_root):
    schema, inventory = _load(repository_root)
    collections = {
        "responsibilities": "responsibility",
        "components": "component",
        "artifacts": "artifact",
        "terraform_objects": "terraformObject",
        "edges": "edge",
        "cost_owners": "costOwner",
        "trust_boundaries": "trustBoundary",
        "fixed_assumptions": "fixedAssumption",
    }
    for collection, definition_name in collections.items():
        required = schema["$defs"][definition_name]["required"]
        for field in required:
            mutated = deepcopy(inventory)
            del mutated[collection][0][field]
            assert list(_validator(schema).iter_errors(mutated)), (
                collection,
                field,
            )
        mutated = deepcopy(inventory)
        mutated[collection][0]["unexpected"] = True
        assert list(_validator(schema).iter_errors(mutated)), collection


def test_digest_changes_for_semantic_mutation_but_not_timestamp(repository_root):
    _, inventory = _load(repository_root)
    original = content_digest(inventory)
    timestamp_only = deepcopy(inventory)
    timestamp_only["generated_at"] = "2030-01-01T00:00:00Z"
    semantic = deepcopy(inventory)
    semantic["inventory_id"] = "changed"

    assert content_digest(timestamp_only) == original
    assert content_digest(semantic) != original
