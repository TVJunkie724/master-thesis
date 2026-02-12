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
    
    # Fallback: if resolved SA path doesn't exist, try gcp_credentials.json
    # in the project upload root (two levels above the google device dir)
    if not os.path.exists(config.service_account_key_path):
        # config_dir = .../upload/<project>/iot_device_simulator/google/<device>
        # project root = config_dir/../../../  (go up 3 levels)
        project_root = os.path.normpath(os.path.join(config_dir, '..', '..', '..'))
        alt = os.path.join(project_root, 'gcp_credentials.json')
        if os.path.exists(alt):
            config.service_account_key_path = alt
