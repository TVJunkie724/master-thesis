"""
Connector Azure Function.

Bridges L1 (Azure) to L2 (remote cloud) in multi-cloud deployments.
POSTs device telemetry to the remote Ingestion endpoint.

Architecture:
    Dispatcher → Connector → [HTTP POST] → Remote Ingestion

Source: src/providers/azure/azure_functions/connector/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging

import azure.functions as func

# Handle import path for shared module
try:
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.inter_cloud import post_to_remote
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
REMOTE_INGESTION_URL = require_env("REMOTE_INGESTION_URL")
INTER_CLOUD_TOKEN = require_env("INTER_CLOUD_TOKEN")

# Create Function App instance
app = func.FunctionApp()


@app.function_name(name="connector")
@app.route(route="connector", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def connector(req: func.HttpRequest) -> func.HttpResponse:
    """
    Forward device telemetry to remote L2 Ingestion endpoint.
    
    Receives events from local Dispatcher and POSTs them to the
    remote cloud's Ingestion function using the shared inter_cloud module.
    
    Args:
        req: HTTP request containing device telemetry
    
    Returns:
        func.HttpResponse: Success/error response
    """
    logging.info("Azure Connector: Received request")
    
    try:
        # Parse incoming event
        event = req.get_json()
        logging.info(f"Event: {json.dumps(event)}")
        
        # POST to remote Ingestion endpoint
        result = post_to_remote(
            url=REMOTE_INGESTION_URL,
            token=INTER_CLOUD_TOKEN,
            payload=event,
            target_layer="L2"
        )
        
        logging.info(f"Successfully POSTed to remote Ingestion: {result}")
        
        return func.HttpResponse(
            json.dumps({"status": "forwarded", "remote_response": result}),
            status_code=200,
            mimetype="application/json"
        )
        
    except ValueError as e:
        logging.error(f"Connector Configuration Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"Connector Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
