import json

from backend.aws_pricing_evidence import (
    AWS_EVIDENCE_REPORT_SCHEMA_VERSION,
    build_aws_pricing_evidence_report,
    write_aws_pricing_evidence_report,
)
from backend.pricing_evidence import validate_evidence_report


FETCHED_AT = "2026-06-08T12:30:00Z"


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
                "source_units": ["Requests"],
                "target_unit": "request",
                "multiplier": 1,
            },
            "per_gb_month": {
                "source_units": ["GB-Mo"],
                "target_unit": "gb_month",
                "multiplier": 1,
            },
            "per_1m_requests": {
                "source_units": ["1M Requests"],
                "target_unit": "1m_requests",
                "multiplier": 1,
            },
        }

    def get_registry_version(self):
        self.calls.append(("get_registry_version", None))
        return "test-registry.v1"


def _mapping(**overrides):
    mapping = {
        "intent_id": "functions.request",
        "provider": "aws",
        "mapping_version": "2026.06.08",
        "review_status": "reviewed",
        "normalization_rule": "per_request",
        "match": {
            "service_code": "AWSLambda",
            "product_family": "Serverless Request",
            "unit": "Requests",
        },
    }
    mapping.update(overrides)
    return mapping


def _aws_product(
    *,
    sku="AWS-SKU-1",
    service_code="AWSLambda",
    service_name="AWS Lambda",
    product_family="Serverless Request",
    usage_type="EU-Requests",
    operation="LambdaInvoke",
    rate_code="AWS-SKU-1.JRTCKXETXF.6YS6EN2CT7",
    description="$0.20 per 1M requests",
    unit="Requests",
    price="0.0000002",
    begin_range="0",
    end_range="Inf",
    attributes=None,
):
    product_attributes = {
        "servicecode": service_code,
        "servicename": service_name,
        "location": "EU (Frankfurt)",
        "locationType": "AWS Region",
        "usagetype": usage_type,
        "operation": operation,
    }
    if attributes:
        product_attributes.update(attributes)
    offer_term_code = "JRTCKXETXF"
    return {
        "product": {
            "sku": sku,
            "productFamily": product_family,
            "attributes": product_attributes,
        },
        "terms": {
            "OnDemand": {
                f"{sku}.{offer_term_code}": {
                    "priceDimensions": {
                        rate_code: {
                            "rateCode": rate_code,
                            "description": description,
                            "beginRange": begin_range,
                            "endRange": end_range,
                            "unit": unit,
                            "pricePerUnit": {"USD": price},
                        }
                    }
                }
            }
        },
    }


def test_aws_evidence_report_preserves_selected_product_term_dimension():
    service = FakeRegistryService(_mapping())

    report = build_aws_pricing_evidence_report(
        [json.dumps(_aws_product())],
        region="eu-central-1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
        request_scope={"filters": [{"Field": "location", "Value": "EU (Frankfurt)"}]},
    )

    assert report["schema_version"] == AWS_EVIDENCE_REPORT_SCHEMA_VERSION
    assert report["review_required"] is False
    assert service.calls == [
        ("list_provider_mappings", "aws"),
        ("list_normalization_rules", None),
        ("get_registry_version", None),
    ]
    record = report["records"][0]
    assert record["intent_id"] == "functions.request"
    assert record["match_status"] == "matched"
    assert record["source_type"] == "fetched"
    assert record["normalization_rule"] == "per_request"
    assert record["normalized_value"] == 0.0000002
    assert record["currency"] == "USD"
    assert record["selected_row"]["serviceCode"] == "AWSLambda"
    assert record["selected_row"]["serviceName"] == "AWS Lambda"
    assert record["selected_row"]["productFamily"] == "Serverless Request"
    assert record["selected_row"]["sku"] == "AWS-SKU-1"
    assert record["selected_row"]["usageType"] == "EU-Requests"
    assert record["selected_row"]["operation"] == "LambdaInvoke"
    assert record["selected_row"]["offerTermKey"] == "AWS-SKU-1.JRTCKXETXF"
    assert record["selected_row"]["offerTermCode"] == "JRTCKXETXF"
    assert record["selected_row"]["rateCode"] == "AWS-SKU-1.JRTCKXETXF.6YS6EN2CT7"
    assert record["selected_row"]["description"] == "$0.20 per 1M requests"
    assert record["selected_row"]["unit"] == "Requests"
    assert record["selected_row"]["pricePerUnit"] == 0.0000002
    assert record["selected_row"]["beginRange"] == "0"
    assert record["selected_row"]["endRange"] == "Inf"
    assert record["selected_row"]["attributes"]["location"] == "EU (Frankfurt)"
    assert record["selected_row"]["price_dimension"]["rateCode"] == "AWS-SKU-1.JRTCKXETXF.6YS6EN2CT7"
    assert record["selected_row"]["raw_payload_ref"]["product"]["sku"] == "AWS-SKU-1"
    assert validate_evidence_report(report["records"], publishable=True) == []


