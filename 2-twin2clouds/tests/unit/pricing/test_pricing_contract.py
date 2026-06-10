import json
from pathlib import Path
from unittest.mock import patch

from backend import config_loader
from backend.fetch_data.calculate_up_to_date_pricing import (
    fetch_aws_data,
    fetch_azure_data,
    fetch_google_data,
)
from backend.pricing_schema import (
    EXPECTED_PRICING_SCHEMA,
    PRICING_CONTRACT_VERSION,
    PRICING_SCHEMA_VERSION,
    attach_pricing_metadata,
    strip_pricing_metadata,
    validate_pricing_payload,
)


SERVICE_MAPPING = {
    "functions": {"aws": "AWSLambda", "azure": "Functions", "gcp": "CloudFunctions"},
    "storage_cool": {"aws": "AmazonS3", "azure": "Storage", "gcp": "CloudStorageNearline"},
    "storage_archive": {"aws": "AmazonS3", "azure": "Storage", "gcp": "CloudStorageArchive"},
    "iot": {"aws": "AWSIoT", "azure": "IoT Hub", "gcp": "CloudPubSub"},
    "storage_hot": {"aws": "AmazonDynamoDB", "azure": "Azure Cosmos DB", "gcp": "Firestore"},
    "twinmaker": {"aws": "IOTTwinMaker", "azure": "Digital Twins", "gcp": "ComputeEngine"},
    "grafana": {"aws": "AmazonGrafana", "azure": "Azure Grafana Service", "gcp": "ComputeEngine"},
    "event_bus": {"aws": "AWSEvents", "azure": "Event Grid", "gcp": "CloudPubSub"},
    "orchestration": {"aws": "AmazonStates", "azure": "Logic Apps", "gcp": "CloudWorkflows"},
    "data_access": {"aws": "AmazonAPIGateway", "azure": "API Management", "gcp": "ApiGateway"},
    "scheduler": {"aws": "AWSEvents", "azure": "", "gcp": "CloudScheduler"},
    "transfer": {"aws": "AWSDataTransfer", "azure": "Bandwidth", "gcp": "ComputeEngine"},
}


