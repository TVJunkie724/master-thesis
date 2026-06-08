import json
from types import SimpleNamespace

from backend.gcp_pricing_evidence import (
    GCP_EVIDENCE_REPORT_SCHEMA_VERSION,
    build_gcp_pricing_evidence_report,
    redact_gcp_error,
    validate_gcp_billing_catalog_access,
    write_gcp_pricing_evidence_report,
)
from backend.pricing_evidence import validate_evidence_report


FETCHED_AT = "2026-06-08T13:00:00Z"


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
            "per_request": {
                "source_units": ["request"],
                "target_unit": "request",
                "multiplier": 1,
            },
            "per_gb_month": {
                "source_units": ["gibibyte month"],
                "target_unit": "gb_month",
                "multiplier": 1,
            },
        }

    def get_registry_version(self):
        self.calls.append(("get_registry_version", None))
        return "test-registry.v1"


class FakeCatalogClient:
    def __init__(self, services=None, skus=None, services_error=None, skus_error=None):
        self.services = services or []
        self.skus = skus or []
        self.services_error = services_error
        self.skus_error = skus_error
        self.calls = []

    def list_services(self, request):
        self.calls.append(("list_services", request))
        if self.services_error:
            raise self.services_error
        return iter(self.services)

    def list_skus(self, request):
        self.calls.append(("list_skus", request))
        if self.skus_error:
            raise self.skus_error
        return iter(self.skus)


def _mapping(**overrides):
    mapping = {
        "intent_id": "functions.request",
        "provider": "gcp",
        "mapping_version": "2026.06.08",
        "review_status": "reviewed",
        "normalization_rule": "per_request",
        "match": {
            "service_name": "Cloud Run Functions",
            "resource_group": "Invocations",
            "unit": "request",
        },
    }
    mapping.update(overrides)
    return mapping


def _gcp_sku(
    *,
    service_id="6F81-5844-456A",
    service_name="Cloud Run Functions",
    sku_id="sku-functions-request",
    description="Invocations",
    resource_family="Serverless",
    resource_group="Invocations",
    usage_type="OnDemand",
    unit="request",
    base_unit="request",
    base_unit_description="request",
    start_usage_amount=0,
    units="0",
    nanos=400,
    regions=None,
):
    return {
        "serviceId": service_id,
        "serviceDisplayName": service_name,
        "skuId": sku_id,
        "description": description,
        "serviceRegions": regions or ["europe-west1"],
        "category": {
            "resourceFamily": resource_family,
            "resourceGroup": resource_group,
            "usageType": usage_type,
        },
        "pricingInfo": [
            {
                "pricingExpression": {
                    "usageUnitDescription": unit,
                    "baseUnit": base_unit,
                    "baseUnitDescription": base_unit_description,
                    "tieredRates": [
                        {
                            "startUsageAmount": start_usage_amount,
                            "unitPrice": {
                                "currencyCode": "USD",
                                "units": units,
                                "nanos": nanos,
                            },
                        }
                    ],
                }
            }
        ],
    }


def test_gcp_catalog_preflight_success_checks_services_and_skus():
    client = FakeCatalogClient(
        services=[SimpleNamespace(name="services/6F81-5844-456A", service_id="6F81-5844-456A")],
        skus=[object()],
    )

    result = validate_gcp_billing_catalog_access(client)

    assert result["status"] == "valid"
    assert result["required_permissions"] == [
        "cloudbilling.services.list",
        "cloudbilling.skus.list",
    ]
    assert client.calls == [
        ("list_services", {}),
        ("list_skus", {"parent": "services/6F81-5844-456A"}),
    ]


def test_gcp_catalog_preflight_failure_is_structured_and_redacted():
    secret_error = RuntimeError(
        '{"private_key":"-----BEGIN PRIVATE KEY-----abc-----END PRIVATE KEY-----",'
        '"client_email":"svc@example.iam.gserviceaccount.com","token":"abc123"}'
    )
    client = FakeCatalogClient(services_error=secret_error)

    result = validate_gcp_billing_catalog_access(client)

    assert result["status"] == "failed"
    assert result["failed_operation"] == "cloudbilling.services.list"
    assert result["required_permission"] == "cloudbilling.services.list"
    rendered = json.dumps(result)
    assert "BEGIN PRIVATE KEY" not in rendered
    assert "svc@example" not in rendered
    assert "abc123" not in rendered
    assert "<redacted>" in rendered


def test_redact_gcp_error_redacts_service_account_fields():
    message = (
        '{"private_key_id":"key-id",'
        '"private_key":"-----BEGIN PRIVATE KEY-----abc-----END PRIVATE KEY-----",'
        '"client_email":"svc@example.iam.gserviceaccount.com"}'
    )

    redacted = redact_gcp_error(message)

    assert "key-id" not in redacted
    assert "BEGIN PRIVATE KEY" not in redacted
    assert "svc@example" not in redacted


