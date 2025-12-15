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

    # L3 Hot Storage connection (Cosmos DB - set after L3 deployment)
    # COSMOS_CONNECTION_STRING = "..." (populated by Python orchestrator)

    # Digital Twin info
    DIGITAL_TWIN_NAME = var.digital_twin_name
    AZURE_CLIENT_ID   = azurerm_user_assigned_identity.main[0].client_id

    # Inter-cloud token for cross-cloud L3 calls
    INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
      app_settings["COSMOS_CONNECTION_STRING"],
    ]
  }
}

# ==============================================================================
# RBAC: L2 Function App → Cosmos DB (via Managed Identity)
# ==============================================================================

# Note: Cosmos DB RBAC is configured in azure_storage.tf after Cosmos DB is created
