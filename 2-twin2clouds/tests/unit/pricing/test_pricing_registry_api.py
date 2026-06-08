import shutil

from fastapi.testclient import TestClient

from backend.pricing_registry import REGISTRY_ROOT
from backend.pricing_registry_service import (
    PricingRegistryLookupError,
    PricingRegistryService,
)
from rest_api import app


client = TestClient(app)


def _copy_registry(tmp_path):
    target = tmp_path / "pricing_registry"
    shutil.copytree(REGISTRY_ROOT, target)
    return target


def test_pricing_registry_service_lists_cost_intents():
    service = PricingRegistryService()

    intents = service.list_intents(metric="cost")

    assert "api.request_million" in intents
    assert all(intent["group"] == "cost" for intent in intents.values())


def test_pricing_registry_service_returns_defensive_copies():
    service = PricingRegistryService()

    intent = service.get_intent("api.request_million")
    intent["group"] = "mutated"

    assert service.get_intent("api.request_million")["group"] == "cost"


def test_pricing_registry_service_reloads_registry_version(tmp_path):
    root = _copy_registry(tmp_path)
    for name in ("intents.yaml", "normalization.yaml", "service_models.yaml", "review_decisions.yaml"):
        path = root / name
        path.write_text(path.read_text().replace("2026.06.08", "2026.06.09"))

    service = PricingRegistryService(root)

    assert service.get_registry_version() == "2026.06.09"


def test_pricing_registry_service_rejects_unknown_provider():
    service = PricingRegistryService()

    try:
        service.list_provider_mappings("oracle")
    except PricingRegistryLookupError as exc:
        assert "Unsupported provider: oracle" in str(exc)
    else:
        raise AssertionError("Expected PricingRegistryLookupError")


def test_get_pricing_registry_status_endpoint():
    response = client.get("/pricing-registry/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "valid"
    assert body["registry_version"] == "2026.06.08"
    assert body["intent_count"] == 16
    assert body["provider_mapping_counts"] == {"aws": 16, "azure": 16, "gcp": 16}


def test_list_pricing_registry_intents_endpoint_supports_metric_filter():
    response = client.get("/pricing-registry/intents?metric=cost")

    assert response.status_code == 200
    body = response.json()
    assert body["registry_version"] == "2026.06.08"
    assert "api.request_million" in body["items"]
    assert all(intent["group"] == "cost" for intent in body["items"].values())


def test_get_pricing_registry_intent_endpoint_returns_stable_shape():
    response = client.get("/pricing-registry/intents/api.request_million")

    assert response.status_code == 200
    assert response.json() == {
        "registry_version": "2026.06.08",
        "item": {
            "group": "cost",
            "description": "API calls normalized per one million requests.",
            "normalized_unit": "1m_requests",
            "required_by": ["cost_model_v1"],
            "expected_providers": ["aws", "azure", "gcp"],
        },
    }


def test_get_pricing_registry_provider_mapping_endpoint():
    response = client.get("/pricing-registry/providers/azure/mappings/api.request_million")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "azure"
    assert body["intent_id"] == "api.request_million"
    assert body["mapping"]["normalization_rule"] == "per_1m_requests"
    assert body["mapping"]["provider"] == "azure"


def test_get_pricing_registry_unknown_intent_returns_structured_404():
    response = client.get("/pricing-registry/intents/does.not.exist")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "PRICING_REGISTRY_ITEM_NOT_FOUND"


def test_get_pricing_registry_unknown_provider_returns_structured_404():
    response = client.get("/pricing-registry/providers/oracle/mappings")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "PRICING_REGISTRY_ITEM_NOT_FOUND"


def test_pricing_registry_endpoints_are_read_only():
    response = client.post("/pricing-registry/intents", json={})

    assert response.status_code == 405
