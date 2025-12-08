"""
GCP Cost Calculation Module
============================
Calculates costs for GCP services (Pub/Sub, Cloud Functions, Firestore, Cloud Storage, Compute Engine).

HARDCODED ASSUMPTIONS (consistent across all providers):
  - Cloud Functions execution duration: 100ms
  - Cloud Functions memory allocation: 128 MB
  - Hours per month: 730 (industry standard)

These assumptions match typical serverless function configurations and ensure
fair cost comparison across AWS/Azure/GCP providers.

Note: GCP uses self-hosted solutions for L4 (Twin Management) and L5 (Grafana)
running on Compute Engine (e2-medium instances), as GCP doesn't offer native
equivalents to AWS TwinMaker or Azure Digital Twins.

Formula documentation: docs/docs-formulas.html
"""

import math

# LAYER 1 - Data Acquisition
# Service: Google Cloud Pub/Sub
# Formula: CTransfer (Volume-Based) - differs from AWS/Azure which use per-message

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
    
    # Hardcoded assumptions - same across all providers for fair comparison.
    # These values represent typical serverless function configurations.
    execution_duration_ms = 100  # Conservative estimate for simple data processing
    allocated_memory_gb = 128 / 1024  # 128 MB in GB
    
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
    Read Cost: (Total Messages / 2) * Read Price
    
    Read Ratio Assumption: 1 read per 2 writes (0.5x)
    Rationale: In a Digital Twin architecture, most data is written by IoT devices
    and read less frequently by dashboards. Dashboard queries are batched/aggregated.
    This matches AWS DynamoDB assumptions for fair cross-provider comparison.
    
    Storage Buffer (+0.5 months): Accounts for mid-month data accumulation.
    As data grows throughout the month, the average storage used is approximately
    half the final amount, hence we add 0.5 months to prorate the storage cost.
    This aligns with AWS DynamoDB and Azure Cosmos DB calculations.
    """
    pricing_layer = pricing["gcp"]["storage_hot"]
    
    # Storage Buffer: Add 0.5 months for mid-month accumulation (same as AWS/Azure)
    storage_duration_adjusted = duration_in_months + 0.5
    
    # Storage Cost
    storage_cost = max(data_size_in_gb - pricing_layer.get("freeStorage", 0), 0) * pricing_layer.get("storagePrice", 0) * storage_duration_adjusted
    
    # Operation Cost (Writes) - each message is a write
    write_cost = total_messages_per_month * pricing_layer.get("writePrice", 0)
    
    # Operation Cost (Reads)
    # Read Ratio: 1 read per 2 writes (aligned with AWS DynamoDB)
    # Previous value of 10:1 was incorrect - Firestore has no inherent ratio,
    # it simply charges per operation. We model expected DT workload patterns.
    reads_per_month = total_messages_per_month / 2.0  # 1 read per 2 writes
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
    Write Cost: (Data Size * 1024 / 100) * Write Price per 10K operations
    Read Cost: Write Count * 0.1 * Read Price (10% reads)
    Retrieval Cost: (Data Size * 0.1 + Data Size) * Retrieval Price
    
    Operation costs added for equivalency with AWS/Azure cool storage calculations.
    """
    pricing_layer = pricing["gcp"]["storage_cool"]
    
    # Storage Cost
    storage_cost = data_size_in_gb * pricing_layer.get("storagePrice", 0) * duration_in_months
    
    # Operation Costs (aligned with AWS/Azure for fair comparison)
    # Write operations: Similar to Azure blob calculation
    amount_of_writes = math.ceil((data_size_in_gb * 1024) / 100)  # 1 write per 100KB block
    amount_of_reads = amount_of_writes * 0.1  # 10% read assumption
    data_retrieval_amount = (data_size_in_gb * 0.1) + data_size_in_gb  # 10% retrieval + initial write
    
    write_cost = amount_of_writes * pricing_layer.get("writePrice", 0)
    read_cost = amount_of_reads * pricing_layer.get("readPrice", 0)
    retrieval_cost = data_retrieval_amount * pricing_layer.get("dataRetrievalPrice", 0)
    
    total_monthly_cost = storage_cost + write_cost + read_cost + retrieval_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb
    }

