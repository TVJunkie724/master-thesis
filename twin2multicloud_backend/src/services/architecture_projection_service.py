"""Read-only projections derived from one selected immutable architecture."""

from __future__ import annotations

import hmac
import json
from typing import Any

from src.services.architecture_contract_service import calculate_digest

LOGICAL_COMPONENT_TO_SLOT = {
    "component.ingestion": "l1",
    "component.processing": "l2",
    "component.hot-storage": "l3_hot",
    "component.cool-storage": "l3_cool",
    "component.archive-storage": "l3_archive",
    "component.twin-state": "l4",
    "component.visualization": "l5",
    "component.eventing": "eventing",
}


def selected_architecture_document(twin) -> dict[str, Any] | None:
    """Return the selected, digest-verified architecture or ``None``.

    This projection is suitable for read/readiness/test helpers. Executable
    deployment packages perform the stricter architecture/specification
    cross-contract validation in ``deployment_service``.
    """

    try:
        runs = tuple(getattr(twin, "cost_calculation_runs", None) or ())
    except TypeError:
        return None
    selected = [
        run
        for run in runs
        if getattr(run, "selected_for_deployment_at", None) is not None
        and getattr(run, "status", None) == "succeeded"
        and getattr(run, "architecture_compatibility_status", None) == "ready"
    ]
    if len(selected) != 1:
        return None
    run = selected[0]
    record = getattr(run, "resolved_architecture", None)
    if (
        record is None
        or getattr(record, "functional_completeness_status", None) != "complete"
    ):
        return None
    try:
        document = json.loads(record.canonical_json)
    except (AttributeError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(document, dict):
        return None
    digest = calculate_digest(document)
    expected = (
        document.get("content_digest"),
        getattr(record, "content_digest", None),
        getattr(run, "resolved_architecture_digest", None),
    )
    if not all(
        isinstance(item, str) and hmac.compare_digest(item, digest) for item in expected
    ):
        return None
    return document


def provider_by_logical_component(twin) -> dict[str, str]:
    """Project every canonical provider assignment by logical component."""

    architecture = selected_architecture_document(twin)
    if architecture is None:
        return {}
    providers: dict[str, str] = {}
    for assignment in architecture.get("component_assignments", ()):
        if not isinstance(assignment, dict):
            return {}
        logical_id = assignment.get("logical_component_id")
        provider = assignment.get("provider")
        if (
            not isinstance(logical_id, str)
            or not logical_id
            or logical_id in providers
            or provider not in {"aws", "azure", "gcp"}
        ):
            return {}
        providers[logical_id] = provider
    return providers


def provider_path(twin) -> dict[str, str]:
    """Return the Eight-component provider path derived from architecture."""

    providers = provider_by_logical_component(twin)
    if not set(LOGICAL_COMPONENT_TO_SLOT).issubset(providers):
        return {}
    return {
        slot: providers[logical_id]
        for logical_id, slot in LOGICAL_COMPONENT_TO_SLOT.items()
    }


def required_providers(twin) -> set[str]:
    """Return the exact provider set required by the selected architecture."""

    return set(provider_by_logical_component(twin).values())


def provider_for_component(twin, logical_component_id: str) -> str | None:
    """Return one provider owned by the selected architecture."""

    return provider_by_logical_component(twin).get(logical_component_id)
