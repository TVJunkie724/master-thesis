# Azure L0 Glue Layer (Cross-Cloud Receiver Functions)
#
# This file creates the L0 Glue layer infrastructure for multi-cloud deployments.
# L0 functions receive data from other clouds and route to local services.
#
# Resources Created:
# - App Service Plan (Consumption Y1): Serverless hosting for L0 functions
# - Linux Function App: Hosts all glue functions
# - Function code deployment via ZIP
#
# Functions Deployed:
# - Ingestion: Receives from remote L1 → routes to local L2
# - Hot Writer: Receives from remote L2 → writes to local L3 Hot
# - Cold Writer: Receives from remote L3 Hot → writes to local L3 Cold
# - Archive Writer: Receives from remote L3 Cold → writes to local L3 Archive
# - Hot Reader: Exposes local L3 Hot data → remote L4/L5
# - Hot Reader Last Entry: Single-entry variant of Hot Reader
#
# Authentication:
# - Uses X-Inter-Cloud-Token header for cross-cloud authentication
# - Token is generated during setup and stored in inter_cloud_connections.json

# ==============================================================================
# L0 App Service Plan (Consumption - Serverless)
# ==============================================================================

resource "azurerm_service_plan" "l0" {
  count               = local.deploy_azure ? 1 : 0
  name                = "${var.digital_twin_name}-l0-plan"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  os_type             = "Linux"
  sku_name            = "Y1"  # Consumption plan

  tags = local.common_tags
}

# ==============================================================================
# L0 Glue Function App
# ==============================================================================

resource "azurerm_linux_function_app" "l0_glue" {
  count               = local.deploy_azure ? 1 : 0
  name                = "${var.digital_twin_name}-l0-glue"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.l0[0].id

  storage_account_name       = azurerm_storage_account.main[0].name
  storage_account_access_key = azurerm_storage_account.main[0].primary_access_key

  # Managed Identity for accessing other Azure resources
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main[0].id]
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }

    # CORS configuration for cross-cloud calls
    cors {
      allowed_origins = ["*"]
    }
  }

  app_settings = {
    # Azure Functions runtime settings
    FUNCTIONS_WORKER_RUNTIME       = "python"
    FUNCTIONS_EXTENSION_VERSION    = "~4"
    AzureWebJobsStorage           = local.azure_storage_connection_string
    WEBSITE_RUN_FROM_PACKAGE      = "1"
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"

    # Cross-cloud authentication
    INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result

    # Digital Twin info (populated by Python orchestrator)
    DIGITAL_TWIN_NAME = var.digital_twin_name

    # Managed Identity Client ID
    AZURE_CLIENT_ID = azurerm_user_assigned_identity.main[0].client_id
  }

  # ZIP deployment will be handled by Python orchestrator post-Terraform
  # using the Kudu API, similar to existing implementation

  tags = local.common_tags

  lifecycle {
    ignore_changes = [
      # Ignore changes to ZIP deployment settings managed by Python orchestrator
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
    ]
  }
}

# ==============================================================================
# Function Code Packaging (for reference - actual deployment via Python)
# ==============================================================================

# Note: The actual function code ZIP is created and deployed by the Python
# orchestrator using the existing Kudu deployment logic. This data source
# shows the pattern for reference.
#
# data "archive_file" "l0_functions" {
#   type        = "zip"
#   source_dir  = "${var.project_path}/azure_functions/l0"
#   output_path = "${path.module}/.terraform/l0_functions.zip"
# }
