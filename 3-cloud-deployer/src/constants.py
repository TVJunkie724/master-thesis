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

# Twin Hierarchy Files (provider-specific, optional)
TWIN_HIERARCHY_DIR_NAME = "twin_hierarchy"
AWS_HIERARCHY_FILE = "aws_hierarchy.json"
AZURE_HIERARCHY_FILE = "azure_hierarchy.json"

REQUIRED_CONFIG_FILES = [
    CONFIG_FILE,
    CONFIG_IOT_DEVICES_FILE,
    CONFIG_EVENTS_FILE,
    CONFIG_CREDENTIALS_FILE,
    CONFIG_PROVIDERS_FILE
]

# Optional config files (not required in zip validation)
OPTIONAL_CONFIG_FILES = [
    CONFIG_OPTIMIZATION_FILE,
    CONFIG_INTER_CLOUD_FILE
]

# Keys required in specific config files
CONFIG_SCHEMAS = {
    CONFIG_FILE: ["digital_twin_name", "hot_storage_size_in_days", "cold_storage_size_in_days", "mode"],
    CONFIG_IOT_DEVICES_FILE: ["id", "properties"],  # Matches template: id, properties
    CONFIG_EVENTS_FILE: ["condition", "action"],  # Matches template: condition, action
    CONFIG_OPTIMIZATION_FILE: ["result"],
    CONFIG_CREDENTIALS_FILE: [], # Dynamic check based on provider
    CONFIG_PROVIDERS_FILE: ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider", "layer_4_provider"],
    CONFIG_INTER_CLOUD_FILE: ["connections"]
}

# Twin Hierarchy Validation Schemas (provider-specific)
AWS_HIERARCHY_SCHEMA = ["type"]  # Each item must have 'type' (entity or component)
AZURE_HIERARCHY_SCHEMA = {
    "header": ["fileVersion"],
    "models": ["@id", "@type", "@context"],
    "twins": ["$dtId", "$metadata"],
    "relationships": ["$dtId", "$targetId", "$relationshipName"]
}

REQUIRED_CREDENTIALS_FIELDS = {
    "aws": ["aws_access_key_id", "aws_secret_access_key", "aws_region"],
    "azure": ["azure_subscription_id", "azure_tenant_id", "azure_client_id", "azure_client_secret", "azure_region", "azure_region_iothub", "azure_region_digital_twin"],
    # GCP: credentials_file and region are always required
    # Either gcp_project_id (private) OR gcp_billing_account (org) must be provided - validated in code
    "gcp": ["gcp_credentials_file", "gcp_region"]
}

# ==========================================
# Azure Region Validation
# ==========================================
# Regions known to NOT support Consumption Plan (Y1) with Linux OS
# Based on empirical testing (December 2025)
# Note: These regions may support Flex Consumption (FC1) but not traditional Y1+Linux
AZURE_UNSUPPORTED_REGIONS_Y1_LINUX = [
    "italynorth",  # Confirmed: Only supports Flex Consumption (FC1), not Y1+Linux
]

# Recommended Azure regions for Consumption Plan (Y1) with Linux
# These regions have been verified to support Y1+Linux combination
AZURE_RECOMMENDED_REGIONS_Y1_LINUX = [
    "westeurope",          # Primary recommendation - full support, high capacity
    "northeurope",         # Alternative - Dublin, Ireland
    "francecentral",       # Alternative - Paris, France  
    "germanywestcentral",  # Alternative - Frankfurt, Germany
    "uksouth",             # Alternative - London, UK
    "eastus",              # Alternative - Virginia, USA
    "westus2",             # Alternative - Washington, USA
]


# ==========================================
# 2. Directory Names
# ==========================================
IOT_DATA_DIR_NAME = "iot_devices_auth"
LAMBDA_FUNCTIONS_DIR_NAME = "lambda_functions"
EVENT_ACTIONS_DIR_NAME = "event_actions"
PROJECT_UPLOAD_DIR_NAME = "upload"
STATE_MACHINES_DIR_NAME = "state_machines"

