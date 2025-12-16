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
  name                = "${var.digital_twin_name}-iothub"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = local.azure_iothub_region

  sku {
    name     = "S1"
    capacity = 1
  }

  tags = local.common_tags
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
  name                = "${var.digital_twin_name}-l1-plan"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  os_type             = "Linux"
  sku_name            = "Y1"  # Consumption plan

  tags = local.common_tags
}

# ==============================================================================
# L1 Function App (Dispatcher)
# ==============================================================================

resource "azurerm_linux_function_app" "l1" {
  count               = var.layer_1_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-l1-functions"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.l1[0].id

  storage_account_name       = azurerm_storage_account.main[0].name
  storage_account_access_key = azurerm_storage_account.main[0].primary_access_key

  # Managed Identity
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main[0].id]
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    # Azure Functions runtime
    FUNCTIONS_WORKER_RUNTIME       = "python"
    FUNCTIONS_EXTENSION_VERSION    = "~4"
    AzureWebJobsStorage           = local.azure_storage_connection_string
    WEBSITE_RUN_FROM_PACKAGE      = "1"
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"

    # IoT Hub connection (for Event Grid subscription)
    IOTHUB_CONNECTION_STRING = azurerm_iothub.main[0].event_hub_events_endpoint

    # Cross-cloud: L2 target URL (set by Python orchestrator based on config)
    # L2_INGESTION_URL = "https://..." (populated post-deployment)

    # Digital Twin info
    DIGITAL_TWIN_NAME = var.digital_twin_name
    AZURE_CLIENT_ID   = azurerm_user_assigned_identity.main[0].client_id

    # Inter-cloud token for cross-cloud L2 calls
    INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
      app_settings["L2_INGESTION_URL"],
    ]
  }
}

# ==============================================================================
# Event Grid System Topic for IoT Hub Events
# ==============================================================================

resource "azurerm_eventgrid_system_topic" "iothub" {
  count                  = var.layer_1_provider == "azure" ? 1 : 0
  name                   = "${var.digital_twin_name}-iothub-events"
  resource_group_name    = azurerm_resource_group.main[0].name
  location               = local.azure_iothub_region
  source_arm_resource_id = azurerm_iothub.main[0].id
  topic_type             = "Microsoft.Devices.IoTHubs"

  tags = local.common_tags
}

# ==============================================================================
# Event Grid Subscription: IoT Hub → L1 Dispatcher
# ==============================================================================

resource "azurerm_eventgrid_system_topic_event_subscription" "iothub_to_dispatcher" {
  count               = var.layer_1_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-iothub-subscription"
  system_topic        = azurerm_eventgrid_system_topic.iothub[0].name
  resource_group_name = azurerm_resource_group.main[0].name

  azure_function_endpoint {
    function_id = "${azurerm_linux_function_app.l1[0].id}/functions/dispatcher"
  }

  included_event_types = [
    "Microsoft.Devices.DeviceTelemetry"
  ]

  # Ensure the function app is fully deployed before creating the subscription
  depends_on = [azurerm_linux_function_app.l1]
}
