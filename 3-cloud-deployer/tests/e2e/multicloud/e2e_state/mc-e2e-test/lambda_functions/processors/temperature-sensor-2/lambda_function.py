"""User Processor AWS Lambda for temperature-sensor-2."""
import json


def process(event):
    payload = event.copy()
    payload["temperature"] = 30
    return payload

def lambda_handler(event, context):
    """Process incoming IoT event."""
    
    # === YOUR PROCESSING LOGIC HERE ===
    processed_event = process(event)
    # ==================================
    
    return processed_event
