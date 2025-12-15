"""
AWS Cost Calculation Module
============================
Calculates costs for AWS services (IoT Core, Lambda, DynamoDB, S3, TwinMaker, Grafana).

HARDCODED ASSUMPTIONS (consistent across all providers):
  - Lambda/Functions execution duration: 100ms
  - Lambda/Functions memory allocation: 128 MB
  - Hours per month: 730 (industry standard)

These assumptions match the actual deployer Lambda configurations (MemorySize=128, Timeout=3s).
Using consistent values across AWS/Azure/GCP ensures fair cost comparison.

Formula documentation: docs/docs-formulas.html
"""

import math
from typing import Dict, Any

from backend.calculation.base import CalculationParams, LayerResult
from backend.calculation.builders import LayerResultBuilder


def _build_layer_result(
    provider: str,
    cost: float,
    data_size: float = None,
    messages: float = None,
    **components
) -> Dict[str, Any]:
    """
    Helper function to build LayerResult using Builder pattern.
    
    This provides a clean integration point for the Builder pattern
    while maintaining backward compatibility with existing code.
    
    Args:
        provider: Provider name (e.g., "AWS")
        cost: Total monthly cost
        data_size: Optional data size in GB
        messages: Optional message count
        **components: Additional cost breakdown components
        
    Returns:
        LayerResult dictionary
    """
    builder = LayerResultBuilder(provider).set_cost(cost)
    
    if data_size is not None:
        builder.set_data_size(data_size)
    if messages is not None:
        builder.set_messages(messages)
    
    for name, value in components.items():
        builder.add_component(name, value)
    
    if components:
        builder.include_components()
    
    return builder.build()


# =============================================================================
# AWSCalculator - Strategy Pattern Implementation
# =============================================================================

