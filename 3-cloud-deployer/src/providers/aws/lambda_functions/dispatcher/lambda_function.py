import json
import os
import boto3


DIGITAL_TWIN_INFO = json.loads(os.environ.get("DIGITAL_TWIN_INFO", None))
# Target function suffix is used to identify the target function, can be either "-processor" or "-connector"
TARGET_FUNCTION_SUFFIX = os.environ.get("TARGET_FUNCTION_SUFFIX", "-processor")

lambda_client = boto3.client("lambda")


def lambda_handler(event, context):
    print("Hello from Dispatcher!")
    print("Event: " + json.dumps(event))

    try:
        # Extract ID
        device_id = event.get("iotDeviceId")
        if not device_id:
             print("Error: 'iotDeviceId' missing in event.")
             return # Stop processing if key data is missing

        target_suffix = os.environ.get("TARGET_FUNCTION_SUFFIX", "-processor")
        
        # Construct target function name
        # FORMAT: {twin_name}-{device_id}{target_suffix}
        twin_name = DIGITAL_TWIN_INFO["config"]["digital_twin_name"]
        function_name = f"{twin_name}-{device_id}{target_suffix}"
        
        print(f"Dispatching to: {function_name}")
        
        # Invoke synchronously (RequestResponse) or async (Event)?
        # Dispatcher is typically fire-and-forget for the device, but we might want to wait for L2 ack.
        # Current design: Event (Async) to decouple.
        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(event).encode("utf-8")
        )
        print("Dispatch successful.")

    except Exception as e:
        print(f"Dispatcher Error: {e}")
        # Optionally: Sending to DLQ or Error SNS topic could happen here.
        raise e # Re-raise to trigger Lambda retry behavior.
