"""
Quick script to send a test IoT message to the deployed infrastructure.
Run this inside the Docker container after enabling Application Insights.
"""
import os
import sys
import json
import time

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from azure.iot.device import IoTHubDeviceClient, Message

def send_test_message():
    """Send a test message to Azure IoT Hub."""
    
    # Get connection string from Terraform state or environment
    # The E2E test gets this from the terraform output
    connection_string = os.environ.get("IOT_DEVICE_CONNECTION_STRING")
    
    if not connection_string:
        print("ERROR: Set IOT_DEVICE_CONNECTION_STRING environment variable")
        print("\nGet it from Azure Portal:")
        print("  IoT Hub -> Devices -> pressure-sensor-1 -> Primary Connection String")
        print("\nOr from terraform output:")
        print("  terraform output -raw azure_iot_device_connection_string_pressure_sensor_1")
        return
    
    print(f"[IOT] Connecting to IoT Hub...")
    client = IoTHubDeviceClient.create_from_connection_string(connection_string)
    
    # Create test message
    payload = {
        "iotDeviceId": "pressure-sensor-1",
        "temperature": 42.5,
        "pressure": 1013.25,
        "humidity": 65.0,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    message = Message(json.dumps(payload))
    message.content_type = "application/json"
    message.content_encoding = "utf-8"
    
    print(f"[IOT] Sending message: {payload}")
    client.send_message(message)
    print("[IOT] ✓ Message sent successfully!")
    print("\n[IOT] Check Azure Function App logs in ~30 seconds:")
    print("  1. Go to Function App: tf-e2e-az-l2-functions")
    print("  2. Click 'Functions' -> 'dispatcher' -> 'Monitor'")
    print("  3. Check 'Invocations' tab for execution logs")
    
    client.disconnect()

if __name__ == "__main__":
    send_test_message()
