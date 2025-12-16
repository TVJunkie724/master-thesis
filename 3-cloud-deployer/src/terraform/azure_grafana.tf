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
  
  # Grafana version (version 9 is widely supported)
  grafana_major_version = 9

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
# RBAC: Grafana Managed Identity → Monitoring Reader
# (For Azure Monitor data sources if needed)
# ==============================================================================

resource "azurerm_role_assignment" "grafana_monitoring_reader" {
  count                = var.layer_5_provider == "azure" ? 1 : 0
  scope                = azurerm_resource_group.main[0].id
  role_definition_name = "Monitoring Reader"
  principal_id         = azurerm_dashboard_grafana.main[0].identity[0].principal_id
}

# ==============================================================================
# RBAC: User Access to Grafana
# Note: Users need "Grafana Admin" or "Grafana Editor" role to access dashboards.
# This is typically configured via Azure AD groups.
# ==============================================================================

# Note: Grafana role assignments for end users are managed separately
# through Azure AD or the Grafana API, not via Terraform.
