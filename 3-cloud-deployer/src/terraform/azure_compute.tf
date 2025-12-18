# Azure L2 Compute Layer (Data Processing)
#
# This file creates the L2 layer infrastructure for data processing.
# L2 receives telemetry from L1 and persists to L3 storage.
#
# Resources Created:
# - App Service Plan (Consumption Y1): Serverless hosting for L2 functions
# - Linux Function App: Hosts persister and processor functions
#
# Functions Deployed:
# - Persister: Receives from L1 dispatcher → writes to L3 Hot storage
# - Event Checker: Validates events against config_events.json rules
#
# Architecture:
#     L1 Dispatcher → L2 Persister → L3 Hot Storage (Cosmos DB)

# ==============================================================================
# L2 App Service Plan (Consumption - Serverless)
# ==============================================================================

resource "azurerm_service_plan" "l2" {
  count               = var.layer_2_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-l2-plan"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  os_type             = "Linux"
  sku_name            = "Y1"  # Consumption plan

  tags = local.common_tags
}

# ==============================================================================
# L2 Function App (Persister/Processor)
# ==============================================================================

resource "azurerm_linux_function_app" "l2" {
  count               = var.layer_2_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-l2-functions"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.l2[0].id

  storage_account_name       = azurerm_storage_account.main[0].name
  storage_account_access_key = azurerm_storage_account.main[0].primary_access_key

  # Deploy function code via Terraform
  zip_deploy_file = var.azure_l2_zip_path != "" ? var.azure_l2_zip_path : null

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
      python_version = "3.11"
    }
  }

  app_settings = {
    # Azure Functions runtime
    FUNCTIONS_WORKER_RUNTIME       = "python"
    FUNCTIONS_EXTENSION_VERSION    = "~4"
    AzureWebJobsStorage           = local.azure_storage_connection_string
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    ENABLE_ORYX_BUILD              = "true"  # Required for remote pip install
    AzureWebJobsFeatureFlags       = "EnableWorkerIndexing"

    # Required for Consumption Plan with zip deploy
    WEBSITE_CONTENTAZUREFILECONNECTIONSTRING = local.azure_storage_connection_string
    WEBSITE_CONTENTSHARE                     = "${var.digital_twin_name}-l2-content"

    # L3 Hot Storage connection (Cosmos DB - set after L3 deployment)
    # COSMOS_CONNECTION_STRING = "..." (populated by Python orchestrator)

    # Digital Twin info
    DIGITAL_TWIN_NAME = var.digital_twin_name
    AZURE_CLIENT_ID   = azurerm_user_assigned_identity.main[0].client_id

    # Inter-cloud token for cross-cloud L3 calls
    INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result

    # Multi-cloud L2→L3: When Azure L2 sends to remote L3
    REMOTE_WRITER_URL = var.layer_2_provider == "azure" && var.layer_3_hot_provider != "azure" ? (
      var.layer_3_hot_provider == "aws" ? try(aws_lambda_function_url.l0_hot_writer[0].function_url, "") :
      var.layer_3_hot_provider == "google" ? try(google_cloudfunctions2_function.hot_writer[0].url, "") : ""
    ) : ""

    # Logic App trigger URL for event checking workflow
    LOGIC_APP_TRIGGER_URL = var.trigger_notification_workflow && var.use_event_checking ? (
      try(azurerm_logic_app_trigger_http_request.event_trigger[0].callback_url, "")
    ) : ""
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [
      app_settings["COSMOS_CONNECTION_STRING"],
    ]
  }
}

# ==============================================================================
# User Functions App (Event Actions, Processors, Feedback)
# ==============================================================================

# This app hosts user-customizable functions that can be updated independently.
# Functions are deployed via Python SDK AFTER terraform apply (not via zip_deploy_file)
# to enable incremental updates with hash comparison.
resource "azurerm_linux_function_app" "user" {
  count               = var.layer_2_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-user-functions"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.l2[0].id  # Share plan with L2

  storage_account_name       = azurerm_storage_account.main[0].name
  storage_account_access_key = azurerm_storage_account.main[0].primary_access_key

  # NO zip_deploy_file - user functions deployed via SDK after terraform

  # Enable SCM Basic Auth (required for SDK zip deploy)
  webdeploy_publish_basic_authentication_enabled = true
  ftp_publish_basic_authentication_enabled       = true

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
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
    ENABLE_ORYX_BUILD              = "true"  # Required for remote pip install
    AzureWebJobsFeatureFlags       = "EnableWorkerIndexing"

    # Required for Consumption Plan with zip deploy
    WEBSITE_CONTENTAZUREFILECONNECTIONSTRING = local.azure_storage_connection_string
    WEBSITE_CONTENTSHARE                     = "${var.digital_twin_name}-user-content"

    # Digital Twin info
    DIGITAL_TWIN_NAME = var.digital_twin_name
    AZURE_CLIENT_ID   = azurerm_user_assigned_identity.main[0].client_id

    # Inter-cloud token for cross-cloud calls
    INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result

    # Cosmos DB connection for user functions to access hot storage
    COSMOS_ENDPOINT = var.layer_3_hot_provider == "azure" ? azurerm_cosmosdb_account.main[0].endpoint : ""
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = []
  }
}

# ==============================================================================
# Azure Logic App (Optional - for notification workflows)
# Only deployed if trigger_notification_workflow is enabled
# ==============================================================================

# TODO: Test Logic App after EventGrid subscription works
# Currently disabled (trigger_notification_workflow = false) for E2E testing
resource "azurerm_logic_app_workflow" "event_notification" {
  count               = var.layer_2_provider == "azure" && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
  name                = "${var.digital_twin_name}-event-workflow"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name

  tags = local.common_tags
}

# Logic App trigger - HTTP Request
# This allows the event-checker function to trigger the workflow
resource "azurerm_logic_app_trigger_http_request" "event_trigger" {
  count        = var.layer_2_provider == "azure" && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
  name         = "event-trigger"
  logic_app_id = azurerm_logic_app_workflow.event_notification[0].id

  schema = jsonencode({
    type = "object"
    properties = {
      eventType = { type = "string" }
      deviceId  = { type = "string" }
      payload   = { type = "object" }
      action    = { type = "string" }
    }
  })
}

# ==============================================================================
# RBAC: L2 Function App → Cosmos DB (via Managed Identity)
# ==============================================================================

# Note: Cosmos DB RBAC is configured in azure_storage.tf after Cosmos DB is created

