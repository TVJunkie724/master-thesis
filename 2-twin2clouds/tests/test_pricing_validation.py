import pytest
from backend.pricing_utils import validate_pricing_schema

def test_validate_pricing_schema_valid_aws():
    data = {
        "transfer": {"pricing_tiers": [], "egressPrice": 0.1},
        "iotCore": {"pricePerDeviceAndMonth": 0.1, "priceRulesTriggered": 0.1, "pricing_tiers": []},
        "lambda": {"requestPrice": 0.1, "durationPrice": 0.1, "freeRequests": 0, "freeComputeTime": 0},
        "dynamoDB": {"writePrice": 0.1, "readPrice": 0.1, "storagePrice": 0.1, "freeStorage": 0},
        "s3InfrequentAccess": {"storagePrice": 0.1, "upfrontPrice": 0.1, "requestPrice": 0.1, "dataRetrievalPrice": 0.1, "transferCostFromDynamoDB": 0, "transferCostFromCosmosDB": 0},
        "s3GlacierDeepArchive": {"storagePrice": 0.1, "lifecycleAndWritePrice": 0.1, "dataRetrievalPrice": 0.1},
        "iotTwinMaker": {"unifiedDataAccessAPICallsPrice": 0.1, "entityPrice": 0.1, "queryPrice": 0.1},
        "awsManagedGrafana": {"editorPrice": 0.1, "viewerPrice": 0.1},
        "stepFunctions": {"pricePer1kStateTransitions": 0.1},
        "eventBridge": {"pricePerMillionEvents": 0.1},
        "apiGateway": {"pricePerMillionCalls": 0.1, "dataTransferOutPrice": 0.1}
    }
    result = validate_pricing_schema("aws", data)
    assert result["status"] == "valid"
    assert result["missing_keys"] == []

def test_validate_pricing_schema_missing_service():
    data = {
        "transfer": {"pricing_tiers": [], "egressPrice": 0.1}
        # Missing other services
    }
    result = validate_pricing_schema("aws", data)
    assert result["status"] == "incomplete"
    assert "iotCore (missing service)" in result["missing_keys"]

def test_validate_pricing_schema_missing_key():
    data = {
        "transfer": {"pricing_tiers": []}, # Missing egressPrice
        "iotCore": {"pricePerDeviceAndMonth": 0.1, "priceRulesTriggered": 0.1, "pricing_tiers": []},
        "lambda": {"requestPrice": 0.1, "durationPrice": 0.1, "freeRequests": 0, "freeComputeTime": 0},
        "dynamoDB": {"writePrice": 0.1, "readPrice": 0.1, "storagePrice": 0.1, "freeStorage": 0},
        "s3InfrequentAccess": {"storagePrice": 0.1, "upfrontPrice": 0.1, "requestPrice": 0.1, "dataRetrievalPrice": 0.1, "transferCostFromDynamoDB": 0, "transferCostFromCosmosDB": 0},
        "s3GlacierDeepArchive": {"storagePrice": 0.1, "lifecycleAndWritePrice": 0.1, "dataRetrievalPrice": 0.1},
        "iotTwinMaker": {"unifiedDataAccessAPICallsPrice": 0.1, "entityPrice": 0.1, "queryPrice": 0.1},
        "awsManagedGrafana": {"editorPrice": 0.1, "viewerPrice": 0.1},
        "stepFunctions": {"pricePer1kStateTransitions": 0.1},
        "eventBridge": {"pricePerMillionEvents": 0.1},
        "apiGateway": {"pricePerMillionCalls": 0.1, "dataTransferOutPrice": 0.1}
    }
    result = validate_pricing_schema("aws", data)
    assert result["status"] == "incomplete"
    assert "transfer.egressPrice" in result["missing_keys"]

def test_validate_pricing_schema_unknown_provider():
    result = validate_pricing_schema("unknown", {"some": "data"})
    assert result["status"] == "unknown_provider"

def test_validate_pricing_schema_empty_data():
    result = validate_pricing_schema("aws", {})
    assert result["status"] == "missing"
