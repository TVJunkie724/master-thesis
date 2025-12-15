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
