from pathlib import Path

#--------------------------------------------------------------------
# Configuration file paths
#--------------------------------------------------------------------
BASE_CONFIG_DIR = Path("upload")

CONFIG_FILE_PATH = BASE_CONFIG_DIR / "config.json"
CREDENTIALS_FILE_PATH = BASE_CONFIG_DIR / "config_credentials.json"
GCP_CREDENTIALS_BASE_FILE_PATH = BASE_CONFIG_DIR 

IOT_DATA_PATH = "iot_devices_auth"
LAMBDA_FUNCTIONS_PATH = "upload/lambda_functions"
EVENT_ACTIONS_PATH = "upload/event_actions"

REQUIRED_CREDENTIALS_FIELDS = {
    "aws": ["aws_access_key_id", "aws_secret_access_key", "aws_region"],
    "azure": ["azure_subscription_id", "azure_client_id", "azure_client_secret", "azure_tenant_id", "azure_region"],
    "google": ["gcp_project_id", "gcp_credentials_file", "gcp_region"]
} 

