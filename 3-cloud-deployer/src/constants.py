from pathlib import Path


#--------------------------------------------------------------------
# Configuration file paths
#--------------------------------------------------------------------
CONFIG_FILE = "config.json"
CONFIG_IOT_DEVICES_FILE = "config_iot_devices.json"
CONFIG_EVENTS_FILE = "config_events.json"
CONFIG_HIERARCHY_FILE = "config_hierarchy.json"
CONFIG_CREDENTIALS_FILE = "config_credentials.json"
CONFIG_PROVIDERS_FILE = "config_providers.json"
CONFIG_OPTIMIZATION_FILE = "config_optimization.json"

IOT_DATA_DIR_NAME = "iot_devices_auth"
LAMBDA_FUNCTIONS_DIR_NAME = "lambda_functions"
EVENT_ACTIONS_DIR_NAME = "event_actions"
PROJECT_UPLOAD_DIR_NAME = "upload"
STATE_MACHINES_DIR_NAME = "state_machines"

AWS_STATE_MACHINE_FILE = "aws_step_function.json"
AZURE_STATE_MACHINE_FILE = "azure_logic_app.json"
GOOGLE_STATE_MACHINE_FILE = "google_cloud_workflow.json"

STATE_MACHINE_SIGNATURES = {
    AWS_STATE_MACHINE_FILE: ["StartAt", "States"],
    AZURE_STATE_MACHINE_FILE: ["definition"], 
    GOOGLE_STATE_MACHINE_FILE: ["main", "steps"]
}

DEFAULT_PROJECT_NAME = "template"

REQUIRED_CONFIG_FILES = [
    CONFIG_FILE,
    CONFIG_IOT_DEVICES_FILE,
    CONFIG_EVENTS_FILE,
    CONFIG_HIERARCHY_FILE,
    CONFIG_CREDENTIALS_FILE,
    CONFIG_PROVIDERS_FILE,
    CONFIG_OPTIMIZATION_FILE
]

REQUIRED_CREDENTIALS_FIELDS = {
    "aws": ["aws_access_key_id", "aws_secret_access_key", "aws_region"],
    "azure": ["azure_subscription_id", "azure_tenant_id", "azure_client_id", "azure_client_secret", "azure_location"],
    "google": ["google_project_id", "google_region", "google_zone", "google_application_credentials"]
}

# Config Schemas for Validation
CONFIG_SCHEMAS = {
    CONFIG_FILE: ["digital_twin_name", "auth_files_path", "endpoint", "root_ca_cert_path", "topic", "payload_file_path", "hot_storage_size_in_days", "cold_storage_size_in_days", "mode"],
    CONFIG_IOT_DEVICES_FILE: ["id", "type"],  # List of objects
    CONFIG_EVENTS_FILE: ["condition", "action"], # List of objects
    CONFIG_OPTIMIZATION_FILE: ["result"], # Nested: inputParamsUsed
    CONFIG_HIERARCHY_FILE: ["id", "type"], # Recursive entity check
    CONFIG_CREDENTIALS_FILE: [], # Validated dynamically
    CONFIG_PROVIDERS_FILE: [] # Validated dynamically
}


# Mapping functions to their provider layer for code validation
FUNCTION_LAYER_MAPPING = {
    "dispatcher": "layer_1_provider",
    "persister": "layer_2_provider",
    "event-checker": "layer_2_provider",
    "event-feedback": "layer_2_provider",
    "hot-reader": "layer_3_hot_provider",
    "hot-to-cold-mover": "layer_3_hot_provider",
    "cold-to-archive-mover": "layer_3_cold_provider"
}