class AWSCalculator:
    """
    AWS cost calculator implementing the CloudProviderCalculator Protocol.
    
    This class wraps the existing standalone calculation functions,
    providing a unified interface for the calculation engine.
    
    Architecture Note (Current State)
    ----------------------------------
    Currently, this class DELEGATES to standalone functions:
    
        def calculate_data_acquisition(self, params, pricing):
            return calculate_aws_cost_data_acquisition(...)  # Standalone function
    
    This approach was chosen because:
    - The standalone functions contain proven, tested formula logic
    - Existing formula tests (test_formulas_aws.py) directly test these functions
    - Minimal refactoring risk - no formula logic changes
    
    Future Work: Full Encapsulation
    ---------------------------------
    To achieve "true" OOP Strategy Pattern, the calculator class methods should
    contain the formula logic directly instead of delegating. This would:
    
    Pros:
        - Single source of truth for AWS calculations
        - True encapsulation of provider logic
        - Cleaner architecture without wrapper layer
        
    Cons:
        - Requires moving ~15 functions' logic into class methods
        - Formula tests would need to test class methods instead
        - Higher refactoring effort
        
    To implement this change:
        1. Move the body of each standalone function into its corresponding
           class method (e.g., calculate_aws_cost_data_acquisition -> 
           AWSCalculator.calculate_data_acquisition)
        2. Update test_formulas_aws.py to instantiate AWSCalculator and
           test class methods
        3. Remove the now-unused standalone functions
        4. Repeat for AzureCalculator and GCPCalculator
    """
    
    name: str = "aws"
    
    def calculate_data_acquisition(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """Calculate AWS IoT Core ingestion costs."""
        return calculate_aws_cost_data_acquisition(
            params["numberOfDevices"],
            params["deviceSendingIntervalInMinutes"],
            params["averageSizeOfMessageInKb"],
            pricing
        )
    
    def calculate_data_processing(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """Calculate AWS Lambda processing costs."""
        return calculate_aws_cost_data_processing(
            params["numberOfDevices"],
            params["deviceSendingIntervalInMinutes"],
            params["averageSizeOfMessageInKb"],
            pricing,
            use_event_checking=params.get("useEventChecking", False),
            trigger_notification_workflow=params.get("triggerNotificationWorkflow", False),
            return_feedback_to_device=params.get("returnFeedbackToDevice", False),
            integrate_error_handling=params.get("integrateErrorHandling", False),
            orchestration_actions_per_message=params.get("orchestrationActionsPerMessage", 3),
            events_per_message=params.get("eventsPerMessage", 1)
        )
    
    def calculate_storage_hot(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any],
        data_size_in_gb: float,
        total_messages_per_month: float
    ) -> LayerResult:
        """Calculate AWS DynamoDB hot storage costs."""
        return calculate_dynamodb_cost(
            data_size_in_gb,
            total_messages_per_month,
            params["averageSizeOfMessageInKb"],
            params["hotStorageDurationInMonths"],
            pricing
        )
    
    def calculate_storage_cool(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any],
        data_size_in_gb: float
    ) -> LayerResult:
        """Calculate AWS S3 Infrequent Access cool storage costs."""
        return calculate_s3_infrequent_access_cost(
            data_size_in_gb,
            params["coolStorageDurationInMonths"],
            pricing
        )
    
    def calculate_storage_archive(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any],
        data_size_in_gb: float
    ) -> LayerResult:
        """Calculate AWS S3 Glacier Deep Archive storage costs."""
        return calculate_s3_glacier_deep_archive_cost(
            data_size_in_gb,
            params["archiveStorageDurationInMonths"],
            pricing
        )
    
    def calculate_twin_management(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """Calculate AWS IoT TwinMaker costs."""
        return calculate_aws_iot_twin_maker_cost(
            params["entityCount"],
            params["numberOfDevices"],
            params["deviceSendingIntervalInMinutes"],
            params["dashboardRefreshesPerHour"],
            params["dashboardActiveHoursPerDay"],
            params["average3DModelSizeInMB"],
            pricing
        )
    
    def calculate_visualization(
        self,
        params: CalculationParams,
        pricing: Dict[str, Any]
    ) -> LayerResult:
        """Calculate Amazon Managed Grafana costs."""
        return calculate_amazon_managed_grafana_cost(
            params["amountOfActiveEditors"],
            params["amountOfActiveViewers"],
            pricing
        )
    
    # -------------------------------------------------------------------------
    # Cross-Cloud Glue Functions
    # -------------------------------------------------------------------------
    
    def calculate_connector_function_cost(
        self,
        number_of_messages: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate AWS Lambda connector function cost."""
        return calculate_aws_connector_function_cost(number_of_messages, pricing)
    
    def calculate_ingestion_function_cost(
        self,
        number_of_messages: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate AWS Lambda ingestion function cost."""
        return calculate_aws_ingestion_function_cost(number_of_messages, pricing)
    
    def calculate_reader_function_cost(
        self,
        number_of_requests: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate AWS Lambda reader function cost."""
        return calculate_aws_reader_function_cost(number_of_requests, pricing)
    
    def calculate_api_gateway_cost(
        self,
        number_of_requests: float,
        pricing: Dict[str, Any]
    ) -> float:
        """Calculate AWS API Gateway cost."""
        return calculate_aws_api_gateway_cost(number_of_requests, pricing)


# =============================================================================
# Standalone Functions (Original Implementation)
# =============================================================================

# LAYER 1 - Data Acquisition
# Service: AWS IoT Core
# Formula: CM (Message-Based) with tiered pricing

def calculate_aws_cost_data_acquisition(
    number_of_devices,
    device_sending_interval_in_minutes,
    average_size_of_message_in_kb,
    pricing
):
    layer_pricing = pricing["aws"]["iotCore"]
    pricing_tiers = layer_pricing["pricing_tiers"]
    
    price_tier1 = pricing_tiers.get("tier1", {}).get("price", 0)
    price_tier2 = pricing_tiers.get("tier2", {}).get("price", 0)
    price_tier3 = pricing_tiers.get("tier3", {}).get("price", 0)
    
    tier1_limit = pricing_tiers.get("tier1", {}).get("limit", 0)
    tier2_limit = pricing_tiers.get("tier2", {}).get("limit", 0)

    # Formula: Total Messages = Devices * (60 / Interval) * 730 hours
    # Using 730 hours/month (industry standard) for consistency with L2 calculations.
    # Message Size Adjustment: Messages are billed in 5KB increments (AWS IoT Core).
    total_messages_per_month = math.ceil(
        number_of_devices * (1.0 / device_sending_interval_in_minutes) * 60 * 730
    )
    
    data_size_in_gb = (total_messages_per_month * average_size_of_message_in_kb) / (1024 * 1024)

    total_messages_per_month_aws = total_messages_per_month
    if average_size_of_message_in_kb > 5:
        total_messages_per_month_aws = total_messages_per_month * math.ceil(average_size_of_message_in_kb / 5.0)

    number_of_rules_triggered = total_messages_per_month_aws
    remaining_messages = total_messages_per_month_aws

    monthly_cost = (number_of_devices * layer_pricing["pricePerDeviceAndMonth"]) + \
                   (2 * number_of_rules_triggered * layer_pricing["priceRulesTriggered"])

    # Tiered Pricing
    if remaining_messages > tier1_limit:
        monthly_cost += tier1_limit * price_tier1
        remaining_messages -= tier1_limit
    else:
        monthly_cost += remaining_messages * price_tier1
        return _build_layer_result(
            provider="AWS",
            cost=monthly_cost,
            messages=total_messages_per_month,
            data_size=math.ceil(data_size_in_gb)
        )

    if remaining_messages > (tier2_limit - tier1_limit):
        monthly_cost += (tier2_limit - tier1_limit) * price_tier2
        remaining_messages -= (tier2_limit - tier1_limit)
    else:
        monthly_cost += remaining_messages * price_tier2
        return _build_layer_result(
            provider="AWS",
            cost=monthly_cost,
            messages=total_messages_per_month,
            data_size=math.ceil(data_size_in_gb)
        )

    monthly_cost += remaining_messages * price_tier3

    return _build_layer_result(
        provider="AWS",
        cost=monthly_cost,
        messages=total_messages_per_month,
        data_size=math.ceil(data_size_in_gb)
    )

# LAYER 2 - Data Processing
# Calculates request cost and compute duration cost using AWS Lambda pricing (see docs/docs-formulas.html)

def calculate_aws_cost_data_processing(
    number_of_devices,
    device_sending_interval_in_minutes,
    average_size_of_message_in_kb,
    pricing,
    use_event_checking=False,
    trigger_notification_workflow=False,
    return_feedback_to_device=False,
    integrate_error_handling=False,
    orchestration_actions_per_message=3,
    events_per_message=1
):
    # Hardcoded assumptions - same across all providers for fair comparison.
    # These values match the deployer's Lambda configuration (MemorySize=128).
    execution_duration_in_ms = 100  # Conservative estimate for simple data processing
    allocated_memory_in_gb = 128.0 / 1024.0  # 128 MB in GB
    layer2_pricing = pricing["aws"]["lambda"]

    # Formula: Executions = Devices * (60 / Interval) * 730 hours
    # Duration Cost: (Total Compute Seconds * Memory in GB - Free Tier) * Duration Price
    # Request Cost: (Total Requests - Free Tier) * Request Price
    executions_per_month = number_of_devices * (60.0 / device_sending_interval_in_minutes) * 730

    data_size_in_gb = (executions_per_month * average_size_of_message_in_kb) / (1024 * 1024)

    request_cost = 0
    if executions_per_month > layer2_pricing["freeRequests"]:
        request_cost = (executions_per_month - layer2_pricing["freeRequests"]) * layer2_pricing["requestPrice"]

    total_compute_seconds = executions_per_month * execution_duration_in_ms * 0.001

    duration_cost = max(
        (total_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"],
        0
    ) * layer2_pricing["durationPrice"]

    total_monthly_cost = request_cost + duration_cost

    # Supporter Services Costs
    event_checker_cost = 0
    step_functions_cost = 0
    feedback_loop_cost = 0
    error_handling_cost = 0

    # 1. Event Checker (Lambda)
    if use_event_checking:
        # Assumes 1 check per message
        # Reuse Lambda pricing logic for simplicity or define specific pricing if different
        # Here we assume similar execution profile to data processing
        event_checker_compute_seconds = executions_per_month * execution_duration_in_ms * 0.001
        event_checker_cost = max(
            (event_checker_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"], 0
        ) * layer2_pricing["durationPrice"]
        
        if executions_per_month > layer2_pricing["freeRequests"]:
             event_checker_cost += (executions_per_month - layer2_pricing["freeRequests"]) * layer2_pricing["requestPrice"]

    # 2. Orchestration (Step Functions)
    if use_event_checking and trigger_notification_workflow:
        step_functions_price = pricing["aws"]["stepFunctions"]["pricePerStateTransition"]
        # Standard Step Functions: charged per state transition
        total_transitions = executions_per_month * orchestration_actions_per_message
        step_functions_cost = total_transitions * step_functions_price

    # 3. Feedback Loop (IoT Core Publish + Lambda)
    if use_event_checking and return_feedback_to_device:
        # IoT Core Publish (C2D)
        iot_pricing = pricing["aws"]["iotCore"]
        feedback_messages = executions_per_month # 1 feedback per message processed
        feedback_loop_cost += (feedback_messages / 1000000) * 1.00 # Approx $1.00 per million messages (simplified)
        
        # Feedback Lambda
        feedback_compute_seconds = feedback_messages * execution_duration_in_ms * 0.001
        feedback_lambda_cost = max(
            (feedback_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"], 0
        ) * layer2_pricing["durationPrice"]
        if feedback_messages > layer2_pricing["freeRequests"]:
            feedback_lambda_cost += (feedback_messages - layer2_pricing["freeRequests"]) * layer2_pricing["requestPrice"]
            
        feedback_loop_cost += feedback_lambda_cost

    # 4. Error Handling (EventBridge + Lambda + DynamoDB Write)
    if integrate_error_handling:
        # EventBridge (Error Bus)
        event_bridge_price = pricing["aws"]["eventBridge"]["pricePerMillionEvents"]
        # Assume 1% error rate for estimation? Or 1 event per message if tracking all?
        # Let's assume 1 event per message for "Error Checking/Routing" overhead if enabled
        total_events = executions_per_month * events_per_message
        error_handling_cost += (total_events / 1000000) * event_bridge_price

        # Error Reporter Lambda
        reporter_compute_seconds = total_events * execution_duration_in_ms * 0.001
        reporter_cost = max(
            (reporter_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"], 0
        ) * layer2_pricing["durationPrice"]
        if total_events > layer2_pricing["freeRequests"]:
            reporter_cost += (total_events - layer2_pricing["freeRequests"]) * layer2_pricing["requestPrice"]
        error_handling_cost += reporter_cost

        # DynamoDB Error Table (Write)
        # Assume 1KB error log
        write_units = total_events # 1 WCU per event (simplified)
        write_price = pricing["aws"]["dynamoDB"]["writePrice"]
        error_handling_cost += write_units * write_price

    total_monthly_cost = request_cost + duration_cost + event_checker_cost + step_functions_cost + feedback_loop_cost + error_handling_cost

    return _build_layer_result(
        provider="AWS",
        cost=total_monthly_cost,
        data_size=data_size_in_gb,
        messages=executions_per_month
    )

def calculate_aws_api_gateway_cost(number_of_requests, pricing):
    # API Gateway Pricing: $1.00 per million requests (simplified tier)
    price_per_million = pricing["aws"]["apiGateway"]["pricePerMillionCalls"]
    return (number_of_requests / 1000000) * price_per_million

# Cross-Cloud Glue Functions
# These use standard Lambda pricing (100ms, 128MB)

def _calculate_lambda_cost(executions, pricing):
    execution_duration_in_ms = 100
    allocated_memory_in_gb = 128.0 / 1024.0
    layer2_pricing = pricing["aws"]["lambda"]
    
    compute_seconds = executions * execution_duration_in_ms * 0.001
    duration_cost = max(
        (compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"], 0
    ) * layer2_pricing["durationPrice"]
    
    request_cost = 0
    if executions > layer2_pricing["freeRequests"]:
        request_cost = (executions - layer2_pricing["freeRequests"]) * layer2_pricing["requestPrice"]
        
    return duration_cost + request_cost

def calculate_aws_connector_function_cost(number_of_messages, pricing):
    return _calculate_lambda_cost(number_of_messages, pricing)

def calculate_aws_ingestion_function_cost(number_of_messages, pricing):
    return _calculate_lambda_cost(number_of_messages, pricing)

def calculate_aws_writer_function_cost(number_of_messages, pricing):
    return _calculate_lambda_cost(number_of_messages, pricing)

def calculate_aws_reader_function_cost(number_of_requests, pricing):
    return _calculate_lambda_cost(number_of_requests, pricing)

# LAYER 3 - Data Storage
# Calculates DynamoDB storage, write, and read costs based on pricing tiers (see docs/docs-formulas.html)

def calculate_dynamodb_cost(
    data_size_in_gb,
    total_messages_per_month,
    average_size_of_message_in_kb,
    storage_duration_in_months,
    pricing
):
    # Formula: Storage Cost = (Data Size * Duration) * Storage Price
    # Write Cost: (Total Messages * Message Size) * Write Price
    # Read Cost: (Total Messages / 2) * Read Price
    # 
    # Read Ratio Assumption: 1 read per 2 writes (0.5x)
    # Rationale: In a Digital Twin architecture, most data is written by IoT devices
    # and read less frequently by dashboards. Dashboard queries are batched/aggregated.
    #
    # Storage Buffer (+0.5 months): Accounts for mid-month data accumulation.
    # As data grows throughout the month, the average storage used is approximately
    # half the final amount, hence we add 0.5 months to prorate the storage cost.
    storage_needed_for_duration = data_size_in_gb * (storage_duration_in_months + 0.5)

    write_units_needed = total_messages_per_month * average_size_of_message_in_kb
    read_units_needed = total_messages_per_month / 2.0  # 1 read per 2 writes

    write_price = pricing["aws"]["dynamoDB"]["writePrice"]
    read_price = pricing["aws"]["dynamoDB"]["readPrice"]
    storage_price = pricing["aws"]["dynamoDB"]["storagePrice"]
    free_storage_per_month = pricing["aws"]["dynamoDB"]["freeStorage"]

    total_storage_price = 0
    if storage_needed_for_duration > (free_storage_per_month * storage_duration_in_months):
        total_storage_price = math.ceil(
            (storage_needed_for_duration - (free_storage_per_month * storage_duration_in_months)) * storage_price
        )

    total_monthly_cost = (write_price * write_units_needed) + \
                         (read_price * read_units_needed) + \
                         total_storage_price

    return _build_layer_result(
        provider="AWS",
        cost=total_monthly_cost,
        data_size=data_size_in_gb
    )

def calculate_s3_infrequent_access_cost(
    data_size_in_gb,
    cool_storage_duration_in_months,
    pricing
):
    storage_price = pricing["aws"]["s3InfrequentAccess"]["storagePrice"]
    upfront_price = pricing["aws"]["s3InfrequentAccess"]["upfrontPrice"]
    request_price = pricing["aws"]["s3InfrequentAccess"]["requestPrice"]
    data_retrieval_price = pricing["aws"]["s3InfrequentAccess"]["dataRetrievalPrice"]
    
    # Formula: Storage Cost = Data Size * Duration * Storage Price
    # Request Cost: (Data Size * 1024 / 100) * 2 * Request Price (Assumption: 2 requests per 100MB)
    # Retrieval Cost: (Data Size * Duration * 0.1 + Data Size) * Retrieval Price
    data_retrieval_amount = (data_size_in_gb * cool_storage_duration_in_months * 0.1) + data_size_in_gb

    amount_of_requests_needed = math.ceil((data_size_in_gb * 1024) / 100) * 2

    total_monthly_cost = (storage_price * data_size_in_gb * cool_storage_duration_in_months) + \
                         (upfront_price * data_size_in_gb * cool_storage_duration_in_months) + \
                         (request_price * amount_of_requests_needed) + \
                         (data_retrieval_price * data_retrieval_amount)

    return _build_layer_result(
        provider="AWS",
        cost=total_monthly_cost,
        data_size=data_size_in_gb
    )

def calculate_s3_glacier_deep_archive_cost(
    data_size_in_gb,
    archive_storage_duration_in_months,
    pricing
):
    # Formula: Storage Cost = Data Size * Duration * Storage Price
    # Request Cost: Data Size * 2 * Lifecycle Price
    # Retrieval Cost: 1% of Data Size * Retrieval Price
    storage_needed_for_duration = data_size_in_gb * archive_storage_duration_in_months
    amount_of_requests_needed = data_size_in_gb * 2
    data_retrieval_amount = 0.01 * storage_needed_for_duration

    storage_price = pricing["aws"]["s3GlacierDeepArchive"]["storagePrice"]
    lifecycle_and_write_price = pricing["aws"]["s3GlacierDeepArchive"]["lifecycleAndWritePrice"]
    data_retrieval_price = pricing["aws"]["s3GlacierDeepArchive"]["dataRetrievalPrice"]

    total_monthly_cost = (storage_needed_for_duration * storage_price) + \
                         (amount_of_requests_needed * lifecycle_and_write_price) + \
                         (data_retrieval_amount * data_retrieval_price)

    return _build_layer_result(
        provider="AWS",
        cost=total_monthly_cost,
        data_size=data_size_in_gb
    )

# LAYER 4 - Twin Management
# Calculates Twin Management costs using IoT TwinMaker pricing (see docs/docs-formulas.html)

def calculate_number_of_queries_to_layer4_from_dashboard(
    dashboard_refreshes_per_hour,
    dashboard_active_hours_per_day
):
    days_in_month = 30
    return dashboard_active_hours_per_day * dashboard_refreshes_per_hour * days_in_month

def calculate_aws_iot_twin_maker_cost(
    entity_count,
    number_of_devices,
    device_sending_interval_in_minutes,
    dashboard_refreshes_per_hour,
    dashboard_active_hours_per_day,
    average_3d_model_size_in_mb,
    pricing
):
    # Formula: Entity Cost = Entity Count * Entity Price
    # API Cost: Total Messages * Unified Data Access Price
    # Query Cost: Number of Queries * Query Price
    # Storage Cost: (Entity Count * Average Model Size) * S3 Storage Price
    unified_data_access_api_calls_price = pricing["aws"]["iotTwinMaker"]["unifiedDataAccessAPICallsPrice"]
    entity_price = pricing["aws"]["iotTwinMaker"]["entityPrice"]
    query_price = pricing["aws"]["iotTwinMaker"]["queryPrice"]
    s3_storage_price = pricing["aws"]["s3InfrequentAccess"]["storagePrice"]

    # Use 730 hours/month for consistency across all layers (industry standard)
    total_messages_per_month = math.ceil(
        number_of_devices * (1.0 / device_sending_interval_in_minutes) * 60 * 730
    )

    number_of_queries = calculate_number_of_queries_to_layer4_from_dashboard(
        dashboard_refreshes_per_hour, dashboard_active_hours_per_day
    )

    # Calculate 3D Model Storage Cost
    # Assumption: Each entity has an associated 3D model asset of the given average size
    total_model_storage_gb = (entity_count * average_3d_model_size_in_mb) / 1024.0
    storage_cost = total_model_storage_gb * s3_storage_price

    total_monthly_cost = (entity_count * entity_price) + \
                         (total_messages_per_month * unified_data_access_api_calls_price) + \
                         (number_of_queries * query_price) + \
                         storage_cost
    
    return _build_layer_result(
        provider="AWS",
        cost=total_monthly_cost
    )

# LAYER 5 - Data Visualization
# Service: Amazon Managed Grafana
#
# PRICING MODEL COMPARISON (why different formulas are comparable):
# - AWS Managed Grafana: Per-seat licensing (editors + viewers). No instance cost.
# - Azure Managed Grafana: Per-seat + instance hours. Includes infrastructure.
# - GCP (Self-Hosted): VM cost (e2-medium) + disk. No per-seat fees.
#
# All three represent the actual cost of running Grafana dashboards on each provider.
# The pricing models differ, but outputs are directly comparable monthly costs.

def calculate_amazon_managed_grafana_cost(
    amount_of_active_editors,
    amount_of_active_viewers,
    pricing
):
    """
    Calculate AWS Managed Grafana visualization cost.
    
    AWS uses a pure per-seat model with differentiated editor/viewer pricing.
    No infrastructure costs are charged separately - they're included in seat prices.
    """
    editor_price = pricing["aws"]["awsManagedGrafana"]["editorPrice"]
    viewer_price = pricing["aws"]["awsManagedGrafana"]["viewerPrice"]

    # Formula: Total Cost = (Editors * Editor Price) + (Viewers * Viewer Price)
    total_monthly_cost = (amount_of_active_editors * editor_price) + \
                         (amount_of_active_viewers * viewer_price)

    return _build_layer_result(
        provider="AWS",
        cost=total_monthly_cost
    )
