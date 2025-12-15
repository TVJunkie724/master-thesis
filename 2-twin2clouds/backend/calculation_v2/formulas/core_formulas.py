"""
Provider-Independent Cost Formulas
===================================
Based on: docs/docs-formulas.html

This module contains pure mathematical formulas that apply across all cloud providers.
Each formula takes generic pricing parameters and returns a cost value.

The formulas are:
- CM (Message-Based): c_m × N_m
- CE (Execution-Based): c_e × max(0, N_e - free) + c_t × max(0, T_e - free)
- CA (Action-Based): c_a × N_a
- CS (Storage-Based): c_s × V × D
- CU (User-Based): (c_editor × N_editor + c_viewer × N_viewer) + c_hour × H
- CTransfer (Data Transfer): c_transfer × GB_transferred

Scientific Foundation:
    Philipp Gritsch, et al. "Twin2Clouds: Cost-Aware Digital Twin Engineering..." (MODELS 2025)
"""


def message_based_cost(
    price_per_message: float,
    num_messages: float
) -> float:
    """
    CM: Message-based cost formula.
    
    Formula: c_m × N_m
    
    Used by: IoT Core (AWS), IoT Hub (Azure)
    
    Args:
        price_per_message: Cost per message (c_m)
        num_messages: Total number of messages (N_m)
        
    Returns:
        Total monthly cost for message processing
    """
    return price_per_message * num_messages


def execution_based_cost(
    price_per_execution: float,
    num_executions: float,
    free_executions: float,
    price_per_compute_unit: float,
    total_compute_units: float,
    free_compute_units: float
) -> float:
    """
    CE: Execution-based cost formula for serverless compute.
    
    Formula: c_e × max(0, N_e - free) + c_t × max(0, T_e - free)
    
    Used by: Lambda (AWS), Functions (Azure), Cloud Functions (GCP)
    
    Args:
        price_per_execution: Cost per request/invocation (c_e)
        num_executions: Total number of executions (N_e)
        free_executions: Free tier executions (freeRequests)
        price_per_compute_unit: Cost per GB-second (c_t)
        total_compute_units: Total GB-seconds of compute (T_e)
        free_compute_units: Free tier compute (freeComputeTime)
        
    Returns:
        Total monthly cost for serverless execution
    """
    request_cost = price_per_execution * max(0, num_executions - free_executions)
    compute_cost = price_per_compute_unit * max(0, total_compute_units - free_compute_units)
    return request_cost + compute_cost


def action_based_cost(
    price_per_action: float,
    num_actions: float
) -> float:
    """
    CA: Action-based cost formula.
    
    Formula: c_a × N_a
    
    Used by: 
        - DynamoDB read/write (AWS)
        - Step Functions state transitions (AWS)
        - EventBridge events (AWS)
        - Logic Apps actions (Azure)
        - Event Grid operations (Azure)
        - Cloud Workflows steps (GCP)
    
    Args:
        price_per_action: Cost per action (c_a)
        num_actions: Total number of actions (N_a)
        
    Returns:
        Total monthly cost for actions
    """
    return price_per_action * num_actions


def storage_based_cost(
    price_per_gb_month: float,
    volume_gb: float,
    duration_months: float = 1.0
) -> float:
    """
    CS: Storage-based cost formula.
    
    Formula: c_s × V × D
    
    Used by:
        - S3 (AWS)
        - DynamoDB storage (AWS)
        - Blob Storage (Azure)
        - Cloud Storage (GCP)
    
    Args:
        price_per_gb_month: Cost per GB per month (c_s)
        volume_gb: Storage volume in GB (V)
        duration_months: Duration in months (D), defaults to 1
        
    Returns:
        Total cost for storage
    """
    return price_per_gb_month * volume_gb * duration_months


