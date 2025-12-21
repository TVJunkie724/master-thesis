"""
Event-Feedback Wrapper AWS Lambda Function.

Merges user-defined processing logic with the IoT Core feedback pipeline.
Executes user logic and sends result to IoT device.

Architecture:
    Event-Checker → Event-Feedback (user logic) → IoT Device
"""
import json
import logging
import os
import boto3
from process import process  # User logic import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lazy-loaded environment variables
_iot_client = None


def _require_env(key: str) -> str:
    """Lazy load environment variable."""
    value = os.environ.get(key, "").strip()
    if not value:
        raise EnvironmentError(f"CRITICAL: {key} is required")
    return value

def _get_iot_client():
    """Lazy initialization of IoT Data client."""
    global _iot_client
    if _iot_client is None:
        _iot_client = boto3.client('iot-data')
    return _iot_client


def lambda_handler(event, context):
    """Execute user processing logic and send feedback to IoT device."""
    logger.info("Event-Feedback Wrapper: Executing user logic...")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        detail = event["detail"]
        payload = detail["payload"]  # Extract payload for user processing
        iot_device_id = detail["iotDeviceId"]
        
        # 1. Execute User Logic
        try:
            processed_payload = process(payload)
            logger.info(f"User Logic Complete. Result: {json.dumps(processed_payload)}")
        except Exception as e:
            logger.error(f"[USER_LOGIC_ERROR] Processing failed: {e}")
            raise e
        
        # 2. Build topic and send to IoT Device
        topic = f"{detail['digitalTwinName']}-{iot_device_id}"
        
        client = _get_iot_client()
        client.publish(
            topic=topic,
            qos=0,
            payload=json.dumps({"message": processed_payload})
        )
        
        logger.info("Feedback sent to device.")
        return {
            "statusCode": 200,
            "body": json.dumps("Feedback sent!")
        }
        
    except Exception as e:
        logger.error(f"Event Feedback Failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps(f"Error: {str(e)}")
        }
