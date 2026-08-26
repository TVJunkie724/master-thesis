import json
from types import SimpleNamespace

from src.services.architecture_contract_service import calculate_digest
from src.services.architecture_projection_service import (
    provider_for_component,
    provider_path,
    required_providers,
)


ASSIGNMENTS = (
    ("component.ingestion", "aws"),
    ("component.processing", "azure"),
    ("component.hot-storage", "azure"),
    ("component.cool-storage", "azure"),
    ("component.archive-storage", "azure"),
    ("component.twin-state", "azure"),
    ("component.visualization", "azure"),
    ("component.eventing", "aws"),
)


def _selected_twin(*, corrupt_digest: bool = False):
    document = {
        "component_assignments": [
            {"logical_component_id": logical_id, "provider": provider}
            for logical_id, provider in ASSIGNMENTS
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
    return SimpleNamespace(cost_calculation_runs=[run])


def test_selected_architecture_projects_all_six_layer_components():
    twin = _selected_twin()

    assert required_providers(twin) == {"aws", "azure"}
    assert provider_path(twin) == {
        "l1": "aws",
        "l2": "azure",
        "l3_hot": "azure",
        "l3_cool": "azure",
        "l3_archive": "azure",
        "l4": "azure",
        "l5": "azure",
        "eventing": "aws",
    }
    assert provider_for_component(twin, "component.eventing") == "aws"


def test_missing_or_corrupt_architecture_has_no_provider_fallback():
    assert required_providers(SimpleNamespace(cost_calculation_runs=[])) == set()
    assert required_providers(_selected_twin(corrupt_digest=True)) == set()
