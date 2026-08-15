import json
from types import SimpleNamespace

from src.services.architecture_contract_service import calculate_digest
from src.services.architecture_projection_service import (
    compatibility_provider_for_component,
    compatibility_required_providers,
    provider_path,
    required_providers,
)


BASE_ASSIGNMENTS = (
    ("component.ingestion", "aws"),
    ("component.processing", "azure"),
    ("component.hot-storage", "gcp"),
    ("component.cool-storage", "aws"),
    ("component.archive-storage", "azure"),
    ("component.twin-state", "gcp"),
    ("component.visualization", "aws"),
)


def _optimizer(**overrides):
    values = {
        "cheapest_l1": None,
        "cheapest_l2": None,
        "cheapest_l3_hot": None,
        "cheapest_l3_cool": None,
        "cheapest_l3_archive": None,
        "cheapest_l4": None,
        "cheapest_l5": None,
        "result_json": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _selected_twin(*, corrupt_digest=False, extra_assignments=()):
    document = {
        "component_assignments": [
            {"logical_component_id": logical_id, "provider": provider}
            for logical_id, provider in (*BASE_ASSIGNMENTS, *extra_assignments)
        ]
    }
    digest = calculate_digest(document)
    document["content_digest"] = digest
    persisted_digest = "sha256:" + ("0" * 64) if corrupt_digest else digest
    record = SimpleNamespace(
        canonical_json=json.dumps(document),
        content_digest=persisted_digest,
        functional_completeness_status="complete",
    )
    run = SimpleNamespace(
        selected_for_deployment_at=object(),
        status="succeeded",
        architecture_compatibility_status="ready",
        resolved_architecture=record,
        resolved_architecture_digest=persisted_digest,
    )
    return SimpleNamespace(
        cost_calculation_runs=[run],
        optimizer_config=_optimizer(cheapest_l1="gcp"),
    )


def test_selected_architecture_projects_baseline_and_event_providers():
    twin = _selected_twin(
        extra_assignments=(("component.event-broker", "azure"),)
    )

    assert required_providers(twin) == {"aws", "azure", "gcp"}
    assert provider_path(twin) == {
        "l1": "aws",
        "l2": "azure",
        "l3_hot": "gcp",
        "l3_cool": "aws",
        "l3_archive": "azure",
        "l4": "gcp",
        "l5": "aws",
    }


def test_legacy_projection_is_used_only_without_a_selected_architecture():
    twin = SimpleNamespace(
        optimizer_config=_optimizer(cheapest_l1="AWS", cheapest_l4="Azure")
    )

    assert compatibility_required_providers(twin) == {"aws", "azure"}
    assert compatibility_provider_for_component(twin, "component.ingestion") == "aws"


def test_corrupt_selected_architecture_fails_closed_without_legacy_fallback():
    twin = _selected_twin(corrupt_digest=True)

    assert compatibility_required_providers(twin) == set()
    assert compatibility_provider_for_component(twin, "component.ingestion") is None
