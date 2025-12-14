"""
Shared ADT Helper Module.

Provides common logic for updating Azure Digital Twins properties.
Used by both ADT Updater (L4, Event Grid) and ADT Pusher (L0, HTTP).

This module contains the core ADT update logic to avoid code duplication
between the two Azure Functions that update Digital Twins:
- ADT Updater: Event Grid triggered, for single-cloud scenarios
- ADT Pusher: HTTP triggered, for multi-cloud scenarios

Architecture:
    ┌─────────────────┐     ┌─────────────────┐
    │  ADT Updater    │     │   ADT Pusher    │
    │  (Event Grid)   │     │    (HTTP)       │
    └────────┬────────┘     └────────┬────────┘
             │                       │
             └───────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   adt_helper.py      │
              │ update_adt_twin()    │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Azure Digital Twins │
              └──────────────────────┘
"""

import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_twin_id_for_device(device_id: str, digital_twin_info: Dict[str, Any]) -> str:
    """
    Map a device ID to its corresponding Digital Twin ID.
    
    This function looks up the device in the digital_twin_info configuration
    to find the associated twin ID. The mapping is essential for routing
    telemetry data to the correct digital twin.
    
    Args:
        device_id: The IoT device identifier (e.g., "temperature-sensor-1")
        digital_twin_info: Configuration dict with device-to-twin mappings
        
    Returns:
        The Digital Twin ID for the given device
        
    Raises:
        ValueError: If no twin mapping exists for the device
        
    Example:
        >>> info = {"devices": {"sensor-1": {"twin_id": "twin-sensor-1"}}}
        >>> get_twin_id_for_device("sensor-1", info)
        'twin-sensor-1'
    """
    if not device_id:
        raise ValueError("device_id is required")
    if not digital_twin_info:
        raise ValueError("digital_twin_info is required")
    
    devices = digital_twin_info.get("devices", {})
    device_config = devices.get(device_id, {})
    twin_id = device_config.get("twin_id")
    
    if not twin_id:
        # Fallback: Use device_id as twin_id (common convention)
        logger.warning(f"No explicit twin mapping for device '{device_id}', using device_id as twin_id")
        twin_id = device_id
    
    return twin_id


def build_adt_patch(telemetry: Dict[str, Any]) -> list:
    """
    Build a JSON Patch document for updating ADT twin properties.
    
    Azure Digital Twins uses JSON Patch (RFC 6902) format for partial updates.
    This function converts telemetry key-value pairs into patch operations.
    
    Args:
        telemetry: Dictionary of property names to values
        
    Returns:
        List of JSON Patch operations
        
    Example:
        >>> build_adt_patch({"temperature": 23.5, "humidity": 60.2})
        [
            {"op": "replace", "path": "/temperature", "value": 23.5},
            {"op": "replace", "path": "/humidity", "value": 60.2}
        ]
    """
    if not telemetry:
        raise ValueError("telemetry is required and cannot be empty")
    
    patch = []
    for key, value in telemetry.items():
        patch.append({
            "op": "replace",
            "path": f"/{key}",
            "value": value
        })
    
    return patch


def update_adt_twin(
    adt_client,
    device_id: str,
    telemetry: Dict[str, Any],
    digital_twin_info: Dict[str, Any]
) -> str:
    """
    Update an Azure Digital Twin with telemetry data.
    
    This is the core function used by both ADT Updater and ADT Pusher
    to update twin properties. It:
    1. Maps the device ID to a twin ID
    2. Builds a JSON Patch from telemetry
    3. Applies the patch to the digital twin
    
    Args:
        adt_client: Initialized DigitalTwinsClient instance
        device_id: The IoT device identifier
        telemetry: Dictionary of property names to values
        digital_twin_info: Configuration dict with device-to-twin mappings
        
    Returns:
        The twin ID that was updated
        
    Raises:
        ValueError: If required arguments are missing
        azure.core.exceptions.ResourceNotFoundError: If twin doesn't exist
        azure.core.exceptions.HttpResponseError: On API errors
    """
    if adt_client is None:
        raise ValueError("adt_client is required")
    if not device_id:
        raise ValueError("device_id is required")
    if not telemetry:
        raise ValueError("telemetry is required")
    if not digital_twin_info:
        raise ValueError("digital_twin_info is required")
    
    # Map device to twin
    twin_id = get_twin_id_for_device(device_id, digital_twin_info)
    
    # Build patch document
    patch = build_adt_patch(telemetry)
    
    # Apply update to digital twin
    logger.info(f"Updating twin '{twin_id}' with {len(patch)} properties")
    adt_client.update_digital_twin(twin_id, patch)
    
    logger.info(f"✓ Successfully updated twin '{twin_id}'")
    return twin_id


def create_adt_client(adt_instance_url: str):
    """
    Create an Azure Digital Twins client using DefaultAzureCredential.
    
    Uses managed identity when running in Azure Functions,
    or falls back to developer credentials locally.
    
    Args:
        adt_instance_url: The ADT instance endpoint URL
            Format: https://{instance-name}.api.{region}.digitaltwins.azure.net
            
    Returns:
        Initialized DigitalTwinsClient
        
    Raises:
        ValueError: If adt_instance_url is missing
        azure.core.exceptions.ClientAuthenticationError: On auth failure
    """
    if not adt_instance_url:
        raise ValueError("adt_instance_url is required")
    
    from azure.digitaltwins.core import DigitalTwinsClient
    from azure.identity import DefaultAzureCredential
    
    credential = DefaultAzureCredential()
    client = DigitalTwinsClient(adt_instance_url, credential)
    
    logger.info(f"Created ADT client for: {adt_instance_url}")
    return client
