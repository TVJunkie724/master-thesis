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
    INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")

    # L3 Hot Storage - Cosmos DB connection for persister (single-cloud mode)
    COSMOS_DB_ENDPOINT  = var.layer_3_hot_provider == "azure" ? azurerm_cosmosdb_account.main[0].endpoint : ""
    COSMOS_DB_KEY       = var.layer_3_hot_provider == "azure" ? azurerm_cosmosdb_account.main[0].primary_key : ""
    COSMOS_DB_DATABASE  = var.layer_3_hot_provider == "azure" ? azurerm_cosmosdb_sql_database.main[0].name : ""
    COSMOS_DB_CONTAINER = "hot"

    # Multi-cloud L2→L3: When Azure L2 sends to remote L3
    REMOTE_WRITER_URL = var.layer_2_provider == "azure" && var.layer_3_hot_provider != "azure" ? (
      var.layer_3_hot_provider == "aws" ? try(aws_lambda_function_url.l0_hot_writer[0].function_url, "") :
      var.layer_3_hot_provider == "google" ? try(google_cloudfunctions2_function.hot_writer[0].url, "") : ""
    ) : ""

    # Multi-cloud L2→L4: When Azure L2 sends to Azure ADT
    REMOTE_ADT_PUSHER_URL = var.layer_4_provider == "azure" ? (
      "https://${var.digital_twin_name}-l0-glue.azurewebsites.net/api/adt-pusher"
    ) : ""
    ADT_PUSHER_TOKEN = var.layer_4_provider == "azure" ? (
      var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")
    ) : ""

    # Logic App trigger URL for event checking workflow
    # FIX: Use workflow access_endpoint instead of separate trigger resource
    # The trigger is defined in the azure_logic_app.json ARM template
    LOGIC_APP_TRIGGER_URL = var.trigger_notification_workflow && var.use_event_checking ? (
      try(azurerm_logic_app_workflow.event_notification[0].access_endpoint, "")
    ) : ""

    # Event checker URL for event checking (optional)
    EVENT_CHECKER_FUNCTION_URL = var.use_event_checking ? "https://${var.digital_twin_name}-l2-functions.azurewebsites.net/api/event-checker" : ""
    USE_EVENT_CHECKING         = var.use_event_checking ? "true" : "false"

    # Azure ADT instance URL (for event-checker)
    ADT_INSTANCE_URL = var.layer_4_provider == "azure" ? "https://${var.digital_twin_name}.${var.azure_region}.digitaltwins.azure.net" : ""

    # Feedback function URL (for event-checker)
    FEEDBACK_FUNCTION_URL = var.return_feedback_to_device ? "https://${var.digital_twin_name}-user-functions.azurewebsites.net/api/event-feedback" : ""
    USE_FEEDBACK          = var.return_feedback_to_device ? "true" : "false"
    USE_LOGIC_APPS        = var.trigger_notification_workflow ? "true" : "false"

    # NEW: Required for Wrapper to find User Functions
    FUNCTION_APP_BASE_URL = "https://${var.digital_twin_name}-user-functions.azurewebsites.net"

    # Full Digital Twin configuration - required by persister for multi-cloud routing
    DIGITAL_TWIN_INFO = var.digital_twin_info_json

    # Persister URL - required by processor_wrapper to call persister
    # NOTE: persister uses AuthLevel.ANONYMOUS to avoid Terraform cycle (see function docstrings)
    PERSISTER_FUNCTION_URL = "https://${var.digital_twin_name}-l2-functions.azurewebsites.net/api/persister"

    # Function Keys - for Azure→Azure HTTP authentication
    # NOTE: L2_FUNCTION_KEY deliberately NOT included here to avoid Terraform cycle.
    # Internal L2 functions (persister, event-checker) use AuthLevel.ANONYMOUS.
    # See src/providers/azure/azure_functions/persister/function_app.py for full explanation.
    #
    # User functions (processors) still require keys - no cycle because L2 app
    # references USER key (different app), not its own key.
    USER_FUNCTION_KEY = try(data.azurerm_function_app_host_keys.user[0].default_function_key, "")

    # IoT Hub connection - required by event_feedback_wrapper to send feedback to devices
    IOT_HUB_CONNECTION_STRING = var.layer_1_provider == "azure" ? azurerm_iothub.main[0].event_hub_events_endpoint : ""
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

  # Deploy user function code via Terraform (changed from SDK deployment)
  zip_deploy_file = var.azure_user_zip_path != "" ? var.azure_user_zip_path : null

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
    INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")

    # Cosmos DB connection for user functions to access hot storage
    COSMOS_ENDPOINT = var.layer_3_hot_provider == "azure" ? azurerm_cosmosdb_account.main[0].endpoint : ""

    # NEW: Required for HTTP call pattern (wrappers call user functions via HTTP)
    FUNCTION_APP_BASE_URL = "https://${var.digital_twin_name}-user-functions.azurewebsites.net"
    
    DIGITAL_TWIN_INFO = jsonencode({
      config = {
        digital_twin_name = var.digital_twin_name
      }
    })
    
    EVENT_FEEDBACK_FUNCTION_URL = var.return_feedback_to_device ? "https://${var.digital_twin_name}-user-functions.azurewebsites.net/api/event-feedback" : ""
    
    PERSISTER_FUNCTION_URL = "https://${var.digital_twin_name}-l2-functions.azurewebsites.net/api/persister"

    # NOTE: USER_FUNCTION_KEY deliberately NOT included in user app's app_settings.
    # This would cause a Terraform cycle (user app → data.user → user app)
    # User functions are passive responders - they receive HTTP calls but don't
    # make outbound calls to other user functions, so they don't need their own key.

    # IoT Hub connection - required by event_feedback_wrapper to send feedback to devices
    IOT_HUB_CONNECTION_STRING = var.layer_1_provider == "azure" ? azurerm_iothub.main[0].event_hub_events_endpoint : ""
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

