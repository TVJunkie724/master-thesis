import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('iot-data')

def lambda_handler(event, context):
    logger.info("Received event: " + json.dumps(event))

    detail = event["detail"]
    payload = detail["payload"]
    iot_device_id = detail["iotDeviceId"]
    
    topic = f"{detail['digitalTwinName']}-{iot_device_id}"

    # Publish feedback to IoT Core
    client.publish(
        topic=topic,
        qos=1,
        payload=json.dumps({"message": payload})
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps('Feedback sent!')
    }
