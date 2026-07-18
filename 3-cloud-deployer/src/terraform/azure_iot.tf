# Azure L1 IoT Layer (Data Acquisition)
#
# This file creates the L1 layer infrastructure for IoT data acquisition.
# L1 receives telemetry from IoT devices and dispatches to L2 processing.
#
# Resources Created:
# - IoT Hub (S1 Standard): Device connectivity and telemetry ingestion
# - RBAC Role Assignments: Managed Identity access to IoT Hub
# - App Service Plan (Consumption Y1): Serverless hosting for L1 functions
# - Linux Function App: Hosts dispatcher function
#
# Functions Deployed:
# - Dispatcher: Receives IoT Hub events → routes to L2 (same or different cloud)
#
# Architecture:
#     IoT Devices → IoT Hub → Event Grid → Dispatcher Function → L2 Ingestion

# ==============================================================================
# Azure IoT Hub
# ==============================================================================

resource "azurerm_iothub" "main" {
  count               = var.layer_1_provider == "azure" ? 1 : 0
  name                = local.azure_iothub_name
  resource_group_name = azurerm_resource_group.main[0].name
  location            = local.azure_iothub_region

  sku {
    name     = var.azure_iot_hub_sku
    capacity = var.azure_iot_hub_capacity
  }

  tags = local.common_tags
}

# Data source to get the built-in iothubowner shared access policy connection string
# Used by E2E tests to verify device registration
data "azurerm_iothub_shared_access_policy" "iothubowner" {
  count               = var.layer_1_provider == "azure" ? 1 : 0
  name                = "iothubowner"
  resource_group_name = azurerm_resource_group.main[0].name
  iothub_name         = azurerm_iothub.main[0].name
}

# ==============================================================================
# RBAC: Managed Identity → IoT Hub Data Contributor
# ==============================================================================

resource "azurerm_role_assignment" "identity_iothub_contributor" {
  count                = var.layer_1_provider == "azure" ? 1 : 0
  scope                = azurerm_iothub.main[0].id
  role_definition_name = "IoT Hub Data Contributor"
  principal_id         = azurerm_user_assigned_identity.main[0].principal_id
}

# ==============================================================================
# L1 App Service Plan (Consumption - Serverless)
# ==============================================================================

resource "azurerm_service_plan" "l1" {
  count               = var.layer_1_provider == "azure" ? 1 : 0
  name                = local.azure_l1_plan_name
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  os_type             = "Linux"
  sku_name            = var.azure_l1_function_plan_sku

  tags = local.common_tags
}

# ==============================================================================
# L1 Function App (Dispatcher)
# ==============================================================================