def test_aws_evidence_ambiguous_dimensions_are_review_required():
    service = FakeRegistryService(_mapping(match={"service_code": "AWSLambda"}))

    report = build_aws_pricing_evidence_report(
        [
            _aws_product(sku="AWS-SKU-A", rate_code="rate-a"),
            _aws_product(
                sku="AWS-SKU-B",
                rate_code="rate-b",
                product_family="Serverless Compute",
                description="$0.0000166667 for every GB-second",
                unit="Lambda-GB-Second",
                price="0.0000166667",
            ),
        ],
        region="eu-central-1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )

    record = report["records"][0]
    assert record["match_status"] == "ambiguous"
    assert record["review_required"] is True
    assert record["selected_row"] is None
    assert len(record["candidate_rows"]) == 2
    assert record["errors"] == ["Multiple AWS candidates matched functions.request"]
    assert any("review_required evidence is not publishable" in error for error in validate_evidence_report(report["records"], publishable=True))


def test_aws_evidence_missing_match_is_review_required_not_fallback():
    service = FakeRegistryService(_mapping())

    report = build_aws_pricing_evidence_report(
        [_aws_product(service_code="AmazonS3", product_family="Storage")],
        region="eu-central-1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )

    record = report["records"][0]
    assert record["match_status"] == "missing"
    assert record["source_type"] == "not_applicable"
    assert record["review_required"] is True
    assert record["selected_row"] is None
    assert record["normalized_value"] is None
    assert record["errors"] == ["No AWS candidate matched functions.request"]
    assert "fallback_static" not in json.dumps(report)


def test_aws_evidence_keeps_rejected_alternatives_with_reasons():
    service = FakeRegistryService(_mapping())

    report = build_aws_pricing_evidence_report(
        [
            _aws_product(),
            _aws_product(
                sku="AWS-SKU-REJECTED",
                rate_code="rate-rejected",
                product_family="Serverless Compute",
                unit="Lambda-GB-Second",
                description="$0.0000166667 for every GB-second",
                price="0.0000166667",
            ),
        ],
        region="eu-central-1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )

    rejected = report["records"][0]["rejected_rows"]
    assert rejected
    assert rejected[0]["candidate_id"] == "aws:AWS-SKU-REJECTED:rate-rejected"
    assert rejected[0]["serviceCode"] == "AWSLambda"
    assert rejected[0]["productFamily"] == "Serverless Compute"
    assert rejected[0]["unit"] == "Lambda-GB-Second"
    assert any("product_name" in reason for reason in rejected[0]["reasons"])


def test_aws_evidence_supports_storage_class_mapping_alias():
    service = FakeRegistryService(
        _mapping(
            intent_id="storage.cool.storage_gb_month",
            normalization_rule="per_gb_month",
            match={
                "service_code": "AmazonS3",
                "storage_class": "Standard-Infrequent Access",
                "unit": "GB-Mo",
            },
        )
    )

    report = build_aws_pricing_evidence_report(
        [
            _aws_product(
                sku="S3-SKU-1",
                service_code="AmazonS3",
                service_name="Amazon Simple Storage Service",
                product_family="Storage",
                attributes={"volumeType": "Standard-Infrequent Access"},
                usage_type="EU-StandardIAStorage",
                operation="StandardIAStorage",
                rate_code="s3-rate",
                unit="GB-Mo",
                price="0.0125",
                description="$0.0125 per GB-Mo of Standard-IA storage",
            )
        ],
        region="eu-central-1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )

    record = report["records"][0]
    assert record["match_status"] == "matched"
    assert record["selected_row"]["skuName"] == "Standard-Infrequent Access"
    assert record["normalized_value"] == 0.0125


def test_write_aws_evidence_report_writes_only_explicit_target(tmp_path):
    service = FakeRegistryService(_mapping())
    report = build_aws_pricing_evidence_report(
        [_aws_product()],
        region="eu-central-1",
        pricing_registry_service=service,
        fetched_at=FETCHED_AT,
    )
    target = tmp_path / "generated" / "aws-evidence.json"

    write_aws_pricing_evidence_report(report, target)

    assert target.exists()
    assert json.loads(target.read_text())["schema_version"] == AWS_EVIDENCE_REPORT_SCHEMA_VERSION
