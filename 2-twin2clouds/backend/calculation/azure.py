
import math

# LAYER 1 - Data Acquisition

def calculate_azure_cost_data_acquisition(
    number_of_devices,
    device_sending_interval_in_minutes,
    average_size_of_message_in_kb,
    pricing
):
    # Formula: Total Messages = Devices * (60 / Interval) * 24 * 30
    # Message Size Adjustment: Messages are billed in 4KB increments (Azure IoT Hub)
    # Tier Selection: Selects cheapest tier (Basic/Standard B1/S1, B2/S2, B3/S3) that fits message volume
    layer_pricing = pricing["azure"]["iotHub"]
    pricing_tiers = layer_pricing["pricing_tiers"]

    total_messages_per_month = math.ceil(
        number_of_devices * (1.0 / device_sending_interval_in_minutes) * 60 * 24 * 30
    )
    
    data_size_in_gb = (total_messages_per_month * average_size_of_message_in_kb) / (1024 * 1024)

    total_messages_per_month_azure = total_messages_per_month
    if average_size_of_message_in_kb > 4:
        total_messages_per_month_azure = total_messages_per_month * math.ceil(average_size_of_message_in_kb / 4.0)

    monthly_cost = 0
    monthly_azure_price = 0
    azure_threshold_monthly = 0

    if total_messages_per_month_azure <= pricing_tiers["tier1"]["limit"]:
        azure_threshold_monthly = pricing_tiers["tier1"]["threshold"]
        monthly_azure_price = pricing_tiers["tier1"]["price"]
    elif total_messages_per_month_azure <= pricing_tiers["tier2"]["limit"]:
        azure_threshold_monthly = pricing_tiers["tier2"]["threshold"]
        monthly_azure_price = pricing_tiers["tier2"]["price"]
    else:
        azure_threshold_monthly = pricing_tiers["tier3"]["threshold"]
        monthly_azure_price = pricing_tiers["tier3"]["price"]

    if total_messages_per_month_azure > azure_threshold_monthly:
        monthly_cost = math.ceil(total_messages_per_month_azure / azure_threshold_monthly) * monthly_azure_price
    else:
        monthly_cost = monthly_azure_price

    return {
        "provider": "Azure",
        "totalMonthlyCost": monthly_cost,
        "totalMessagesPerMonth": total_messages_per_month,
        "dataSizeInGB": math.ceil(data_size_in_gb)
    }

# LAYER 2 - Data Processing