resource "azurerm_linux_function_app" "l1" {
  count               = var.layer_1_provider == "azure" ? 1 : 0
  name                = local.azure_l1_functions_name
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.l1[0].id

  storage_account_name       = azurerm_storage_account.main[0].name
  storage_account_access_key = azurerm_storage_account.main[0].primary_access_key

  # Deploy function code via Terraform (enables EventGrid to find the dispatcher)
  zip_deploy_file = var.azure_l1_zip_path != "" ? var.azure_l1_zip_path : null

  # Enable SCM Basic Auth (required for zip_deploy_file)
  webdeploy_publish_basic_authentication_enabled = true
  ftp_publish_basic_authentication_enabled       = true

  # Managed Identity
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main[0].id]
  }

  site_config {
    application_stack {
      python_version = local.python_runtime_azure
    }
  }

  app_settings = {
    # Azure Functions runtime
    FUNCTIONS_WORKER_RUNTIME       = "python"
    FUNCTIONS_EXTENSION_VERSION    = "~4"
    AzureWebJobsStorage            = local.azure_storage_connection_string
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    ENABLE_ORYX_BUILD              = "true" # Required for remote pip install
    AzureWebJobsFeatureFlags       = "EnableWorkerIndexing"

    # Code version hash - triggers update-in-place when ZIP content changes
    FUNCTION_CODE_VERSION = var.azure_l1_zip_path != "" ? filemd5(var.azure_l1_zip_path) : ""

    # Required for Consumption Plan with zip deploy
    WEBSITE_CONTENTAZUREFILECONNECTIONSTRING = local.azure_storage_connection_string
    WEBSITE_CONTENTSHARE                     = local.azure_l1_content_share

    # IoT Hub connection (for Event Grid subscription)
    IOTHUB_CONNECTION_STRING = azurerm_iothub.main[0].event_hub_events_endpoint

    # Multi-cloud L1→L2: When Azure L1 sends to remote L2
    REMOTE_INGESTION_URL = var.layer_1_provider == "azure" && var.layer_2_provider != "azure" ? (
      var.layer_2_provider == "aws" ? try(aws_lambda_function_url.l0_ingestion[0].function_url, "") :
      var.layer_2_provider == "google" ? try(google_cloudfunctions2_function.ingestion[0].url, "") : ""
    ) : ""

    # Digital Twin info
    DIGITAL_TWIN_NAME = var.digital_twin_name
    AZURE_CLIENT_ID   = azurerm_user_assigned_identity.main[0].client_id

    # Inter-cloud token for cross-cloud L2 calls
    INTER_CLOUD_TOKEN = local.inter_cloud_token_value

    # Full Digital Twin configuration - required by dispatcher for routing
    DIGITAL_TWIN_INFO = var.digital_twin_info_json

    # Target function suffix: connector for multi-cloud, processor for single-cloud
    # This tells the dispatcher whether to route to connector (cross-cloud) or processor (same-cloud)
    TARGET_FUNCTION_SUFFIX = local.target_function_suffix

    # L2 Function App URL - required by dispatcher to call processor_wrapper (single-cloud)
    # or connector (multi-cloud). Connector is LOCAL to L1, so use L1 URL when multi-cloud.
    # Points to L2-functions when single-cloud, L1-functions when multi-cloud.
    FUNCTION_APP_BASE_URL = var.layer_2_provider == "azure" ? local.azure_l2_functions_url : local.azure_l1_functions_url

    # L2 Function Key - required for Azure→Azure HTTP authentication (single-cloud only)
    # processor_wrapper has AuthLevel.FUNCTION so requires this key
    # Multi-cloud connector uses AuthLevel.ANONYMOUS (see connector/function_app.py docstring)
    L2_FUNCTION_KEY = var.layer_2_provider == "azure" ? try(data.azurerm_function_app_host_keys.l2[0].default_function_key, "") : ""

    # Application Insights for logging
    APPINSIGHTS_INSTRUMENTATIONKEY        = local.app_insights_key
    APPLICATIONINSIGHTS_CONNECTION_STRING = local.app_insights_conn_str
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = []
  }
}

# ==============================================================================
# Event Grid System Topic for IoT Hub Events
# ==============================================================================

resource "azurerm_eventgrid_system_topic" "iothub" {
  count               = var.layer_1_provider == "azure" ? 1 : 0
  name                = local.azure_iothub_events_name
  resource_group_name = azurerm_resource_group.main[0].name
  location            = local.azure_iothub_region
  source_resource_id  = azurerm_iothub.main[0].id
  topic_type          = "Microsoft.Devices.IoTHubs"

  tags = local.common_tags
}

# ==============================================================================
# Wait for Function App Code Sync
# ==============================================================================

# Azure Functions needs time to sync and recognize functions after zip_deploy_file.
# This delay ensures the dispatcher function is registered before EventGrid tries to subscribe.
resource "time_sleep" "wait_for_function_sync" {
  count           = var.layer_1_provider == "azure" && var.azure_l1_zip_path != "" ? 1 : 0
  depends_on      = [azurerm_linux_function_app.l1]
  create_duration = "180s" # Wait 3 minutes for Oryx build + function indexing
}

# ==============================================================================
# Event Grid Subscription: IoT Hub → L1 Dispatcher
# ==============================================================================

# EventGrid subscription to route IoT Hub telemetry to L1 dispatcher function.
# NOTE: Requires zip_deploy_file on the function app to ensure the dispatcher
# function exists before this subscription is created.
resource "azurerm_eventgrid_system_topic_event_subscription" "iothub_to_dispatcher" {
  # Only create if L1 is Azure AND we have a ZIP file (function code deployed)
  count               = var.layer_1_provider == "azure" && var.azure_l1_zip_path != "" ? 1 : 0
  name                = local.azure_iothub_subscription
  system_topic        = azurerm_eventgrid_system_topic.iothub[0].name
  resource_group_name = azurerm_resource_group.main[0].name

  azure_function_endpoint {
    function_id = "${azurerm_linux_function_app.l1[0].id}/functions/dispatcher"
  }

  included_event_types = [
    "Microsoft.Devices.DeviceTelemetry"
  ]

  # Ensure the function app (with code) is deployed and synced before creating the subscription
  depends_on = [time_sleep.wait_for_function_sync]
}
