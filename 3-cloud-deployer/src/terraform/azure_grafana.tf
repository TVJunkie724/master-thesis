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
# RBAC: Grafana Admin User Provisioning
# 
# This implements a "create-if-not-exists" pattern:
# - If user exists in Entra ID: Only assign Grafana Admin role
# - If user doesn't exist: Create user with temp password, then assign role
# ==============================================================================

# Query tenant's verified domains
data "azuread_domains" "tenant" {
  count = var.layer_5_provider == "azure" ? 1 : 0
}

locals {
  # Config available and valid
  azure_grafana_enabled = var.layer_5_provider == "azure" && var.grafana_admin_email != ""
  
  # Extract domain from email
  email_domain = local.azure_grafana_enabled ? split("@", var.grafana_admin_email)[1] : ""
  
  # Get verified domains from tenant
  verified_domains = try([for d in data.azuread_domains.tenant[0].domains : d.domain_name if d.verified], [])
  
  # Check if email domain is verified in tenant
  domain_is_verified = contains(local.verified_domains, local.email_domain)
}

# Check if user already exists in Entra ID (lookup by email)
data "azuread_users" "check_existing" {
  count          = local.azure_grafana_enabled ? 1 : 0
  mails          = [var.grafana_admin_email]
  ignore_missing = true
}

locals {
  # User exists if we found any matching users
  user_found = local.azure_grafana_enabled && length(
    try(data.azuread_users.check_existing[0].users, [])
  ) > 0
  
  # Existing user's object_id (if found)
  existing_user_object_id = local.user_found ? data.azuread_users.check_existing[0].users[0].object_id : null
  
  # Create user only if: not found AND domain is verified in tenant
  should_create_user = local.azure_grafana_enabled && !local.user_found && local.domain_is_verified
}

# Generate secure password for new user
resource "random_password" "grafana_admin" {
  count            = local.should_create_user ? 1 : 0
  length           = 16
  special          = true
  override_special = "!@#$%^&*()-_=+"
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 2
}

# Create user in Entra ID if they don't exist AND domain is verified
resource "azuread_user" "grafana_admin" {
  count = local.should_create_user ? 1 : 0
  
  user_principal_name   = var.grafana_admin_email
  display_name          = "${var.grafana_admin_first_name} ${var.grafana_admin_last_name}"
  mail                  = var.grafana_admin_email
  password              = random_password.grafana_admin[0].result
  force_password_change = true
}

locals {
  # Final object_id: from existing user OR newly created
  grafana_admin_object_id = coalesce(
    local.existing_user_object_id,
    try(azuread_user.grafana_admin[0].object_id, null)
  )
}

# Assign Grafana Admin role (with deterministic UUID for idempotency)
# NOTE: Uses azure_grafana_enabled for count (known at plan time) to avoid
# "count depends on apply" error when creating new users.
resource "azurerm_role_assignment" "grafana_admin" {
  count = local.azure_grafana_enabled ? 1 : 0
  
  # Deterministic UUID prevents duplicate assignment errors on re-apply
  name                 = uuidv5("dns", "${var.grafana_admin_email}-grafana-admin")
  scope                = azurerm_dashboard_grafana.main[0].id
  role_definition_name = "Grafana Admin"
  
  # Use coalesce to pick existing user OR newly created user's object_id
  # At apply time, one of these will be available
  principal_id = coalesce(
    local.existing_user_object_id,
    try(azuread_user.grafana_admin[0].object_id, null)
  )
  
  # Ensure user is created before role assignment
  depends_on = [azuread_user.grafana_admin]
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

