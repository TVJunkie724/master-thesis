# Azure Setup Layer (Foundation Resources)
#
# This file creates the foundational Azure resources that all other layers depend on.
# Resources are created conditionally based on whether any layer uses Azure.
#
# Resources Created:
# - Resource Group: Container for all Azure resources
# - User-Assigned Managed Identity: For secure authentication between services
# - Storage Account: For Azure Function deployments and state storage
# - Random Password: For inter-cloud authentication token (if not provided)

# ==============================================================================
# Random Password for Inter-Cloud Token
# ==============================================================================

resource "random_password" "inter_cloud_token" {
  count   = var.inter_cloud_token == "" && local.deploy_azure ? 1 : 0
  length  = 64
  special = false
}

# ==============================================================================
# Resource Group
# ==============================================================================

resource "azurerm_resource_group" "main" {
  count    = local.deploy_azure ? 1 : 0
  name     = "${var.digital_twin_name}-rg"
  location = var.azure_region

  tags = local.common_tags
}

# ==============================================================================
# User-Assigned Managed Identity
# ==============================================================================

resource "azurerm_user_assigned_identity" "main" {
  count               = local.deploy_azure ? 1 : 0
  name                = "${var.digital_twin_name}-identity"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location

  tags = local.common_tags
}

# ==============================================================================
# Storage Account (for Function App deployments)
# ==============================================================================

resource "azurerm_storage_account" "main" {
  count                    = local.deploy_azure ? 1 : 0
  name                     = replace("${var.digital_twin_name}storage", "-", "")
  resource_group_name      = azurerm_resource_group.main[0].name
  location                 = azurerm_resource_group.main[0].location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

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
