"""Intent-to-result trace metadata for calculation v2."""
from __future__ import annotations

from typing import Any

from backend.calculation_v2.strategy_context import CalculationStrategyExecutionContext
from backend.pricing_registry_service import PricingRegistryService


TRACE_SCHEMA_VERSION = "intent-to-result-trace.v1"
MAX_TRACE_ITEMS = 64

_PROVIDER_COST_KEYS = {
    "aws": "awsCosts",
    "azure": "azureCosts",
    "gcp": "gcpCosts",
}

_FIELD_RESULT_MAP = {
    "transfer.egress_gb": ("transferCosts", None),
    "iot.message_ingest": ("L1", {"aws": "iot_core", "azure": "iot_hub", "gcp": "pubsub"}),
    "functions.request": ("L2", None),
    "functions.compute_gb_second": ("L2", None),
    "storage.hot.storage_gb_month": ("L3_hot", None),
    "storage.hot.read_request": ("L3_hot", None),
    "storage.hot.write_request": ("L3_hot", None),
    "storage.cool.storage_gb_month": ("L3_cool", None),
    "storage.archive.storage_gb_month": ("L3_archive", None),
    "storage.archive.write_request": ("L3_archive", None),
    "api.request_million": ("L4", None),
    "orchestration.state_transition": ("L2", None),
    "event_bus.event_million": ("L2", None),
    "digital_twin.query_unit": ("L4", None),
    "grafana.editor_user_month": ("L5", {"aws": "grafana", "azure": "grafana", "gcp": "grafana"}),
    "grafana.viewer_user_month": ("L5", {"aws": "grafana", "azure": "grafana", "gcp": "grafana"}),
}

_WORKLOAD_VALUE_MAP = {
    "monthly_egress_gb": "data_size_per_month_gb",
    "monthly_iot_messages": "total_messages_per_month",
    "monthly_function_requests": "total_messages_per_month",
    "monthly_function_gb_seconds": "estimated_function_gb_seconds",
    "hot_storage_gb_month": "hot_storage_gb",
    "monthly_storage_read_requests": "queries_per_month",
    "monthly_storage_write_requests": "total_messages_per_month",
    "cool_storage_gb_month": "cool_storage_gb",
    "archive_storage_gb_month": "archive_storage_gb",
    "monthly_archive_write_requests": "total_messages_per_month",
    "monthly_api_requests": "queries_per_month",
    "monthly_state_transitions": "total_messages_per_month",
    "monthly_events": "total_messages_per_month",
    "monthly_digital_twin_query_units": "queries_per_month",
    "editor_user_months": "amountOfActiveEditors",
    "viewer_user_months": "amountOfActiveViewers",
}


