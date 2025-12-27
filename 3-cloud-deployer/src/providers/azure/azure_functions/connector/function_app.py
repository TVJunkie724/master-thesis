"""
Connector Azure Function.

Bridges L1 (Azure) to L2 (remote cloud) in multi-cloud deployments.
POSTs device telemetry to the remote Ingestion endpoint.

Architecture:
    Dispatcher → Connector → [HTTP POST] → Remote Ingestion

SECURITY NOTE - AuthLevel.ANONYMOUS
==================================
This function uses AuthLevel.ANONYMOUS instead of AuthLevel.FUNCTION due to a
Terraform infrastructure limitation:

Problem: When deploying Azure Function Apps with Terraform, retrieving the
function's host key creates a circular dependency:
  1. L1 Function App needs L1_FUNCTION_KEY in its app_settings
  2. L1_FUNCTION_KEY comes from data.azurerm_function_app_host_keys.l1
  3. That data source depends on the L1 Function App being created
  4. CYCLE: L1 App → data.l1 → L1 App

Terraform cannot resolve this cycle, causing deployment to fail.

Workaround: Internal L1 functions (connector) that are only called by other L1 
functions (dispatcher) use AuthLevel.ANONYMOUS. This is acceptable because:
  - The connector is only called by the dispatcher (same Function App)
  - It is NOT exposed to the public internet directly
  - It uses INTER_CLOUD_TOKEN for securing the outbound call to remote clouds
  - Network-level security (Azure VNet, Private Endpoints) can be added for
    production deployments

Future Fix: See docs/future-work.md for proper solutions when Terraform
supports post-deployment app_settings updates or two-phase deployments.

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


# Lazy loading for environment variables to allow Azure function discovery
_remote_ingestion_url = None
_inter_cloud_token = None

def _get_remote_ingestion_url():
    global _remote_ingestion_url
    if _remote_ingestion_url is None:
        _remote_ingestion_url = require_env("REMOTE_INGESTION_URL")
    return _remote_ingestion_url

def _get_inter_cloud_token():
    global _inter_cloud_token
    if _inter_cloud_token is None:
        _inter_cloud_token = require_env("INTER_CLOUD_TOKEN")
    return _inter_cloud_token


# Create Blueprint for registration by main function_app.py
bp = func.Blueprint()


@bp.function_name(name="connector")
# AuthLevel.ANONYMOUS: See module docstring for Terraform cycle limitation explanation
@bp.route(route="connector", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
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
            url=_get_remote_ingestion_url(),
            token=_get_inter_cloud_token(),
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
        logging.exception(f"Connector Error: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
