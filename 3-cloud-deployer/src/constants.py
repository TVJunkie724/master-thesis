from pathlib import Path

#--------------------------------------------------------------------
# Configuration file paths
#--------------------------------------------------------------------
 

IOT_DATA_DIR_NAME = "iot_devices_auth"
LAMBDA_FUNCTIONS_DIR_NAME = "lambda_functions"
EVENT_ACTIONS_DIR_NAME = "event_actions"

REQUIRED_CONFIG_FILES = [
    "config.json",
    "config_iot_devices.json",
    "config_events.json",
    "config_hierarchy.json",
    "config_credentials.json",
    "config_providers.json"
]

REQUIRED_CREDENTIALS_FIELDS = {
    "aws": ["aws_access_key_id", "aws_secret_access_key", "aws_region"],
    "azure": ["azure_subscription_id", "azure_client_id", "azure_client_secret", "azure_tenant_id", "azure_region"],
    "google": ["gcp_project_id", "gcp_credentials_file", "gcp_region"]
} 

