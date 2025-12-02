
import math

# LAYER 1 - Data Acquisition
# This section calculates costs for AWS IoT Core data acquisition.
# Formula details are documented in docs/docs-formulas.html.

def calculate_aws_cost_data_acquisition(
    number_of_devices,
    device_sending_interval_in_minutes,
    average_size_of_message_in_kb,
    pricing
):
    layer_pricing = pricing["aws"]["iotCore"]
    pricing_tiers = layer_pricing["pricing_tiers"]
    
    tier1_limit = pricing_tiers["tier1"]["limit"]
    tier2_limit = pricing_tiers["tier2"]["limit"]
    # tier3_limit = pricing_tiers["tier3"]["limit"] # Infinity

    price_tier1 = pricing_tiers["tier1"]["price"]
    price_tier2 = pricing_tiers["tier2"]["price"]
    price_tier3 = pricing_tiers["tier3"]["price"]

    # Formula: Total Messages = Devices * (60 / Interval) * 24 * 30
    # Message Size Adjustment: Messages are billed in 5KB increments (AWS IoT Core)
    total_messages_per_month = math.ceil(
        number_of_devices * (1.0 / device_sending_interval_in_minutes) * 60 * 24 * 30
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
        return {
            "provider": "AWS",
            "totalMonthlyCost": monthly_cost,
            "totalMessagesPerMonth": total_messages_per_month,
            "dataSizeInGB": math.ceil(data_size_in_gb)
        }

    if remaining_messages > (tier2_limit - tier1_limit):
        monthly_cost += (tier2_limit - tier1_limit) * price_tier2
        remaining_messages -= (tier2_limit - tier1_limit)
    else:
        monthly_cost += remaining_messages * price_tier2
        return {
            "provider": "AWS",
            "totalMonthlyCost": monthly_cost,
            "totalMessagesPerMonth": total_messages_per_month,
            "dataSizeInGB": math.ceil(data_size_in_gb)
        }

    monthly_cost += remaining_messages * price_tier3

    return {
        "provider": "AWS",
        "totalMonthlyCost": monthly_cost,
        "totalMessagesPerMonth": total_messages_per_month,
        "dataSizeInGB": math.ceil(data_size_in_gb)
    }

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
    execution_duration_in_ms = 100
    allocated_memory_in_gb = 128.0 / 1024.0
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

    return {
        "provider": "AWS",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb,
        "totalMessagesPerMonth": executions_per_month
    }

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
    # Read Cost: (Total Messages / 2) * Read Price (Assumption: 1 read per 2 writes)
    storage_needed_for_duration = data_size_in_gb * (storage_duration_in_months + 0.5)

    write_units_needed = total_messages_per_month * average_size_of_message_in_kb
    read_units_needed = total_messages_per_month / 2.0

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

    return {
        "provider": "AWS",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb
    }

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

    return {
        "provider": "AWS",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb
    }

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

    return {
        "provider": "AWS",
        "dataSizeInGB": data_size_in_gb,
        "totalMonthlyCost": total_monthly_cost
    }

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
    pricing
):
    # Formula: Entity Cost = Entity Count * Entity Price
    # API Cost: Total Messages * Unified Data Access Price
    # Query Cost: Number of Queries * Query Price
    unified_data_access_api_calls_price = pricing["aws"]["iotTwinMaker"]["unifiedDataAccessAPICallsPrice"]
    entity_price = pricing["aws"]["iotTwinMaker"]["entityPrice"]
    query_price = pricing["aws"]["iotTwinMaker"]["queryPrice"]

    total_messages_per_month = math.ceil(
        number_of_devices * (1.0 / device_sending_interval_in_minutes) * 60 * 24 * 30
    )

    number_of_queries = calculate_number_of_queries_to_layer4_from_dashboard(
        dashboard_refreshes_per_hour, dashboard_active_hours_per_day
    )

    total_monthly_cost = (entity_count * entity_price) + \
                         (total_messages_per_month * unified_data_access_api_calls_price) + \
                         (number_of_queries * query_price)
    
    return {
        "provider": "AWS",
        "totalMonthlyCost": total_monthly_cost
    }

# LAYER 5 - Data Visualization

def calculate_amazon_managed_grafana_cost(
    amount_of_active_editors,
    amount_of_active_viewers,
    pricing
):
    editor_price = pricing["aws"]["awsManagedGrafana"]["editorPrice"]
    viewer_price = pricing["aws"]["awsManagedGrafana"]["viewerPrice"]

    # Formula: Total Cost = (Editors * Editor Price) + (Viewers * Viewer Price)
    total_monthly_cost = (amount_of_active_editors * editor_price) + \
                         (amount_of_active_viewers * viewer_price)

    return {
        "provider": "AWS",
        "totalMonthlyCost": total_monthly_cost
    }
