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

from typing import Dict, Any, Optional
from dataclasses import dataclass
import math

from backend.calculation_v2.layers import (
    AWSLayerCalculators,
    AzureLayerCalculators,
    GCPLayerCalculators,
)
from backend.config_loader import load_combined_pricing
from backend.logger import logger


# =============================================================================
# Calculator Instances
# =============================================================================

_aws_calc = AWSLayerCalculators()
_azure_calc = AzureLayerCalculators()
_gcp_calc = GCPLayerCalculators()


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
    
    return {
        "total_messages_per_month": total_messages_per_month,
        "data_size_per_month_gb": data_size_per_month_gb,
        "hot_storage_gb": hot_storage_gb,
        "cool_storage_gb": cool_storage_gb,
        "archive_storage_gb": archive_storage_gb,
        "queries_per_month": queries_per_month,
        "num_devices": num_devices,
        "msg_size_kb": msg_size_kb,
        "hot_duration": hot_duration,
        "cool_duration": cool_duration,
        "archive_duration": archive_duration,
    }


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
        pricing=pricing
    )
    
    # L5: Visualization
    l5 = _aws_calc.calculate_l5_cost(
        num_editors=params.get("amountOfActiveEditors", 0),
        num_viewers=params.get("amountOfActiveViewers", 0),
        pricing=pricing
    )
    
    return {
        "L1": {"cost": l1.total_cost, "dataSizeInGB": l1.data_size_gb, "components": l1.components},
        "L2": {"cost": l2.total_cost, "dataSizeInGB": derived["data_size_per_month_gb"], "components": l2.components},
        "L3_hot": {"cost": l3_hot.total_cost, "dataSizeInGB": derived["hot_storage_gb"], "components": l3_hot.components},
        "L3_cool": {"cost": l3_cool.total_cost, "dataSizeInGB": derived["cool_storage_gb"], "components": l3_cool.components},
        "L3_archive": {"cost": l3_archive.total_cost, "dataSizeInGB": derived["archive_storage_gb"], "components": l3_archive.components},
        "L4": {"cost": l4.total_cost, "components": l4.components},
        "L5": {"cost": l5.total_cost, "components": l5.components},
        "totalMessagesPerMonth": derived["total_messages_per_month"],
    }


