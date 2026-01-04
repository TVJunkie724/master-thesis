# ============================================================================
# Azure Digital Twins (L4) Focused E2E Test - Terraform Configuration
# ============================================================================
# 
# Purpose:
#   Deploys ONLY Layer 4 resources (Azure Digital Twins + 3D Scene Assets)
#   for rapid testing of ADT deployment and 3D scene upload without the full
#   infrastructure stack (L0-L3, L5).
#
# What this tests:
#   1. ADT instance creation
#   2. Storage container for 3D scenes
#   3. GLB model file upload  
#   4. 3DScenesConfiguration.json upload
#   5. RBAC permissions for ADT to access storage
#
# Usage:
#   This file is used by tests/e2e/azure/test_azure_adt_e2e.py
#   Run via: python tests/e2e/run_e2e_test.py azure-adt
#
# Note:
#   DTDL models and Digital Twins are created by Python SDK after Terraform,
#   as they are generated dynamically from config_hierarchy.json.
#   This test verifies the infrastructure is ready for that step.
# ============================================================================

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# ============================================================================
# Variables
# ============================================================================

variable "azure_subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "azure_tenant_id" {
  description = "Azure AD Tenant ID"
  type        = string
}

variable "azure_client_id" {
  description = "Azure Service Principal Client ID"
  type        = string
}

variable "azure_client_secret" {
  description = "Azure Service Principal Client Secret"
  type        = string
  sensitive   = true
}

variable "azure_region" {
  description = "Azure region for deployment"
  type        = string
  default     = "westeurope"
}

variable "test_name_suffix" {
  description = "Suffix for test resources to ensure uniqueness"
  type        = string
  default     = "e2e"
}

variable "scene_assets_path" {
  description = "Path to scene assets directory containing azure/scene.glb and azure/3DScenesConfiguration.json"
  type        = string
  default     = ""
}

variable "platform_user_email" {
  description = "Email for platform user (ADT Data Owner). Leave empty to skip user creation."
  type        = string
  default     = ""
}

variable "platform_user_first_name" {
  description = "First name for platform user"
  type        = string
  default     = "Platform"
}

variable "platform_user_last_name" {
  description = "Last name for platform user"
  type        = string
  default     = "Admin"
}

# ============================================================================
# Provider Configuration
# ============================================================================

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

# ============================================================================
# Random suffix for unique naming
# ============================================================================

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# ============================================================================
# Locals
# ============================================================================

locals {
  resource_prefix     = "adt-${var.test_name_suffix}"
  unique_suffix       = random_string.suffix.result
  scene_assets_azure  = var.scene_assets_path != "" ? "${var.scene_assets_path}/azure" : ""
  has_scene_assets    = var.scene_assets_path != ""
  
  # Platform user logic
  platform_user_enabled = var.platform_user_email != ""
  user_email_domain     = local.platform_user_enabled ? split("@", var.platform_user_email)[1] : ""
  
  common_tags = {
    Purpose = "adt-e2e-test"
  }
}

# ============================================================================
# Platform User Configuration (mirrors production azure_user.tf)
# ============================================================================

# Query tenant's verified domains
data "azuread_domains" "tenant" {
  count = local.platform_user_enabled ? 1 : 0
}

locals {
  # Get verified domains from tenant
  tenant_verified_domains = local.platform_user_enabled ? try([for d in data.azuread_domains.tenant[0].domains : d.domain_name if d.verified], []) : []
  
  # Check if email domain is verified in tenant
  user_domain_is_verified = contains(local.tenant_verified_domains, local.user_email_domain)
}

# Check if user already exists in Entra ID
data "azuread_users" "platform_user_check" {
  count          = local.platform_user_enabled ? 1 : 0
  mails          = [var.platform_user_email]
  ignore_missing = true
}

locals {
  # User exists if we found any matching users
  platform_user_found = local.platform_user_enabled && length(
    try(data.azuread_users.platform_user_check[0].users, [])
  ) > 0
  
  # Existing user's object_id (if found)
  existing_platform_user_object_id = local.platform_user_found ? data.azuread_users.platform_user_check[0].users[0].object_id : null
  
  # Create user only if: not found AND domain is verified in tenant
  should_create_platform_user = local.platform_user_enabled && !local.platform_user_found && local.user_domain_is_verified
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
  platform_user_object_id = local.platform_user_enabled ? coalesce(
    local.existing_platform_user_object_id,
    try(azuread_user.platform_user[0].object_id, null)
  ) : null
}

# ============================================================================
# Resource Group
# ============================================================================

resource "azurerm_resource_group" "test" {
  name     = "rg-${local.resource_prefix}-${local.unique_suffix}"
  location = var.azure_region
  tags     = local.common_tags
}

# ============================================================================
# Storage Account (for 3D Scenes)
# ============================================================================

