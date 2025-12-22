"""
Event-Feedback Wrapper AWS Lambda.

Calls user-defined event-feedback Lambda and sends result to IoT device.

Architecture:
    Event-Checker → Event-Feedback Wrapper → Lambda Invoke → User Function → Wrapper → IoT Device
"""
import json
import logging
import os
import boto3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Lazy-loaded environment variables
_iot_client = None
_lambda_client = None
_event_feedback_lambda_name = None


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

def _get_lambda_client():
    """Lazy initialization of Lambda client."""
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client('lambda')
    return _lambda_client

def _get_event_feedback_lambda_name():
    """Lazy load event feedback Lambda name."""
    global _event_feedback_lambda_name
    if _event_feedback_lambda_name is None:
        _event_feedback_lambda_name = os.environ.get("EVENT_FEEDBACK_LAMBDA_NAME", "").strip()
    return _event_feedback_lambda_name


def lambda_handler(event, context):
    """Execute user processing logic and send feedback to IoT device."""
    logger.info("Event-Feedback Wrapper: Executing user logic...")
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        detail = event["detail"]
        payload = detail["payload"]  # Extract payload for user processing
        iot_device_id = detail["iotDeviceId"]
        
        # 1. Call User Event-Feedback Lambda
        lambda_name = _get_event_feedback_lambda_name()
        if not lambda_name:
            logger.warning("EVENT_FEEDBACK_LAMBDA_NAME not set - using passthrough")
            processed_payload = payload
        else:
            try:
                logger.info(f"Invoking user event-feedback Lambda: {lambda_name}")
                response = _get_lambda_client().invoke(
                    FunctionName=lambda_name,
                    InvocationType="RequestResponse",
                    Payload=json.dumps(payload).encode("utf-8")
                )
                processed_payload = json.loads(response['Payload'].read().decode("utf-8"))
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
