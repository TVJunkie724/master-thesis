"""
GCP IoT Device Simulator - Global configuration.
Mirrors pattern from aws/globals.py.

Note: GCP uses Pub/Sub for IoT messaging (IoT Core deprecated Jan 2023).
"""
import json
import os
import re

_SAFE_DEVICE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

class Config:
    def __init__(self):
        self.project_id = None
        self.topic_name = None
        self.device_id = None
        self.service_account_key_path = None
        self.payload_path = None
        self.configs_root = None
        self.config_filename = None

config = Config()

def load_config(config_path: str):
    """Load configuration from JSON file.
    
    Resolves relative paths (service_account_key_path, payload_path)
    relative to the directory that contains the config file.
    """
    config_dir = os.path.dirname(os.path.abspath(config_path))
    
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    def _resolve(path, default):
        p = path if path else default
        if not os.path.isabs(p):
            p = os.path.normpath(os.path.join(config_dir, p))
        return p
    
    config.project_id = data['project_id']
    config.topic_name = data['topic_name']
    config.device_id = data['device_id']
    config.service_account_key_path = _resolve(
        data.get('service_account_key_path'), 'service_account.json',
    )
    config.payload_path = _resolve(
        data.get('payload_path'), '../payloads.json',
    )
    if os.path.basename(config_path) == "config_generated.json":
        config.configs_root = os.path.dirname(config_dir)
        config.config_filename = "config_generated.json"
    else:
        config.configs_root = os.path.join(config_dir, "configs")
        config.config_filename = "config.json"


def get_device_config_path(device_id):
    if not isinstance(device_id, str) or not _SAFE_DEVICE_ID.fullmatch(device_id) or ".." in device_id:
        raise ValueError("Invalid simulator device ID")
    return os.path.join(config.configs_root, device_id, config.config_filename)
