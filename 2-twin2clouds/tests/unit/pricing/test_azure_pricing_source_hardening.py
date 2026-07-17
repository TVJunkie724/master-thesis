import json
from unittest.mock import patch

import pytest

from backend.azure_pricing_evidence import build_azure_intent_evidence
from backend.fetch_data.cloud_price_fetcher_azure import fetch_azure_price
from backend.pricing_schema import attach_pricing_metadata, validate_pricing_payload


REGION = "westeurope"


def _azure_row(**overrides):
    row = {
        "currencyCode": "USD",
        "retailPrice": 0.25,
        "unitPrice": 0.25,
        "unitOfMeasure": "1 GB/Month",
        "armRegionName": REGION,
        "serviceName": "Azure Cosmos DB",
        "productName": "Azure Cosmos DB",
        "skuName": "RUs",
        "meterName": "Data Stored",
        "meterId": "aa57abaf-ec18-4387-9348-07b177eab8db",
        "skuId": "DZH318Z0BPJH/0028",
        "productId": "DZH318Z0BPJH",
        "type": "Consumption",
        "tierMinimumUnits": 0,
        "isPrimaryMeterRegion": True,
        "effectiveStartDate": "2023-01-01T00:00:00Z",
    }
    row.update(overrides)
    return row


def _blob_row(storage_class, meter_id, sku_id, price):
    return _azure_row(
        serviceName="Storage",
        productName="Blob Storage",
        skuName=f"{storage_class} LRS",
        meterName=f"{storage_class} LRS Data Stored",
        meterId=meter_id,
        skuId=sku_id,
        productId="DZH318Z0BNZJ",
        retailPrice=price,
        unitPrice=price,
    )


def _transfer_rows():
    prices = [(0, 0), (100, 0.087), (10335, 0.083), (51295, 0.07), (153695, 0.05), (512095, 0.05)]
    return [
        _azure_row(
            serviceName="Bandwidth",
            productName="Rtn Preference: MGN",
            skuName="Standard",
            meterName="Standard Data Transfer Out",
            meterId="9995d93a-7d35-4d3f-9c69-7a7fea447ef4",
            skuId="DZH318Z0BNVX/003F",
            productId="DZH318Z0BNVX",
            unitOfMeasure="1 GB",
            retailPrice=price,
            unitPrice=price,
            tierMinimumUnits=threshold,
            isPrimaryMeterRegion=False,
        )
        for threshold, price in prices
    ]


def _adt_row(
    *,
    meter_name,
    price,
    meter_id,
    sku_id="DZH318Z0BZ0T/000C",
    region=REGION,
):
    return _azure_row(
        serviceName="Digital Twins",
        productName="Digital Twins",
        skuName="Standard",
        meterName=meter_name,
        meterId=meter_id,
        skuId=sku_id,
        productId="DZH318Z0BZ0T",
        unitOfMeasure="1K",
        armRegionName=region,
        retailPrice=price,
        unitPrice=price,
        isPrimaryMeterRegion=True,
    )


def _adt_rows(*, region=REGION):
    suffix = "weu" if region == REGION else "eus"
    prices = (
        (0.00325, 0.00130, 0.00065)
        if region == REGION
        else (0.00250, 0.00100, 0.00050)
    )
    sku_id = "DZH318Z0BZ0T/000C" if region == REGION else "DZH318Z0BZ0T/0005"
    return [
        _adt_row(
            meter_name="Standard Operations",
            price=prices[0],
            meter_id=f"operation-{suffix}",
            sku_id=sku_id,
            region=region,
        ),
        _adt_row(
            meter_name="Standard Message",
            price=prices[1],
            meter_id=f"message-{suffix}",
            sku_id=sku_id,
            region=region,
        ),
        _adt_row(
            meter_name="Standard Query Units",
            price=prices[2],
            meter_id=f"query-{suffix}",
            sku_id=sku_id,
            region=region,
        ),
    ]


