"""
ADT Updater Azure Function.

Event Grid triggered function that receives IoT Hub telemetry events
and updates Azure Digital Twins properties.

This function is deployed as part of L4 (Twin Management) and is used
for SINGLE-CLOUD scenarios where IoT Hub and ADT are both on Azure.

Architecture:
    IoT Hub → Event Grid → ADT Updater → Azure Digital Twins

For multi-cloud scenarios (L1 on AWS/GCP, L4 on Azure), the ADT Pusher
function in L0 Glue handles the updates instead.

Environment Variables Required:
    - ADT_INSTANCE_URL: Azure Digital Twins endpoint URL
    - DIGITAL_TWIN_INFO: JSON config with device-to-twin mappings

Authentication:
    Uses DefaultAzureCredential via Managed Identity.
"""

import azure.functions as func
import json
import logging
import os
import sys

# Handle import path for both deployed (with _shared) and test contexts
try:
    from _shared.adt_helper import (
        create_adt_client,
        update_adt_twin
    )
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from _shared.adt_helper import (
        create_adt_client,
        update_adt_twin
    )
    from _shared.env_utils import require_env

app = func.FunctionApp()

# ==========================================
# Environment Variable Validation (Fail-Fast)
# ==========================================

class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass


# Load required configuration at module load time (fail-fast)
try:
    ADT_INSTANCE_URL = require_env("ADT_INSTANCE_URL")
    DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
except ConfigurationError as e:
    logging.error(f"Configuration Error: {e}")
    # Allow module to load for testing, but will fail at runtime
    ADT_INSTANCE_URL = None
    DIGITAL_TWIN_INFO = None


# ==========================================
# Event Grid Triggered Function
# ==========================================

@app.function_name(name="adt-updater")
@app.event_grid_trigger(arg_name="event")
def adt_updater(event: func.EventGridEvent) -> None:
    """
    Update Azure Digital Twin from IoT Hub telemetry event.
    
    This function is triggered by Event Grid when IoT Hub receives
    telemetry from a device. It extracts the telemetry data and
    updates the corresponding digital twin.
    
    Expected Event Grid Event Format:
        {
            "id": "unique-event-id",
            "subject": "devices/{device-id}",
            "eventType": "Microsoft.Devices.DeviceTelemetry",
            "data": {
                "body": {
                    "temperature": 23.5,
                    "humidity": 60.2
                },
                "systemProperties": {
                    "iothub-connection-device-id": "sensor-1"
                },
                "properties": {}
            }
        }
    """
    logging.info(f"ADT Updater: Received event {event.id}")
    
    # Fail-fast if configuration is missing
    if not ADT_INSTANCE_URL or not DIGITAL_TWIN_INFO:
        logging.error("ADT Updater: Missing required configuration")
        raise ConfigurationError("ADT_INSTANCE_URL and DIGITAL_TWIN_INFO are required")
    
    try:
        # Parse event data
        event_data = event.get_json()
        logging.info(f"Event data: {json.dumps(event_data)}")
        
        # Extract device ID from system properties
        system_props = event_data.get("systemProperties", {})
        device_id = system_props.get("iothub-connection-device-id")
        
        if not device_id:
            # Fallback: try to extract from subject
            subject = event.subject
            if subject and subject.startswith("devices/"):
                device_id = subject.split("/")[1]
        
        if not device_id:
            logging.error("ADT Updater: Could not determine device ID")
            raise ValueError("device_id could not be extracted from event")
        
        # Extract telemetry from body
        telemetry = event_data.get("body", {})
        
        if not telemetry:
            logging.warning(f"ADT Updater: No telemetry data in event for device {device_id}")
            return
        
        # Create ADT client and update twin
        adt_client = create_adt_client(ADT_INSTANCE_URL)
        twin_id = update_adt_twin(
            adt_client=adt_client,
            device_id=device_id,
            telemetry=telemetry,
            digital_twin_info=DIGITAL_TWIN_INFO
        )
        
        logging.info(f"ADT Updater: Successfully updated twin '{twin_id}'")
        
    except json.JSONDecodeError as e:
        logging.error(f"ADT Updater: Failed to parse event JSON: {e}")
        raise
    except ValueError as e:
        logging.error(f"ADT Updater: Validation error: {e}")
        raise
    except Exception as e:
        logging.exception(f"ADT Updater: Unexpected error: {type(e).__name__}: {e}")
        raise
