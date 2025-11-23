
import math

def calculate_gcp_cost_data_acquisition(number_of_devices, device_sending_interval_in_minutes, average_size_of_message_in_kb, pricing):
    """
    Calculate GCP Data Acquisition Cost (Cloud Pub/Sub).
    Pub/Sub is priced by data volume (GB).
    
    Formula: Total Messages = Devices * (60 / Interval) * 24 * 30
    Cost: Messages * Price Per Message (Approximation for volume-based pricing)
    """
    pricing_layer = pricing["gcp"]["iot"]
    
    # Messages per month
    messages_per_month = number_of_devices * (60 / device_sending_interval_in_minutes) * 730
    
    # Data volume in GB
    data_volume_gb = (messages_per_month * average_size_of_message_in_kb) / (1024 * 1024)
        
    cost = messages_per_month * pricing_layer.get("pricePerMessage", 0)
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": cost,
        "dataSizeInGB": data_volume_gb,
        "totalMessagesPerMonth": messages_per_month
    }

def calculate_gcp_cost_data_processing(number_of_devices, device_sending_interval_in_minutes, average_size_of_message_in_kb, pricing):
    """
    Calculate GCP Data Processing Cost (Cloud Functions).
    
    Formula: Executions = Devices * (60 / Interval) * 730 hours
    Request Cost: (Executions - Free Tier) * Request Price
    Compute Cost: (Total GB-Seconds - Free Tier) * Duration Price
    """
    pricing_layer = pricing["gcp"]["functions"]
    
    execution_duration_ms = 100 # Assumption
    allocated_memory_gb = 128 / 1024 # Assumption
    
    executions_per_month = number_of_devices * (60 / device_sending_interval_in_minutes) * 730
    
    data_size_in_gb = (executions_per_month * average_size_of_message_in_kb) / (1024 * 1024)
    
    # Request Cost
    request_cost = 0
    if executions_per_month > pricing_layer.get("freeRequests", 0):
        request_cost = (executions_per_month - pricing_layer.get("freeRequests", 0)) * pricing_layer.get("requestPrice", 0)
        
    # Compute Cost
    total_compute_seconds = executions_per_month * execution_duration_ms * 0.001
    total_gb_seconds = total_compute_seconds * allocated_memory_gb
    
    compute_cost = 0
    if total_gb_seconds > pricing_layer.get("freeComputeTime", 0):
        compute_cost = (total_gb_seconds - pricing_layer.get("freeComputeTime", 0)) * pricing_layer.get("durationPrice", 0)
        
    total_monthly_cost = request_cost + compute_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb,
        "totalMessagesPerMonth": executions_per_month
    }

def calculate_firestore_cost(data_size_in_gb, total_messages_per_month, average_size_of_message_in_kb, duration_in_months, pricing):
    """
    Calculate GCP Hot Storage Cost (Firestore).
    
    Formula: Storage Cost = (Data Size - Free Tier) * Storage Price * Duration
    Write Cost: Total Messages * Write Price
    Read Cost: (Total Messages * 10) * Read Price (Assumption: 10 reads per write)
    """
    pricing_layer = pricing["gcp"]["storage_hot"]
    
    # Storage Cost
    storage_cost = max(data_size_in_gb - pricing_layer.get("freeStorage", 0), 0) * pricing_layer.get("storagePrice", 0) * duration_in_months
    
    # Operation Cost (Writes)
    # Assuming each message is a write
    write_cost = total_messages_per_month * pricing_layer.get("writePrice", 0)
    
    # Operation Cost (Reads)
    # Assumption: 10 reads per write (similar to Azure/AWS assumptions in original code?)
    # Original AWS code: read_units = total_messages_per_month * 10 (if not provided)
    reads_per_month = total_messages_per_month * 10
    read_cost = reads_per_month * pricing_layer.get("readPrice", 0)
    
    total_monthly_cost = storage_cost + write_cost + read_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb
    }

def calculate_gcp_storage_cool_cost(data_size_in_gb, duration_in_months, pricing):
    """
    Calculate GCP Cool Storage Cost (Cloud Storage Nearline).
    
    Formula: Storage Cost = Data Size * Storage Price * Duration
    """
    pricing_layer = pricing["gcp"]["storage_cool"]
    
    storage_cost = data_size_in_gb * pricing_layer.get("storagePrice", 0) * duration_in_months
    
    # Retrieval cost (if applicable, but usually calculated upon transfer out)
    # Here we just calculate storage cost for the duration
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": storage_cost,
        "dataSizeInGB": data_size_in_gb
    }

def calculate_gcp_storage_archive_cost(data_size_in_gb, duration_in_months, pricing):
    """
    Calculate GCP Archive Storage Cost (Cloud Storage Archive).
    
    Formula: Storage Cost = Data Size * Storage Price * Duration
    """
    pricing_layer = pricing["gcp"]["storage_archive"]
    
    storage_cost = data_size_in_gb * pricing_layer.get("storagePrice", 0) * duration_in_months
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": storage_cost,
        "dataSizeInGB": data_size_in_gb
    }

def calculate_gcp_twin_maker_cost(entity_count, number_of_devices, device_sending_interval_in_minutes, dashboard_refreshes_per_hour, dashboard_active_hours_per_day, pricing):
    """
    Calculate GCP Twin Management Cost.
    Placeholder implementation using generic entity/operation pricing.
    
    Formula: Cost = Entity Count * Entity Price
    """
    pricing_layer = pricing["gcp"]["twinmaker"]
    
    # Placeholder logic similar to AWS/Azure
    cost = entity_count * pricing_layer.get("entityPrice", 0)
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": cost
    }

def calculate_gcp_managed_grafana_cost(amount_of_active_users, pricing):
    """
    Calculate GCP Visualization Cost.
    
    Formula: Cost = Active Users * Price Per User
    """
    pricing_layer = pricing["gcp"]["grafana"]
    
    # Assuming a mix of editors and viewers or just a flat user price
    # Use viewerPrice as base if userPrice not defined, or average
    price_per_user = pricing_layer.get("viewerPrice", 5.0)
    
    cost = amount_of_active_users * price_per_user
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": cost
    }
