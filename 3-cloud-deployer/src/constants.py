from pathlib import Path

#--------------------------------------------------------------------
# Configuration file paths
#--------------------------------------------------------------------
 

IOT_DATA_DIR_NAME = "iot_devices_auth"
LAMBDA_FUNCTIONS_DIR_NAME = "lambda_functions"
EVENT_ACTIONS_DIR_NAME = "event_actions"
PROJECT_UPLOAD_DIR_NAME = "upload"

DEFAULT_PROJECT_NAME = "template"

CONFIG_FILE = "config.json"
CONFIG_IOT_DEVICES_FILE = "config_iot_devices.json"
CONFIG_EVENTS_FILE = "config_events.json"
CONFIG_HIERARCHY_FILE = "config_hierarchy.json"
CONFIG_CREDENTIALS_FILE = "config_credentials.json"
CONFIG_PROVIDERS_FILE = "config_providers.json"

REQUIRED_CONFIG_FILES = [
    CONFIG_FILE,
    CONFIG_IOT_DEVICES_FILE,
    CONFIG_EVENTS_FILE,
    CONFIG_HIERARCHY_FILE,
    CONFIG_CREDENTIALS_FILE,
    CONFIG_PROVIDERS_FILE
]

REQUIRED_CREDENTIALS_FIELDS = {
    "aws": ["aws_access_key_id", "aws_secret_access_key", "aws_region"],
    "azure": ["azure_subscription_id", "azure_client_id", "azure_client_secret", "azure_tenant_id", "azure_region"],
    "google": ["gcp_project_id", "gcp_credentials_file", "gcp_region"]
} 

