# ==============================================================================
# Azure Platform User Configuration
# ==============================================================================
# Shared user creation/lookup logic for both L4 (ADT) and L5 (Grafana).
# Implements "create-if-not-exists" pattern for Azure Entra ID users.
#
# This file is used when either L4=Azure OR L5=Azure.
# The platform_user_object_id local is used by:
#   - azure_grafana.tf for Grafana Admin role assignment
#   - azure_twins.tf for ADT Data Owner and Storage Blob Reader roles
# ==============================================================================

# Query tenant's verified domains (needed for user creation validation)
data "azuread_domains" "tenant" {
  count = (var.layer_4_provider == "azure" || var.layer_5_provider == "azure") ? 1 : 0
}

locals {
  # Azure user provisioning enabled when L4 or L5 is Azure AND email is provided
  azure_user_enabled = (var.layer_4_provider == "azure" || var.layer_5_provider == "azure") && var.platform_user_email != ""
  
  # Extract domain from email
  user_email_domain = local.azure_user_enabled ? split("@", var.platform_user_email)[1] : ""
  
  # Get verified domains from tenant - MUST guard access when neither L4 nor L5 is Azure
  tenant_verified_domains = (var.layer_4_provider == "azure" || var.layer_5_provider == "azure") ? try([for d in data.azuread_domains.tenant[0].domains : d.domain_name if d.verified], []) : []
  
  # Check if email domain is verified in tenant
  user_domain_is_verified = contains(local.tenant_verified_domains, local.user_email_domain)
}

# Check if user already exists in Entra ID (lookup by email)
data "azuread_users" "platform_user_check" {
  count          = local.azure_user_enabled ? 1 : 0
  mails          = [var.platform_user_email]
  ignore_missing = true
}

locals {
  # User exists if we found any matching users
  platform_user_found = local.azure_user_enabled && length(
    try(data.azuread_users.platform_user_check[0].users, [])
  ) > 0
  
  # Existing user's object_id (if found)
  existing_platform_user_object_id = local.platform_user_found ? data.azuread_users.platform_user_check[0].users[0].object_id : null
  
  # Create user only if: not found AND domain is verified in tenant
  should_create_platform_user = local.azure_user_enabled && !local.platform_user_found && local.user_domain_is_verified
}

# Generate secure password for new user
resource "random_password" "platform_user" {
  count            = local.should_create_platform_user ? 1 : 0
  length           = 16
  special          = true
  override_special = "!@#$%^&*()-_=+"
  min_lower        = 2
  min_upper        = 2
  min_numeric      = 2
  min_special      = 2
}

# Create user in Entra ID if they don't exist AND domain is verified
resource "azuread_user" "platform_user" {
  count = local.should_create_platform_user ? 1 : 0
  
  user_principal_name   = var.platform_user_email
  display_name          = "${var.platform_user_first_name} ${var.platform_user_last_name}"
  mail                  = var.platform_user_email
  password              = random_password.platform_user[0].result
  force_password_change = true
}

locals {
  # Final object_id: from existing user OR newly created
  # IMPORTANT: Only compute when L4 or L5 is Azure, otherwise coalesce() fails with no non-null args
  platform_user_object_id = local.azure_user_enabled ? coalesce(
    local.existing_platform_user_object_id,
    try(azuread_user.platform_user[0].object_id, null)
  ) : null
}
