# --- CONTEXT: System Wrapper (DO NOT EDIT) ---
# Your process() function is imported and called by this Cloud Function.
# This shows what happens when your code is deployed:
#
# """Processor Wrapper GCP Cloud Function - Merges user logic with system pipeline."""
# import json
# import os
# import logging
# import requests
# import functions_framework
# from process import process  # <-- YOUR FUNCTION IS IMPORTED HERE
#
# PERSISTER_FUNCTION_URL = os.environ.get("PERSISTER_FUNCTION_URL")
#
# def _invoke_persister(payload: dict) -> None:
#     """Invoke Persister function via HTTP POST."""
#     response = requests.post(PERSISTER_FUNCTION_URL, json=payload, timeout=30)
#     logging.info(f"Persister invoked: {response.status_code}")
#
# @functions_framework.http
# def processor(request):
#     """Execute user processing logic and invoke Persister."""
#     event = request.get_json()
#
#     # YOUR process() FUNCTION IS CALLED HERE:
#     processed_event = process(event)  # <-- YOUR CODE RUNS HERE
#
#     # Then the result is sent to the Persister:
#     _invoke_persister(processed_event)
#
#     return (json.dumps({"status": "processed"}), 200, {"Content-Type": "application/json"})
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
