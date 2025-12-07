import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

client = boto3.client('iot-data')

def lambda_handler(event, context):
    logger.info("Received event: " + json.dumps(event))

    try:
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
    except Exception as e:
        logger.error(f"Event Feedback Failed: {e}")
        # Return error status to caller (if synchronous invocation)
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }
    
    return {
        'statusCode': 200,
        'body': json.dumps('Feedback sent!')
    }