# Project metadata and versioning
PROJECT_INFO_FILE = "project_info.json"
PAYLOADS_FILE = "payloads.json"
PROJECT_VERSIONS_DIR_NAME = "versions"
IOT_DEVICE_SIMULATOR_DIR_NAME = "iot_device_simulator"

AWS_CORE_LAMBDA_DIR_NAME = "src/providers/aws/lambda_functions"

# ==========================================
# 3. State Machine Definitions
# ==========================================
AWS_STATE_MACHINE_FILE = "aws_step_function.json"
AZURE_STATE_MACHINE_FILE = "azure_logic_app.json"
GOOGLE_STATE_MACHINE_FILE = "google_cloud_workflow.json"

STATE_MACHINE_SIGNATURES = {
    AWS_STATE_MACHINE_FILE: ["StartAt", "States"],
    AZURE_STATE_MACHINE_FILE: ["definition"], 
    GOOGLE_STATE_MACHINE_FILE: ["main"]  # 'steps' is inside 'main', not top-level
}

# ==========================================
# 4. Defaults
# ==========================================
DEFAULT_PROJECT_NAME = "template"

# ==========================================
# 5. AWS Policy ARNs
# ==========================================
AWS_POLICY_LAMBDA_BASIC_EXECUTION = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
AWS_POLICY_LAMBDA_ROLE = "arn:aws:iam::aws:policy/service-role/AWSLambdaRole"
AWS_POLICY_DYNAMODB_FULL_ACCESS = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess_v2"
AWS_POLICY_DYNAMODB_READ_ONLY = "arn:aws:iam::aws:policy/AmazonDynamoDBReadOnlyAccess"
AWS_POLICY_S3_FULL_ACCESS = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
AWS_POLICY_S3_READ_ONLY = "arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess"
AWS_POLICY_LAMBDA_READ_ONLY = "arn:aws:iam::aws:policy/AWSLambda_ReadOnlyAccess"
AWS_POLICY_STEP_FUNCTIONS_FULL_ACCESS = "arn:aws:iam::aws:policy/AWSStepFunctionsFullAccess"
AWS_POLICY_IOT_DATA_ACCESS = "arn:aws:iam::aws:policy/AWSIoTDataAccess"
AWS_POLICY_ADMIN_ACCESS = "arn:aws:iam::aws:policy/AdministratorAccess"

# ==========================================
# 6. AWS Resource Constants
# ==========================================
AWS_CRON_HOT_TO_COLD = "cron(0 12 * * ? *)"
AWS_CRON_COLD_TO_ARCHIVE = "cron(0 18 * * ? *)"

# Aliases for layer files
AWS_HOT_COLD_SCHEDULE = AWS_CRON_HOT_TO_COLD
AWS_COLD_ARCHIVE_SCHEDULE = AWS_CRON_COLD_TO_ARCHIVE


# ==========================================
# 8. Scene Asset Constants (3D Visualization)
# ==========================================
SCENE_ASSETS_DIR_NAME = "scene_assets"
SCENE_GLB_FILE = "scene.glb"
SCENE_JSON_FILE = "scene.json"  # AWS TwinMaker
AZURE_SCENE_CONFIG_FILE = "3DScenesConfiguration.json"

# Required scene files per provider (when needs3DModel=true)
SCENE_REQUIRED_FILES = {
    "aws": [
        f"{SCENE_ASSETS_DIR_NAME}/aws/{SCENE_GLB_FILE}",
        f"{SCENE_ASSETS_DIR_NAME}/aws/{SCENE_JSON_FILE}"
    ],
    "azure": [
        f"{SCENE_ASSETS_DIR_NAME}/azure/{SCENE_GLB_FILE}",
        f"{SCENE_ASSETS_DIR_NAME}/azure/{AZURE_SCENE_CONFIG_FILE}"
    ]
}
