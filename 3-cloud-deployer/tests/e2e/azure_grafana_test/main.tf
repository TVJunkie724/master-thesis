# Azure Managed Grafana E2E Test
# 
# This is a focused Terraform config to test ONLY:
# - Azure Managed Grafana workspace creation
# - Entra ID user provisioning (create-if-not-exists pattern)
# - Grafana Admin role assignment
#
# Usage:
#   cd tests/e2e/azure_grafana_test
#   terraform init
#   terraform plan -var-file=test.tfvars.json
#   terraform apply -var-file=test.tfvars.json
#   terraform destroy -var-file=test.tfvars.json
#
# Note: State files remain in this directory for easy debugging.

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "azure_subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "azure_tenant_id" {
  description = "Azure Tenant ID"
  type        = string
}

variable "azure_client_id" {
  description = "Azure Service Principal Client ID"
  type        = string
  sensitive   = true
}

variable "azure_client_secret" {
  description = "Azure Service Principal Client Secret"
  type        = string
  sensitive   = true
}

variable "azure_region" {
  description = "Azure region for resources"
  type        = string
  default     = "westeurope"
}

variable "platform_user_email" {
  description = "Email for the Grafana admin user (created in Entra ID if not exists)"
  type        = string
}

variable "platform_user_first_name" {
  description = "First name for the Grafana admin user"
  type        = string
  default     = "Grafana"
}

variable "platform_user_last_name" {
  description = "Last name for the Grafana admin user"
  type        = string
  default     = "Admin"
}

variable "test_name_suffix" {
  description = "Suffix for resource names (for unique naming)"
  type        = string
  default     = "e2e"
}

# =============================================================================
# Providers
# =============================================================================

provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
  tenant_id       = var.azure_tenant_id
  client_id       = var.azure_client_id
  client_secret   = var.azure_client_secret
}

provider "azuread" {
  tenant_id     = var.azure_tenant_id
  client_id     = var.azure_client_id
  client_secret = var.azure_client_secret
}

# =============================================================================
# Resource Group
# =============================================================================

resource "azurerm_resource_group" "test" {
  name     = "rg-grafana-${var.test_name_suffix}"
  location = var.azure_region

  tags = {
    Purpose = "grafana-e2e-test"
  }
}

# =============================================================================
# Azure Managed Grafana
# =============================================================================

resource "azurerm_dashboard_grafana" "test" {
  name                = "grafana-${var.test_name_suffix}"
  resource_group_name = azurerm_resource_group.test.name
  location            = azurerm_resource_group.test.location

  # Standard SKU for production use
  sku = "Standard"

  # Grafana version (11 required by Azure for Standard SKU)
  grafana_major_version = "11"

  # Enable managed identity for data source authentication
  identity {
    type = "SystemAssigned"
  }

  # Enable public access (can be restricted via Azure AD)
  public_network_access_enabled = true

  # Zone redundancy for high availability (optional)
  zone_redundancy_enabled = false

  tags = {
    Purpose = "grafana-e2e-test"
  }
}

# =============================================================================
# Entra ID User Provisioning (Create-if-not-exists pattern)
# =============================================================================

# Query tenant's verified domains
data "azuread_domains" "tenant" {}

locals {
  # Extract domain from email
  email_domain = split("@", var.platform_user_email)[1]

  # Get verified domains from tenant
  verified_domains = [for d in data.azuread_domains.tenant.domains : d.domain_name if d.verified]

  # Check if email domain is verified in tenant
  domain_is_verified = contains(local.verified_domains, local.email_domain)
}

# Check if user already exists in Entra ID (lookup by email)
data "azuread_users" "check_existing" {
  mails          = [var.platform_user_email]
  ignore_missing = true
}

locals {
  # User exists if we found any matching users
  user_found = length(try(data.azuread_users.check_existing.users, [])) > 0

  # Existing user's object_id (if found)
  existing_user_object_id = local.user_found ? data.azuread_users.check_existing.users[0].object_id : null

  # Create user only if: not found AND domain is verified in tenant
  should_create_user = !local.user_found && local.domain_is_verified
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

  user_principal_name   = var.platform_user_email
  display_name          = "${var.platform_user_first_name} ${var.platform_user_last_name}"
  mail                  = var.platform_user_email
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
resource "azurerm_role_assignment" "grafana_admin" {
  count = local.grafana_admin_object_id != null ? 1 : 0

  # Deterministic UUID prevents duplicate assignment errors on re-apply
  name                 = uuidv5("dns", "${var.platform_user_email}-grafana-admin")
  scope                = azurerm_dashboard_grafana.test.id
  role_definition_name = "Grafana Admin"
  principal_id         = local.grafana_admin_object_id

  # Ensure user is created before role assignment
  depends_on = [azuread_user.grafana_admin]
}

# =============================================================================
# RBAC: Deploying Service Principal → Grafana Admin
# Required for E2E tests to query Grafana API immediately after deployment.
# =============================================================================

data "azurerm_client_config" "current" {}

resource "azurerm_role_assignment" "grafana_deployer" {
  scope                            = azurerm_dashboard_grafana.test.id
  role_definition_name             = "Grafana Admin"
  principal_id                     = data.azurerm_client_config.current.object_id
  skip_service_principal_aad_check = true
}

# =============================================================================
# Outputs
# =============================================================================

output "resource_group_name" {
  description = "Resource group containing Grafana"
  value       = azurerm_resource_group.test.name
}

output "grafana_id" {
  description = "Grafana workspace ID"
  value       = azurerm_dashboard_grafana.test.id
}

output "grafana_endpoint" {
  description = "Grafana workspace URL"
  value       = azurerm_dashboard_grafana.test.endpoint
}

output "user_exists_in_tenant" {
  description = "Whether the Grafana admin user already existed in Entra ID"
  value       = local.user_found
}

output "user_created" {
  description = "Whether a new user was created in Entra ID"
  value       = local.should_create_user
}

output "domain_verified" {
  description = "Whether the email domain is verified in the tenant"
  value       = local.domain_is_verified
}

output "grafana_admin_object_id" {
  description = "Entra ID object ID for the Grafana admin user"
  value       = local.grafana_admin_object_id
}

output "test_summary" {
  description = "Summary of the test"
  value = <<-EOT
    ✅ Azure Grafana E2E Test Complete
    
    Grafana URL: ${azurerm_dashboard_grafana.test.endpoint}
    Admin Email: ${var.platform_user_email}
    User Existed: ${local.user_found}
    User Created: ${local.should_create_user}
    Domain Verified: ${local.domain_is_verified}
    
    ${local.should_create_user ? "The Grafana admin user was created in Entra ID with a temporary password." : local.user_found ? "The existing Entra ID user was assigned Grafana Admin role." : "WARNING: Could not provision user (domain not verified in tenant)."}
  EOT
}
