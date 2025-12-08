"""
IoT Device Simulator - MQTT Transmission.

This module handles MQTT communication with AWS IoT Core,
sending test payloads from the configured payloads.json file.

Migration Status:
    - Uses globals for device certificates and endpoint config.
    - This is a standalone utility - no migration needed.
"""

import globals
import os
import json
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from datetime import datetime, timezone


payload_index = 0



def send_mqtt(payload):
  iot_device_id = globals.config["device_id"] # Use configured device ID for connection
  
  # Optional: Check if payload ID matches device ID
  if payload.get("iotDeviceId") != iot_device_id:
      print(f"WARNING: Payload iotDeviceId '{payload.get('iotDeviceId')}' does not match configured device '{iot_device_id}'")

  client = AWSIoTMQTTClient(iot_device_id)
  client.configureEndpoint(globals.config["endpoint"], 8883)
  client.configureCredentials(globals.config["root_ca_path"], globals.config["key_path"], globals.config["cert_path"])

  topic = globals.config["topic"]

  client.connect()
  client.publish(topic, json.dumps(payload), 1)
  client.disconnect()

  print(f"Message sent! Topic: {topic}, Payload: {payload}")


def send():
  global payload_index

  payloads_path = globals.config["payload_path"]

  with open(payloads_path, "r", encoding="utf-8") as f:
    payloads = json.load(f)

  if payload_index >= len(payloads):
    payload_index = 0

  payload = payloads[payload_index]
  payload_index += 1

  if "time" not in payload or payload["time"] == "":
    payload["time"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

  send_mqtt(payload)
