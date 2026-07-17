"""
Cost Calculation Engine v2
===========================

New orchestration module using component-level architecture.

This module provides the same interface as the old engine.py:
- calculate_aws_costs(params, pricing)
- calculate_azure_costs(params, pricing)
- calculate_gcp_costs(params, pricing)
- calculate_cheapest_costs(params, pricing)

But internally uses the new layer calculators from calculation_v2.
"""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any, Dict

from backend.calculation_v2.layers import (
    AWSLayerCalculators,
    AzureLayerCalculators,
    GCPLayerCalculators,
    LayerResult,
    SUPPORTED_LAYER_KEYS,
    SUPPORTED_PROVIDER_KEYS,
)
from backend.calculation_v2.currency import apply_result_currency
from backend.calculation_v2.formulas import (
    billable_1kb_units,
)
from backend.calculation_v2.path_optimizer import (
    LAYER_ORDER,
    build_optimization_diagnostics,
    build_transfer_pricing_context,
    evaluate_complete_paths,
)
from backend.calculation_v2.strategy_context import (
    CalculationStrategyExecutionContext,
    resolve_calculation_strategy_execution_context,
)
from backend.calculation_v2.strategy_traceability import (
    TRACE_SCHEMA_VERSION as STRATEGY_TRACE_SCHEMA_VERSION,
    build_intent_result_trace as build_strategy_result_trace,
)
from backend.calculation_v2.traceability import (
    TRACE_SCHEMA_VERSION,
    build_intent_result_trace,
)
from backend.calculation_v2.transfer_pricing import (
    TransferPricingContractError,
    TransferRouteClass,
)
from backend.optimization.context import OptimizationMetricContext
from backend.optimization.profiles import build_default_profile_registry
from backend.optimization.scoring import OptimizationCandidate
from backend.deployment_specification import (
    build_resolved_deployment_specification,
)
from backend.pricing_catalog_models import PricingCatalogContext
from backend.pricing_registry_service import PricingRegistryService
from backend.transfer_catalog import validate_transfer_catalog


# =============================================================================
# Calculator Instances
# =============================================================================

_aws_calc = AWSLayerCalculators()
_azure_calc = AzureLayerCalculators()
_gcp_calc = GCPLayerCalculators()


def _layer_result_payload(
    result: LayerResult,
    *,
    data_size_gb: float | None = None,
) -> Dict[str, Any]:
    """Serialize a layer result without losing capability information."""
    payload: Dict[str, Any] = {
        "cost": result.total_cost,
        "components": dict(result.components),
        "deploymentSelections": [
            selection.as_dict() for selection in result.deployment_selections
        ],
        "supported": result.supported,
    }
    if data_size_gb is not None:
        payload["dataSizeInGB"] = data_size_gb
    if result.unsupported_reason is not None:
        payload["unsupportedReason"] = result.unsupported_reason
    if result.details:
        payload["details"] = result.details_as_dict()
    return payload


def _supported_provider_options(
    provider_costs: Mapping[str, Mapping[str, Any]],
    layer: str,
) -> tuple[tuple[str, float], ...]:
    """Return validated provider costs that are executable for a layer."""
    if layer not in SUPPORTED_LAYER_KEYS:
        raise ValueError(f"Unknown architecture layer: {layer!r}")
    providers = frozenset(provider_costs)
    if providers != SUPPORTED_PROVIDER_KEYS:
        missing = sorted(SUPPORTED_PROVIDER_KEYS - providers)
        unexpected = sorted(providers - SUPPORTED_PROVIDER_KEYS)
        raise ValueError(
            "Provider cost results must cover the canonical provider set; "
            f"missing={missing}, unexpected={unexpected}"
        )

    options: list[tuple[str, float]] = []
    for provider, costs in provider_costs.items():
        if not isinstance(costs, Mapping):
            raise ValueError(f"{provider} provider cost result must be a mapping")
        payload = costs.get(layer)
        if not isinstance(payload, Mapping):
            raise ValueError(f"Missing {provider} result for architecture layer {layer}")

        supported = payload.get("supported")
        if not isinstance(supported, bool):
            raise ValueError(
                f"{provider} result for {layer} must declare a boolean supported state"
            )
        if not supported:
            reason = payload.get("unsupportedReason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(
                    f"Unsupported {provider} result for {layer} requires a reason"
                )
            continue

        cost = payload.get("cost")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            raise ValueError(f"{provider} result for {layer} must declare a numeric cost")
        normalized_cost = float(cost)
        if not isfinite(normalized_cost) or normalized_cost < 0:
            raise ValueError(
                f"{provider} result for {layer} must declare a finite non-negative cost"
            )
        options.append((provider, normalized_cost))

    if not options:
        raise ValueError(f"No provider supports architecture layer {layer}")
    return tuple(options)