def test_gcp_evidence_report_preserves_selected_sku_rate_and_normalization():
    service = FakeRegistryService(_mapping())
    preflight = {"status": "valid"}

    report = build_gcp_pricing_evidence_report(
        [_gcp_sku()],
        region="europe-west1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
        preflight=preflight,
    )

    assert report["schema_version"] == GCP_EVIDENCE_REPORT_SCHEMA_VERSION
    assert report["review_required"] is False
    assert report["preflight"] == preflight
    assert service.calls == [
        ("list_provider_mappings", "gcp"),
        ("list_normalization_rules", None),
        ("get_registry_version", None),
    ]
    record = report["records"][0]
    assert record["intent_id"] == "functions.request"
    assert record["match_status"] == "matched"
    assert record["source_type"] == "fetched"
    assert record["normalization_rule"] == "per_request"
    assert record["normalized_value"] == 0.0000004
    assert record["selected_row"]["serviceId"] == "6F81-5844-456A"
    assert record["selected_row"]["skuId"] == "sku-functions-request"
    assert record["selected_row"]["serviceDisplayName"] == "Cloud Run Functions"
    assert record["selected_row"]["description"] == "Invocations"
    assert record["selected_row"]["resourceGroup"] == "Invocations"
    assert record["selected_row"]["unit"] == "request"
    assert record["selected_row"]["startUsageAmount"] == 0
    assert record["selected_row"]["pricePerUnit"] == 0.0000004
    assert record["selected_row"]["raw_payload_ref"]["sku"]["skuId"] == "sku-functions-request"
    assert validate_evidence_report(report["records"], publishable=True) == []


def test_gcp_evidence_report_requires_review_when_preflight_not_valid():
    service = FakeRegistryService(_mapping())

    report = build_gcp_pricing_evidence_report(
        [_gcp_sku()],
        region="europe-west1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
        preflight={"status": "failed", "error": {"message": "<redacted>"}},
    )

    assert report["review_required"] is True
    assert report["records"][0]["match_status"] == "matched"


def test_gcp_evidence_ambiguous_matches_are_review_required():
    service = FakeRegistryService(_mapping(match={"service_name": "Cloud Run Functions"}))

    report = build_gcp_pricing_evidence_report(
        [
            _gcp_sku(sku_id="sku-a"),
            _gcp_sku(sku_id="sku-b", description="Memory", resource_group="Compute", unit="gibibyte second"),
        ],
        region="europe-west1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
        preflight={"status": "valid"},
    )

    record = report["records"][0]
    assert record["match_status"] == "ambiguous"
    assert record["review_required"] is True
    assert record["selected_row"] is None
    assert len(record["candidate_rows"]) == 2
    assert record["errors"] == ["Multiple GCP candidates matched functions.request"]


def test_gcp_evidence_missing_match_is_review_required_not_fallback():
    service = FakeRegistryService(_mapping())

    report = build_gcp_pricing_evidence_report(
        [_gcp_sku(service_name="Firestore", resource_group="Storage")],
        region="europe-west1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
        preflight={"status": "valid"},
    )

    record = report["records"][0]
    assert record["match_status"] == "missing"
    assert record["source_type"] == "not_applicable"
    assert record["review_required"] is True
    assert record["selected_row"] is None
    assert record["normalized_value"] is None
    assert "fallback_static" not in json.dumps(report)


def test_gcp_evidence_keeps_rejected_alternatives_with_reasons():
    service = FakeRegistryService(_mapping())

    report = build_gcp_pricing_evidence_report(
        [
            _gcp_sku(),
            _gcp_sku(sku_id="sku-rejected", resource_group="Compute", description="Memory"),
        ],
        region="europe-west1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
        preflight={"status": "valid"},
    )

    rejected = report["records"][0]["rejected_rows"]
    assert rejected
    assert rejected[0]["skuId"] == "sku-rejected"
    assert rejected[0]["resourceGroup"] == "Compute"
    assert any("resource_group" in reason for reason in rejected[0]["reasons"])


def test_write_gcp_evidence_report_writes_only_explicit_target(tmp_path):
    service = FakeRegistryService(_mapping())
    report = build_gcp_pricing_evidence_report(
        [_gcp_sku()],
        region="europe-west1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
        preflight={"status": "valid"},
    )
    target = tmp_path / "generated" / "gcp-evidence.json"

    write_gcp_pricing_evidence_report(report, target)

    assert target.exists()
    assert json.loads(target.read_text())["schema_version"] == GCP_EVIDENCE_REPORT_SCHEMA_VERSION
