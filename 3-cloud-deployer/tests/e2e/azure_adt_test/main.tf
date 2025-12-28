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
  
  common_tags = {
    Purpose = "adt-e2e-test"
  }
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
  name                     = "adt${var.test_name_suffix}${local.unique_suffix}"
  resource_group_name      = azurerm_resource_group.test.name
  location                 = azurerm_resource_group.test.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  # Enable blob public access for 3D Scenes Studio
  allow_nested_items_to_be_public = false
  
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

# Upload 3D Scenes configuration
resource "azurerm_storage_blob" "scene_config" {
  count                  = local.has_scene_assets ? 1 : 0
  name                   = "3DScenesConfiguration.json"
  storage_account_name   = azurerm_storage_account.test.name
  storage_container_name = azurerm_storage_container.scenes[0].name
  type                   = "Block"
  source                 = "${local.scene_assets_azure}/3DScenesConfiguration.json"
  content_md5            = filemd5("${local.scene_assets_azure}/3DScenesConfiguration.json")
  content_type           = "application/json"
}

# ============================================================================
# Azure Digital Twins Instance
# ============================================================================

resource "azurerm_digital_twins_instance" "test" {
  name                = "${local.resource_prefix}-${local.unique_suffix}"
  resource_group_name = azurerm_resource_group.test.name
  location            = azurerm_resource_group.test.location
  
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
