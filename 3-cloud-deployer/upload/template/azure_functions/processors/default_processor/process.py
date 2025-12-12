# --- CONTEXT: System Wrapper (DO NOT EDIT) ---
# Your process() function is imported and called by this Azure Function.
# This shows what happens when your code is deployed:
#
# """Processor Wrapper Azure Function - Merges user logic with system pipeline."""
# import json
# import os
# import logging
# import urllib.request
# import urllib.error
#
# import azure.functions as func
# from process import process  # <-- YOUR FUNCTION IS IMPORTED HERE
#
# PERSISTER_FUNCTION_URL = os.environ.get("PERSISTER_FUNCTION_URL")
#
# app = func.FunctionApp()
#
# def _invoke_persister(payload: dict) -> None:
#     """Invoke Persister function via HTTP POST."""
#     data = json.dumps(payload).encode("utf-8")
#     req = urllib.request.Request(PERSISTER_FUNCTION_URL, data=data,
#                                   headers={"Content-Type": "application/json"}, method="POST")
#     with urllib.request.urlopen(req, timeout=30) as response:
#         logging.info(f"Persister invoked: {response.getcode()}")
#
# @app.function_name(name="processor")
# @app.route(route="processor", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
# def processor(req: func.HttpRequest) -> func.HttpResponse:
#     """Execute user processing logic and invoke Persister."""
#     event = req.get_json()
#
#     # YOUR process() FUNCTION IS CALLED HERE:
#     processed_event = process(event)  # <-- YOUR CODE RUNS HERE
#
#     # Then the result is sent to the Persister:
#     _invoke_persister(processed_event)
#
#     return func.HttpResponse(json.dumps({"status": "processed"}), status_code=200)
# ---------------------------------------------

# Example Event:
# {
#   "iotDeviceId": "temperature-sensor-1",
#   "time": "",
#   "temperature": 28
# }

def process(event):
    """
    Process the incoming IoT event.
    This function is called by the system wrapper (processor_wrapper).
    Return the modified event to be passed to the Persister.
    
    Args:
        event: IoT telemetry event dict
        
    Returns:
        dict: Modified event to persist
    """
    # Example Logic:
    # event["temperature_f"] = event["temperature"] * 1.8 + 32
    
    return event
