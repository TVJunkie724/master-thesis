import globals
import aws.globals_aws as globals_aws
from datetime import datetime, timezone
import json

def post_init_values_to_iot_core():
  # Topic structure as per original logic, using the config topic
  # But Original used: globals.dispatcher_iot_rule_topic() which calls config[...]
  # Let's see globals_aws.py: dispatcher_iot_rule_topic is NOT there.
  # It was in Original src/globals.py. 
  # In Target src/aws/globals_aws.py, we have `dispatcher_iot_rule_name` etc. but maybe not the topic helper in the same way?
  # Wait, in Step 118, `globals_aws.py` has `dispatcher_iot_rule_name` (line 118) but `dispatcher_iot_rule_topic` is missing.
  # Original `dispatcher_iot_rule_topic` was: return config["digital_twin_name"] + "/iot-data"
  # So I will inline that logic or use the same string construction.
  
  topic = globals.config["digital_twin_name"] + "/iot-data"

  for iot_device in globals.config_iot_devices:
    # Check for initValue in properties
    has_init = any("initValue" in prop for prop in iot_device["properties"])
    if not has_init:
      continue

    payload = {
      "iotDeviceId": iot_device["id"],
      "time": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    }

    for property in iot_device["properties"]:
      # Only include properties that HAVE an initValue? Or all? 
      # Original code: payload[property["name"]] = property.get("initValue", None)
      # It included all properties, setting None if propery didn't have initValue.
      # But wait, logic: `if not has_init: continue` meaning if NO property has initValue, skip device.
      # If at least one has, then iterate ALL properties.
      payload[property["name"]] = property.get("initValue", None)

    globals_aws.aws_iot_data_client.publish(
        topic=topic,
        qos=1,
        payload=json.dumps(payload).encode("utf-8")
    )
    log(f"Posted init values for IoT device id: {iot_device['id']}")

def log(string):
    if globals.logger:
        globals.logger.info(f"Init Value Deployer: {string}")
    else:
        print(f"Init Value Deployer: {string}")

def deploy():
  post_init_values_to_iot_core()

def destroy():
  pass

def info():
  pass
