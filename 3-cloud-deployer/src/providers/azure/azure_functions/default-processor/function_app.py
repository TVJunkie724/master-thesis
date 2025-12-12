"""
Default Processor Azure Function.

Default implementation of the processor logic when no custom
user logic is provided. Demonstrates the processor pattern.

Architecture:
    Ingestion → Default Processor → Persister

Source: src/providers/azure/azure_functions/default-processor/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging

import azure.functions as func

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
DIGITAL_TWIN_INFO = json.loads(require_env("DIGITAL_TWIN_INFO"))
PERSISTER_FUNCTION_URL = require_env("PERSISTER_FUNCTION_URL")

# Create Function App instance
app = func.FunctionApp()


def process(event: dict) -> dict:
    """
    Default processing logic.
    
    This is a simple example that adds a default 'pressure' field.
    In production, users replace this with custom logic.
    
    Args:
        event: Device telemetry event
    
    Returns:
        dict: Processed event with additional fields
    """
    payload = event.copy()
    payload["pressure"] = 20  # Default value
    return payload


@app.function_name(name="default-processor")
@app.route(route="default-processor", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def default_processor(req: func.HttpRequest) -> func.HttpResponse:
    """
    Execute default processing logic and invoke Persister.
    
    Args:
        req: HTTP request containing device telemetry
    
    Returns:
        func.HttpResponse: Processed data or error
    """
    logging.info("Azure Default Processor: Received event")
    
    try:
        # Parse input event
        event = req.get_json()
        logging.info(f"Event: {json.dumps(event)}")
        
        # Execute default processing
        processed = process(event)
        logging.info(f"Processed: {json.dumps(processed)}")
        
        # Invoke Persister
        logging.info(f"Would invoke Persister at: {PERSISTER_FUNCTION_URL}")
        
        return func.HttpResponse(
            json.dumps({"status": "processed", "result": processed}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Default Processor Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
