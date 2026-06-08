import json

from backend.azure_pricing_evidence import (
    AZURE_EVIDENCE_REPORT_SCHEMA_VERSION,
    build_azure_pricing_evidence_report,
    write_azure_pricing_evidence_report,
)
from backend.pricing_evidence import validate_evidence_report


FETCHED_AT = "2026-06-08T12:00:00Z"


class FakeRegistryService:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def list_provider_mappings(self, provider):
        self.calls.append(("list_provider_mappings", provider))
        return {self.mapping["intent_id"]: self.mapping}

    def list_normalization_rules(self):
        self.calls.append(("list_normalization_rules", None))
        return {
            "per_1m_requests": {
                "source_units": ["1M Calls"],
                "target_unit": "1m_requests",
                "multiplier": 1,
            },
            "per_request": {
                "source_units": ["Requests"],
                "target_unit": "request",
                "multiplier": 1,
            },
        }

    def get_registry_version(self):
        self.calls.append(("get_registry_version", None))
        return "test-registry.v1"


def _mapping(**overrides):
    mapping = {
        "intent_id": "api.request_million",
        "provider": "azure",
        "mapping_version": "2026.06.08",
        "review_status": "reviewed",
        "normalization_rule": "per_1m_requests",
        "match": {
            "service_name": "API Management",
            "sku_name": "Consumption",
            "meter_name": "Calls",
            "unit": "1M Calls",
            "price_type": "Consumption",
            "region": "westeurope",
        },
    }
    mapping.update(overrides)
    return mapping


def _row(**overrides):
    row = {
        "currencyCode": "USD",
        "retailPrice": 3.5,
        "unitOfMeasure": "1M Calls",
        "armRegionName": "westeurope",
        "serviceName": "API Management",
        "productName": "API Management",
        "skuName": "Consumption",
        "meterName": "Calls",
        "meterId": "meter-api-consumption",
        "skuId": "sku-consumption",
        "productId": "product-api-management",
        "priceType": "Consumption",
        "tierMinimumUnits": 0,
        "isPrimaryMeterRegion": True,
    }
    row.update(overrides)
    return row


def test_azure_evidence_report_preserves_selected_retail_row_and_normalization():
    service = FakeRegistryService(_mapping())

    report = build_azure_pricing_evidence_report(
        [_row()],
        region="westeurope",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )

    assert report["schema_version"] == AZURE_EVIDENCE_REPORT_SCHEMA_VERSION
    assert report["review_required"] is False
    assert service.calls == [
        ("list_provider_mappings", "azure"),
        ("list_normalization_rules", None),
        ("get_registry_version", None),
    ]
    record = report["records"][0]
    assert record["intent_id"] == "api.request_million"
    assert record["match_status"] == "matched"
    assert record["source_type"] == "fetched"
    assert record["normalization_rule"] == "per_1m_requests"
    assert record["normalized_value"] == 3.5
    assert record["currency"] == "USD"
    assert record["selected_row"]["serviceName"] == "API Management"
    assert record["selected_row"]["productName"] == "API Management"
    assert record["selected_row"]["skuName"] == "Consumption"
    assert record["selected_row"]["meterName"] == "Calls"
    assert record["selected_row"]["unitOfMeasure"] == "1M Calls"
    assert record["selected_row"]["retailPrice"] == 3.5
    assert record["selected_row"]["currencyCode"] == "USD"
    assert record["selected_row"]["armRegionName"] == "westeurope"
    assert record["selected_row"]["tierMinimumUnits"] == 0
    assert record["selected_row"]["meterId"] == "meter-api-consumption"
    assert record["selected_row"]["skuId"] == "sku-consumption"
    assert record["selected_row"]["productId"] == "product-api-management"
    assert record["selected_row"]["raw_payload_ref"]["meterId"] == "meter-api-consumption"
    assert record["candidate_rows"][0]["candidate_id"].startswith("azure:meter-api-consumption")
    assert validate_evidence_report(report["records"], publishable=True) == []


def test_azure_evidence_ambiguous_matches_are_review_required_with_candidates():
    service = FakeRegistryService(_mapping(match={"service_name": "API Management"}))

    report = build_azure_pricing_evidence_report(
        [
            _row(meterId="meter-a", meterName="Calls"),
            _row(meterId="meter-b", meterName="Other Calls"),
        ],
        region="westeurope",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )

    record = report["records"][0]
    assert record["match_status"] == "ambiguous"
    assert record["review_required"] is True
    assert record["selected_row"] is None
    assert len(record["candidate_rows"]) == 2
    assert record["errors"] == ["Multiple Azure candidates matched api.request_million"]
    assert any("review_required evidence is not publishable" in error for error in validate_evidence_report(report["records"], publishable=True))


def test_azure_evidence_missing_match_is_review_required_not_fallback():
    service = FakeRegistryService(_mapping())

    report = build_azure_pricing_evidence_report(
        [_row(serviceName="Logic Apps", meterId="logic-meter")],
        region="westeurope",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )

    record = report["records"][0]
    assert record["match_status"] == "missing"
    assert record["source_type"] == "not_applicable"
    assert record["review_required"] is True
    assert record["selected_row"] is None
    assert record["normalized_value"] is None
    assert record["errors"] == ["No Azure candidate matched api.request_million"]
    assert "fallback_static" not in json.dumps(report)


def test_azure_evidence_keeps_rejected_alternatives():
    service = FakeRegistryService(_mapping())

    report = build_azure_pricing_evidence_report(
        [
            _row(),
            _row(meterId="meter-rejected", skuName="Developer", meterName="Calls"),
        ],
        region="westeurope",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )

    rejected = report["records"][0]["rejected_rows"]
    assert rejected
    assert rejected[0]["candidate_id"].startswith("azure:meter-rejected")
    assert rejected[0]["serviceName"] == "API Management"
    assert rejected[0]["skuName"] == "Developer"
    assert rejected[0]["meterName"] == "Calls"
    assert rejected[0]["retailPrice"] == 3.5
    assert any("sku_name" in reason for reason in rejected[0]["reasons"])


def test_write_azure_evidence_report_writes_only_explicit_target(tmp_path):
    service = FakeRegistryService(_mapping())
    report = build_azure_pricing_evidence_report(
        [_row()],
        region="westeurope",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )
    target = tmp_path / "generated" / "azure-evidence.json"

    write_azure_pricing_evidence_report(report, target)

    assert target.exists()
    assert json.loads(target.read_text())["schema_version"] == AZURE_EVIDENCE_REPORT_SCHEMA_VERSION
