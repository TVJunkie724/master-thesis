from datetime import datetime, timezone

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
from tests.unit.pricing.transfer_fixtures import pricing_catalog_context_for


def _trace():
    result = calculate_cheapest_costs(
        STANDARD_PARAMS,
        REALISTIC_PRICING,
        pricing_catalog_context=pricing_catalog_context_for(REALISTIC_PRICING),
    )
    return result, result["resultTrace"]


def _find(trace, provider, intent_id):
    for item in trace:
        if item["provider"] == provider and item["intent_id"] == intent_id:
            return item
    raise AssertionError(f"Missing trace item for {provider}.{intent_id}")


def test_calculation_result_exposes_bounded_trace_metadata():
    result, trace = _trace()
    expected_records = PricingRegistryService().get_status()[
        "provider_pricing_contract_count"
    ]

    assert result["resultTraceSchemaVersion"] == TRACE_SCHEMA_VERSION
    assert len(trace) == expected_records
    assert len(json.dumps(trace)) < 250_000
    assert trace[0]["trace_id"] == "aws.api.request_million.L4.v1"


def test_aws_iot_core_trace_connects_intent_to_formula_contribution():
    _, trace = _trace()

    item = _find(trace, "aws", "iot.message_ingest")

    assert item["service"] == "AWSIoT"
    assert item["formula_set_id"] == "cost_formula_set_v1"
    assert item["formula_ref"] == "tiered_unit_cost"
    assert (
        item["provider_pricing_contract_id"]
        == "aws.iot_message_ingest.pricing_contract.v1"
    )
    assert item["pricing_model_classification_id"] == "aws.iot_message_ingest.model.v1"
    assert item["price_source_classification_ids"] == [
        "aws.iot_message_ingest.source.v1"
    ]
    assert item["workload_inputs"]["monthly_iot_messages"] > 0
    assert item["cost_contribution"] > 0
    assert item["cost_contribution_scope"] == "component_total"
    assert item["cost_contribution_is_additive"] is False
    assert item["result_component_key"] == "iot_core"
    assert item["selection_status"] in {"selected", "alternative"}


def test_azure_iot_hub_trace_includes_model_and_source_classifications():
    _, trace = _trace()

    item = _find(trace, "azure", "iot.message_ingest")

    assert item["service"] == "IoT Hub"
    assert item["source_type"] == "provider_api"
    assert item["source_build_path"] == "fetched_from_provider_api"
    assert item["selected_evidence_id"].startswith("azure.iot.message_ingest")
    assert item["publishability_status"] == "publishable"


def test_azure_digital_twins_trace_uses_exact_quantities_and_components():
    _, trace = _trace()
    expectations = {
        "digital_twin.operation": (
            "monthly_digital_twin_billable_operations",
            "digital_twins_operations",
            "request_unit_cost",
        ),
        "digital_twin.message": (
            "monthly_digital_twin_routed_messages",
            "digital_twins_routed_messages",
            "message_unit_cost",
        ),
        "digital_twin.query_unit": (
            "monthly_digital_twin_query_units",
            "digital_twins_query_units",
            "query_unit_cost",
        ),
    }

    for intent_id, (
        workload_field,
        component_key,
        formula_ref,
    ) in expectations.items():
        item = _find(trace, "azure", intent_id)
        assert item["result_component_key"] == component_key
        assert item["formula_ref"] == formula_ref
        assert item["workload_inputs"][workload_field] is not None
        assert item["selection_status"] in {"selected", "alternative"}

    routed_message = _find(trace, "azure", "digital_twin.message")
    assert routed_message["workload_inputs"][
        "monthly_digital_twin_routed_messages"
    ] == 0
    assert routed_message["cost_contribution"] == 0


