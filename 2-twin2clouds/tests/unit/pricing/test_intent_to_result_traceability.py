import json
import shutil

import yaml

from backend.calculation_v2.engine import calculate_cheapest_costs
from backend.calculation_v2.strategy_traceability import TRACE_SCHEMA_VERSION
from backend.pricing_registry import REGISTRY_ROOT
from backend.pricing_registry_service import PricingRegistryService
from tests.unit.calculation_v2.test_engine_consistency import (
    REALISTIC_PRICING,
    STANDARD_PARAMS,
)


def _trace():
    result = calculate_cheapest_costs(STANDARD_PARAMS, REALISTIC_PRICING)
    return result, result["resultTrace"]


def _find(trace, provider, intent_id):
    for item in trace:
        if item["provider"] == provider and item["intent_id"] == intent_id:
            return item
    raise AssertionError(f"Missing trace item for {provider}.{intent_id}")


def test_calculation_result_exposes_bounded_trace_metadata():
    result, trace = _trace()

    assert result["resultTraceSchemaVersion"] == TRACE_SCHEMA_VERSION
    assert len(trace) == 48
    assert len(json.dumps(trace)) < 250_000
    assert trace[0]["trace_id"] == "aws.api.request_million.L4.v1"


def test_aws_iot_core_trace_connects_intent_to_formula_contribution():
    _, trace = _trace()

    item = _find(trace, "aws", "iot.message_ingest")

    assert item["service"] == "AWSIoT"
    assert item["formula_set_id"] == "cost_formula_set_v1"
    assert item["formula_ref"] == "tiered_unit_cost"
    assert item["provider_pricing_contract_id"] == "aws.iot_message_ingest.pricing_contract.v1"
    assert item["pricing_model_classification_id"] == "aws.iot_message_ingest.model.v1"
    assert item["price_source_classification_ids"] == ["aws.iot_message_ingest.source.v1"]
    assert item["workload_inputs"]["monthly_iot_messages"] > 0
    assert item["cost_contribution"] > 0


def test_azure_iot_hub_trace_includes_model_and_source_classifications():
    _, trace = _trace()

    item = _find(trace, "azure", "iot.message_ingest")

    assert item["service"] == "IoT Hub"
    assert item["source_type"] == "provider_api"
    assert item["source_build_path"] == "fetched_from_provider_api"
    assert item["selected_evidence_id"].startswith("azure.iot.message_ingest")
    assert item["publishability_status"] == "publishable"


def test_gcp_pubsub_trace_includes_workload_inputs_and_formula_ref():
    _, trace = _trace()

    item = _find(trace, "gcp", "iot.message_ingest")

    assert item["service"] == "Cloud Pub/Sub"
    assert item["formula_ref"] == "tiered_unit_cost"
    assert item["workload_inputs"]["monthly_iot_messages"] > 0
    assert item["cost_contribution"] > 0


def test_grafana_traces_include_safe_selected_evidence_summary():
    _, trace = _trace()

    aws = _find(trace, "aws", "grafana.editor_user_month")
    azure = _find(trace, "azure", "grafana.viewer_user_month")

    assert aws["selected_evidence_summary"]["source_type"] == "provider_api"
    assert azure["selected_evidence_summary"]["source_type"] == "provider_api"
    assert aws["cost_contribution"] is not None
    assert azure["cost_contribution"] is not None


def test_storage_trace_includes_normalization_steps():
    _, trace = _trace()

    item = _find(trace, "aws", "storage.hot.storage_gb_month")

    assert item["result_field"] == "L3_hot"
    assert item["normalization_steps"] == [{"normalization_rule": "per_gb_month"}]
    assert item["workload_inputs"]["hot_storage_gb_month"] > 0


def test_trace_includes_verification_gate_status_for_each_item():
    _, trace = _trace()

    item = _find(trace, "azure", "iot.message_ingest")
    gates = {gate["gate"]: gate["status"] for gate in item["verification_gates"]}

    assert gates["G1_REGISTRY_COMPLETENESS"] == "passed"
    assert gates["G6_PUBLISHABILITY"] == "passed"
    assert gates["G7_CALCULATION_READINESS"] == "passed"
    assert item["verification_status"] == "passed"


def test_trace_ids_are_deterministic_for_snapshot_comparison():
    _, first = _trace()
    _, second = _trace()

    assert [item["trace_id"] for item in first] == [item["trace_id"] for item in second]


def test_trace_redacts_credential_like_source_values(tmp_path):
    root = tmp_path / "pricing_registry"
    shutil.copytree(REGISTRY_ROOT, root)
    path = root / "price_source_classifications.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["classifications"]["aws.iot_message_ingest.source.v1"]["source_url"] = (
        "/Users/caroline/private_key.json"
    )
    path.write_text(yaml.safe_dump(doc, sort_keys=False))

    result = calculate_cheapest_costs(
        STANDARD_PARAMS,
        REALISTIC_PRICING,
        pricing_registry_service=PricingRegistryService(root),
    )
    serialized = json.dumps(result["resultTrace"])

    assert "/Users/" not in serialized
    assert "private_key" not in serialized
    assert "[redacted]" in serialized


def test_trace_does_not_dump_raw_provider_pricing_payloads():
    _, trace = _trace()
    serialized = json.dumps(trace)

    assert "pricePerDeviceAndMonth" not in serialized
    assert "durationPrice" not in serialized
    assert "storagePrice" not in serialized
    assert "client_secret" not in serialized
