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
    for name in (
        "intents.yaml",
        "normalization.yaml",
        "service_models.yaml",
        "review_decisions.yaml",
        "pricing_model_classifications.yaml",
        "price_source_classifications.yaml",
        "optimization_bundles.yaml",
        "calculation_strategies.yaml",
        "formula_sets.yaml",
        "workload_contracts.yaml",
        "provider_pricing_contracts.yaml",
        "transfer_routes.yaml",
    ):
        path = root / name
        path.write_text(path.read_text().replace("2026.07.17", "2026.07.18"))

    service = PricingRegistryService(root)

    assert service.get_registry_version() == "2026.07.18"


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
    expected = PricingRegistryService().get_status()

    assert response.status_code == 200
    body = response.json()
    assert body == expected
    assert body["provider_mapping_counts"]["aws"] == 19
    assert body["provider_mapping_counts"]["azure"] == 18
    assert body["provider_mapping_counts"]["gcp"] == 16


def test_list_pricing_registry_intents_endpoint_supports_metric_filter():
    response = client.get("/pricing-registry/intents?metric=cost")

    assert response.status_code == 200
    body = response.json()
    assert body["registry_version"] == "2026.07.17"
    assert "api.request_million" in body["items"]
    assert all(intent["group"] == "cost" for intent in body["items"].values())


def test_get_pricing_registry_intent_endpoint_returns_stable_shape():
    response = client.get("/pricing-registry/intents/api.request_million")

    assert response.status_code == 200
    assert response.json() == {
        "registry_version": "2026.07.17",
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


def test_list_pricing_model_classifications_endpoint_supports_provider_filter():
    response = client.get("/pricing-registry/pricing-model-classifications?provider=aws")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 19
    assert body["items"]["aws.iot_message_ingest.model.v1"]["pricing_model_type"] == (
        "tiered_message_unit"
    )
    assert (
        body["items"]["aws.digital_twin_account_bundle_month.model.v1"][
            "pricing_model_type"
        ]
        == "account_wide_tiered_bundle"
    )
    assert all(item["provider"] == "aws" for item in body["items"].values())


def test_list_price_source_classifications_endpoint_supports_provider_filter():
    response = client.get("/pricing-registry/price-source-classifications?provider=gcp")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 16
    assert body["items"]["gcp.iot_message_ingest.source.v1"]["source_type"] == "provider_api"
    assert all(item["provider"] == "gcp" for item in body["items"].values())


def test_field_verification_matrix_endpoint_covers_active_fields():
    response = client.get("/pricing-registry/field-verification-matrix")

    assert response.status_code == 200
    rows = response.json()["items"]
    expected_count = sum(
        PricingRegistryService().get_status()["provider_mapping_counts"].values()
    )
    assert len(rows) == expected_count
    assert {
        (row["provider"], row["field"], row["selected_source_type"])
        for row in rows
    } >= {
        ("aws", "iot.message_ingest", "provider_api"),
        ("azure", "iot.message_ingest", "provider_api"),
        ("gcp", "iot.message_ingest", "provider_api"),
    }
    assert all(row["verification_status"] == "passed" for row in rows)


def test_unknown_provider_filter_returns_structured_404():
    response = client.get("/pricing-registry/field-verification-matrix?provider=oracle")

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "PRICING_REGISTRY_ITEM_NOT_FOUND"


def test_list_optimization_bundles_endpoint_exposes_strategy_contract():
    response = client.get("/pricing-registry/optimization-bundles")

    assert response.status_code == 200
    bundle = response.json()["items"]["cost_minimization_v1"]
    assert bundle["calculation_strategy_id"] == "cost_calculation_v2"
    assert bundle["formula_set_id"] == "cost_formula_set_v1"
    assert bundle["workload_contract_id"] == "digital_twin_workload_v1"
    assert len(bundle["provider_pricing_contract_ids"]) == (
        PricingRegistryService().get_status()["provider_pricing_contract_count"]
    )


def test_list_provider_pricing_contracts_endpoint_supports_provider_filter():
    response = client.get("/pricing-registry/provider-pricing-contracts?provider=azure")

    assert response.status_code == 200
    contracts = response.json()["items"]
    assert len(contracts) == (
        PricingRegistryService().get_status()["provider_mapping_counts"]["azure"]
    )
    assert all(contract["provider"] == "azure" for contract in contracts.values())
    assert {
        "azure.digital_twin_operation.pricing_contract.v1",
        "azure.digital_twin_message.pricing_contract.v1",
        "azure.digital_twin_query_unit.pricing_contract.v1",
    } <= set(contracts)
    assert contracts["azure.iot_message_ingest.pricing_contract.v1"][
        "allowed_formula_refs"
    ] == ["tiered_unit_cost"]
