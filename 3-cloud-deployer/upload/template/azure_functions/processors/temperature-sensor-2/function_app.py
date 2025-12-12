"""
Temperature Sensor 2 Processor Azure Function.

Processing logic for temperature-sensor-2 device.
Azure equivalent of AWS temperature-sensor-2 Lambda processor.
"""
import json
import logging

import azure.functions as func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = func.FunctionApp()


@app.function_name(name="temperature-sensor-2-processor")
@app.route(route="temperature-sensor-2-processor", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def main(req: func.HttpRequest) -> func.HttpResponse:
    """Process temperature-sensor-2 events with validation."""
    event = req.get_json()
    logger.info("Received event: " + json.dumps(event))
    
    # Processing logic for temp sensor 2 (e.g. converting unit or validating)
    # Mimicking behavior: Just passing through or doing simple check
    records = event if isinstance(event, list) else [event]
    for record in records:
        if "temperature" in record and record["temperature"] > 100:
            logger.warning(f"High temp detected: {record['temperature']}")
    
    return func.HttpResponse(
        json.dumps(event),
        status_code=200,
        mimetype="application/json"
    )