def calculate_azure_costs(params: Dict[str, Any], pricing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate all Azure layer costs.
    """
    derived = _calculate_derived_params(params)
    
    # L1: Data Acquisition
    l1 = _azure_calc.calculate_l1_cost(
        messages_per_month=derived["total_messages_per_month"],
        pricing=pricing
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
        operations_per_month=derived["total_messages_per_month"],
        queries_per_month=derived["queries_per_month"],
        messages_per_month=derived["total_messages_per_month"],
        pricing=pricing
    )
    
    # L5: Visualization
    l5 = _azure_calc.calculate_l5_cost(
        num_editors=params.get("amountOfActiveEditors", 0),
        num_viewers=params.get("amountOfActiveViewers", 0),
        pricing=pricing
    )
    
    return {
        "L1": {"cost": l1.total_cost, "dataSizeInGB": derived["data_size_per_month_gb"], "components": l1.components},
        "L2": {"cost": l2.total_cost, "dataSizeInGB": derived["data_size_per_month_gb"], "components": l2.components},
        "L3_hot": {"cost": l3_hot.total_cost, "dataSizeInGB": derived["hot_storage_gb"], "components": l3_hot.components},
        "L3_cool": {"cost": l3_cool.total_cost, "dataSizeInGB": derived["cool_storage_gb"], "components": l3_cool.components},
        "L3_archive": {"cost": l3_archive.total_cost, "dataSizeInGB": derived["archive_storage_gb"], "components": l3_archive.components},
        "L4": {"cost": l4.total_cost, "components": l4.components},
        "L5": {"cost": l5.total_cost, "components": l5.components},
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
        pricing=pricing
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
        "L1": {"cost": l1.total_cost, "dataSizeInGB": derived["data_size_per_month_gb"], "components": l1.components},
        "L2": {"cost": l2.total_cost, "dataSizeInGB": derived["data_size_per_month_gb"], "components": l2.components},
        "L3_hot": {"cost": l3_hot.total_cost, "dataSizeInGB": derived["hot_storage_gb"], "components": l3_hot.components},
        "L3_cool": {"cost": l3_cool.total_cost, "dataSizeInGB": derived["cool_storage_gb"], "components": l3_cool.components},
        "L3_archive": {"cost": l3_archive.total_cost, "dataSizeInGB": derived["archive_storage_gb"], "components": l3_archive.components},
        "L4": {"cost": l4.total_cost, "components": l4.components},
        "L5": {"cost": l5.total_cost, "components": l5.components},
        "totalMessagesPerMonth": derived["total_messages_per_month"],
    }


# =============================================================================
# Cross-Cloud Transfer Costs
# =============================================================================

def _calculate_egress_cost(data_gb: float, pricing: Dict[str, Any], source_provider: str) -> float:
    """
    Calculate egress cost for data leaving a provider.
    
    Standard egress rates (simplified):
    - AWS: ~$0.09/GB
    - Azure: ~$0.087/GB
    - GCP: ~$0.12/GB
    """
    if source_provider == "AWS":
        price = pricing.get("aws", {}).get("egress", {}).get("pricePerGB", 0.09)
    elif source_provider == "Azure":
        price = pricing.get("azure", {}).get("egress", {}).get("pricePerGB", 0.087)
    elif source_provider == "GCP":
        price = pricing.get("gcp", {}).get("egress", {}).get("pricePerGB", 0.12)
    else:
        price = 0.10  # Default
    
    return data_gb * price


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
    pricing: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Orchestrate cost calculation and find the cheapest path across providers.
    
    This function:
    1. Calculates costs for each provider (AWS, Azure, GCP)
    2. For each layer, determines the cheapest provider
    3. Accounts for cross-cloud transfer costs
    4. Returns the optimal path and all cost breakdowns
    
    Args:
        params: Input parameters from the API
        pricing: Optional pricing data (loaded if not provided)
        
    Returns:
        Dictionary with:
        - awsCosts: Full cost breakdown for AWS
        - azureCosts: Full cost breakdown for Azure  
        - gcpCosts: Full cost breakdown for GCP
        - calculationResult: Optimal provider for each layer
        - cheapestPath: List of layer-provider combinations
        - totalCost: Total cost of the optimal path
    """
    # Load pricing if not provided
    if pricing is None:
        pricing = load_combined_pricing()
    
    # Calculate costs for each provider
    aws_costs = calculate_aws_costs(params, pricing)
    azure_costs = calculate_azure_costs(params, pricing)
    gcp_costs = calculate_gcp_costs(params, pricing)
    
    derived = _calculate_derived_params(params)
    
    # GCP self-hosted options are disabled by default (not implemented)
    allow_gcp_l4 = params.get("allowGcpSelfHostedL4", False)
    allow_gcp_l5 = params.get("allowGcpSelfHostedL5", False)
    
    # Determine cheapest for each layer
    def get_cheapest(layer: str, include_gcp: bool = True) -> tuple:
        """Return (provider, cost) for cheapest option at this layer."""
        options = [
            ("AWS", aws_costs[layer]["cost"]),
            ("Azure", azure_costs[layer]["cost"]),
        ]
        if include_gcp:
            options.append(("GCP", gcp_costs[layer]["cost"]))
        
        return min(options, key=lambda x: x[1])
    
    # Find cheapest path
    result = {}
    
    # L1
    l1_provider, l1_cost = get_cheapest("L1")
    result["L1"] = l1_provider
    
    # L2
    l2_provider, l2_cost = get_cheapest("L2")
    result["L2"] = l2_provider
    
    # L3 (hot, cool, archive)
    l3_hot_provider, l3_hot_cost = get_cheapest("L3_hot")
    l3_cool_provider, l3_cool_cost = get_cheapest("L3_cool")
    l3_archive_provider, l3_archive_cost = get_cheapest("L3_archive")
    result["L3"] = {
        "Hot": l3_hot_provider,
        "Cool": l3_cool_provider,
        "Archive": l3_archive_provider
    }
    
    # L4
    l4_provider, l4_cost = get_cheapest("L4", include_gcp=allow_gcp_l4)
    result["L4"] = l4_provider
    
    # L5
    l5_provider, l5_cost = get_cheapest("L5", include_gcp=allow_gcp_l5)
    result["L5"] = l5_provider
    
    # Calculate transfer costs for cross-cloud transitions
    transfer_costs = {}
    
    # L1 → L2 transfer
    if l1_provider != l2_provider:
        egress = _calculate_egress_cost(derived["data_size_per_month_gb"], pricing, l1_provider)
        glue = _calculate_glue_cost(derived["total_messages_per_month"], pricing, l2_provider)
        transfer_costs["L1_to_L2"] = egress + glue
    
    # L2 → L3_hot transfer
    if l2_provider != l3_hot_provider:
        egress = _calculate_egress_cost(derived["data_size_per_month_gb"], pricing, l2_provider)
        glue = _calculate_glue_cost(derived["total_messages_per_month"], pricing, l3_hot_provider)
        transfer_costs["L2_to_L3_hot"] = egress + glue
    
    # L3_hot → L3_cool transfer
    if l3_hot_provider != l3_cool_provider:
        egress = _calculate_egress_cost(derived["hot_storage_gb"], pricing, l3_hot_provider)
        glue = _calculate_glue_cost(derived["total_messages_per_month"], pricing, l3_cool_provider)
        transfer_costs["L3_hot_to_L3_cool"] = egress + glue
    
    # L3_cool → L3_archive transfer
    if l3_cool_provider != l3_archive_provider:
        egress = _calculate_egress_cost(derived["cool_storage_gb"], pricing, l3_cool_provider)
        glue = _calculate_glue_cost(derived["total_messages_per_month"], pricing, l3_archive_provider)
        transfer_costs["L3_cool_to_L3_archive"] = egress + glue
    
    # L3_hot → L4 transfer (Hot Reader for Digital Twin queries)
    if l3_hot_provider != l4_provider:
        # Queries from L4 go through Hot Reader Function URL
        egress = _calculate_egress_cost(derived["queries_per_month"] * derived["msg_size_kb"] / (1024 * 1024), pricing, l3_hot_provider)
        glue = _calculate_glue_cost(derived["queries_per_month"], pricing, l4_provider)
        transfer_costs["L3_hot_to_L4"] = egress + glue
    
    # Calculate total cost
    total_cost = (
        l1_cost + l2_cost +
        l3_hot_cost + l3_cool_cost + l3_archive_cost +
        l4_cost + l5_cost +
        sum(transfer_costs.values())
    )
    
    # Build cheapest path list
    cheapest_path = [
        f"L1_{l1_provider}",
        f"L2_{l2_provider}",
        f"L3_hot_{l3_hot_provider}",
        f"L3_cool_{l3_cool_provider}",
        f"L3_archive_{l3_archive_provider}",
        f"L4_{l4_provider}",
        f"L5_{l5_provider}",
    ]
    
    return {
        "calculationResult": result,
        "awsCosts": aws_costs,
        "azureCosts": azure_costs,
        "gcpCosts": gcp_costs,
        "transferCosts": transfer_costs,
        "cheapestPath": cheapest_path,
        "totalCost": round(total_cost, 2),
    }