# =============================================================================
# Parameter Helpers
# =============================================================================

def _calculate_derived_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate derived parameters from the raw input params.
    
    This mirrors the logic from the old engine but centralizes it.
    """
    # Extract base params
    num_devices = params["numberOfDevices"]
    interval_minutes = params["deviceSendingIntervalInMinutes"]
    msg_size_kb = params["averageSizeOfMessageInKb"]
    
    # Calculate messages
    messages_per_device_per_hour = 60 / interval_minutes
    messages_per_device_per_day = messages_per_device_per_hour * 24
    messages_per_device_per_month = messages_per_device_per_day * 30
    total_messages_per_month = num_devices * messages_per_device_per_month
    
    # Calculate data sizes
    data_size_per_month_kb = total_messages_per_month * msg_size_kb
    data_size_per_month_gb = data_size_per_month_kb / (1024 * 1024)
    
    # Storage calculations
    hot_duration = params["hotStorageDurationInMonths"]
    cool_duration = params["coolStorageDurationInMonths"]
    archive_duration = params["archiveStorageDurationInMonths"]
    
    hot_storage_gb = data_size_per_month_gb * hot_duration
    cool_storage_gb = data_size_per_month_gb * cool_duration
    archive_storage_gb = data_size_per_month_gb * archive_duration
    
    # Dashboard/queries
    dashboard_hours = params.get("dashboardActiveHoursPerDay", 0)
    dashboard_refreshes = params.get("dashboardRefreshesPerHour", 0)
    api_calls_per_refresh = params.get("apiCallsPerDashboardRefresh", 1)
    
    queries_per_day = dashboard_hours * dashboard_refreshes * api_calls_per_refresh
    queries_per_month = queries_per_day * 30

    query_units_per_query = float(
        params.get("averageDigitalTwinQueryUnitsPerQuery", 1.0)
    )
    query_response_size_kb = float(
        params.get("averageDigitalTwinQueryResponseSizeInKb", 1.0)
    )
    query_response_operations = billable_1kb_units(
        queries_per_month,
        query_response_size_kb,
    )
    billable_operations = total_messages_per_month + query_response_operations
    billable_query_units = queries_per_month * query_units_per_query
    assumption_sources = params.get("_assumption_sources")
    if not isinstance(assumption_sources, Mapping):
        assumption_sources = {}
    
    return {
        "total_messages_per_month": total_messages_per_month,
        "data_size_per_month_gb": data_size_per_month_gb,
        "hot_storage_gb": hot_storage_gb,
        "cool_storage_gb": cool_storage_gb,
        "archive_storage_gb": archive_storage_gb,
        "queries_per_month": queries_per_month,
        "monthly_digital_twin_billable_operations": billable_operations,
        "monthly_digital_twin_routed_messages": 0.0,
        "monthly_digital_twin_query_units": billable_query_units,
        "digital_twin_query_response_operations": query_response_operations,
        "average_digital_twin_query_units_per_query": query_units_per_query,
        "average_digital_twin_query_response_size_kb": query_response_size_kb,
        "digital_twin_assumption_sources": {
            "averageDigitalTwinQueryUnitsPerQuery": assumption_sources.get(
                "averageDigitalTwinQueryUnitsPerQuery",
                "explicit_input"
                if "averageDigitalTwinQueryUnitsPerQuery" in params
                else "compatibility_default",
            ),
            "averageDigitalTwinQueryResponseSizeInKb": assumption_sources.get(
                "averageDigitalTwinQueryResponseSizeInKb",
                "explicit_input"
                if "averageDigitalTwinQueryResponseSizeInKb" in params
                else "compatibility_default",
            ),
        },
        "num_devices": num_devices,
        "msg_size_kb": msg_size_kb,
        "hot_duration": hot_duration,
        "cool_duration": cool_duration,
        "archive_duration": archive_duration,
    }


def _ensure_supported_result_profile(
    result_schema_version: str,
    metric_provider_ids: tuple[str, ...],
    primary_metric_id: str,
) -> None:
    """Fail fast when a profile exceeds this engine's executable contract."""
    if result_schema_version != "cost-result.v1":
        raise ValueError(
            "calculate_cheapest_costs currently supports only cost-result.v1. "
            f"Received {result_schema_version!r}."
        )
    if primary_metric_id not in metric_provider_ids:
        raise ValueError(
            "Scoring strategy primary metric must be declared by the active "
            f"profile: {primary_metric_id!r}"
        )