resource "azurerm_storage_account" "test" {
  # Storage names: lowercase alphanumeric only, 3-24 chars. Remove hyphens from suffix.
  name                     = "adt${replace(var.test_name_suffix, "-", "")}${local.unique_suffix}"
  resource_group_name      = azurerm_resource_group.test.name
  location                 = azurerm_resource_group.test.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  # Enable blob public access for 3D Scenes Studio
  allow_nested_items_to_be_public = false
  
  # CORS configuration required for 3D Scenes Studio browser access
  blob_properties {
    cors_rule {
      allowed_headers    = ["*"]
      # Include write methods for 3D Scene building (PUT for saving configs)
      allowed_methods    = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "DELETE"]
      allowed_origins    = ["https://explorer.digitaltwins.azure.net"]
      exposed_headers    = ["*"]
      max_age_in_seconds = 3600
    }
  }
  
  tags = local.common_tags
}

# ============================================================================
# Storage Container for 3D Scenes
# ============================================================================

resource "azurerm_storage_container" "scenes" {
  count                 = local.has_scene_assets ? 1 : 0
  name                  = "3dscenes"
  storage_account_id    = azurerm_storage_account.test.id
  container_access_type = "private"
}

# ============================================================================
# Upload 3D Scene Assets
# ============================================================================

# Upload GLB model
resource "azurerm_storage_blob" "scene_glb" {
  count                  = local.has_scene_assets ? 1 : 0
  name                   = "scene.glb"
  storage_account_name   = azurerm_storage_account.test.name
  storage_container_name = azurerm_storage_container.scenes[0].name
  type                   = "Block"
  source                 = "${local.scene_assets_azure}/scene.glb"
  content_md5            = filemd5("${local.scene_assets_azure}/scene.glb")
  content_type           = "model/gltf-binary"
}

# Upload 3D Scenes configuration with dynamic URL replacement
# The template file contains {{STORAGE_URL}} placeholder which is replaced with actual storage URL
locals {
  scene_config_raw = local.has_scene_assets ? file("${local.scene_assets_azure}/3DScenesConfiguration.json") : ""
  scene_storage_url = local.has_scene_assets ? "https://${azurerm_storage_account.test.name}.blob.core.windows.net/${azurerm_storage_container.scenes[0].name}" : ""
  scene_config_content = replace(local.scene_config_raw, "{{STORAGE_URL}}", local.scene_storage_url)
}

resource "azurerm_storage_blob" "scene_config" {
  count                  = local.has_scene_assets ? 1 : 0
  name                   = "3DScenesConfiguration.json"
  storage_account_name   = azurerm_storage_account.test.name
  storage_container_name = azurerm_storage_container.scenes[0].name
  type                   = "Block"
  source_content         = local.scene_config_content
  content_md5            = md5(local.scene_config_content)
  content_type           = "application/json"
}

# ============================================================================
# Azure Digital Twins Instance
# ============================================================================

resource "azurerm_digital_twins_instance" "test" {
  name                = "${local.resource_prefix}-${local.unique_suffix}"
  resource_group_name = azurerm_resource_group.test.name
  location            = azurerm_resource_group.test.location
  
  identity {
    type = "SystemAssigned"
  }
  
  tags = local.common_tags
}

# ============================================================================
# RBAC: Service Principal → ADT Data Owner
# (Allows deployer to create DTDL models and twins)
# ============================================================================

data "azurerm_client_config" "current" {}

resource "azurerm_role_assignment" "adt_data_owner" {
  scope                            = azurerm_digital_twins_instance.test.id
  role_definition_name             = "Azure Digital Twins Data Owner"
  principal_id                     = data.azurerm_client_config.current.object_id
  skip_service_principal_aad_check = true
}

# ============================================================================
# RBAC: ADT Identity → Storage Blob Data Reader
# (Allows ADT to read 3D scene files from storage)
# ============================================================================

resource "azurerm_role_assignment" "adt_storage_reader" {
  count                = local.has_scene_assets ? 1 : 0
  scope                = azurerm_storage_account.test.id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_digital_twins_instance.test.identity[0].principal_id
  
  depends_on = [azurerm_digital_twins_instance.test]
}

# ============================================================================
# RBAC: Platform User → ADT Data Owner
# (Allows the platform user to access ADT Explorer and 3D Scenes Studio)
# ============================================================================

resource "azurerm_role_assignment" "platform_user_adt_owner" {
  count                = local.platform_user_enabled ? 1 : 0
  scope                = azurerm_digital_twins_instance.test.id
  role_definition_name = "Azure Digital Twins Data Owner"
  
  # Use deterministic UUID for idempotency (matches production pattern)
  name                 = uuidv5("dns", "${var.platform_user_email}-adt-owner")
  principal_id         = local.platform_user_object_id
  
  depends_on = [azuread_user.platform_user]
}

# RBAC: Platform User → Storage Blob Data Contributor (for building 3D scenes)
# Per Azure docs: "For building 3D scenes, you need Storage Blob Data Contributor"
resource "azurerm_role_assignment" "platform_user_storage_contributor" {
  count                = local.platform_user_enabled && local.has_scene_assets ? 1 : 0
  scope                = azurerm_storage_account.test.id
  role_definition_name = "Storage Blob Data Contributor"
  
  # Use deterministic UUID for idempotency (matches production pattern)
  name                 = uuidv5("dns", "${var.platform_user_email}-scenes-contributor")
  principal_id         = local.platform_user_object_id
  
  depends_on = [azuread_user.platform_user]
}

