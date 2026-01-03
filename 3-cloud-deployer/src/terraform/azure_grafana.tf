# Azure L5 Visualization Layer (Grafana)
#
# This file creates the L5 layer infrastructure for data visualization.
# L5 provides dashboards for monitoring Digital Twin data.
#
# Resources Created:
# - Azure Managed Grafana: Visualization workspace
# - RBAC Role Assignments: Managed Identity access for data sources
#
# Note: Grafana datasource configuration is done by Python orchestrator
# after Terraform provisions the workspace, as it requires API calls
# with authentication tokens.
#
# Architecture:
#     L3 Hot Reader → JSON API Datasource → Grafana Dashboard
#
# Note: L5 relies on the L3 Hot Reader function for data access.
# It does NOT depend on L4 (Digital Twins).

# ==============================================================================
# Azure Managed Grafana
# ==============================================================================

resource "azurerm_dashboard_grafana" "main" {
  count               = var.layer_5_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-grafana"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location

  # Standard SKU for production use
  sku = "Standard"
  
  # Grafana version (11 required for Standard SKU as of 2024)
  grafana_major_version = "11"

  # Enable managed identity for data source authentication
  identity {
    type = "SystemAssigned"
  }

  # Enable public access (can be restricted via Azure AD)
  public_network_access_enabled = true

  # Zone redundancy for high availability (optional)
  zone_redundancy_enabled = false

  tags = local.common_tags
}

# ==============================================================================
# NOTE: Monitoring Reader role NOT needed for our architecture!
# Our L5 uses: Grafana → JSON API → Hot Reader → Cosmos DB
# Azure Monitor datasources are NOT used, so this role is skipped.
# ==============================================================================

# resource "azurerm_role_assignment" "grafana_monitoring_reader" {
#   count                = var.layer_5_provider == "azure" ? 1 : 0
#   scope                = azurerm_resource_group.main[0].id
#   role_definition_name = "Monitoring Reader"
#   principal_id         = azurerm_dashboard_grafana.main[0].identity[0].principal_id
# }

# ==============================================================================
# RBAC: Grafana Admin User Role Assignment
# 
# User creation logic is now in azure_user.tf (shared with L4 ADT).
# This section only assigns the Grafana Admin role to the platform user.
# ==============================================================================

locals {
  # L5 Azure Grafana enabled when provider is Azure AND email is provided
  azure_grafana_enabled = var.layer_5_provider == "azure" && var.platform_user_email != ""
}

# Assign Grafana Admin role (with deterministic UUID for idempotency)
resource "azurerm_role_assignment" "grafana_admin" {
  count = local.azure_grafana_enabled ? 1 : 0
  
  # Deterministic UUID prevents duplicate assignment errors on re-apply
  name                 = uuidv5("dns", "${var.platform_user_email}-grafana-admin")
  scope                = azurerm_dashboard_grafana.main[0].id
  role_definition_name = "Grafana Admin"
  
  # Use shared platform_user_object_id from azure_user.tf
  principal_id = local.platform_user_object_id
  
  # Ensure user is created before role assignment
  depends_on = [azuread_user.platform_user]
}

# ==============================================================================
# RBAC: Deploying Service Principal → Grafana Admin
# Required for E2E tests to query Grafana API immediately after deployment.
# Manual users don't need this - they have time for propagation naturally.
# ==============================================================================

data "azurerm_client_config" "current" {}

resource "azurerm_role_assignment" "grafana_deployer" {
  count                            = var.layer_5_provider == "azure" ? 1 : 0
  scope                            = azurerm_dashboard_grafana.main[0].id
  role_definition_name             = "Grafana Admin"
  principal_id                     = data.azurerm_client_config.current.object_id
  skip_service_principal_aad_check = true
}

# Wait for Azure RBAC propagation (typically 5-10 min, using 180s + test retry logic)
resource "time_sleep" "wait_for_grafana_role" {
  count           = var.layer_5_provider == "azure" ? 1 : 0
  create_duration = "180s"
  depends_on      = [azurerm_role_assignment.grafana_deployer]
}

