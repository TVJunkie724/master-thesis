# Azure L4 Digital Twins Layer (Twin Management)
#
# This file creates the L4 layer infrastructure for Digital Twin management.
# L4 maintains a real-time digital representation of physical IoT devices.
#
# Resources Created:
# - Azure Digital Twins Instance: Twin graph service
# - RBAC Role Assignments: Managed Identity access to ADT
# - Event Grid Topic: For twin change events (optional)
#
# Note: DTDL models and twin instances are created by Python orchestrator
# after Terraform provisions the ADT instance, as models are generated
# dynamically from config_hierarchy.json.
#
# Architecture:
#     L3 Hot Storage → ADT Updater (Python SDK) → Azure Digital Twins
#
# Note: L4 does NOT require a dedicated Function App. The ADT is updated:
# - Same-cloud: Python SDK calls directly from L2 persister
# - Cross-cloud: Via L0 Glue layer (ADT Pusher function)

# ==============================================================================
# Azure Digital Twins Instance
# ==============================================================================

resource "azurerm_digital_twins_instance" "main" {
  count               = var.layer_4_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-adt"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location

  # SystemAssigned identity required for RBAC to access storage for 3D Scenes
  identity {
    type = "SystemAssigned"
  }

  tags = local.common_tags
}

# ==============================================================================
# RBAC: Managed Identity → Azure Digital Twins Data Owner
# ==============================================================================

resource "azurerm_role_assignment" "identity_adt_owner" {
  count                = var.layer_4_provider == "azure" ? 1 : 0
  scope                = azurerm_digital_twins_instance.main[0].id
  role_definition_name = "Azure Digital Twins Data Owner"
  principal_id         = azurerm_user_assigned_identity.main[0].principal_id
}

# ==============================================================================
# RBAC: Service Principal → Azure Digital Twins Data Owner
# (For Python orchestrator to upload DTDL models)
# ==============================================================================

# Note: The service principal used by the deployer also needs ADT access.
# This is typically the same principal used for Terraform authentication.
# If using a different principal for the Python orchestrator, add a separate
# role assignment here.

# ==============================================================================
# Event Grid Topic for ADT Events (Optional - for change notifications)
# ==============================================================================

# Uncomment if you need to subscribe to ADT twin change events
# resource "azurerm_eventgrid_topic" "adt_events" {
#   count               = var.layer_4_provider == "azure" ? 1 : 0
#   name                = "${var.digital_twin_name}-adt-events"
#   resource_group_name = azurerm_resource_group.main[0].name
#   location            = azurerm_resource_group.main[0].location
#
#   tags = local.common_tags
# }

# ==============================================================================
# 3D Scene Assets for ADT 3D Scenes Studio
# ==============================================================================

locals {
  l4_azure_scene_enabled = var.layer_4_provider == "azure" && var.needs_3d_model && var.scene_assets_path != ""
  scene_assets_azure     = var.scene_assets_path != "" ? "${var.scene_assets_path}/azure" : ""
}

# Storage container for 3D scenes
resource "azurerm_storage_container" "scenes" {
  count                 = local.l4_azure_scene_enabled ? 1 : 0
  name                  = "3dscenes"
  storage_account_id    = azurerm_storage_account.main[0].id
  container_access_type = "private"
}

# Upload GLB model
resource "azurerm_storage_blob" "scene_glb" {
  count                  = local.l4_azure_scene_enabled ? 1 : 0
  name                   = "scene.glb"
  storage_account_name   = azurerm_storage_account.main[0].name
  storage_container_name = azurerm_storage_container.scenes[0].name
  type                   = "Block"
  source                 = "${local.scene_assets_azure}/scene.glb"
  content_md5            = filemd5("${local.scene_assets_azure}/scene.glb")
  content_type           = "model/gltf-binary"
}

# Upload 3D Scenes configuration with dynamic URL replacement
# The template file contains {{STORAGE_URL}} placeholder which is replaced with actual storage URL
locals {
  scene_config_raw = local.l4_azure_scene_enabled ? file("${local.scene_assets_azure}/3DScenesConfiguration.json") : ""
  scene_storage_url = local.l4_azure_scene_enabled ? "https://${azurerm_storage_account.main[0].name}.blob.core.windows.net/${azurerm_storage_container.scenes[0].name}" : ""
  scene_config_content = replace(local.scene_config_raw, "{{STORAGE_URL}}", local.scene_storage_url)
}

resource "azurerm_storage_blob" "scene_config" {
  count                  = local.l4_azure_scene_enabled ? 1 : 0
  name                   = "3DScenesConfiguration.json"
  storage_account_name   = azurerm_storage_account.main[0].name
  storage_container_name = azurerm_storage_container.scenes[0].name
  type                   = "Block"
  source_content         = local.scene_config_content
  content_md5            = md5(local.scene_config_content)
  content_type           = "application/json"
}

# ==============================================================================
# RBAC: ADT Identity → Storage Blob Data Reader
# (Required for ADT to read 3D scene files from storage for 3D Scenes Studio)
# ==============================================================================

resource "azurerm_role_assignment" "adt_storage_reader" {
  count                = local.l4_azure_scene_enabled ? 1 : 0
  scope                = azurerm_storage_account.main[0].id
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = azurerm_digital_twins_instance.main[0].identity[0].principal_id

  depends_on = [azurerm_digital_twins_instance.main]
}

# ==============================================================================
# RBAC: Platform User → Azure Digital Twins Data Owner
# (Required for user to access ADT instance via 3D Scenes Studio)
# ==============================================================================

locals {
  # Enable user ADT access when L4=Azure AND email is provided
  l4_azure_user_enabled = var.layer_4_provider == "azure" && var.platform_user_email != ""
}

resource "azurerm_role_assignment" "adt_user_owner" {
  count                = local.l4_azure_user_enabled ? 1 : 0
  scope                = azurerm_digital_twins_instance.main[0].id
  role_definition_name = "Azure Digital Twins Data Owner"
  
  # Use deterministic UUID for idempotency
  name                 = uuidv5("dns", "${var.platform_user_email}-adt-owner")
  principal_id         = local.platform_user_object_id

  depends_on = [azuread_user.platform_user]
}

# ==============================================================================
# RBAC: Platform User → Storage Blob Data Reader
# (Required for user to view 3D scenes in 3D Scenes Studio)
# ==============================================================================

resource "azurerm_role_assignment" "scenes_user_reader" {
  count                = local.l4_azure_user_enabled && local.l4_azure_scene_enabled ? 1 : 0
  scope                = azurerm_storage_account.main[0].id
  role_definition_name = "Storage Blob Data Reader"
  
  # Use deterministic UUID for idempotency
  name                 = uuidv5("dns", "${var.platform_user_email}-scenes-reader")
  principal_id         = local.platform_user_object_id

  depends_on = [azuread_user.platform_user]
}
