# --- CONTEXT: System Wrapper (DO NOT EDIT) ---
# from process import process
# import boto3...
# def lambda_handler(event, context):
#     result = process(event)
#     # invoke persister...
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
    This function is called by the system wrapper.
    Return the modified event to be passed to the Persister.
    """
    # Example Logic:
    # event["temperature_f"] = event["temperature"] * 1.8 + 32
    
    return event
