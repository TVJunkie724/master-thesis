# --- CONTEXT: System Wrapper (DO NOT EDIT) ---
# Your process() function is imported and called by the Event-Feedback wrapper.
# This shows what happens when your code is deployed:
#
# """Event-Feedback Wrapper - Sends feedback to IoT devices."""
# import json
# import boto3
# from process import process  # <-- YOUR FUNCTION IS IMPORTED HERE
#
# client = boto3.client('iot-data')
#
# def lambda_handler(event, context):
#     detail = event["detail"]
#     payload = detail["payload"]  # Extract payload for user processing
#     
#     # YOUR process() FUNCTION IS CALLED HERE:
#     processed_payload = process(payload)  # <-- YOUR CODE RUNS HERE
#     
#     # Then the wrapper wraps and sends to device:
#     topic = f"{detail['digitalTwinName']}-{detail['iotDeviceId']}"
#     client.publish(topic=topic, payload=json.dumps({"message": processed_payload}))
# ---------------------------------------------

# --- INPUT/OUTPUT SCHEMA ---
# Input: Feedback payload dict from event-checker
# {
#   "message": "High Temp Warning",        # Static message from config
#   "actual_value": 35.2,                  # Runtime value that triggered event
#   "threshold": 30.0,                     # Threshold from condition
#   "condition": "entity.sensor.temp == 30" # Full condition string
# }
#
# Output: Processed payload dict (sent to IoT device as {"message": <your output>})
# {
#   "command": "REDUCE_SPEED",
#   "target_temp": 25,
#   "reason": "Temperature 35.2°C exceeded threshold 30.0°C"
# }

def process(payload: dict) -> dict:
    """
    Process the feedback payload before sending to device.
    
    Args:
        payload: Feedback payload from event-checker containing:
            - message: Static message from config_events.json
            - actual_value: Runtime value that triggered the event
            - threshold: Threshold value from condition
            - condition: Full condition string
        
    Returns:
        dict: Processed payload (wrapper will wrap as {"message": <your output>})
    """
    # Example: Pass through or transform
    return payload
