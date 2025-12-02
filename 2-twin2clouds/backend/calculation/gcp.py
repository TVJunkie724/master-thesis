
import math

def calculate_gcp_cost_data_acquisition(number_of_devices, device_sending_interval_in_minutes, average_size_of_message_in_kb, pricing):
    """
    Calculate GCP Data Acquisition Cost (Cloud Pub/Sub).
    Pub/Sub is priced by data volume (GB).
    
    Formula: Total Messages = Devices * (60 / Interval) * 24 * 30
    Cost: Data Volume (GB) * Price Per GB
    """
    pricing_layer = pricing["gcp"]["iot"]
    
    # Messages per month
    messages_per_month = number_of_devices * (60 / device_sending_interval_in_minutes) * 730
    
    # Data volume in GB
    data_volume_gb = (messages_per_month * average_size_of_message_in_kb) / (1024 * 1024)
        
    # Use pricePerGiB (volume based)
    cost = data_volume_gb * pricing_layer.get("pricePerGiB", 0)
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": cost,
        "dataSizeInGB": data_volume_gb,
        "totalMessagesPerMonth": messages_per_month
    }

def calculate_gcp_cost_data_processing(
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

    # Supporter Services Costs
    event_checker_cost = 0
    workflows_cost = 0
    feedback_loop_cost = 0
    error_handling_cost = 0

    # 1. Event Checker (Function)
    if use_event_checking:
        # Assumes 1 check per message
        event_checker_compute_seconds = executions_per_month * execution_duration_ms * 0.001
        event_checker_gb_seconds = event_checker_compute_seconds * allocated_memory_gb
        
        event_checker_compute_cost = 0
        if event_checker_gb_seconds > pricing_layer.get("freeComputeTime", 0):
            event_checker_compute_cost = (event_checker_gb_seconds - pricing_layer.get("freeComputeTime", 0)) * pricing_layer.get("durationPrice", 0)
            
        event_checker_request_cost = 0
        if executions_per_month > pricing_layer.get("freeRequests", 0):
            event_checker_request_cost = (executions_per_month - pricing_layer.get("freeRequests", 0)) * pricing_layer.get("requestPrice", 0)
            
        event_checker_cost = event_checker_compute_cost + event_checker_request_cost

    # 2. Orchestration (Cloud Workflows)
    if use_event_checking and trigger_notification_workflow:
        workflows_price = pricing["gcp"]["cloudWorkflows"]["stepPrice"] # Or price per execution?
        # Cloud Workflows pricing is per 1000 steps.
        # Let's assume pricePerStep is actually price per 1000 steps or similar unit.
        # Typically: Free tier 5000 steps. Then $0.01 per 1000 steps.
        # We need to check how the fetcher stores this.
        # Assuming pricePerStep is cost for 1 step for simplicity, or adjusted in fetcher.
        total_steps = executions_per_month * orchestration_actions_per_message
        workflows_cost = total_steps * workflows_price

    # 3. Feedback Loop (Pub/Sub + Function)
    if use_event_checking and return_feedback_to_device:
        # Pub/Sub Publish
        pubsub_pricing = pricing["gcp"]["iot"] # Reusing IoT/PubSub pricing
        feedback_messages = executions_per_month
        feedback_volume_gb = (feedback_messages * average_size_of_message_in_kb) / (1024 * 1024)
        feedback_loop_cost += feedback_volume_gb * pubsub_pricing.get("pricePerGiB", 0)
        
        # Feedback Function
        feedback_compute_seconds = feedback_messages * execution_duration_ms * 0.001
        feedback_gb_seconds = feedback_compute_seconds * allocated_memory_gb
        
        feedback_function_cost = 0
        if feedback_gb_seconds > pricing_layer.get("freeComputeTime", 0):
            feedback_function_cost += (feedback_gb_seconds - pricing_layer.get("freeComputeTime", 0)) * pricing_layer.get("durationPrice", 0)
            
        if feedback_messages > pricing_layer.get("freeRequests", 0):
            feedback_function_cost += (feedback_messages - pricing_layer.get("freeRequests", 0)) * pricing_layer.get("requestPrice", 0)
            
        feedback_loop_cost += feedback_function_cost

    # 4. Error Handling (Pub/Sub + Function + Firestore Write)
    if integrate_error_handling:
        # Pub/Sub (Error Topic)
        total_events = executions_per_month * events_per_message
        error_volume_gb = (total_events * 1.0) / (1024 * 1024) # Assume 1KB per error
        pubsub_pricing = pricing["gcp"]["iot"]
        error_handling_cost += error_volume_gb * pubsub_pricing.get("pricePerGiB", 0)

        # Error Reporter Function
        reporter_compute_seconds = total_events * execution_duration_ms * 0.001
        reporter_gb_seconds = reporter_compute_seconds * allocated_memory_gb
        
        reporter_cost = 0
        if reporter_gb_seconds > pricing_layer.get("freeComputeTime", 0):
            reporter_cost += (reporter_gb_seconds - pricing_layer.get("freeComputeTime", 0)) * pricing_layer.get("durationPrice", 0)
            
        if total_events > pricing_layer.get("freeRequests", 0):
            reporter_cost += (total_events - pricing_layer.get("freeRequests", 0)) * pricing_layer.get("requestPrice", 0)
        error_handling_cost += reporter_cost

        # Firestore Error Collection (Write)
        firestore_pricing = pricing["gcp"]["storage_hot"]
        write_cost = total_events * firestore_pricing.get("writePrice", 0)
        error_handling_cost += write_cost

    total_monthly_cost = request_cost + compute_cost + event_checker_cost + workflows_cost + feedback_loop_cost + error_handling_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb,
        "totalMessagesPerMonth": executions_per_month
    }

