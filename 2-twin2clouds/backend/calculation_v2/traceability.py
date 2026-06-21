"""Intent-to-result trace construction for cost calculation results.

The trace is intentionally metadata-only: it references registry/evidence
identity and formula contracts without embedding raw provider pricing payloads
or credentials.
"""

from __future__ import annotations

from typing import Any, Mapping

from backend.calculation_v2.components import LayerType, Provider
from backend.calculation_v2.pricing_source_inventory import (
    PricingFailureBehavior,
    PricingSourceRecord,
    pricing_source_inventory_by_id,
)
from backend.calculation_v2.strategy_contracts import (
    FormulaBindingContract,
    OptimizationStrategyContract,
    PricingIntentContract,
    cost_strategy_contract,
)


TRACE_SCHEMA_VERSION = "intent-result-trace.v1"

_LAYER_SELECTIONS = {
    LayerType.L1_INGESTION: ("L1", ("L1",)),
    LayerType.L2_PROCESSING: ("L2", ("L2",)),
    LayerType.L3_HOT_STORAGE: ("L3_hot", ("L3", "Hot")),
    LayerType.L3_COOL_STORAGE: ("L3_cool", ("L3", "Cool")),
    LayerType.L3_ARCHIVE_STORAGE: ("L3_archive", ("L3", "Archive")),
    LayerType.L4_TWIN_MANAGEMENT: ("L4", ("L4",)),
    LayerType.L5_VISUALIZATION: ("L5", ("L5",)),
}


def build_intent_result_trace(
    *,
    params: Mapping[str, Any],
    derived: Mapping[str, Any],
    calculation_result: Mapping[str, Any],
    provider_costs: Mapping[str, Mapping[str, Any]],
    transfer_costs: Mapping[str, float],
    optimization_metadata: Mapping[str, Any],
    pricing_registry_reference: str,
    contract: OptimizationStrategyContract | None = None,
) -> dict[str, Any]:
    """Build a bounded, secret-free trace for one calculation result."""

    strategy = contract or cost_strategy_contract()
    inventory = pricing_source_inventory_by_id(strategy)
    bindings_by_intent = _bindings_by_intent(strategy)
    selected_path = _selected_path_entries(calculation_result, provider_costs)
    records = []

    for intent in strategy.pricing_intents:
        layer_cost_key, selected_provider = _selected_provider_for_intent(
            intent,
            calculation_result,
        )
        provider_cost = provider_costs.get(intent.provider.value, {})
        contribution = _contribution_for_intent(
            intent=intent,
            selected_provider=selected_provider,
            layer_cost_key=layer_cost_key,
            provider_cost=provider_cost,
            transfer_costs=transfer_costs,
        )
        if not contribution.get("selected"):
            continue

        for field in intent.fields:
            record_id = f"{intent.intent_id}.{field.field_id}"
            source_record = inventory[record_id]
            binding = bindings_by_intent.get(intent.intent_id)
            records.append(
                _trace_record(
                    source_record=source_record,
                    binding=binding,
                    contribution=contribution,
                    pricing_registry_reference=pricing_registry_reference,
                )
            )

    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "profile": _profile_trace(optimization_metadata),
        "workload": _workload_trace(params, derived),
        "selected_path": selected_path,
        "transfer_trace": _transfer_trace_entries(
            calculation_result,
            transfer_costs,
            pricing_registry_reference,
        ),
        "records": records,
        "summary": _summary(records, selected_path, transfer_costs),
    }


def _bindings_by_intent(
    strategy: OptimizationStrategyContract,
) -> dict[str, FormulaBindingContract]:
    bindings = {}
    for binding in strategy.formula_bindings:
        for intent_id in binding.intent_ids:
            bindings.setdefault(intent_id, binding)
    return bindings