def calculate_gcp_storage_archive_cost(data_size_in_gb, duration_in_months, pricing):
    """
    Calculate GCP Archive Storage Cost (Cloud Storage Archive).
    
    Formula: Storage Cost = Data Size * Storage Price * Duration
    Write Cost: Data Size * Write Price (lifecycle transition)
    Retrieval Cost: 1% of Data Size * Retrieval Price
    
    Operation costs added for equivalency with AWS Glacier/Azure Archive calculations.
    """
    pricing_layer = pricing["gcp"]["storage_archive"]
    
    # Storage Cost
    storage_needed_for_duration = data_size_in_gb * duration_in_months
    storage_cost = storage_needed_for_duration * pricing_layer.get("storagePrice", 0)
    
    # Write Cost (lifecycle transition - aligned with AWS Glacier)
    amount_of_writes = data_size_in_gb * 2  # Similar to AWS: 2 writes per GB
    write_cost = amount_of_writes * pricing_layer.get("writePrice", 0)
    
    # Retrieval Cost (1% retrieval assumption - aligned with AWS Glacier)
    data_retrieval_amount = storage_needed_for_duration * 0.01
    retrieval_cost = data_retrieval_amount * pricing_layer.get("dataRetrievalPrice", 0)
    
    total_monthly_cost = storage_cost + write_cost + retrieval_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": total_monthly_cost,
        "dataSizeInGB": data_size_in_gb
    }

def calculate_gcp_twin_maker_cost(entity_count, number_of_devices, device_sending_interval_in_minutes, dashboard_refreshes_per_hour, dashboard_active_hours_per_day, average_3d_model_size_in_mb, pricing):
    """
    Calculate GCP Twin Management Cost.
    GCP uses Compute Engine (IaaS) for this layer.
    
    Formula: Cost = (Instance Price * 730 hours) + (Storage Price * Storage Size) + (Model Storage Price * Model Size)
    """
    pricing_layer = pricing["gcp"]["twinmaker"]
    cloud_storage_price = pricing["gcp"]["storage_cool"]["storagePrice"]
    
    # Instance Cost (e2-medium)
    instance_cost = pricing_layer.get("e2MediumPrice", 0) * 730
    
    # Storage Cost (Assuming 50GB for OS + Data on the instance)
    storage_size_gb = 50 
    storage_cost = storage_size_gb * pricing_layer.get("storagePrice", 0)

    # 3D Model Storage Cost (Cloud Storage Nearline)
    total_model_storage_gb = (entity_count * average_3d_model_size_in_mb) / 1024.0
    model_storage_cost = total_model_storage_gb * cloud_storage_price
    
    cost = instance_cost + storage_cost + model_storage_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": cost
    }

# LAYER 5 - Data Visualization
# Service: Self-Hosted Grafana on Compute Engine
#
# PRICING MODEL COMPARISON (why different formulas are comparable):
# - AWS Managed Grafana: Per-seat licensing (editors + viewers). No instance cost.
# - Azure Managed Grafana: Per-seat + instance hours. Includes infrastructure.
# - GCP (Self-Hosted): VM cost (e2-medium) + disk. No per-seat fees.
#
# GCP doesn't offer a managed Grafana service, so we calculate the cost of running
# a self-hosted Grafana instance on Compute Engine. This is a fair comparison because
# it represents the actual cost a GCP customer would incur for this capability.
#
# All three represent the actual cost of running Grafana dashboards on each provider.
# The pricing models differ, but outputs are directly comparable monthly costs.

def calculate_gcp_managed_grafana_cost(amount_of_active_users, pricing):
    """
    Calculate GCP Visualization Cost (Self-Hosted Grafana).
    
    GCP uses Compute Engine (IaaS) for this layer as there's no managed Grafana service.
    This calculates the cost of running a self-hosted Grafana instance.
    
    Note: User count is not directly used in cost calculation since self-hosted
    Grafana doesn't have per-seat licensing. The instance can handle multiple users
    within its capacity limits.
    
    Formula: Cost = (Instance Price * 730 hours) + (Storage Price * Storage Size)
    """
    pricing_layer = pricing["gcp"]["grafana"]
    
    # Instance Cost (e2-medium - suitable for small/medium Grafana deployments)
    instance_cost = pricing_layer.get("e2MediumPrice", 0) * 730
    
    # Storage Cost (20GB for Grafana DB/Logs - typical deployment)
    storage_size_gb = 20
    storage_cost = storage_size_gb * pricing_layer.get("storagePrice", 0)
    
    cost = instance_cost + storage_cost
    
    return {
        "provider": "GCP",
        "totalMonthlyCost": cost
    }