def calculate_gcp_api_gateway_cost(number_of_requests, pricing):
    # API Gateway Pricing: Per million calls
    price_per_million = pricing["gcp"]["apiGateway"]["pricePerMillionCalls"]
    return (number_of_requests / 1000000) * price_per_million

# Cross-Cloud Glue Functions
# These use standard Cloud Functions pricing

def _calculate_function_cost(executions, pricing):
    execution_duration_ms = 100
    allocated_memory_gb = 128 / 1024
    pricing_layer = pricing["gcp"]["functions"]
    
    total_compute_seconds = executions * execution_duration_ms * 0.001
    total_gb_seconds = total_compute_seconds * allocated_memory_gb
    
    compute_cost = 0
    if total_gb_seconds > pricing_layer.get("freeComputeTime", 0):
        compute_cost = (total_gb_seconds - pricing_layer.get("freeComputeTime", 0)) * pricing_layer.get("durationPrice", 0)
        
    request_cost = 0
    if executions > pricing_layer.get("freeRequests", 0):
        request_cost = (executions - pricing_layer.get("freeRequests", 0)) * pricing_layer.get("requestPrice", 0)
        
    return compute_cost + request_cost

def calculate_gcp_connector_function_cost(number_of_messages, pricing):
    return _calculate_function_cost(number_of_messages, pricing)

def calculate_gcp_ingestion_function_cost(number_of_messages, pricing):
    return _calculate_function_cost(number_of_messages, pricing)

def calculate_gcp_writer_function_cost(number_of_messages, pricing):
    return _calculate_function_cost(number_of_messages, pricing)

def calculate_gcp_reader_function_cost(number_of_requests, pricing):
    return _calculate_function_cost(number_of_requests, pricing)

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
    GCP uses Compute Engine (IaaS) for this layer.
    
    Formula: Cost = (Instance Price * 730 hours) + (Storage Price * Storage Size)
    """
    pricing_layer = pricing["gcp"]["twinmaker"]
    
    # Instance Cost (e2-medium)
    instance_cost = pricing_layer.get("e2MediumPrice", 0) * 730
    
    # Storage Cost (Assuming 100GB for the twin model/db as a baseline, or use entity_count proxy?)
    # For now, let's assume a fixed storage size or derive from entities.
    # Let's assume 50GB for OS + Data.
    storage_size_gb = 50 
    storage_cost = storage_size_gb * pricing_layer.get("storagePrice", 0)
    
    cost = instance_cost + storage_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": cost
    }

def calculate_gcp_managed_grafana_cost(amount_of_active_users, pricing):
    """
    Calculate GCP Visualization Cost.
    GCP uses Compute Engine (IaaS) for this layer.
    
    Formula: Cost = (Instance Price * 730 hours) + (Storage Price * Storage Size)
    """
    pricing_layer = pricing["gcp"]["grafana"]
    
    # Instance Cost (e2-medium)
    instance_cost = pricing_layer.get("e2MediumPrice", 0) * 730
    
    # Storage Cost (Assuming 20GB for Grafana DB/Logs)
    storage_size_gb = 20
    storage_cost = storage_size_gb * pricing_layer.get("storagePrice", 0)
    
    cost = instance_cost + storage_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": cost
    }