def build_intent_result_trace(
    *,
    execution_context: CalculationStrategyExecutionContext,
    pricing_registry_service: PricingRegistryService,
    params: dict[str, Any],
    derived_params: dict[str, Any],
    result_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build bounded, secret-free trace items for calculation results."""
    trace_items = []
    registry = pricing_registry_service.load()
    for contract_id in execution_context.provider_pricing_contract_ids[:MAX_TRACE_ITEMS]:
        contract = registry.provider_pricing_contracts[contract_id]
        model = registry.pricing_model_classifications[
            contract["pricing_model_classification_id"]
        ]
        source = registry.price_source_classifications[
            contract["price_source_classification_id"]
        ]
        trace_items.append(
            _trace_item(
                execution_context=execution_context,
                params=params,
                derived_params=derived_params,
                result_payload=result_payload,
                contract=contract,
                model=model,
                source=source,
            )
        )
    return trace_items


def _trace_item(
    *,
    execution_context: CalculationStrategyExecutionContext,
    params: dict[str, Any],
    derived_params: dict[str, Any],
    result_payload: dict[str, Any],
    contract: dict[str, Any],
    model: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    provider = contract["provider"]
    field = contract["field"]
    result_field, component_keys = _FIELD_RESULT_MAP.get(field, (contract["layer"], None))
    cost_contribution = _cost_contribution(
        provider=provider,
        result_field=result_field,
        component_keys=component_keys,
        result_payload=result_payload,
    )
    formula_ref = (contract.get("allowed_formula_refs") or ["unknown"])[0]
    return _sanitize_value(
        {
            "trace_id": f"{provider}.{field}.{result_field}.v1",
            "provider": provider,
            "layer": contract["layer"],
            "service": contract["service"],
            "intent_id": field,
            "workload_contract_id": execution_context.workload_contract_id,
            "workload_inputs": _workload_inputs(contract, params, derived_params),
            "optimization_profile_id": execution_context.optimization_profile_id,
            "calculation_strategy_id": execution_context.calculation_strategy_id,
            "formula_set_id": execution_context.formula_set_id,
            "formula_ref": formula_ref,
            "provider_pricing_contract_id": contract["id"],
            "pricing_model_classification_id": model["id"],
            "price_source_classification_ids": [source["id"]],
            "selected_evidence_id": _selected_evidence_id(source),
            "selected_evidence_summary": _selected_evidence_summary(source),
            "rejected_alternative_ids": [],
            "normalization_steps": [
                {"normalization_rule": rule}
                for rule in contract.get("normalization_rules") or []
            ],
            "result_field": result_field,
            "cost_contribution": cost_contribution,
            "currency": source.get("currency") or "USD",
            "output_metric_unit": contract.get("output_metric_unit"),
            "publishability_status": (
                "publishable" if model.get("publishable") and source.get("publishable")
                else "not_publishable"
            ),
            "verification_gates": _verification_gates(model, source),
            "verification_gate": "G7_CALCULATION_READINESS",
            "verification_status": "passed"
            if model.get("publishable") and source.get("publishable")
            else "failed",
            "verification_error_code": None
            if model.get("publishable") and source.get("publishable")
            else "UNPUBLISHABLE_SOURCE_STATE",
            "verification_error_message": None
            if model.get("publishable") and source.get("publishable")
            else "Trace source or model is not publishable.",
            "source_build_path": source.get("expected_build_path"),
            "source_type": source.get("source_type"),
        }
    )


def _workload_inputs(
    contract: dict[str, Any],
    params: dict[str, Any],
    derived_params: dict[str, Any],
) -> dict[str, Any]:
    values = {}
    merged = {**params, **derived_params}
    estimated_gb_seconds = (
        float(derived_params.get("total_messages_per_month") or 0) * 0.125 * 0.1
    )
    merged["estimated_function_gb_seconds"] = estimated_gb_seconds
    for field in contract.get("consumed_workload_fields") or []:
        source_key = _WORKLOAD_VALUE_MAP.get(field)
        values[field] = merged.get(source_key) if source_key else None
    return values


def _cost_contribution(
    *,
    provider: str,
    result_field: str,
    component_keys: dict[str, str] | None,
    result_payload: dict[str, Any],
) -> float | None:
    if result_field == "transferCosts":
        return round(sum((result_payload.get("transferCosts") or {}).values()), 6)
    provider_costs = result_payload.get(_PROVIDER_COST_KEYS[provider], {})
    payload = provider_costs.get(result_field) or {}
    if component_keys:
        component_key = component_keys.get(provider)
        components = payload.get("components") or {}
        if component_key in components:
            return _round_or_none(components[component_key])
    return _round_or_none(payload.get("cost"))


def _selected_evidence_id(source: dict[str, Any]) -> str:
    refs = source.get("required_evidence_refs") or []
    if refs:
        return str(refs[0])
    return str(source.get("api_request_id") or source["id"])


def _selected_evidence_summary(source: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "source_type",
        "source_url",
        "api_request_id",
        "catalog_sku_id",
        "region_scope",
        "currency",
        "effective_date",
        "retrieved_at",
        "review_status",
        "verification_status",
    )
    return {key: source.get(key) for key in keys if source.get(key) not in (None, "")}


def _verification_gates(model: dict[str, Any], source: dict[str, Any]) -> list[dict[str, Any]]:
    publishable = bool(model.get("publishable") and source.get("publishable"))
    return [
        {"gate": "G1_REGISTRY_COMPLETENESS", "status": "passed"},
        {"gate": "G2_SOURCE_BUILDABILITY", "status": "passed"},
        {"gate": "G3_EVIDENCE_PRESENCE", "status": "passed"},
        {"gate": "G4_NORMALIZATION", "status": "passed"},
        {"gate": "G5_CONTRACT_COMPATIBILITY", "status": "passed"},
        {
            "gate": "G6_PUBLISHABILITY",
            "status": "passed" if publishable else "failed",
            "error_code": None if publishable else "UNPUBLISHABLE_SOURCE_STATE",
        },
        {
            "gate": "G7_CALCULATION_READINESS",
            "status": "passed" if publishable else "failed",
            "error_code": None if publishable else "CALCULATION_NOT_READY",
        },
    ]


def _round_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    return None


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_value(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value[:50]]
    if isinstance(value, str):
        sanitized = value
        for marker in (
            "private_key",
            "client_secret",
            "access_key",
            "secret_access_key",
            "credential",
            "/Users/",
        ):
            sanitized = sanitized.replace(marker, "[redacted]")
        return sanitized[:500]
    return value