def _selected_provider_for_intent(
    intent: PricingIntentContract,
    calculation_result: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    if intent.layer == LayerType.L0_GLUE:
        return "transfer", None

    layer_info = _LAYER_SELECTIONS.get(intent.layer)
    if not layer_info:
        return None, None

    layer_cost_key, result_path = layer_info
    current: Any = calculation_result
    for path_item in result_path:
        if not isinstance(current, Mapping) or path_item not in current:
            return layer_cost_key, None
        current = current[path_item]

    return layer_cost_key, str(current) if current is not None else None


def _contribution_for_intent(
    *,
    intent: PricingIntentContract,
    selected_provider: str | None,
    layer_cost_key: str | None,
    provider_cost: Mapping[str, Any],
    transfer_costs: Mapping[str, float],
) -> dict[str, Any]:
    provider_label = _provider_label(intent.provider)

    if intent.layer == LayerType.L0_GLUE:
        selected_transfers = _transfer_segments_for_provider(provider_label, transfer_costs)
        return {
            "selected": bool(selected_transfers),
            "path_key": "transfer",
            "cost": round(sum(segment["cost"] for segment in selected_transfers), 6),
            "component_keys": [],
            "transfer_segments": selected_transfers,
        }

    selected = selected_provider == provider_label
    layer_payload = provider_cost.get(layer_cost_key or "", {})
    layer_cost = layer_payload.get("cost") if isinstance(layer_payload, Mapping) else None
    components = layer_payload.get("components") if isinstance(layer_payload, Mapping) else None
    return {
        "selected": selected,
        "path_key": f"{layer_cost_key}_{provider_label}" if layer_cost_key else provider_label,
        "cost": round(float(layer_cost), 6) if isinstance(layer_cost, (int, float)) else None,
        "component_keys": sorted(components.keys()) if isinstance(components, Mapping) else [],
        "transfer_segments": [],
    }


def _trace_record(
    *,
    source_record: PricingSourceRecord,
    binding: FormulaBindingContract | None,
    contribution: Mapping[str, Any],
    pricing_registry_reference: str,
) -> dict[str, Any]:
    record_id = source_record.record_id
    return {
        "trace_id": f"trace:{record_id}",
        "record_id": record_id,
        "intent_id": source_record.intent_id,
        "provider": source_record.provider,
        "layer": source_record.layer,
        "service_key": source_record.service_key,
        "field_id": source_record.field_id,
        "source": {
            "primary_source_type": source_record.policy.primary_source_type.value,
            "refreshability": source_record.policy.refreshability.value,
            "failure_behavior": source_record.policy.failure_behavior.value,
            "evidence": source_record.policy.evidence.value,
            "emergency_fallback_source_type": (
                source_record.policy.emergency_fallback_source_type.value
                if source_record.policy.emergency_fallback_source_type
                else None
            ),
            "emergency_fallback_allowed": source_record.policy.emergency_fallback_allowed,
        },
        "pricing": {
            "key_path": list(source_record.key_path),
            "aliases": [list(alias) for alias in source_record.aliases],
            "canonical_unit": source_record.canonical_unit,
            "source_unit": source_record.source_unit,
            "quantity_basis": source_record.quantity_basis,
            "normalizer": source_record.normalizer,
        },
        "formula": _formula_trace(binding),
        "contribution": dict(contribution),
        "verification": _verification_trace(
            source_record=source_record,
            selected=bool(contribution.get("selected")),
            evidence_reference_id=f"{pricing_registry_reference}/{record_id}",
        ),
    }


def _formula_trace(binding: FormulaBindingContract | None) -> dict[str, Any] | None:
    if binding is None:
        return None

    return {
        "binding_id": binding.binding_id,
        "formula_type": binding.formula_type.name,
        "calculation_entrypoint": binding.calculation_entrypoint,
        "result_component": binding.result_component,
        "required_usage_inputs": list(binding.required_usage_inputs),
        "normalizer": binding.normalizer,
    }


def _verification_trace(
    *,
    source_record: PricingSourceRecord,
    selected: bool,
    evidence_reference_id: str,
) -> dict[str, Any]:
    if not selected:
        status = "not_selected"
    elif source_record.policy.failure_behavior == PricingFailureBehavior.MARK_UNSUPPORTED:
        status = "unsupported"
    elif source_record.policy.failure_behavior == PricingFailureBehavior.REQUIRE_REVIEW:
        status = "review_required"
    else:
        status = "ready"

    review_required = status == "review_required"
    publishable = status in {"ready", "not_selected"}
    return {
        "status": status,
        "review_required": review_required,
        "publishable": publishable,
        "evidence_reference_id": evidence_reference_id,
    }


def _profile_trace(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "profile_id": metadata.get("profile_id"),
        "objective": metadata.get("objective"),
        "metric_provider_ids": list(metadata.get("metric_provider_ids") or []),
        "calculation_model_ids": list(metadata.get("calculation_model_ids") or []),
        "scoring_strategy_id": metadata.get("scoring_strategy_id"),
        "intent_group_ids": list(metadata.get("intent_group_ids") or []),
        "result_schema_version": metadata.get("result_schema_version"),
        "pricing_registry_version": metadata.get("pricing_registry_version"),
    }


def _workload_trace(params: Mapping[str, Any], derived: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "inputs": {
            "numberOfDevices": params.get("numberOfDevices"),
            "deviceSendingIntervalInMinutes": params.get("deviceSendingIntervalInMinutes"),
            "averageSizeOfMessageInKb": params.get("averageSizeOfMessageInKb"),
            "hotStorageDurationInMonths": params.get("hotStorageDurationInMonths"),
            "coolStorageDurationInMonths": params.get("coolStorageDurationInMonths"),
            "archiveStorageDurationInMonths": params.get("archiveStorageDurationInMonths"),
            "amountOfActiveEditors": params.get("amountOfActiveEditors"),
            "amountOfActiveViewers": params.get("amountOfActiveViewers"),
            "dashboardRefreshesPerHour": params.get("dashboardRefreshesPerHour"),
            "dashboardActiveHoursPerDay": params.get("dashboardActiveHoursPerDay"),
        },
        "derived": {
            "total_messages_per_month": _rounded(derived.get("total_messages_per_month")),
            "data_size_per_month_gb": _rounded(derived.get("data_size_per_month_gb")),
            "hot_storage_gb": _rounded(derived.get("hot_storage_gb")),
            "cool_storage_gb": _rounded(derived.get("cool_storage_gb")),
            "archive_storage_gb": _rounded(derived.get("archive_storage_gb")),
            "queries_per_month": _rounded(derived.get("queries_per_month")),
        },
    }


def _selected_path_entries(
    calculation_result: Mapping[str, Any],
    provider_costs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    entries = []
    layer_mappings = [
        ("L1", "L1", calculation_result.get("L1")),
        ("L2", "L2", calculation_result.get("L2")),
        ("L3_hot", "L3.Hot", (calculation_result.get("L3") or {}).get("Hot")),
        ("L3_cool", "L3.Cool", (calculation_result.get("L3") or {}).get("Cool")),
        ("L3_archive", "L3.Archive", (calculation_result.get("L3") or {}).get("Archive")),
        ("L4", "L4", calculation_result.get("L4")),
        ("L5", "L5", calculation_result.get("L5")),
    ]

    for layer_cost_key, result_path, provider_label in layer_mappings:
        provider_key = _provider_key(str(provider_label)) if provider_label else None
        cost_payload = (provider_costs.get(provider_key or "") or {}).get(layer_cost_key, {})
        entries.append(
            {
                "result_path": result_path,
                "layer_cost_key": layer_cost_key,
                "provider": provider_label,
                "path_key": f"{layer_cost_key}_{provider_label}" if provider_label else layer_cost_key,
                "cost": _rounded(cost_payload.get("cost")) if isinstance(cost_payload, Mapping) else None,
            }
        )

    return entries


def _summary(
    records: list[Mapping[str, Any]],
    selected_path: list[Mapping[str, Any]],
    transfer_costs: Mapping[str, float],
) -> dict[str, Any]:
    selected_records = [
        record for record in records if record.get("contribution", {}).get("selected")
    ]
    review_required = [
        record
        for record in selected_records
        if record.get("verification", {}).get("review_required")
    ]
    unsupported = [
        record
        for record in selected_records
        if record.get("verification", {}).get("status") == "unsupported"
    ]
    return {
        "record_count": len(records),
        "selected_record_count": len(selected_records),
        "review_required_count": len(review_required),
        "unsupported_count": len(unsupported),
        "selected_path_count": len(selected_path),
        "transfer_segment_count": len(transfer_costs),
        "publishable": not review_required and not unsupported,
    }


def _transfer_segments_for_provider(
    provider_label: str,
    transfer_costs: Mapping[str, float],
) -> list[dict[str, Any]]:
    segments = []
    for segment, cost in sorted(transfer_costs.items()):
        if _transfer_source_provider(segment) == provider_label:
            segments.append({"segment": segment, "cost": _rounded(cost)})
    return segments


def _transfer_trace_entries(
    calculation_result: Mapping[str, Any],
    transfer_costs: Mapping[str, float],
    pricing_registry_reference: str,
) -> list[dict[str, Any]]:
    path = {
        "L1": calculation_result.get("L1"),
        "L2": calculation_result.get("L2"),
        "L3_hot": (calculation_result.get("L3") or {}).get("Hot"),
        "L3_cool": (calculation_result.get("L3") or {}).get("Cool"),
        "L3_archive": (calculation_result.get("L3") or {}).get("Archive"),
        "L4": calculation_result.get("L4"),
    }
    segment_layers = {
        "L1_to_L2": ("L1", "L2"),
        "L2_to_L3_hot": ("L2", "L3_hot"),
        "L3_hot_to_L3_cool": ("L3_hot", "L3_cool"),
        "L3_cool_to_L3_archive": ("L3_cool", "L3_archive"),
        "L3_hot_to_L4": ("L3_hot", "L4"),
    }

    entries = []
    for segment, cost in sorted(transfer_costs.items()):
        source_layer, target_layer = segment_layers.get(segment, (None, None))
        source_provider = path.get(source_layer)
        source_intent_id = (
            f"{_provider_key(str(source_provider))}.transfer.egress"
            if source_provider
            else None
        )
        entries.append(
            {
                "segment": segment,
                "source_layer": source_layer,
                "target_layer": target_layer,
                "source_provider": source_provider,
                "target_provider": path.get(target_layer),
                "cost": _rounded(cost),
                "source_intent_id": source_intent_id,
                "evidence_reference_ids": (
                    [
                        f"{pricing_registry_reference}/{source_intent_id}.egress",
                        f"{pricing_registry_reference}/{source_intent_id}.egress_tiers",
                    ]
                    if source_intent_id
                    else []
                ),
            }
        )
    return entries


def _transfer_source_provider(segment: str) -> str | None:
    # The segment name identifies the source layer. The provider is resolved in
    # transfer_trace; L0 intent rows are not duplicated into selected field
    # records because transfer pricing is represented as segment-level cost.
    return None


def _provider_label(provider: Provider) -> str:
    return {
        Provider.AWS: "AWS",
        Provider.AZURE: "Azure",
        Provider.GCP: "GCP",
    }[provider]


def _provider_key(provider_label: str) -> str:
    return {
        "AWS": "aws",
        "Azure": "azure",
        "GCP": "gcp",
    }[provider_label]


def _rounded(value: Any) -> float | int | None:
    if not isinstance(value, (int, float)):
        return None
    rounded = round(float(value), 6)
    return int(rounded) if rounded.is_integer() else rounded