# ============================================================================
# Outputs
# ============================================================================

output "resource_group_name" {
  value       = azurerm_resource_group.test.name
  description = "Resource group name"
}

output "adt_endpoint" {
  value       = "https://${azurerm_digital_twins_instance.test.host_name}"
  description = "Azure Digital Twins endpoint URL"
}

output "adt_id" {
  value       = azurerm_digital_twins_instance.test.id
  description = "Azure Digital Twins instance ID"
}

output "storage_account_name" {
  value       = azurerm_storage_account.test.name
  description = "Storage account for 3D scenes"
}

output "scenes_container_url" {
  value       = local.has_scene_assets ? "https://${azurerm_storage_account.test.name}.blob.core.windows.net/${azurerm_storage_container.scenes[0].name}" : ""
  description = "3D Scenes container URL for linking to ADT"
}

output "scene_glb_url" {
  value       = local.has_scene_assets ? azurerm_storage_blob.scene_glb[0].url : ""
  description = "URL of uploaded GLB model"
}

output "scene_config_url" {
  value       = local.has_scene_assets ? azurerm_storage_blob.scene_config[0].url : ""
  description = "URL of uploaded 3DScenesConfiguration.json"
}

output "test_summary" {
  value = <<-EOT
============================================================
✅ Azure Digital Twins E2E Test Complete
    
ADT Endpoint: https://${azurerm_digital_twins_instance.test.host_name}
Storage Account: ${azurerm_storage_account.test.name}
Scenes Container: ${local.has_scene_assets ? "https://${azurerm_storage_account.test.name}.blob.core.windows.net/${azurerm_storage_container.scenes[0].name}" : "N/A (no scene assets)"}

GLB Uploaded: ${local.has_scene_assets ? "scene.glb" : "N/A"}
Config Uploaded: ${local.has_scene_assets ? "3DScenesConfiguration.json" : "N/A"}

RBAC Assigned:
  - Service Principal → ADT Data Owner (for DTDL upload)
  - ADT Identity → Storage Blob Data Reader (for 3D scenes)

Next step: Use Python SDK to upload DTDL models and create twins.
============================================================
EOT
  description = "Test summary"
}

# ============================================================================
# Portal and 3D Scenes Studio Links (for manual inspection)
# ============================================================================

output "azure_3d_scenes_studio_url" {
  description = "Direct link to Azure 3D Scenes Studio for this ADT instance"
  value = local.has_scene_assets ? join("", [
    "https://explorer.digitaltwins.azure.net/3dscenes?",
    "adt-url=https://${azurerm_digital_twins_instance.test.host_name}&",
    "storage-url=https://${azurerm_storage_account.test.name}.blob.core.windows.net/${azurerm_storage_container.scenes[0].name}"
  ]) : null
}

output "azure_adt_portal_url" {
  description = "Azure Portal link to ADT instance"
  value = "https://portal.azure.com/#@/resource${azurerm_digital_twins_instance.test.id}/overview"
}

output "azure_storage_portal_url" {
  description = "Azure Portal link to Storage Account"
  value = "https://portal.azure.com/#@/resource${azurerm_storage_account.test.id}/overview"
}

# ============================================================================
# Platform User Outputs
# ============================================================================

output "platform_user_email" {
  description = "Email of the platform user (ADT Data Owner)"
  value       = var.platform_user_email != "" ? var.platform_user_email : null
}

output "platform_user_password" {
  description = "Initial password for platform user (only if new user was created)"
  value       = local.should_create_platform_user ? random_password.platform_user[0].result : null
  sensitive   = true
}

output "platform_user_created" {
  description = "Whether a new Entra ID user was created (true = created, false = existing)"
  value       = local.should_create_platform_user
}

output "azure_adt_access_instructions" {
  description = "How to access Azure Digital Twins and 3D Scenes Studio"
  value = <<-EOT
========== Azure Digital Twins Access ==========
ADT Instance: adt-${var.test_name_suffix}-${random_string.suffix.result}
ADT Endpoint: https://${azurerm_digital_twins_instance.test.host_name}

3D Scenes Studio: https://explorer.digitaltwins.azure.net/3dscenes
Storage Container: ${azurerm_storage_account.test.name}/${local.has_scene_assets ? azurerm_storage_container.scenes[0].name : "N/A"}

Platform User: ${var.platform_user_email != "" ? var.platform_user_email : "NOT CONFIGURED"}
${local.should_create_platform_user ? "Password: Run 'terraform output -raw platform_user_password'" : (local.platform_user_found ? "User: Existing (ADT Data Owner role assigned)" : "")}

Azure Portal: https://portal.azure.com
=================================================
EOT
}


