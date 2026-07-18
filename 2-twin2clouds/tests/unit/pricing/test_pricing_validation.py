from backend.pricing_utils import validate_pricing_schema
from tests.unit.pricing.transfer_fixtures import canonical_transfer_fetch


def _aws_transfer():
    return {
        key: value
        for key, value in canonical_transfer_fetch("aws").items()
        if not key.startswith("__")
    }

def test_validate_pricing_schema_valid_aws():
    data = {
        "transfer": _aws_transfer(),
        "iotCore": {"pricePerDeviceAndMonth": 0.1, "priceRulesTriggered": 0.1, "pricing_tiers": []},
        "lambda": {"requestPrice": 0.1, "durationPrice": 0.1, "freeRequests": 0, "freeComputeTime": 0},
        "dynamoDB": {"writePrice": 0.1, "readPrice": 0.1, "storagePrice": 0.1, "freeStorage": 0},
        "s3InfrequentAccess": {"storagePrice": 0.1, "upfrontPrice": 0.1, "requestPrice": 0.1, "dataRetrievalPrice": 0.1},
        "s3GlacierDeepArchive": {"storagePrice": 0.1, "lifecycleAndWritePrice": 0.1, "dataRetrievalPrice": 0.1},
        "iotTwinMaker": {
            "usageRates": {
                "entityPricePerMonth": 0.1,
                "queryPrice": 0.1,
                "unifiedDataAccessApiCallPrice": 0.1,
            },
            "tieredBundle": {
                "tiers": [
                    {
                        "tierId": tier_id,
                        "minimumEntities": minimum,
                        "maximumEntities": maximum,
                        "monthlyBasePrice": 1.0,
                        "includedQueries": included,
                        "includedApiCalls": included,
                        "queryOveragePrice": 0.1,
                        "apiCallOveragePrice": 0.1,
                    }
                    for tier_id, minimum, maximum, included in (
                        ("TIER_1", 1, 1000, 1),
                        ("TIER_2", 1001, 5000, 2),
                        ("TIER_3", 5001, 10000, 3),
                        ("TIER_4", 10001, 20000, 4),
                    )
                ]
            },
        },
        "awsManagedGrafana": {"editorPrice": 0.1, "viewerPrice": 0.1},
        "stepFunctions": {"pricePer1kStateTransitions": 0.1, "pricePerStateTransition": 0.1},
        "eventBridge": {"pricePerMillionEvents": 0.1},
        "apiGateway": {"pricePerMillionCalls": 0.1},
        "scheduler": {"jobPrice": 0.1}
    }
    result = validate_pricing_schema("aws", data)
    assert result["status"] == "valid"
    assert result["missing_keys"] == []

def test_validate_pricing_schema_missing_service():
    data = {
        "transfer": _aws_transfer()
        # Missing other services
    }
    result = validate_pricing_schema("aws", data)
    assert result["status"] == "incomplete"
    assert "iotCore (missing service)" in result["missing_keys"]

def test_validate_pricing_schema_missing_key():
    data = {
        "transfer": {"pricing_tiers": []},
        "iotCore": {"pricePerDeviceAndMonth": 0.1, "priceRulesTriggered": 0.1, "pricing_tiers": []},
        "lambda": {"requestPrice": 0.1, "durationPrice": 0.1, "freeRequests": 0, "freeComputeTime": 0},
        "dynamoDB": {"writePrice": 0.1, "readPrice": 0.1, "storagePrice": 0.1, "freeStorage": 0},
        "s3InfrequentAccess": {"storagePrice": 0.1, "upfrontPrice": 0.1, "requestPrice": 0.1, "dataRetrievalPrice": 0.1},
        "s3GlacierDeepArchive": {"storagePrice": 0.1, "lifecycleAndWritePrice": 0.1, "dataRetrievalPrice": 0.1},
        "iotTwinMaker": {"usageRates": {}, "tieredBundle": {"tiers": []}},
        "awsManagedGrafana": {"editorPrice": 0.1, "viewerPrice": 0.1},
        "stepFunctions": {"pricePer1kStateTransitions": 0.1},
        "eventBridge": {"pricePerMillionEvents": 0.1},
        "apiGateway": {"pricePerMillionCalls": 0.1}
    }
    result = validate_pricing_schema("aws", data)
    assert result["status"] == "incomplete"
    assert "transfer.billing_unit" in result["missing_keys"]

def test_validate_pricing_schema_unknown_provider():
    result = validate_pricing_schema("unknown", {"some": "data"})
    assert result["status"] == "unknown_provider"

def test_validate_pricing_schema_empty_data():
    result = validate_pricing_schema("aws", {})
    assert result["status"] == "missing"
