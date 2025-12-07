from pathlib import Path

# ==========================================
# 1. Configuration Filenames
# ==========================================
CONFIG_FILE = "config.json"
CONFIG_IOT_DEVICES_FILE = "config_iot_devices.json"
CONFIG_EVENTS_FILE = "config_events.json"
CONFIG_HIERARCHY_FILE = "config_hierarchy.json"
CONFIG_CREDENTIALS_FILE = "config_credentials.json"
CONFIG_PROVIDERS_FILE = "config_providers.json"
CONFIG_OPTIMIZATION_FILE = "config_optimization.json"
CONFIG_INTER_CLOUD_FILE = "config_inter_cloud.json"

REQUIRED_CONFIG_FILES = [
    CONFIG_FILE,
    CONFIG_IOT_DEVICES_FILE,
    CONFIG_EVENTS_FILE,
    CONFIG_HIERARCHY_FILE,
    CONFIG_CREDENTIALS_FILE,
    CONFIG_PROVIDERS_FILE
]

# Keys required in specific config files
CONFIG_SCHEMAS = {
    CONFIG_FILE: ["digital_twin_name", "digital_twin_description"],
    CONFIG_IOT_DEVICES_FILE: ["iotDeviceId", "description", "manufacturer", "sensors"],
    CONFIG_EVENTS_FILE: ["name", "paramName", "condition", "threshold", "action"],
    CONFIG_HIERARCHY_FILE: ["name", "type"],
    CONFIG_OPTIMIZATION_FILE: ["result"],
    CONFIG_CREDENTIALS_FILE: [], # Dynamic check based on provider
    CONFIG_PROVIDERS_FILE: ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider"],
    CONFIG_INTER_CLOUD_FILE: ["connections"]
}

REQUIRED_CREDENTIALS_FIELDS = {
    "aws": ["aws_access_key_id", "aws_secret_access_key", "aws_region"],
    "azure": ["azure_subscription_id", "azure_tenant_id", "azure_client_id", "azure_client_secret", "azure_location"],
    "google": ["google_project_id", "google_region", "google_zone", "google_application_credentials"]
}

# ==========================================
# 2. Directory Names
# ==========================================
IOT_DATA_DIR_NAME = "iot_devices_auth"
LAMBDA_FUNCTIONS_DIR_NAME = "lambda_functions"
EVENT_ACTIONS_DIR_NAME = "event_actions"
PROJECT_UPLOAD_DIR_NAME = "upload"
STATE_MACHINES_DIR_NAME = "state_machines"

# ==========================================
# 3. State Machine Definitions
# ==========================================
AWS_STATE_MACHINE_FILE = "aws_step_function.json"
AZURE_STATE_MACHINE_FILE = "azure_logic_app.json"
GOOGLE_STATE_MACHINE_FILE = "google_cloud_workflow.json"

STATE_MACHINE_SIGNATURES = {
    AWS_STATE_MACHINE_FILE: ["StartAt", "States"],
    AZURE_STATE_MACHINE_FILE: ["definition"], 
    GOOGLE_STATE_MACHINE_FILE: ["main", "steps"]
}

# ==========================================
# 4. Defaults
# ==========================================
DEFAULT_PROJECT_NAME = "template"

# ==========================================
# 6. Layer & Function Mappings
# ==========================================
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
