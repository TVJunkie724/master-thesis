"""Strict Five-layer v2 workload and Eventing-scenario resolution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from .diagnostics import ArchitectureResolutionError


CONTRACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "generated"
    / "five-layer-workload"
    / "v2"
)
_SIZES = ("small", "medium", "large")
_SCENARIO_VARIANT_FIELDS = frozenset({"currency"})


@dataclass(frozen=True)
class ResolvedFiveLayerV2Workload:
    size: str
    workload: Mapping[str, Any]
    eventing_scenario: Mapping[str, Any]
    eventing_scenario_ref: Mapping[str, str]


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Five-layer v2 workload contract is unavailable: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"Five-layer v2 workload document must be an object: {path}")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@lru_cache(maxsize=1)
def _sources() -> tuple[
    Draft202012Validator,
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    schema = _read(CONTRACT_ROOT / "workload.schema.json")
    Draft202012Validator.check_schema(schema)
    fixtures = {
        size: _read(CONTRACT_ROOT / "fixtures" / "valid" / f"core-{size}.json")
        for size in _SIZES
    }
    catalog = _read(CONTRACT_ROOT / "eventing-scenario-catalog.json")
    return (
        Draft202012Validator(schema, format_checker=FormatChecker()),
        fixtures,
        catalog,
    )


def resolve_five_layer_v2_workload(
    payload: Mapping[str, Any],
) -> ResolvedFiveLayerV2Workload:
    """Resolve exactly one immutable Core/Eventing scenario pair."""

    validator, fixtures, catalog = _sources()
    copied = dict(payload)
    errors = sorted(
        validator.iter_errors(copied),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "$"
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            path,
            first.message,
        )
    scenario_identity = {
        key: value
        for key, value in copied.items()
        if key not in _SCENARIO_VARIANT_FIELDS
    }
    size = next(
        (
            key
            for key, fixture in fixtures.items()
            if scenario_identity
            == {
                field: value
                for field, value in fixture.items()
                if field not in _SCENARIO_VARIANT_FIELDS
            }
        ),
        None,
    )
    if size is None:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "workload",
            "Five-layer v2 accepts only the immutable Small, Medium, or Large Core scenario",
        )
    scenario_id = str(copied["eventingScenarioId"])
    expected_id = f"eventing-{size}-v1"
    if scenario_id != expected_id:
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "eventingScenarioId",
            "Core and Eventing scenarios must use the same size",
        )
    scenario = next(
        (
            item
            for item in catalog["scenarios"]
            if item["scenario_id"] == scenario_id
        ),
        None,
    )
    digest = catalog["scenario_digests"].get(scenario_id)
    if scenario is None or not isinstance(digest, str):
        raise ArchitectureResolutionError(
            "ARCH_WORKLOAD_INCOMPATIBLE",
            "eventingScenarioId",
            "Eventing scenario reference is unavailable",
        )
    return ResolvedFiveLayerV2Workload(
        size=size,
        workload=_freeze(copied),
        eventing_scenario=_freeze(scenario),
        eventing_scenario_ref=_freeze(
            {"id": scenario_id, "version": "1", "digest": digest}
        ),
    )