def user_based_cost(
    price_per_editor: float,
    num_editors: int,
    price_per_viewer: float,
    num_viewers: int,
    price_per_hour: float = 0.0,
    total_hours: float = 0.0
) -> float:
    """
    CU: User-based cost formula for licensed services or VMs.
    
    Formula: (c_editor × N_editor + c_viewer × N_viewer) + c_hour × H
    
    Used by:
        - Managed Grafana (AWS/Azure) - seat-based
        - Self-hosted VMs (GCP) - hourly-based
    
    Args:
        price_per_editor: Cost per editor seat (c_u_editor)
        num_editors: Number of editor users (N_editor)
        price_per_viewer: Cost per viewer seat (c_u_viewer)
        num_viewers: Number of viewer users (N_viewer)
        price_per_hour: Cost per hour for VMs (c_u_hour), defaults to 0
        total_hours: Total VM hours (H), defaults to 0
        
    Returns:
        Total monthly cost for user licenses or VM time
    """
    seat_cost = (price_per_editor * num_editors) + (price_per_viewer * num_viewers)
    time_cost = price_per_hour * total_hours
    return seat_cost + time_cost


def transfer_cost(
    price_per_gb: float,
    gb_transferred: float
) -> float:
    """
    CTransfer: Data transfer cost formula.
    
    Formula: c_transfer × GB_transferred
    
    Used by:
        - Data egress (all providers)
        - Pub/Sub data transfer (GCP)
        - Cross-cloud data movement
    
    Args:
        price_per_gb: Cost per GB transferred (c_transfer)
        gb_transferred: Total GB transferred (GB_transferred)
        
    Returns:
        Total cost for data transfer
    """
    return price_per_gb * gb_transferred


def _normalize_limit(limit):
    """
    Normalize a tier limit value.
    
    Handles string "Infinity" from JSON by converting to float('inf').
    
    Args:
        limit: The limit value (number or string)
        
    Returns:
        float: Normalized numeric limit
    """
    if isinstance(limit, str) and limit.lower() == "infinity":
        return float('inf')
    return float(limit)


def tiered_message_cost(
    num_messages: float,
    tiers: list
) -> float:
    """
    Tiered pricing for message-based services like IoT Core.
    
    AWS IoT Core and similar services use tiered pricing where
    the price per message decreases as volume increases.
    
    Args:
        num_messages: Total number of messages
        tiers: List of dicts with 'limit' and 'price' keys, sorted by limit ascending
               Example: [{"limit": 1_000_000_000, "price": 1.0},
                        {"limit": 4_000_000_000, "price": 0.8},
                        {"limit": float('inf'), "price": 0.7}]
        
    Returns:
        Total cost applying tiered pricing
    """
    total_cost = 0.0
    remaining = num_messages
    previous_limit = 0
    
    for tier in tiers:
        tier_limit = _normalize_limit(tier["limit"])
        tier_price = tier["price"]
        
        # Calculate messages in this tier
        tier_capacity = tier_limit - previous_limit
        messages_in_tier = min(remaining, tier_capacity)
        
        # Add cost for this tier
        total_cost += messages_in_tier * tier_price
        remaining -= messages_in_tier
        previous_limit = tier_limit
        
        if remaining <= 0:
            break
    
    return total_cost


def tiered_transfer_cost(
    gb_transferred: float,
    tiers: list
) -> float:
    """
    Tiered pricing for data transfer/egress.
    
    Cloud providers typically offer tiered pricing for data egress
    where the price per GB decreases as volume increases.
    
    Args:
        gb_transferred: Total GB to transfer
        tiers: List of dicts with 'limit' (in GB) and 'price' keys
               Example: [{"limit": 100, "price": 0.0},  # Free tier
                        {"limit": 10240, "price": 0.09},
                        {"limit": float('inf'), "price": 0.05}]
        
    Returns:
        Total cost applying tiered pricing
    """
    total_cost = 0.0
    remaining = gb_transferred
    previous_limit = 0
    
    for tier in tiers:
        tier_limit = _normalize_limit(tier["limit"])
        tier_price = tier["price"]
        
        # Calculate GB in this tier
        tier_capacity = tier_limit - previous_limit
        gb_in_tier = min(remaining, tier_capacity)
        
        # Add cost for this tier
        total_cost += gb_in_tier * tier_price
        remaining -= gb_in_tier
        previous_limit = tier_limit
        
        if remaining <= 0:
            break
    
    return total_cost
