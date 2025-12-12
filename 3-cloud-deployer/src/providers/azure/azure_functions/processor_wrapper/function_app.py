"""
Processor Wrapper Azure Function.

Merges user-defined processing logic with the system pipeline.
Executes user logic and then invokes the Persister.

Architecture:
    Ingestion → Processor (user logic) → Persister

Source: src/providers/azure/azure_functions/processor_wrapper/function_app.py
Editable: Yes - This is the runtime Azure Function code
"""
import json
import os
import sys
import logging
import urllib.request
import urllib.error

import azure.functions as func
from process import process  # User logic import

# Handle import path for shared module
try:
    from _shared.env_utils import require_env
except ModuleNotFoundError:
    _func_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _func_dir not in sys.path:
        sys.path.insert(0, _func_dir)
    from _shared.env_utils import require_env


# Required environment variables - fail fast if missing
PERSISTER_FUNCTION_URL = require_env("PERSISTER_FUNCTION_URL")

# Create Function App instance
app = func.FunctionApp()


def _invoke_persister(payload: dict) -> None:
    """
    Invoke Persister function via HTTP POST.
    
    Args:
        payload: Processed event data to persist
    """
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(PERSISTER_FUNCTION_URL, data=data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            logging.info(f"Persister invoked successfully: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logging.error(f"Failed to invoke Persister: {e.code} {e.reason}")
        raise
    except urllib.error.URLError as e:
        logging.error(f"Network error invoking Persister: {e.reason}")
        raise


@app.function_name(name="processor")
@app.route(route="processor", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def processor(req: func.HttpRequest) -> func.HttpResponse:
    """
    Execute user processing logic and invoke Persister.
    
    This function wraps user-defined `process()` logic with the
    system pipeline, ensuring processed data flows to storage.
    """
    logging.info("Azure Processor Wrapper: Executing user logic...")
    
    try:
        # Parse input event
        event = req.get_json()
        
        # 1. Execute User Logic
        try:
            processed_event = process(event)
            logging.info(f"User Logic Complete. Result: {json.dumps(processed_event)}")
        except Exception as e:
            logging.error(f"[USER_LOGIC_ERROR] Processing failed: {e}")
            return func.HttpResponse(
                json.dumps({"error": "User logic error", "message": str(e)}),
                status_code=500,
                mimetype="application/json"
            )
        
        # 2. Invoke Persister
        _invoke_persister(processed_event)
        
        return func.HttpResponse(
            json.dumps({"status": "processed", "result": processed_event}),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"[SYSTEM_ERROR] Processor error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "System error", "message": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