def test_aws_twinmaker_trace_separates_standard_dimensions_and_bundle_mode():
    params = dict(STANDARD_PARAMS)
    pricing = dict(REALISTIC_PRICING)
    pricing["__aws_schema__"] = {
        "pricing_region": "eu-central-1",
        "snapshot_digest": "sha256:" + ("a" * 64),
    }
    params["providerPricingContexts"] = {
        "awsTwinMaker": {
            "schemaVersion": "aws-twinmaker-account-pricing-context.v1",
            "status": "available",
            "sourceRefreshRunId": "refresh-run-1",
            "connectionFingerprint": "sha256:" + ("b" * 64),
            "providerAccountId": "123456789012",
            "pricingRegion": "eu-central-1",
            "catalogSnapshotDigest": "sha256:" + ("a" * 64),
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "currentPlan": {
                "mode": "STANDARD",
                "billableEntityCount": 1,
                "effectiveAt": None,
                "updatedAt": None,
                "updateReason": None,
                "bundle": None,
            },
            "pendingPlan": None,
        }
    }

    result = calculate_cheapest_costs(
        params,
        pricing,
        pricing_catalog_context=pricing_catalog_context_for(pricing),
    )
    trace = result["resultTrace"]

    expected = {
        "digital_twin.entity_month": (
            "twinmaker_entities",
            "digital_twin_entity_months",
        ),
        "digital_twin.query": (
            "twinmaker_queries",
            "monthly_digital_twin_queries",
        ),
        "digital_twin.api_call": (
            "twinmaker_api_calls",
            "monthly_digital_twin_api_calls",
        ),
    }
    for intent_id, (component, workload) in expected.items():
        item = _find(trace, "aws", intent_id)
        assert item["runtime_applicability"] is True
        assert item["result_component_key"] == component
        assert item["workload_inputs"][workload] is not None
        assert item["cost_contribution"] >= 0
        assert item["provider_pricing_context"]["status"] == "compatible"
        assert item["provider_pricing_context"]["observedMode"] == "STANDARD"

    bundle = _find(trace, "aws", "digital_twin.account_bundle_month")
    assert bundle["runtime_applicability"] is False
    assert bundle["runtime_applicability_reason"] == "AWS_TWINMAKER_STANDARD_MODE"
    assert bundle["selection_status"] == "not_applicable"
    assert bundle["cost_contribution"] == 0
    assert bundle["provider_pricing_context"]["sourceRefreshRunId"] == (
        "refresh-run-1"
    )


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


def test_trace_distinguishes_selection_provider_alternatives_and_unsupported_rows():
    result, trace = _trace()
    selected_path = {
        entry.split("_", 1)[0]: entry.rsplit("_", 1)[-1].lower()
        for entry in result["cheapestPath"]
        if not entry.startswith("L3_")
    }

    l1_records = {
        provider: _find(trace, provider, "iot.message_ingest")
        for provider in ("aws", "azure", "gcp")
    }
    gcp_l4 = _find(trace, "gcp", "digital_twin.query_unit")
    aws_l4 = _find(trace, "aws", "digital_twin.query")

    selected_l1 = l1_records[selected_path["L1"]]
    alternative_l1 = next(
        record
        for provider, record in l1_records.items()
        if provider != selected_path["L1"]
    )
    assert selected_l1["selection_status"] == "selected"
    assert selected_l1["selected_for_path"] is True
    assert alternative_l1["selection_status"] == "alternative"
    assert alternative_l1["selected_for_path"] is False
    assert gcp_l4["selection_status"] == "unsupported"
    assert aws_l4["selection_status"] == "unsupported"
    assert aws_l4["runtime_applicability"] is False
    assert aws_l4["provider_pricing_context"]["reasonCode"] == (
        "AWS_TWINMAKER_PLAN_UNOBSERVED"
    )


def test_trace_separates_provider_alternatives_from_rejected_evidence():
    _, trace = _trace()
    item = _find(trace, "aws", "iot.message_ingest")

    assert item["alternative_record_ids"] == [
        "azure.iot_message_ingest.pricing_contract.v1",
        "gcp.iot_message_ingest.pricing_contract.v1",
    ]
    assert item["rejected_evidence_ids"] == []
    assert item["runtime_selected_evidence_available"] is False
    assert item["evidence_reference_kind"] == "registry_contract_reference"


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
        pricing_catalog_context=pricing_catalog_context_for(
            REALISTIC_PRICING
        ),
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
