# Azure Setup Layer (Foundation Resources)
#
# This file creates the foundational Azure resources that all other layers depend on.
# Resources are created conditionally based on whether any layer uses Azure.
#
# Resources Created:
# - Resource Group: Container for all Azure resources
# - User-Assigned Managed Identity: For secure authentication between services
# - Storage Account: For Azure Function deployments and state storage

# ==============================================================================
# Azure Resource Names - Single Source of Truth
# ==============================================================================

locals {
  # Setup
  azure_resource_group_name  = "${var.digital_twin_name}-rg"
  azure_identity_name        = "${var.digital_twin_name}-identity"
  # Azure storage accounts: max 24 chars, lowercase alphanumeric only, globally unique
  azure_storage_account_name = substr("${replace(var.digital_twin_name, "-", "")}st${local.deployment_suffix}", 0, 24)

  # L0 Glue
  azure_l0_plan_name     = "${var.digital_twin_name}-l0-plan"
  azure_l0_glue_name     = "${var.digital_twin_name}-l0-glue-${local.deployment_suffix}"
  azure_l0_content_share = "${var.digital_twin_name}-l0-content"

  # L1 IoT
  azure_iothub_name         = "${var.digital_twin_name}-iothub-${local.deployment_suffix}"
  azure_l1_plan_name        = "${var.digital_twin_name}-l1-plan"
  azure_l1_functions_name   = "${var.digital_twin_name}-l1-functions-${local.deployment_suffix}"
  azure_l1_content_share    = "${var.digital_twin_name}-l1-content"
  azure_iothub_events_name  = "${var.digital_twin_name}-iothub-events"
  azure_iothub_subscription = "${var.digital_twin_name}-iothub-subscription"

  # L2 Compute
  azure_l2_plan_name        = "${var.digital_twin_name}-l2-plan"
  azure_l2_functions_name   = "${var.digital_twin_name}-l2-functions-${local.deployment_suffix}"
  azure_l2_content_share    = "${var.digital_twin_name}-l2-content"
  azure_user_functions_name = "${var.digital_twin_name}-user-functions-${local.deployment_suffix}"
  azure_user_content_share  = "${var.digital_twin_name}-user-content"
  azure_event_workflow_name = "${var.digital_twin_name}-event-workflow"
  azure_logic_app_name      = "${var.digital_twin_name}-logic-app-definition"

  # L3 Storage
  azure_cosmos_account_name   = "${var.digital_twin_name}-cosmos-${local.deployment_suffix}"
  azure_cosmos_db_name        = "${var.digital_twin_name}-db"
  azure_cosmos_container_name = local.storage_tier_hot  # Uses cross-provider constant
  azure_l3_plan_name          = "${var.digital_twin_name}-l3-plan"
  azure_l3_functions_name     = "${var.digital_twin_name}-l3-functions-${local.deployment_suffix}"
  azure_l3_content_share      = "${var.digital_twin_name}-l3-content"

  # L4 ADT
  azure_adt_name = "${var.digital_twin_name}-adt"
  # Note: uses local.scenes_container_name from cross_cloud.tf

  # L5 Grafana
  azure_grafana_name = "${var.digital_twin_name}-grafana"

  # ===========================================================================
  # Azure URLs - Centralized function app URLs
  # ===========================================================================

  azure_l0_glue_url        = "https://${local.azure_l0_glue_name}.azurewebsites.net"
  azure_l1_functions_url   = "https://${local.azure_l1_functions_name}.azurewebsites.net"
  azure_l2_functions_url   = "https://${local.azure_l2_functions_name}.azurewebsites.net"
  azure_user_functions_url = "https://${local.azure_user_functions_name}.azurewebsites.net"
  # ADT URL must use the actual host_name from the resource (not string-constructed)
  # Azure's format is: name.api.region-code.digitaltwins.azure.net (e.g., .api.weu.)
  azure_adt_url            = try("https://${azurerm_digital_twins_instance.main[0].host_name}", "")
}

# ==============================================================================
# Resource Group
# ==============================================================================

resource "azurerm_resource_group" "main" {
  count    = local.deploy_azure ? 1 : 0
  name     = local.azure_resource_group_name
  location = var.azure_region

  tags = local.common_tags
}

# ==============================================================================
# User-Assigned Managed Identity
# ==============================================================================

resource "azurerm_user_assigned_identity" "main" {
  count               = local.deploy_azure ? 1 : 0
  name                = local.azure_identity_name
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location

  tags = local.common_tags
}

# ==============================================================================
# Storage Account (for Function App deployments)
# ==============================================================================

resource "azurerm_storage_account" "main" {
  count                    = local.deploy_azure ? 1 : 0
  name                     = local.azure_storage_account_name
  resource_group_name      = azurerm_resource_group.main[0].name
  location                 = azurerm_resource_group.main[0].location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  # CORS configuration for Azure 3D Scenes Studio
  # Required for the 3D visualization to access GLB assets from the storage account
  blob_properties {
    cors_rule {
      allowed_origins    = ["https://explorer.digitaltwins.azure.net"]
      # Include write methods for 3D Scene building (PUT for saving configs)
      allowed_methods    = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "DELETE"]
      allowed_headers    = ["*"]
      exposed_headers    = ["*"]
      max_age_in_seconds = 3600
    }
  }

  tags = local.common_tags
}

# ==============================================================================
# Storage Account Connection String (for Function Apps)
# ==============================================================================

# Local value to avoid repeating the connection string pattern
locals {
  azure_storage_connection_string = local.deploy_azure ? (
    "DefaultEndpointsProtocol=https;AccountName=${azurerm_storage_account.main[0].name};AccountKey=${azurerm_storage_account.main[0].primary_access_key};EndpointSuffix=core.windows.net"
  ) : ""
}