FETCHED_BY_PROVIDER = {
    "aws": {
        "transfer": {"egressPrice": 0.09},
        "iot": {
            "pricePerDeviceAndMonth": 0.0035,
            "priceRulesTriggered": 0.00000015,
            "messageTiers": {
                "tier_first": 0.000001,
                "tier_next": 0.0000008,
                "tier_over": 0.0000007,
            },
        },
        "functions": {
            "requestPrice": 0.0000002,
            "durationTiers": {"tier1": 0.0000166667},
            "freeRequests": 1000000,
            "freeComputeTime": 400000,
        },
        "storage_hot": {
            "writePrice": 0.000000625,
            "readPrice": 0.000000125,
            "storagePrice": 0.25,
            "freeStorage": 25,
        },
        "storage_cool": {
            "storagePrice": 0.0125,
            "upfrontPrice": 0.0001,
            "requestPrice": 0.00001,
            "dataRetrievalPrice": 0.01,
        },
        "storage_archive": {
            "storagePrice": 0.00099,
            "lifecycleAndWritePrice": 0.00005,
            "dataRetrievalPrice": 0.0025,
        },
        "twinmaker": {
            "unifiedDataAccessAPICallsPrice": 0.0000015,
            "entityPrice": 0.05,
            "queryPrice": 0.00005,
        },
        "grafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
        "orchestration": {"pricePer1kStateTransitions": 0.025},
        "event_bus": {"pricePerMillionEvents": 1.0},
        "data_access": {"pricePerMillionCalls": 3.5},
        "scheduler": {"jobPrice": 0.000001},
    },
    "azure": {
        "transfer": {
            "pricing_tiers": {"tier1": {"limit": "Infinity", "price": 0.087}},
            "egressPrice": 0.087,
        },
        "iot": {"pricing_tiers": {"tier1": {"limit": "Infinity", "price": 25}}},
        "functions": {
            "requestPrice": 0.0000002,
            "durationPrice": 0.000016,
            "freeRequests": 1000000,
            "freeComputeTime": 400000,
        },
        "storage_hot": {
            "requestPrice": 0.0584,
            "minimumRequestUnits": 400,
            "RUsPerRead": 1,
            "RUsPerWrite": 10,
            "storagePrice": 0.25,
        },
        "storage_cool": {
            "storagePrice": 0.01,
            "upfrontPrice": 0.0001,
            "writePrice": 0.02,
            "readPrice": 0.01,
            "dataRetrievalPrice": 0.01,
        },
        "storage_archive": {
            "storagePrice": 0.00099,
            "writePrice": 0.02,
            "dataRetrievalPrice": 0.02,
        },
        "twinmaker": {
            "messagePrice": 0.000001,
            "operationPrice": 0.0000025,
            "queryPrice": 0.0000005,
            "queryUnitTiers": [{"lower": 1, "value": 15}],
        },
        "grafana": {"userPrice": 6.0, "hourlyPrice": 0.069},
        "orchestration": {"pricePer1kStateTransitions": 0.025},
        "event_bus": {"pricePerMillionEvents": 0.6},
        "data_access": {"pricePerMillionCalls": 3.5},
    },
    "gcp": {
        "transfer": {"egressPrice": 0.12},
        "iot": {"pricePerGiB": 0.0000004, "pricePerDeviceAndMonth": 0},
        "functions": {
            "requestPrice": 0.0000004,
            "durationPrice": 0.0000025,
            "freeRequests": 2000000,
            "freeComputeTime": 400000,
        },
        "storage_hot": {
            "writePrice": 0.0000018,
            "readPrice": 0.0000006,
            "storagePrice": 0.18,
            "freeStorage": 1,
        },
        "storage_cool": {
            "storagePrice": 0.01,
            "upfrontPrice": 0.0,
            "requestPrice": 0.00001,
            "dataRetrievalPrice": 0.01,
        },
        "storage_archive": {
            "storagePrice": 0.0012,
            "lifecycleAndWritePrice": 0.00005,
            "dataRetrievalPrice": 0.05,
        },
        "twinmaker": {
            "e2CorePrice": 0.02,
            "e2RamPrice": 0.007,
            "storagePrice": 0.04,
        },
        "grafana": {
            "e2CorePrice": 0.02,
            "e2RamPrice": 0.007,
            "storagePrice": 0.04,
        },
        "data_access": {"pricePerMillionCalls": 0.000003},
        "orchestration": {"stepPrice": 0.000001},
        "scheduler": {"jobPrice": 0.1},
    },
}


class _FakeFetcher:
    def __init__(self, provider: str):
        self.provider = provider

    def fetch_price(self, *, service_name: str, **kwargs):
        return FETCHED_BY_PROVIDER[self.provider].get(service_name, {})


def test_expected_pricing_schema_covers_all_providers():
    assert set(EXPECTED_PRICING_SCHEMA) == {"aws", "azure", "gcp"}
    for provider, services in EXPECTED_PRICING_SCHEMA.items():
        assert services, f"{provider} must define at least one service"
        for service, fields in services.items():
            assert fields, f"{provider}.{service} must define required fields"


def test_template_matches_versioned_provider_contract():
    template = json.loads(Path("json/pricing.json").read_text())

    for provider in ("aws", "azure", "gcp"):
        validation = validate_pricing_payload(provider, template[provider])
        assert validation["schema_version"] == PRICING_SCHEMA_VERSION
        assert validation["contract_version"] == PRICING_CONTRACT_VERSION
        assert validation["status"] == "valid"
        assert validation["missing_keys"] == []
        assert validation["quality_status"] == "review_required"
        assert validation["review_required"] is True


def test_legacy_payload_without_quality_metadata_requires_review():
    template = json.loads(Path("json/pricing.json").read_text())

    validation = validate_pricing_payload("azure", template["azure"])

    assert validation["status"] == "valid"
    assert validation["quality_status"] == "review_required"
    assert validation["review_required"] is True


def test_attach_pricing_metadata_marks_fallback_as_review_required():
    template = json.loads(Path("json/pricing.json").read_text())
    payload = attach_pricing_metadata("aws", template["aws"], fetched={})

    validation = validate_pricing_payload("aws", payload)

    assert validation["status"] == "valid"
    assert validation["quality_status"] == "review_required"
    assert validation["review_required"] is True
    assert "lambda.requestPrice" in validation["fallback_fields"]
    assert payload["__quality__"]["field_sources"]["lambda.requestPrice"] == "fallback_static"


