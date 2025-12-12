"""
Temperature Sensor 2 Processor Google Cloud Function.

Processing logic for temperature-sensor-2 device.
GCP equivalent of AWS temperature-sensor-2 Lambda processor.
"""
import json
import logging
import functions_framework

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@functions_framework.http
def main(request):
    """Process temperature-sensor-2 events with validation."""
    event = request.get_json()
    logger.info("Received event: " + json.dumps(event))
    
    # Processing logic for temp sensor 2 (e.g. converting unit or validating)
    # Mimicking behavior: Just passing through or doing simple check
    records = event if isinstance(event, list) else [event]
    for record in records:
        if "temperature" in record and record["temperature"] > 100:
            logger.warning(f"High temp detected: {record['temperature']}")
    
    return (json.dumps(event), 200, {"Content-Type": "application/json"})