# =============================================================================
# Provider Cost Calculators
# =============================================================================

def calculate_aws_costs(params: Dict[str, Any], pricing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate all AWS layer costs.
    
    Returns dict with costs for L1, L2, L3 (hot/cool/archive), L4, L5.
    """
    derived = _calculate_derived_params(params)
    
    # L1: Data Acquisition
    l1 = _aws_calc.calculate_l1_cost(
        number_of_devices=derived["num_devices"],
        messages_per_month=derived["total_messages_per_month"],
        average_message_size_kb=derived["msg_size_kb"],
        pricing=pricing
    )
    
    # L2: Data Processing
    l2 = _aws_calc.calculate_l2_cost(
        executions_per_month=derived["total_messages_per_month"],
        pricing=pricing,
        number_of_device_types=params.get("numberOfDeviceTypes", 1),
        use_event_checking=params.get("useEventChecking", False),
        trigger_notification_workflow=params.get("triggerNotificationWorkflow", False),
        return_feedback_to_device=params.get("returnFeedbackToDevice", False),
        integrate_error_handling=params.get("integrateErrorHandling", False),
        num_event_actions=params.get("numberOfEventActions", 0),
        events_per_message=params.get("eventsPerMessage", 1),
        orchestration_actions=params.get("orchestrationActionsPerMessage", 3),
        event_trigger_rate=params.get("eventTriggerRate", 0.1)
    )
    
    # L3: Storage tiers
    l3_hot = _aws_calc.calculate_l3_hot_cost(
        writes_per_month=derived["total_messages_per_month"],
        reads_per_month=derived["queries_per_month"],
        storage_gb=derived["hot_storage_gb"],
        pricing=pricing,
        hot_reader_queries_per_month=derived["queries_per_month"]
    )
    
    l3_cool = _aws_calc.calculate_l3_cool_cost(
        storage_gb=derived["cool_storage_gb"],
        writes_per_month=derived["total_messages_per_month"],
        pricing=pricing
    )
    
    l3_archive = _aws_calc.calculate_l3_archive_cost(
        storage_gb=derived["archive_storage_gb"],
        writes_per_month=derived["total_messages_per_month"],
        pricing=pricing
    )
    
    # L4: Twin Management
    l4 = _aws_calc.calculate_l4_cost(
        entity_count=params.get("entityCount", 1),
        queries_per_month=derived["queries_per_month"],
        api_calls_per_month=derived["queries_per_month"],
        pricing=pricing,
        account_pricing_context=(
            params.get("providerPricingContexts", {}).get("awsTwinMaker")
            if isinstance(params.get("providerPricingContexts"), Mapping)
            else None
        ),
    )
    
    # L5: Visualization
    l5 = _aws_calc.calculate_l5_cost(
        num_editors=params.get("amountOfActiveEditors", 0),
        num_viewers=params.get("amountOfActiveViewers", 0),
        pricing=pricing
    )
    
    return {
        "L1": _layer_result_payload(l1, data_size_gb=l1.data_size_gb),
        "L2": _layer_result_payload(l2, data_size_gb=derived["data_size_per_month_gb"]),
        "L3_hot": _layer_result_payload(l3_hot, data_size_gb=derived["hot_storage_gb"]),
        "L3_cool": _layer_result_payload(l3_cool, data_size_gb=derived["cool_storage_gb"]),
        "L3_archive": _layer_result_payload(
            l3_archive,
            data_size_gb=derived["archive_storage_gb"],
        ),
        "L4": _layer_result_payload(l4),
        "L5": _layer_result_payload(l5),
        "totalMessagesPerMonth": derived["total_messages_per_month"],
        "providerPricingContext": (
            l4.details_as_dict().get("pricingContext")
            if isinstance(l4.details, Mapping)
            else None
        ),
    }


def calculate_azure_costs(params: Dict[str, Any], pricing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate all Azure layer costs.
    """
    derived = _calculate_derived_params(params)
    
    # L1: Data Acquisition
    l1 = _azure_calc.calculate_l1_cost(
        messages_per_month=derived["total_messages_per_month"],
        pricing=pricing,
        average_message_size_kb=derived["msg_size_kb"],
    )
    
    # L2: Data Processing
    l2 = _azure_calc.calculate_l2_cost(
        executions_per_month=derived["total_messages_per_month"],
        pricing=pricing,
        number_of_device_types=params.get("numberOfDeviceTypes", 1),
        use_event_checking=params.get("useEventChecking", False),
        use_orchestration=params.get("triggerNotificationWorkflow", False),
        return_feedback_to_device=params.get("returnFeedbackToDevice", False),
        use_error_handling=params.get("integrateErrorHandling", False),
        num_event_actions=params.get("numberOfEventActions", 0),
        event_trigger_rate=params.get("eventTriggerRate", 0.1)
    )
    
    # L3: Storage tiers
    l3_hot = _azure_calc.calculate_l3_hot_cost(
        writes_per_month=derived["total_messages_per_month"],
        reads_per_month=derived["queries_per_month"],
        storage_gb=derived["hot_storage_gb"],
        pricing=pricing,
        hot_reader_queries_per_month=derived["queries_per_month"]
    )
    
    l3_cool = _azure_calc.calculate_l3_cool_cost(
        storage_gb=derived["cool_storage_gb"],
        writes_per_month=derived["total_messages_per_month"],
        pricing=pricing
    )
    
    l3_archive = _azure_calc.calculate_l3_archive_cost(
        storage_gb=derived["archive_storage_gb"],
        writes_per_month=derived["total_messages_per_month"],
        pricing=pricing
    )
    
    # L4: Twin Management
    l4 = _azure_calc.calculate_l4_cost(
        billable_operations=derived["monthly_digital_twin_billable_operations"],
        billable_query_units=derived["monthly_digital_twin_query_units"],
        billable_messages=derived["monthly_digital_twin_routed_messages"],
        telemetry_updates_per_month=derived["total_messages_per_month"],
        pricing=pricing
    )
    
    # L5: Visualization
    l5 = _azure_calc.calculate_l5_cost(
        num_editors=params.get("amountOfActiveEditors", 0),
        num_viewers=params.get("amountOfActiveViewers", 0),
        pricing=pricing
    )
    
    return {
        "L1": _layer_result_payload(l1, data_size_gb=derived["data_size_per_month_gb"]),
        "L2": _layer_result_payload(l2, data_size_gb=derived["data_size_per_month_gb"]),
        "L3_hot": _layer_result_payload(l3_hot, data_size_gb=derived["hot_storage_gb"]),
        "L3_cool": _layer_result_payload(l3_cool, data_size_gb=derived["cool_storage_gb"]),
        "L3_archive": _layer_result_payload(
            l3_archive,
            data_size_gb=derived["archive_storage_gb"],
        ),
        "L4": _layer_result_payload(l4),
        "L5": _layer_result_payload(l5),
        "totalMessagesPerMonth": derived["total_messages_per_month"],
    }


def calculate_gcp_costs(params: Dict[str, Any], pricing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate all GCP layer costs.
    """
    derived = _calculate_derived_params(params)
    
    # L1: Data Acquisition (volume-based for GCP)
    l1 = _gcp_calc.calculate_l1_cost(
        data_volume_gb=derived["data_size_per_month_gb"],
        messages_per_month=derived["total_messages_per_month"],
        pricing=pricing,
        average_message_size_kb=derived["msg_size_kb"],
    )
    
    # L2: Data Processing
    l2 = _gcp_calc.calculate_l2_cost(
        executions_per_month=derived["total_messages_per_month"],
        pricing=pricing,
        number_of_device_types=params.get("numberOfDeviceTypes", 1),
        use_event_checking=params.get("useEventChecking", False),
        use_orchestration=params.get("triggerNotificationWorkflow", False),
        return_feedback_to_device=params.get("returnFeedbackToDevice", False),
        num_event_actions=params.get("numberOfEventActions", 0),
        event_trigger_rate=params.get("eventTriggerRate", 0.1)
    )
    
    # L3: Storage tiers
    l3_hot = _gcp_calc.calculate_l3_hot_cost(
        writes_per_month=derived["total_messages_per_month"],
        reads_per_month=derived["queries_per_month"],
        storage_gb=derived["hot_storage_gb"],
        pricing=pricing,
        hot_reader_queries_per_month=derived["queries_per_month"]
    )
    
    l3_cool = _gcp_calc.calculate_l3_cool_cost(
        storage_gb=derived["cool_storage_gb"],
        writes_per_month=derived["total_messages_per_month"],
        pricing=pricing
    )
    
    l3_archive = _gcp_calc.calculate_l3_archive_cost(
        storage_gb=derived["archive_storage_gb"],
        writes_per_month=derived["total_messages_per_month"],
        pricing=pricing
    )
    
    # L4: Twin Management (self-hosted on GCP)
    l4 = _gcp_calc.calculate_l4_cost(pricing=pricing)
    
    # L5: Visualization (self-hosted on GCP)
    l5 = _gcp_calc.calculate_l5_cost(pricing=pricing)
    
    return {
        "L1": _layer_result_payload(l1, data_size_gb=derived["data_size_per_month_gb"]),
        "L2": _layer_result_payload(l2, data_size_gb=derived["data_size_per_month_gb"]),
        "L3_hot": _layer_result_payload(l3_hot, data_size_gb=derived["hot_storage_gb"]),
        "L3_cool": _layer_result_payload(l3_cool, data_size_gb=derived["cool_storage_gb"]),
        "L3_archive": _layer_result_payload(
            l3_archive,
            data_size_gb=derived["archive_storage_gb"],
        ),
        "L4": _layer_result_payload(l4),
        "L5": _layer_result_payload(l5),
        "totalMessagesPerMonth": derived["total_messages_per_month"],
    }


# =============================================================================
# Cross-Cloud Transfer Costs
# =============================================================================

def _calculate_egress_cost(
    data_gb: float,
    pricing: Dict[str, Any],
    source_provider: str,
    execution_context: CalculationStrategyExecutionContext | None = None,
) -> float:
    """Calculate egress from the validated provider transfer catalog."""
    if execution_context is not None:
        execution_context.ensure_formula_ref(
            "transfer_tier_cost",
            provider=source_provider,
            field="transfer.egress_gb",
        )
    if not isinstance(source_provider, str):
        raise ValueError("source_provider must be a supported provider name")
    provider_key = source_provider.lower()
    if provider_key not in {"aws", "azure", "gcp"}:
        raise ValueError(f"Unsupported transfer source provider: {source_provider!r}")

    provider_pricing = pricing.get(provider_key)
    transfer = (
        provider_pricing.get("transfer")
        if isinstance(provider_pricing, Mapping)
        else None
    )
    if not isinstance(transfer, Mapping):
        raise ValueError(
            f"Missing required pricing field for {provider_key}.transfer.catalog"
        )

    try:
        decimal_gb = Decimal(str(data_gb))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("data_gb must be a finite non-negative number") from exc
    if not decimal_gb.is_finite() or decimal_gb < 0:
        raise ValueError("data_gb must be a finite non-negative number")

    try:
        table = validate_transfer_catalog(
            provider_key,
            transfer.get("source_region"),
            transfer,
        )
    except TransferPricingContractError as exc:
        raise ValueError(
            f"Invalid required pricing field for {provider_key}.transfer.catalog: "
            f"{exc.code}"
        ) from exc
    volume_bytes = decimal_gb * Decimal(1_000_000_000)
    return float(table.cost_for_bytes(volume_bytes))


def _calculate_glue_cost(messages: float, pricing: Dict[str, Any], provider: str) -> float:
    """Calculate cost of glue functions for cross-cloud communication."""
    if provider == "AWS":
        return _aws_calc.calculate_glue_cost(messages, pricing)
    elif provider == "Azure":
        return _azure_calc.calculate_glue_cost(messages, pricing)
    elif provider == "GCP":
        return _gcp_calc.calculate_glue_cost(messages, pricing)
    return 0.0


# =============================================================================
# Main Orchestration - Calculate Cheapest Costs
# =============================================================================

def calculate_cheapest_costs(
    params: Dict[str, Any],
    pricing: Dict[str, Any],
    *,
    pricing_catalog_context: PricingCatalogContext,
    optimization_profile_id: str | None = None,
    pricing_registry_service: PricingRegistryService | None = None,
) -> Dict[str, Any]:
    """
    Orchestrate cost calculation and find the cheapest path across providers.
    
    This function:
    1. Calculates costs for each provider (AWS, Azure, GCP)
    2. Enumerates every executable complete baseline path
    3. Applies route-aware pooled transfer and glue costs
    4. Scores complete paths and returns the globally cheapest result
    
    Args:
        params: Input parameters from the API
        pricing: Exact resolved pricing data for all providers
        pricing_catalog_context: Exact immutable catalog references and regions
        optimization_profile_id: Optional executable optimization profile.
        
    Returns:
        Dictionary with:
        - awsCosts: Full cost breakdown for AWS
        - azureCosts: Full cost breakdown for Azure  
        - gcpCosts: Full cost breakdown for GCP
        - calculationResult: Optimal provider for each layer
        - cheapestPath: List of layer-provider combinations
        - totalCost: Total cost of the optimal path
    """
    if params.get("allowGcpSelfHostedL4") or params.get("allowGcpSelfHostedL5"):
        raise ValueError(
            "GCP self-hosted L4/L5 cannot be enabled until the Deployer "
            "implements and verifies those deployment paths"
        )
    if not isinstance(pricing_catalog_context, PricingCatalogContext):
        raise TypeError("pricing_catalog_context must be a PricingCatalogContext")

    registry_service = pricing_registry_service or PricingRegistryService()
    pricing_registry = registry_service.load()
    profile_registry = (
        build_default_profile_registry(registry_service)
        if pricing_registry_service is not None
        else build_default_profile_registry()
    )
    execution_context = resolve_calculation_strategy_execution_context(
        optimization_profile_id=optimization_profile_id,
        profile_registry=profile_registry,
        pricing_registry_service=registry_service,
        publishable_mode=True,
    )
    optimization_profile = profile_registry.select_profile(optimization_profile_id)
    cost_metric_provider = profile_registry.get_metric_provider("cost")
    scoring_strategy = profile_registry.get_scoring_strategy(
        optimization_profile.scoring_strategy_id
    )
    _ensure_supported_result_profile(
        optimization_profile.result_schema_version,
        tuple(optimization_profile.metric_provider_ids),
        scoring_strategy.primary_metric_id,
    )
    optimization_metadata = profile_registry.build_result_metadata(
        optimization_profile.profile_id
    )
    pricing_registry_reference = (
        f"pricing_registry:{optimization_metadata['pricing_registry_version']}"
    )
    
    # Calculate costs for each provider
    execution_context.ensure_provider_context("aws")
    aws_costs = calculate_aws_costs(params, pricing)
    execution_context.ensure_provider_context("azure")
    azure_costs = calculate_azure_costs(params, pricing)
    execution_context.ensure_provider_context("gcp")
    gcp_costs = calculate_gcp_costs(params, pricing)
    
    derived = _calculate_derived_params(params)
    
    provider_costs = {
        "AWS": aws_costs,
        "Azure": azure_costs,
        "GCP": gcp_costs,
    }

    for provider in ("aws", "azure", "gcp"):
        execution_context.ensure_formula_ref(
            "transfer_tier_cost",
            provider=provider,
            field="transfer.egress_gb",
        )

    layer_options = {
        layer_key: _supported_provider_options(provider_costs, layer_key)
        for layer_key, _ in LAYER_ORDER
    }

    def resolve_glue_cost(provider, invocations):
        label = {
            "aws": "AWS",
            "azure": "Azure",
            "gcp": "GCP",
        }[provider.value]
        return Decimal(
            str(_calculate_glue_cost(float(invocations), pricing, label))
        )

    evaluation_set = evaluate_complete_paths(
        layer_options=layer_options,
        derived=derived,
        pricing=pricing,
        pricing_catalog_context=pricing_catalog_context,
        pricing_registry=pricing_registry,
        glue_cost_resolver=resolve_glue_cost,
    )
    snapshot_references = tuple(
        f"pricing_catalog:{pricing_catalog_context.catalogs[provider].snapshot_id}"
        for provider in ("aws", "azure", "gcp")
    )
    candidates = []
    evaluations_by_id = {}
    for evaluation in evaluation_set.evaluations:
        evaluations_by_id[evaluation.candidate_id] = evaluation
        metric_result = cost_metric_provider.compute(
            OptimizationMetricContext(
                candidate_id=evaluation.candidate_id,
                metric_inputs={"cost": float(evaluation.total_cost)},
                evidence_references=(
                    pricing_registry_reference,
                    *snapshot_references,
                ),
                metadata={
                    assignment.layer_key: assignment.provider.value
                    for assignment in evaluation.assignments
                },
            )
        )
        candidates.append(
            OptimizationCandidate(
                candidate_id=evaluation.candidate_id,
                dimensions={
                    assignment.layer_key: assignment.provider.value
                    for assignment in evaluation.assignments
                },
                metrics={"cost": metric_result},
            )
        )
    best_candidate = scoring_strategy.select_best(candidates)
    winner = evaluations_by_id[best_candidate.candidate_id]

    provider_labels = {
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "GCP",
    }
    selected = {
        assignment.layer_key: provider_labels[assignment.provider.value]
        for assignment in winner.assignments
    }
    result = {
        "L1": selected["L1"],
        "L2": selected["L2"],
        "L3": {
            "Hot": selected["L3_hot"],
            "Cool": selected["L3_cool"],
            "Archive": selected["L3_archive"],
        },
        "L4": selected["L4"],
        "L5": selected["L5"],
    }
    transfer_costs = {
        charge.route.segment_id: float(charge.total_cost)
        for charge in winner.transfer_charges
        if charge.route.route_class
        == TransferRouteClass.CROSS_PROVIDER_PUBLIC_INTERNET
    }
    cheapest_path = [
        f"{assignment.layer_key}_{provider_labels[assignment.provider.value]}"
        for assignment in winner.assignments
    ]
    
    result_payload = {
        "optimization_profile_id": optimization_profile.profile_id,
        "calculation_strategy_id": execution_context.calculation_strategy_id,
        "result_schema_version": optimization_profile.result_schema_version,
        "trace_schema_version": TRACE_SCHEMA_VERSION,
        "optimizationProfile": optimization_metadata,
        "calculationStrategy": execution_context.to_result_metadata(),
        "evidenceReferences": {
            "pricing_registry": pricing_registry_reference,
            "pricing_evidence_contract": "pricing-evidence.v1",
            "intent_group_ids": list(optimization_metadata.get("intent_group_ids") or []),
            "calculation_strategy": (
                f"calculation_strategy:{execution_context.calculation_strategy_id}"
            ),
            "formula_set": f"formula_set:{execution_context.formula_set_id}",
            "workload_contract": (
                f"workload_contract:{execution_context.workload_contract_id}"
            ),
            "pricing_contract_group": (
                f"pricing_contract_group:{execution_context.pricing_contract_group_id}"
            ),
        },
        "calculationResult": result,
        "awsCosts": aws_costs,
        "azureCosts": azure_costs,
        "gcpCosts": gcp_costs,
        "providerPricingContexts": {
            "awsTwinMaker": aws_costs.get("providerPricingContext"),
        },
        "transferCosts": transfer_costs,
        "transferPricingContext": build_transfer_pricing_context(winner),
        "optimizationDiagnostics": build_optimization_diagnostics(
            evaluation_set,
            winner,
        ),
        "cheapestPath": cheapest_path,
        "totalCost": round(float(winner.total_cost), 2),
    }
    result_payload["resolvedDeploymentSpecification"] = (
        build_resolved_deployment_specification(
            calculation_run_id=str(params.get("calculationRunId") or ""),
            selected_providers=selected,
            provider_costs=provider_costs,
            glue_selections={
                "aws": _aws_calc.glue_deployment_selection(),
                "azure": _azure_calc.glue_deployment_selection(),
                "gcp": _gcp_calc.glue_deployment_selection(),
            },
            optimization_metadata=optimization_metadata,
            execution_context=execution_context,
            pricing_catalog_context=pricing_catalog_context,
        )
    )
    result_payload["intentTrace"] = build_intent_result_trace(
        params=params,
        derived=derived,
        calculation_result=result,
        provider_costs={
            "aws": aws_costs,
            "azure": azure_costs,
            "gcp": gcp_costs,
        },
        transfer_costs=transfer_costs,
        optimization_metadata=optimization_metadata,
        pricing_registry_reference=pricing_registry_reference,
    )
    result_payload["resultTraceSchemaVersion"] = STRATEGY_TRACE_SCHEMA_VERSION
    result_payload["resultTrace"] = build_strategy_result_trace(
        execution_context=execution_context,
        pricing_registry_service=registry_service,
        params=params,
        derived_params=derived,
        result_payload=result_payload,
    )
    return apply_result_currency(
        result_payload,
        str(params.get("currency") or "USD"),
    )
