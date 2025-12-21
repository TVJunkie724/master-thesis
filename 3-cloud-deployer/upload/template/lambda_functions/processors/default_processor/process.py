# --- CONTEXT: System Wrapper (DO NOT EDIT) ---
# Your process() function is imported and called by the Processor wrapper.
# This shows what happens when your code is deployed:
#
# """Processor Wrapper - Processes IoT telemetry and sends to Persister."""
# import json
# import boto3
# from process import process  # <-- YOUR FUNCTION IS IMPORTED HERE
#
# lambda_client = boto3.client('lambda')
#
# def lambda_handler(event, context):
#     # YOUR process() FUNCTION IS CALLED HERE:
#     processed_event = process(event)  # <-- YOUR CODE RUNS HERE
#     
#     # Then the wrapper sends to Persister:
#     lambda_client.invoke(
#         FunctionName=PERSISTER_LAMBDA_NAME,
#         InvocationType='Event',
#         Payload=json.dumps(processed_event)
#     )
# ---------------------------------------------

# --- INPUT/OUTPUT SCHEMA ---
# Input: IoT telemetry event dict
# {
#   "iotDeviceId": "temperature-sensor-1",
#   "time": "2025-12-21T22:00:00Z",
#   "temperature": 28
# }
#
# Output: Modified event dict (passed to Persister)
# {
#   "iotDeviceId": "temperature-sensor-1",
#   "time": "2025-12-21T22:00:00Z",
#   "temperature": 28,
#   "temperature_f": 82.4  # Added by user logic
# }

def process(event: dict) -> dict:
    """
    Process the incoming IoT event.
    
    This is where you add your custom processing logic.
    The event is then automatically sent to the Persister.
    
    Args:
        event: IoT telemetry event dict
        
    Returns:
        dict: Processed event (can be modified or returned as-is)
    """
    # Example: Pass through without modification
    return event
