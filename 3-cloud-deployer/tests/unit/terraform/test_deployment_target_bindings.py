"""Structured Terraform binding coverage for deployment selections."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import hcl2

from tests.utils.deployment_specification import (
    load_registry,
    load_verification_matrix,
)


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"
VAR_REFERENCE = re.compile(r"\bvar\.([A-Za-z][A-Za-z0-9_]*)\b")


def _references(value: object) -> set[str]:
    return set(VAR_REFERENCE.findall(json.dumps(value, sort_keys=True)))


def _parsed_terraform() -> list[tuple[Path, dict[str, Any]]]:
    parsed = []
    for path in sorted(TERRAFORM_ROOT.glob("*.tf")):
        with path.open(encoding="utf-8") as source:
            parsed.append((path, hcl2.load(source)))
    return parsed


def _deployment_targets() -> set[str]:
    registry = load_registry()
    return {
        definition["terraform_target"]
        for component in registry["components"].values()
        for definition in component["dimensions"].values()
        if definition["classification"] == "deployable_selection"
    }


def test_matrix_and_registry_cover_the_same_terraform_targets():
    matrix = load_verification_matrix()
    matrix_targets = {
        target
        for targets in matrix["expected_targets_by_component"].values()
        for target in targets
    }

    assert matrix_targets == _deployment_targets()
    assert len(matrix_targets) == 50


def test_each_deployment_target_has_one_fail_closed_variable_declaration():
    declarations: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for path, parsed in _parsed_terraform():
        for variable_group in parsed.get("variable", []):
            for name, body in variable_group.items():
                declarations.setdefault(name.strip('"'), []).append((path, body))

    for target in sorted(_deployment_targets()):
        assert target in declarations, f"Terraform variable missing: {target}"
        assert len(declarations[target]) == 1, (
            f"Terraform variable must be unique: {target}"
        )
        path, body = declarations[target][0]
        validations = body.get("validation", [])
        assert validations, f"Variable validation missing: {path}:{target}"
        for validation in validations:
            assert validation.get("condition")
            assert validation.get("error_message")
        assert body.get("default") is None


def test_each_deployment_target_has_a_non_guard_resource_or_local_consumer():
    consumers: dict[str, set[str]] = {
        target: set() for target in _deployment_targets()
    }
    for path, parsed in _parsed_terraform():
        for local_group in parsed.get("locals", []):
            for target in _references(local_group).intersection(consumers):
                consumers[target].add(f"{path.name}:locals")
        for resource_group in parsed.get("resource", []):
            for resource_type, resources in resource_group.items():
                for resource_name, body in resources.items():
                    if (
                        resource_type == "terraform_data"
                        and resource_name.endswith(
                            "_deployment_specification_guard"
                        )
                    ):
                        continue
                    for target in _references(body).intersection(consumers):
                        consumers[target].add(
                            f"{path.name}:{resource_type}.{resource_name}"
                        )

    missing = {
        target: paths
        for target, paths in consumers.items()
        if not paths
    }
    assert not missing
