"""
High Temperature Callback 2 AWS Lambda Function.

Event action with MQTT feedback capability.
"""
import json
import logging
import os
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)


client = boto3.client('iot-data')

def lambda_handler(event, context):
    logger.info("Received event: " + json.dumps(event))
    
    # Callback logic 2
    detail = event["detail"]
    if "action" in detail and "feedback" in detail["action"]:
        feedback = detail["action"]["feedback"]
        payload = feedback["payload"]
        if feedback["type"] == "mqtt":
             iot_id = feedback.get("iotDeviceId", "unknown")
             topic = f"dt-feedback-{iot_id}" # Simplified topic logic
             client.publish(topic=topic, qos=1, payload=json.dumps(payload))

    return {
        'statusCode': 200,
        'body': json.dumps('Callback 2 executed')
    }