# Logic App workflow resource (creates the container)
resource "azurerm_logic_app_workflow" "event_notification" {
  count               = var.layer_2_provider == "azure" && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
  name                = "${var.digital_twin_name}-event-workflow"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name

  tags = local.common_tags

  # The workflow definition is set via ARM template below because
  # azurerm_logic_app_workflow doesn't support complex definitions directly
  lifecycle {
    ignore_changes = [parameters]
  }
}

# FIX: Apply workflow definition via ARM template deployment
# Without this, the Logic App appears empty in the Azure Portal designer
resource "azurerm_resource_group_template_deployment" "logic_app_definition" {
  count               = var.layer_2_provider == "azure" && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
  name                = "${var.digital_twin_name}-logic-app-definition"
  resource_group_name = azurerm_resource_group.main[0].name
  deployment_mode     = "Incremental"

  template_content = jsonencode({
    "$schema"      = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    contentVersion = "1.0.0.0"
    resources = [{
      type       = "Microsoft.Logic/workflows"
      apiVersion = "2019-05-01"
      name       = azurerm_logic_app_workflow.event_notification[0].name
      location   = azurerm_resource_group.main[0].location
      properties = {
        state      = "Enabled"
        definition = jsondecode(file(var.logic_app_definition_file)).definition
      }
    }]
  })

  depends_on = [azurerm_logic_app_workflow.event_notification]
}

# NOTE: The HTTP trigger is now defined directly in azure_logic_app.json
# and deployed via the ARM template above. This eliminates the conflict that
# caused the Logic App designer to appear empty in the Azure Portal.
# See: https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/logic_app_trigger_http_request

# ==============================================================================
# RBAC: L2 Function App → Cosmos DB (via Managed Identity)
# ==============================================================================

# Note: Cosmos DB RBAC is configured in azure_storage.tf after Cosmos DB is created