def test_attach_pricing_metadata_marks_model_constants_as_curated():
    aws_payload = {
        "lambda": {"freeRequests": 1_000_000, "freeComputeTime": 400_000},
        "dynamoDB": {"freeStorage": 25},
        "s3InfrequentAccess": {"upfrontPrice": 0.0001},
    }
    azure_payload = {
        "functions": {"freeRequests": 1_000_000, "freeComputeTime": 400_000},
        "cosmosDB": {"minimumRequestUnits": 400, "RUsPerRead": 1, "RUsPerWrite": 10},
        "blobStorageCool": {"upfrontPrice": 0.0001},
        "azureDigitalTwins": {"queryUnitTiers": [{"lower": 1, "value": 15}]},
    }

    aws = attach_pricing_metadata("aws", aws_payload, fetched={})
    azure = attach_pricing_metadata("azure", azure_payload, fetched={})

    assert aws["__quality__"]["field_sources"]["lambda.freeRequests"] == "curated"
    assert aws["__quality__"]["field_sources"]["dynamoDB.freeStorage"] == "curated"
    assert aws["__quality__"]["field_sources"]["s3InfrequentAccess.upfrontPrice"] == "curated"
    assert azure["__quality__"]["field_sources"]["functions.freeComputeTime"] == "curated"
    assert azure["__quality__"]["field_sources"]["cosmosDB.RUsPerRead"] == "curated"
    assert azure["__quality__"]["field_sources"]["azureDigitalTwins.queryUnitTiers"] == "curated"
    assert "lambda.freeRequests" not in aws["__quality__"]["fallback_fields"]
    assert "cosmosDB.RUsPerRead" not in azure["__quality__"]["fallback_fields"]


def test_incomplete_payload_is_review_required_even_without_fallback_metadata():
    validation = validate_pricing_payload("aws", {"transfer": {"pricing_tiers": []}})

    assert validation["status"] == "incomplete"
    assert validation["quality_status"] == "review_required"
    assert validation["review_required"] is True
    assert "transfer.egressPrice" in validation["missing_keys"]


def test_fetched_provider_payloads_are_schema_valid_and_publishable():
    with patch(
        "backend.fetch_data.calculate_up_to_date_pricing.PriceFetcherFactory.create",
        side_effect=lambda provider: _FakeFetcher(provider),
    ), patch("backend.fetch_data.calculate_up_to_date_pricing.config_loader.load_aws_credentials"):
        results = {
            "aws": fetch_aws_data(
                {"aws_region": "eu-central-1"},
                SERVICE_MAPPING,
                {"eu-central-1": "EU (Frankfurt)"},
                aws_client_credentials={
                    "aws_access_key_id": "access-key",
                    "aws_secret_access_key": "secret-key",
                    "region_name": "us-east-1",
                },
            ),
            "azure": fetch_azure_data(
                {"azure_region": "westeurope"},
                SERVICE_MAPPING,
                {"westeurope": "West Europe"},
            ),
            "gcp": fetch_google_data(
                {"gcp_region": "europe-west1"},
                SERVICE_MAPPING,
                {"europe-west1": "europe-west1"},
                billing_client=object(),
            ),
        }

    for provider, payload in results.items():
        validation = validate_pricing_payload(provider, payload)
        assert validation["status"] == "valid"
        assert validation["quality_status"] == "publishable"
        assert validation["fallback_fields"] == []
        assert payload["__schema__"]["provider"] == provider


def test_combined_pricing_strips_reserved_metadata_before_calculation():
    aws = attach_pricing_metadata(
        "aws",
        json.loads(Path("json/pricing.json").read_text())["aws"],
        fetched={},
    )

    with patch.object(
        config_loader,
        "load_json_file_optional",
        side_effect=[aws, {"__schema__": {}, "functions": {}}, {"__quality__": {}, "iot": {}}],
    ):
        combined = config_loader.load_combined_pricing()

    assert "__schema__" not in combined["aws"]
    assert "__quality__" not in combined["aws"]
    assert "__schema__" not in combined["azure"]
    assert "__quality__" not in combined["gcp"]
    assert combined["aws"] == strip_pricing_metadata(aws)
