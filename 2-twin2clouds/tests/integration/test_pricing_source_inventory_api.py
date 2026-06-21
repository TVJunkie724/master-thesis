"""
Pricing source inventory API contract tests.
"""

from fastapi.testclient import TestClient

from rest_api import app


client = TestClient(app)


def test_pricing_source_inventory_returns_typed_contract():
    response = client.get("/pricing/source_inventory")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "pricing-source-inventory.v1"
    assert payload["objective"] == "cost"
    assert payload["provider"] is None
    assert payload["summary"]["total"] == len(payload["records"])
    assert payload["summary"]["review_required"] > 0

    record = next(
        item
        for item in payload["records"]
        if item["record_id"] == "azure.l4.digital_twins.query_unit_tiers"
    )
    assert record["primary_source_type"] == "static_official_table"
    assert record["refreshability"] == "static_non_fetchable"
    assert record["failure_behavior"] == "require_review"
    assert record["review_state"] == "review_required"
    assert record["key_path"] == ["azure", "azureDigitalTwins", "queryUnitTiers"]


def test_pricing_source_inventory_filters_by_provider():
    response = client.get("/pricing/source_inventory", params={"provider": "azure"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "azure"
    assert payload["summary"]["total"] == len(payload["records"])
    assert payload["records"]
    assert {record["provider"] for record in payload["records"]} == {"azure"}


def test_pricing_source_inventory_rejects_unknown_provider():
    response = client.get("/pricing/source_inventory", params={"provider": "oracle"})

    assert response.status_code == 400
    assert "Invalid provider" in response.json()["detail"]


def test_pricing_source_inventory_is_declared_in_openapi():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    endpoint = schema["paths"]["/pricing/source_inventory"]["get"]
    assert endpoint["operationId"] == "getPricingSourceInventory"
    assert "PricingSourceInventoryResponse" in str(endpoint["responses"]["200"])