@pytest.mark.parametrize(
    ("neutral_service", "row", "expected"),
    [
        ("storage_hot", _azure_row(), 0.25),
        (
            "storage_cool",
            _blob_row(
                "Cool",
                "8bf84600-37ce-42ab-a6d7-0c322aed8182",
                "DZH318Z0BNZJ/0096",
                0.01,
            ),
            0.01,
        ),
        (
            "storage_archive",
            _blob_row(
                "Archive",
                "7d07cbf5-5686-4123-9ebe-36ca3e461c43",
                "DZH318Z0BNZJ/0097",
                0.0018,
            ),
            0.0018,
        ),
    ],
)
@patch("backend.fetch_data.cloud_price_fetcher_azure._retail_query_items")
def test_exact_storage_rows_override_broad_keyword_candidates(
    mock_query, neutral_service, row, expected
):
    mock_query.return_value = [
        row,
        _azure_row(
            meterId="wrong-meter",
            skuId="wrong-sku",
            productId="wrong-product",
            productName="Data Lake Storage",
            retailPrice=0.0001,
            unitPrice=0.0001,
        ),
    ]
    service_name = "Azure Cosmos DB" if neutral_service == "storage_hot" else "Storage"

    result = fetch_azure_price(
        neutral_service,
        REGION,
        {REGION: REGION},
        {neutral_service: {"azure": service_name}},
    )

    assert result["storagePrice"] == expected
    record = result["__evidence__"]["storagePrice"]
    assert record["match_status"] == "matched"
    assert record["review_required"] is False
    assert record["selected_row"]["effectiveStartDate"] == "2023-01-01T00:00:00Z"
    assert record["rejected_rows"]


@patch("backend.fetch_data.cloud_price_fetcher_azure._retail_query_items")
def test_transfer_rows_build_exact_canonical_decimal_gb_tiers(mock_query):
    mock_query.return_value = _transfer_rows() + [
        _transfer_rows()[1]
        | {
            "productName": "Bandwidth - Routing Preference: Internet",
            "meterId": "wrong-routing-meter",
            "skuId": "wrong-routing-sku",
            "retailPrice": 0.08,
            "unitPrice": 0.08,
        }
    ]

    result = fetch_azure_price(
        "transfer",
        REGION,
        {REGION: REGION},
        {"transfer": {"azure": "Bandwidth"}},
    )

    assert "egressPrice" not in result
    assert result["billing_unit"] == "gb"
    assert result["bytes_per_billing_unit"] == 1_000_000_000
    assert result["network_tier"] == "microsoft_premium_global_network"
    assert [
        (
            tier["start_quantity"],
            tier["end_quantity"],
            tier["unit_price"],
        )
        for tier in result["pricing_tiers"]
    ] == [
        (0, 100, 0),
        (100, 10335, 0.087),
        (10335, 51295, 0.083),
        (51295, 153695, 0.07),
        (153695, 512095, 0.05),
        (512095, None, 0.05),
    ]
    evidence = result["__evidence__"]["pricing_tiers"]
    assert len(evidence["selected_rows"]) == 6
    assert evidence["rejected_rows"][0]["productName"] == "Bandwidth - Routing Preference: Internet"
    assert result["__transfer_evidence__"]["evidence_id"] == result["evidence_id"]


@pytest.mark.parametrize(
    ("region", "expected", "expected_sku"),
    [
        (
            "westeurope",
            {
                "pricePerOperation": 0.00000325,
                "pricePerMessage": 0.00000130,
                "pricePerQueryUnit": 0.00000065,
            },
            "DZH318Z0BZ0T/000C",
        ),
        (
            "eastus",
            {
                "pricePerOperation": 0.00000250,
                "pricePerMessage": 0.00000100,
                "pricePerQueryUnit": 0.00000050,
            },
            "DZH318Z0BZ0T/0005",
        ),
    ],
)
@patch("backend.fetch_data.cloud_price_fetcher_azure._retail_query_items")
def test_adt_meters_are_selected_semantically_and_normalized_per_unit(
    mock_query,
    region,
    expected,
    expected_sku,
):
    mock_query.return_value = _adt_rows(region=region)

    result = fetch_azure_price(
        "twinmaker",
        region,
        {region: region},
        {"twinmaker": {"azure": "Digital Twins"}},
    )

    for field, value in expected.items():
        assert result[field] == pytest.approx(value)
        evidence = result["__evidence__"][field]
        assert evidence["match_status"] == "matched"
        assert evidence["review_required"] is False
        assert evidence["selected_row"]["armRegionName"] == region
        assert evidence["selected_row"]["skuId"] == expected_sku
        assert evidence["selected_row"]["meterId"]


