"""Tests for intent-to-result calculation trace metadata."""

import json

from backend.calculation_v2.engine import calculate_cheapest_costs
from backend.calculation_v2.traceability import TRACE_SCHEMA_VERSION


def _sample_params():
    return {
        "numberOfDevices": 100,
        "deviceSendingIntervalInMinutes": 2.0,
        "averageSizeOfMessageInKb": 0.25,
        "hotStorageDurationInMonths": 1,
        "coolStorageDurationInMonths": 3,
        "archiveStorageDurationInMonths": 12,
        "needs3DModel": False,
        "entityCount": 1,
        "amountOfActiveEditors": 2,
        "amountOfActiveViewers": 5,
        "dashboardRefreshesPerHour": 4,
        "dashboardActiveHoursPerDay": 8,
        "currency": "USD",
        "useEventChecking": True,
        "triggerNotificationWorkflow": True,
        "integrateErrorHandling": False,
        "orchestrationActionsPerMessage": 3,
        "eventsPerMessage": 1,
        "apiCallsPerDashboardRefresh": 1,
        "allowGcpSelfHostedL4": False,
        "allowGcpSelfHostedL5": False,
    }


def _sample_pricing():
    return {
        "aws": {
            "iotCore": {
                "pricePerDeviceAndMonth": 0.25,
                "priceRulesTriggered": 0.000001,
                "pricing_tiers": {"tier1": {"limit": "Infinity", "price": 0.000001}},
            },
            "lambda": {
                "requestPrice": 0.0000002,
                "durationPrice": 0.0000166667,
                "freeRequests": 1000000,
                "freeComputeTime": 400000,
            },
            "stepFunctions": {"pricePerStateTransition": 0.000025},
            "eventBridge": {"pricePerMillionEvents": 1.0},
            "dynamoDB": {
                "writePrice": 0.0000125,
                "readPrice": 0.00000025,
                "storagePrice": 0.25,
                "freeStorage": 25,
            },
            "s3InfrequentAccess": {"storagePrice": 0.0125, "requestPrice": 0.000001},
            "s3GlacierDeepArchive": {"storagePrice": 0.00099, "lifecycleAndWritePrice": 0.00005},
            "iotTwinMaker": {
                "usageRates": {
                    "queryPrice": 0.001,
                    "entityPricePerMonth": 0.000001,
                    "unifiedDataAccessApiCallPrice": 0.000001,
                },
            },
            "awsManagedGrafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
            "egress": {"pricePerGB": 0.09},
        },
        "azure": {
            "iotHub": {
                "pricing_tiers": {
                    "tier1": {"threshold": 400000, "limit": 120000000, "price": 25}
                }
            },
            "functions": {
                "requestPrice": 0.0000002,
                "durationPrice": 0.000016,
                "freeRequests": 1000000,
                "freeComputeTime": 400000,
            },
            "logicApps": {"pricePerAction": 0.000025},
            "eventGrid": {"pricePerMillionOperations": 0.60},
            "cosmosDB": {"requestUnitPrice": 0.25, "storagePrice": 0.25},
            "blobStorageCool": {"storagePrice": 0.01, "writePrice": 0.00001},
            "blobStorageArchive": {"storagePrice": 0.002, "writePrice": 0.00002},
            "azureDigitalTwins": {
                "pricePerOperation": 0.0000025,
                "pricePerQueryUnit": 0.0000005,
                "pricePerMessage": 0.000001,
            },
            "azureManagedGrafana": {"editorPrice": 9.0, "viewerPrice": 5.0},
            "egress": {"pricePerGB": 0.087},
        },
        "gcp": {
            "iot": {"pricePerGiB": 0.04},
            "functions": {
                "invocationPrice": 0.0000004,
                "gbSecondPrice": 0.0000025,
                "freeInvocations": 2000000,
                "freeGBSeconds": 400000,
            },
            "cloudWorkflows": {"pricePerStep": 0.00001},
            "storage_hot": {"writePrice": 0.18, "readPrice": 0.06, "storagePrice": 0.026},
            "storage_cool": {"storagePrice": 0.01, "writePrice": 0.01},
            "storage_archive": {"storagePrice": 0.004, "writePrice": 0.05},
            "twinmaker": {"e2MediumPrice": 0.0335, "storagePrice": 0.04},
            "grafana": {"e2MediumPrice": 0.0335, "storagePrice": 0.04},
            "egress": {"pricePerGB": 0.12},
        },
    }


def test_calculation_result_contains_stable_intent_trace_shape():
    result = calculate_cheapest_costs(_sample_params(), _sample_pricing())

    assert result["trace_schema_version"] == TRACE_SCHEMA_VERSION
    trace = result["intentTrace"]
    assert trace["schema_version"] == TRACE_SCHEMA_VERSION
    assert trace["profile"]["profile_id"] == "cost_minimization_v1"
    assert trace["workload"]["inputs"]["numberOfDevices"] == 100
    assert trace["workload"]["derived"]["total_messages_per_month"] > 0
    assert trace["summary"]["record_count"] == len(trace["records"])
    assert trace["summary"]["selected_path_count"] == 7
    assert trace["summary"]["transfer_segment_count"] == len(trace["transfer_trace"])

    first = trace["records"][0]
    assert set(first) == {
        "trace_id",
        "record_id",
        "intent_id",
        "provider",
        "layer",
        "service_key",
        "field_id",
        "source",
        "pricing",
        "formula",
        "contribution",
        "verification",
    }
    assert first["trace_id"].startswith("trace:")
    assert first["source"]["primary_source_type"]
    assert first["pricing"]["canonical_unit"]
    assert first["formula"]["binding_id"].startswith("cost.")
    assert first["verification"]["evidence_reference_id"].startswith("pricing_registry:")

    if trace["transfer_trace"]:
        transfer = trace["transfer_trace"][0]
        assert transfer["source_intent_id"].endswith(".transfer.egress")
        assert transfer["evidence_reference_ids"]


def test_selected_trace_records_match_selected_path():
    result = calculate_cheapest_costs(_sample_params(), _sample_pricing())
    trace = result["intentTrace"]

    selected_path = {
        item["layer_cost_key"]: item["provider"]
        for item in trace["selected_path"]
    }
    selected_records = [
        record
        for record in trace["records"]
        if record["contribution"]["selected"] and record["layer"] != "L0_GLUE"
    ]

    assert selected_records
    for record in selected_records:
        path_key = record["contribution"]["path_key"]
        layer_cost_key = path_key.rsplit("_", 1)[0]
        assert selected_path[layer_cost_key] == _provider_label(record["provider"])


def test_trace_is_bounded_and_secret_free():
    result = calculate_cheapest_costs(_sample_params(), _sample_pricing())
    serialized = json.dumps(result["intentTrace"])

    assert "aws_secret_access_key" not in serialized
    assert "private_key" not in serialized
    assert "access_token" not in serialized
    assert "pricePerDeviceAndMonth" in serialized
    assert "wJalrXUtnFEMI" not in serialized
    assert len(serialized) < 70000


def _provider_label(provider: str) -> str:
    return {"aws": "AWS", "azure": "Azure", "gcp": "GCP"}[provider]
