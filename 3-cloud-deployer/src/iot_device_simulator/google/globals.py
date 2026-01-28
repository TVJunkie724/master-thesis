"""
GCP IoT Device Simulator - Global configuration.
Mirrors pattern from aws/globals.py.

Note: GCP uses Pub/Sub for IoT messaging (IoT Core deprecated Jan 2023).
"""
import json
import os

class Config:
    def __init__(self):
        self.project_id = None
        self.topic_name = None
        self.device_id = None
        self.service_account_key_path = None
        self.payload_path = None

config = Config()

def load_config(config_path: str):
    """Load configuration from JSON file."""
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    config.project_id = data['project_id']
    config.topic_name = data['topic_name']
    config.device_id = data['device_id']
    config.service_account_key_path = data.get('service_account_key_path', 'service_account.json')
    config.payload_path = data.get('payload_path', '../payloads.json')