def test_adt_duplicate_semantic_candidate_fails_closed_as_ambiguous():
    duplicate = _adt_rows()
    duplicate.append(
        _adt_row(
            meter_name="Standard Query Units",
            price=0.00070,
            meter_id="query-weu-v2",
        )
    )

    evidence = build_azure_intent_evidence(
        duplicate,
        intent_id="digital_twin.query_unit",
        region=REGION,
    )

    assert evidence["match_status"] == "ambiguous"
    assert evidence["review_required"] is True
    assert evidence["normalized_value"] is None
    assert evidence["selected_row"] is None
    assert len(evidence["candidate_rows"]) == 2


def test_changed_stable_identity_fails_closed():
    evidence = build_azure_intent_evidence(
        [_azure_row(unitOfMeasure="100 GB/Month")],
        intent_id="storage.hot.storage_gb_month",
        region=REGION,
    )

    assert evidence["match_status"] == "changed"
    assert evidence["review_required"] is True
    assert evidence["normalized_value"] is None


def test_same_meter_id_across_consumption_and_reservation_rows_does_not_collide():
    exact = _blob_row(
        "Cool",
        "8bf84600-37ce-42ab-a6d7-0c322aed8182",
        "DZH318Z0BNZJ/0096",
        0.01,
    )
    reservation = exact | {
        "productName": "Storage Reserved Capacity_v8",
        "skuName": "Cool - 10 PB LRS",
        "meterName": "Cool - 10 PB LRS Data Stored",
        "productId": "DZH318XZM2XZ",
        "skuId": "DZH318XZM2XZ/01PZ",
        "type": "Reservation",
        "retailPrice": 9_311_400.0,
        "unitPrice": 9_311_400.0,
        "isPrimaryMeterRegion": False,
    }

    evidence = build_azure_intent_evidence(
        [exact, reservation],
        intent_id="storage.cool.storage_gb_month",
        region=REGION,
    )

    assert evidence["normalized_value"] == 0.01
    assert evidence["selected_row"]["productName"] == "Blob Storage"
    assert evidence["selected_row"]["candidate_id"] != evidence["rejected_rows"][0]["candidate_id"]


def test_rejected_evidence_is_bounded_and_does_not_expose_secret_fields():
    rejected = [
        _azure_row(
            meterId=f"wrong-meter-{index}",
            productName="Backup Storage",
            client_secret="must-not-survive",
        )
        for index in range(30)
    ]

    evidence = build_azure_intent_evidence(
        [_azure_row(), *rejected],
        intent_id="storage.hot.storage_gb_month",
        region=REGION,
    )

    assert len(evidence["rejected_rows"]) == 25
    assert "must-not-survive" not in json.dumps(evidence)
    assert all("raw_payload_ref" not in row for row in evidence["rejected_rows"])


@patch("backend.fetch_data.cloud_price_fetcher_azure._retail_query_items")
def test_non_usd_exact_row_fails_closed(mock_query):
    mock_query.return_value = [_azure_row(currencyCode="EUR")]

    result = fetch_azure_price(
        "storage_hot",
        REGION,
        {REGION: REGION},
        {"storage_hot": {"azure": "Azure Cosmos DB"}},
    )

    assert "storagePrice" not in result
    evidence = result["__evidence__"]["storagePrice"]
    assert evidence["review_required"] is True
    assert evidence["errors"] == [
        "Azure pricing intent storage.hot.storage_gb_month returned non-USD currency"
    ]


@patch("backend.fetch_data.cloud_price_fetcher_azure._retail_query_items")
def test_generated_metadata_exposes_bounded_evidence_and_derived_transfer_value(mock_query):
    mock_query.return_value = _transfer_rows()
    transfer = fetch_azure_price(
        "transfer",
        REGION,
        {REGION: REGION},
        {"transfer": {"azure": "Bandwidth"}},
    )
    payload = attach_pricing_metadata(
        "azure",
        {
            "transfer": {
                key: value
                for key, value in transfer.items()
                if not key.startswith("__")
            }
        },
        {"transfer": transfer},
    )

    fields = payload["__evidence__"]["fields"]
    assert fields["transfer.pricing_tiers"]["selected_rows"]
    assert fields["transfer.catalog"]["evidence_id"] == transfer["evidence_id"]
    assert "__evidence__" not in validate_pricing_payload("azure", payload)["missing_keys"]