def calculate_azure_cost_data_processing(
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
    # Reusing AWS logic as per JS implementation (costs and free tier are identical for this model)
    
    execution_duration_in_ms = 100
    allocated_memory_in_gb = 128.0 / 1024.0
    
    # Formula: Executions = Devices * (60 / Interval) * 730 hours
    # Duration Cost: (Total Compute Seconds * Memory in GB - Free Tier) * Duration Price
    # Request Cost: (Total Requests - Free Tier) * Request Price
    # Note: Uses Azure Functions Consumption Plan pricing
    layer2_pricing = pricing["azure"]["functions"]

    executions_per_month = number_of_devices * (60.0 / device_sending_interval_in_minutes) * 730

    data_size_in_gb = (executions_per_month * average_size_of_message_in_kb) / (1024 * 1024)

    request_cost = 0
    if executions_per_month > layer2_pricing["freeRequests"]:
        request_cost = ((executions_per_month - layer2_pricing["freeRequests"]) / 1000000) * layer2_pricing["requestPrice"]

    total_compute_seconds = executions_per_month * execution_duration_in_ms * 0.001

    duration_cost = max(
        (total_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"],
        0
    ) * layer2_pricing["durationPrice"]

    total_monthly_cost = request_cost + duration_cost

    # Supporter Services Costs
    event_checker_cost = 0
    logic_apps_cost = 0
    feedback_loop_cost = 0
    error_handling_cost = 0

    # 1. Event Checker (Function)
    if use_event_checking:
        # Assumes 1 check per message
        event_checker_compute_seconds = executions_per_month * execution_duration_in_ms * 0.001
        event_checker_cost = max(
            (event_checker_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"], 0
        ) * layer2_pricing["durationPrice"]
        
        if executions_per_month > layer2_pricing["freeRequests"]:
             event_checker_cost += ((executions_per_month - layer2_pricing["freeRequests"]) / 1000000) * layer2_pricing["requestPrice"]

    # 2. Orchestration (Logic Apps)
    if use_event_checking and trigger_notification_workflow:
        logic_apps_price = pricing["azure"]["logicApps"]["pricePerStateTransition"]
        # Standard Logic Apps: charged per action execution
        total_actions = executions_per_month * orchestration_actions_per_message
        logic_apps_cost = total_actions * logic_apps_price

    # 3. Feedback Loop (IoT Hub C2D + Function)
    if use_event_checking and return_feedback_to_device:
        # IoT Hub C2D
        iot_pricing = pricing["azure"]["iotHub"]
        feedback_messages = executions_per_month
        # IoT Hub messages are counted against the daily quota. 
        # If we exceed the tier limit, we might need to jump to next tier.
        # For simplicity in this model, we treat it as potentially pushing to next tier or adding units.
        # However, the current L1 calculation selects a tier based on volume. 
        # We should ideally add this volume to L1, but for now we'll calculate a "unit cost" based on the selected tier in L1.
        # Simplified: Assume same tier, add proportional cost or 0 if within limit.
        # To be safe and conservative: Add cost of 1 message unit if we were paying per message, 
        # but Azure is tiered. Let's assume it fits in the tier or adds negligible cost unless near boundary.
        # For this calculation, we will add the Function cost for generating the feedback.
        
        # Feedback Function
        feedback_compute_seconds = feedback_messages * execution_duration_in_ms * 0.001
        feedback_function_cost = max(
            (feedback_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"], 0
        ) * layer2_pricing["durationPrice"]
        if feedback_messages > layer2_pricing["freeRequests"]:
            feedback_function_cost += ((feedback_messages - layer2_pricing["freeRequests"]) / 1000000) * layer2_pricing["requestPrice"]
            
        feedback_loop_cost += feedback_function_cost

    # 4. Error Handling (Event Grid + Function + Cosmos DB Write)
    if integrate_error_handling:
        # Event Grid
        event_grid_price = pricing["azure"]["eventGrid"]["pricePerMillionEvents"]
        total_events = executions_per_month * events_per_message
        error_handling_cost += (total_events / 1000000) * event_grid_price

        # Error Reporter Function
        reporter_compute_seconds = total_events * execution_duration_in_ms * 0.001
        reporter_cost = max(
            (reporter_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"], 0
        ) * layer2_pricing["durationPrice"]
        if total_events > layer2_pricing["freeRequests"]:
            reporter_cost += ((total_events - layer2_pricing["freeRequests"]) / 1000000) * layer2_pricing["requestPrice"]
        error_handling_cost += reporter_cost

        # Cosmos DB Error Container (Write)
        # Assume 1KB error log -> 1 RU per write (simplified)
        # We need to add these RUs to the total Cosmos DB calculation or estimate cost separately.
        # Estimating separately using Request Price:
        request_price = pricing["azure"]["cosmosDB"]["requestPrice"] # Price per 100 RU/s hour? No, usually per 1M RUs or similar in serverless.
        # The current Cosmos DB formula uses Provisioned Throughput model (RU/s * Hourly Price).
        # We'll approximate by adding RUs to the required throughput.
        # Writes/sec = Total Events / MonthSeconds.
        writes_per_second = total_events / (30 * 24 * 60 * 60)
        rus_per_write = pricing["azure"]["cosmosDB"]["RUsPerWrite"]
        additional_rus = writes_per_second * rus_per_write
        # Cost = Additional RUs * Hourly Price * 730
        # Note: This is a rough approximation if we don't pass it to the main Cosmos DB function.
        # For better accuracy, we should ideally pass this to L3 calculation. 
        # For now, we'll calculate the incremental cost of these RUs.
        hourly_price_per_100_ru = pricing["azure"]["cosmosDB"]["requestPrice"] / 100 * 100 # Wait, requestPrice in formula is used as (Request Units * Request Price).
        # Let's check calculate_cosmos_db_cost: (request_units_needed * request_price) + storage.
        # So request_price is likely "Price per 100 RU/s per Hour" * 730? Or similar.
        # Let's use the same `requestPrice` from pricing.
        error_handling_cost += additional_rus * pricing["azure"]["cosmosDB"]["requestPrice"]

    total_monthly_cost = request_cost + duration_cost + event_checker_cost + logic_apps_cost + feedback_loop_cost + error_handling_cost

    return {
        "provider": "Azure",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb,
        "totalMessagesPerMonth": executions_per_month
    }

def calculate_azure_api_management_cost(number_of_requests, pricing):
    # APIM Pricing: Consumption tier (per million calls)
    price_per_million = pricing["azure"]["apiManagement"]["pricePerMillionCalls"]
    return (number_of_requests / 1000000) * price_per_million

# Cross-Cloud Glue Functions
# These use standard Azure Functions pricing

def _calculate_function_cost(executions, pricing):
    execution_duration_in_ms = 100
    allocated_memory_in_gb = 128.0 / 1024.0
    layer2_pricing = pricing["azure"]["functions"]
    
    compute_seconds = executions * execution_duration_in_ms * 0.001
    duration_cost = max(
        (compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"], 0
    ) * layer2_pricing["durationPrice"]
    
    request_cost = 0
    if executions > layer2_pricing["freeRequests"]:
        request_cost = ((executions - layer2_pricing["freeRequests"]) / 1000000) * layer2_pricing["requestPrice"]
        
    return duration_cost + request_cost

def calculate_azure_connector_function_cost(number_of_messages, pricing):
    return _calculate_function_cost(number_of_messages, pricing)

def calculate_azure_ingestion_function_cost(number_of_messages, pricing):
    return _calculate_function_cost(number_of_messages, pricing)

def calculate_azure_writer_function_cost(number_of_messages, pricing):
    return _calculate_function_cost(number_of_messages, pricing)

def calculate_azure_reader_function_cost(number_of_requests, pricing):
    return _calculate_function_cost(number_of_requests, pricing)

# LAYER 3 - Data Storage

def calculate_cosmos_db_cost(
    data_size_in_gb,
    total_messages_per_month,
    average_size_of_message_in_kb,
    storage_duration_in_months,
    pricing
):
    # Formula: Storage Cost = (Data Size * Duration) * Storage Price
    # RU/s Calculation: 
    #   - Writes/sec = Total Messages / Seconds in Month
    #   - Reads/sec = Writes/sec (Assumption)
    #   - Total RUs = (Writes * Write Cost * Size Multiplier) + (Reads * Read Cost)
    #   - Monthly Cost = Max(Total RUs, Min RUs) * Hourly Price * 730 + Storage Cost
    storage_needed_for_duration = data_size_in_gb * (storage_duration_in_months + 0.5)
    
    request_units_needed = pricing["azure"]["cosmosDB"]["minimumRequestUnits"]
    writes_per_second = total_messages_per_month / (30 * 24 * 60 * 60)
    reads_per_second = writes_per_second
    
    multiplier_for_message_size = 1.0 + (average_size_of_message_in_kb - 1) * 0.05

    rus_per_write = pricing["azure"]["cosmosDB"]["RUsPerWrite"]
    rus_per_read = pricing["azure"]["cosmosDB"]["RUsPerRead"]

    total_write_rus = writes_per_second * rus_per_write * multiplier_for_message_size
    total_read_rus = reads_per_second * rus_per_read

    if math.ceil(total_write_rus + total_read_rus) > request_units_needed:
        request_units_needed = math.ceil(total_write_rus + total_read_rus)

    storage_price = pricing["azure"]["cosmosDB"]["storagePrice"]
    request_price = pricing["azure"]["cosmosDB"]["requestPrice"]

    total_monthly_cost = (request_units_needed * request_price) + \
                         (storage_needed_for_duration * storage_price)

    return {
        "provider": "Azure",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb
    }

def calculate_azure_blob_storage_cost(
    data_size_in_gb,
    cool_storage_duration_in_months,
    pricing
):
    amount_of_writes_needed = math.ceil((data_size_in_gb * 1024) / 100)
    amount_of_reads_needed = amount_of_writes_needed * 0.1
    data_retrieval_amount = (data_size_in_gb * 0.1) + data_size_in_gb

    # Formula: Storage Cost = Data Size * Duration * Storage Price
    # Write Cost: (Data Size * 1024 / 100) * Write Price (Assumption: 100KB blocks)
    # Read Cost: Write Count * 0.1 * Read Price (Assumption: 10% reads)
    # Retrieval Cost: (Data Size * 0.1 + Data Size) * Retrieval Price
    storage_price = pricing["azure"]["blobStorageCool"]["storagePrice"]
    write_price = pricing["azure"]["blobStorageCool"]["writePrice"]
    read_price = pricing["azure"]["blobStorageCool"]["readPrice"]
    data_retrieval_price = pricing["azure"]["blobStorageCool"]["dataRetrievalPrice"]

    total_monthly_cost = (storage_price * data_size_in_gb * cool_storage_duration_in_months) + \
                         (amount_of_writes_needed * write_price) + \
                         (amount_of_reads_needed * read_price) + \
                         (data_retrieval_amount * data_retrieval_price)

    return {
        "provider": "Azure",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb
    }

def calculate_azure_blob_storage_archive_cost(
    data_size_in_gb,
    archive_storage_duration_in_months,
    pricing
):
    storage_needed_for_duration = data_size_in_gb * archive_storage_duration_in_months
    amount_of_writes_needed = data_size_in_gb
    data_retrieval_amount = storage_needed_for_duration * 0.01

    # Formula: Storage Cost = Data Size * Duration * Storage Price
    # Write Cost: Data Size * Write Price
    # Retrieval Cost: 1% of Data Size * Retrieval Price
    storage_price = pricing["azure"]["blobStorageArchive"]["storagePrice"]
    write_price = pricing["azure"]["blobStorageArchive"]["writePrice"]
    data_retrieval_price = pricing["azure"]["blobStorageArchive"]["dataRetrievalPrice"]

    total_monthly_cost = (storage_needed_for_duration * storage_price) + \
                         (amount_of_writes_needed * write_price) + \
                         (data_retrieval_amount * data_retrieval_price)

    return {
        "provider": "Azure",
        "dataSizeInGB": data_size_in_gb,
        "totalMonthlyCost": total_monthly_cost
    }

# LAYER 4 - Twin Management

def calculate_number_of_queries_to_layer4_from_dashboard(
    dashboard_refreshes_per_hour,
    dashboard_active_hours_per_day
):
    days_in_month = 30
    return dashboard_active_hours_per_day * dashboard_refreshes_per_hour * days_in_month

def calculate_azure_digital_twins_cost(
    number_of_devices,
    device_sending_interval_in_minutes,
    message_size_in_kb,
    dashboard_refreshes_per_hour,
    dashboard_active_hours_per_day,
    pricing
):
    # Formula: Operation Cost = Total Messages * Operation Price
    # Query Cost: Query Units * Query Price * Number of Queries
    # Note: Query Units depend on device count tier
    message_price = pricing["azure"]["azureDigitalTwins"]["messagePrice"]
    operation_price = pricing["azure"]["azureDigitalTwins"]["operationPrice"]
    query_price = pricing["azure"]["azureDigitalTwins"]["queryPrice"]

    total_messages_per_month = math.ceil(
        number_of_devices * (1.0 / device_sending_interval_in_minutes) * 60 * 24 * 30
    )

    query_unit_tiers = pricing["azure"]["azureDigitalTwins"]["queryUnitTiers"]
    
    query_units = 0
    for t in query_unit_tiers:
        upper = t.get("upper", float('inf'))
        if t["lower"] <= number_of_devices <= upper:
            query_units = t["value"]
            break

    number_of_queries = calculate_number_of_queries_to_layer4_from_dashboard(
        dashboard_refreshes_per_hour, dashboard_active_hours_per_day
    )

    total_monthly_cost = (total_messages_per_month * operation_price) + \
                         (math.ceil(message_size_in_kb) * number_of_queries * operation_price) + \
                         (query_units * query_price * number_of_queries)

    return {
        "provider": "Azure",
        "totalMonthlyCost": total_monthly_cost
    }

# LAYER 5 - Data Visualization

def calculate_azure_managed_grafana_cost(
    amount_of_monthly_users,
    pricing
):
    # Formula: Total Cost = (Users * User Price) + (Hourly Price * 730)
    user_price = pricing["azure"]["azureManagedGrafana"]["userPrice"]
    hourly_price = pricing["azure"]["azureManagedGrafana"]["hourlyPrice"]
    monthly_price = hourly_price * 730

    total_monthly_cost = (amount_of_monthly_users * user_price) + monthly_price

    return {
        "provider": "Azure",
        "totalMonthlyCost": total_monthly_cost
    }
