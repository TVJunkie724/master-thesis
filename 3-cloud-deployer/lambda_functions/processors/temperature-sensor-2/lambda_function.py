import json
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
  logger.info("Received event: " + json.dumps(event))

  # Processing logic for temp sensor 2 (e.g. converting unit or validating)
  # Mimicking behavior: Just passing through or doing simple check
  for record in event:
    if "temperature" in record and record["temperature"] > 100:
      logger.warning(f"High temp detected: {record['temperature']}")
  
  return event
