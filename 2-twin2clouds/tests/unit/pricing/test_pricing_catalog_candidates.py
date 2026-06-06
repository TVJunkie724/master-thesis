import json

from backend.pricing_catalog_candidates import (
    CANDIDATE_SCHEMA_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    build_pricing_catalog_snapshot,
    extract_pricing_candidates,
    write_pricing_catalog_snapshot,
)


FETCHED_AT = "2026-06-06T20:00:00Z"


def test_azure_catalog_snapshot_preserves_ambiguous_meter_candidates():
    raw_items = [
        {
            "currencyCode": "USD",
            "retailPrice": 0.000025,
            "unitOfMeasure": "1 Action",
            "armRegionName": "westeurope",
            "serviceName": "Logic Apps",
            "productName": "Logic Apps",
            "skuName": "Consumption",
            "meterName": "Actions",
            "meterId": "meter-actions",
            "skuId": "sku-consumption",
            "productId": "product-logic-apps",
            "priceType": "Consumption",
            "tierMinimumUnits": 0,
            "isPrimaryMeterRegion": True,
        },
        {
            "currencyCode": "USD",
            "retailPrice": 0.000125,
            "unitOfMeasure": "1 Action",
            "armRegionName": "westeurope",
            "serviceName": "Logic Apps",
            "productName": "Logic Apps Standard",
            "skuName": "Standard",
            "meterName": "Actions",
            "meterId": "meter-standard-actions",
            "skuId": "sku-standard",
            "productId": "product-logic-apps-standard",
            "priceType": "Consumption",
            "tierMinimumUnits": 0,
            "isPrimaryMeterRegion": True,
        },
    ]

    snapshot = build_pricing_catalog_snapshot(
        "azure",
        raw_items,
        source_api="azure-retail-prices",
        request_scope={"region": "westeurope", "service": "Logic Apps"},
        fetched_at=FETCHED_AT,
    )

    assert snapshot["schema_version"] == SNAPSHOT_SCHEMA_VERSION
    assert snapshot["candidate_count"] == 2
    assert len({candidate["candidate_id"] for candidate in snapshot["candidates"]}) == 2
    assert [candidate["provider_identifiers"]["meter_id"] for candidate in snapshot["candidates"]] == [
        "meter-actions",
        "meter-standard-actions",
    ]
    assert snapshot["candidates"][0]["schema_version"] == CANDIDATE_SCHEMA_VERSION
    assert snapshot["candidates"][0]["unit"] == "1 Action"
    assert snapshot["candidates"][0]["price_type"] == "Consumption"


def test_aws_candidate_extraction_preserves_sku_rate_and_usage_evidence():
    raw_price_list_item = {
        "product": {
            "sku": "AWS-SKU-1",
            "productFamily": "API Gateway Request",
            "attributes": {
                "servicecode": "AmazonApiGateway",
                "servicename": "Amazon API Gateway",
                "location": "EU (Frankfurt)",
                "locationType": "AWS Region",
                "usagetype": "EU-Requests",
                "operation": "ApiGatewayRequest",
            },
        },
        "terms": {
            "OnDemand": {
                "AWS-SKU-1.JRTCKXETXF": {
                    "priceDimensions": {
                        "AWS-SKU-1.JRTCKXETXF.6YS6EN2CT7": {
                            "rateCode": "AWS-SKU-1.JRTCKXETXF.6YS6EN2CT7",
                            "description": "$1.00 per million requests",
                            "beginRange": "0",
                            "endRange": "Inf",
                            "unit": "Requests",
                            "pricePerUnit": {"USD": "0.000001"},
                        }
                    }
                }
            }
        },
    }

    candidates = extract_pricing_candidates(
        "aws",
        [json.dumps(raw_price_list_item)],
        source_snapshot_id="aws-snapshot",
        fetched_at=FETCHED_AT,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["candidate_id"] == "aws:AWS-SKU-1:AWS-SKU-1.JRTCKXETXF.6YS6EN2CT7"
    assert candidate["provider_identifiers"]["sku"] == "AWS-SKU-1"
    assert candidate["provider_identifiers"]["service_code"] == "AmazonApiGateway"
    assert candidate["provider_identifiers"]["usage_type"] == "EU-Requests"
    assert candidate["raw_price"] == 0.000001
    assert candidate["currency"] == "USD"
    assert candidate["tier"] == {"begin_range": "0", "end_range": "Inf"}


def test_gcp_candidate_extraction_preserves_sku_and_tier_information():
    raw_sku = {
        "serviceId": "6F81-5844-456A",
        "serviceDisplayName": "API Gateway",
        "skuId": "gcp-sku-1",
        "description": "API calls",
        "serviceRegions": ["europe-west1"],
        "category": {
            "resourceFamily": "ApplicationServices",
            "resourceGroup": "API Gateway",
            "usageType": "OnDemand",
        },
        "pricingInfo": [
            {
                "pricingExpression": {
                    "usageUnitDescription": "request",
                    "baseUnit": "request",
                    "baseUnitDescription": "request",
                    "tieredRates": [
                        {
                            "startUsageAmount": 0,
                            "unitPrice": {
                                "currencyCode": "USD",
                                "units": "0",
                                "nanos": 3_000,
                            },
                        },
                        {
                            "startUsageAmount": 1_000_000,
                            "unitPrice": {
                                "currencyCode": "USD",
                                "units": "0",
                                "nanos": 2_000,
                            },
                        },
                    ],
                }
            }
        ],
    }

    candidates = extract_pricing_candidates(
        "gcp",
        [raw_sku],
        source_snapshot_id="gcp-snapshot",
        fetched_at=FETCHED_AT,
    )

    assert len(candidates) == 2
    assert candidates[0]["provider_identifiers"]["service_id"] == "6F81-5844-456A"
    assert candidates[0]["provider_identifiers"]["sku_id"] == "gcp-sku-1"
    assert candidates[0]["raw_price"] == 0.000003
    assert candidates[0]["tier"]["start_usage_amount"] == 0
    assert candidates[1]["tier"]["start_usage_amount"] == 1_000_000


def test_snapshot_sanitizes_secret_like_raw_payload_fields():
    snapshot = build_pricing_catalog_snapshot(
        "azure",
        [
            {
                "serviceName": "Example",
                "meterName": "Example Meter",
                "meterId": "meter-1",
                "retailPrice": 1,
                "currencyCode": "USD",
                "unitOfMeasure": "1 Unit",
                "debug_secret": "should-not-survive",
            }
        ],
        source_api="test",
        fetched_at=FETCHED_AT,
    )

    raw_ref = snapshot["candidates"][0]["raw_payload_ref"]
    assert raw_ref["debug_secret"] == "<redacted>"


def test_write_pricing_catalog_snapshot_writes_only_explicit_target(tmp_path):
    snapshot = build_pricing_catalog_snapshot(
        "azure",
        [
            {
                "serviceName": "Example",
                "meterName": "Example Meter",
                "meterId": "meter-1",
                "retailPrice": 1,
                "currencyCode": "USD",
                "unitOfMeasure": "1 Unit",
            }
        ],
        source_api="test",
        fetched_at=FETCHED_AT,
    )
    target = tmp_path / "snapshots" / "azure.json"

    write_pricing_catalog_snapshot(snapshot, target)

    assert target.exists()
    assert json.loads(target.read_text())["schema_version"] == SNAPSHOT_SCHEMA_VERSION
