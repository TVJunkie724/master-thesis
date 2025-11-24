
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
    pricing
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
        request_cost = (executions_per_month - layer2_pricing["freeRequests"]) * layer2_pricing["requestPrice"]

    total_compute_seconds = executions_per_month * execution_duration_in_ms * 0.001

    duration_cost = max(
        (total_compute_seconds * allocated_memory_in_gb) - layer2_pricing["freeComputeTime"],
        0
    ) * layer2_pricing["durationPrice"]

    total_monthly_cost = request_cost + duration_cost

    return {
        "provider": "Azure",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb,
        "totalMessagesPerMonth": executions_per_month
    }

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
