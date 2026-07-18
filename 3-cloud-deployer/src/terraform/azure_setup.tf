# Azure Setup Layer (Foundation Resources)
#
# This file creates the foundational Azure resources that all other layers depend on.
# Resources are created conditionally based on whether any layer uses Azure.
#
# Resources Created:
# - Resource Group: Container for all Azure resources
# - User-Assigned Managed Identity: For secure authentication between services
# - Storage Account: For Azure Function deployments and state storage

# ==============================================================================
# Azure Resource Names - Single Source of Truth
# ==============================================================================

locals {
  # Setup
  azure_resource_group_name = "${var.digital_twin_name}-rg"
  azure_identity_name       = "${var.digital_twin_name}-identity"
  # Azure storage accounts: max 24 chars, lowercase alphanumeric only, globally unique
  azure_storage_account_name = substr("${replace(var.digital_twin_name, "-", "")}st${local.deployment_suffix}", 0, 24)

  # L0 Glue
  azure_l0_plan_name     = "${var.digital_twin_name}-l0-plan"
  azure_l0_glue_name     = "${var.digital_twin_name}-l0-glue-${local.deployment_suffix}"
  azure_l0_content_share = "${var.digital_twin_name}-l0-content"

  # L1 IoT
  azure_iothub_name         = "${var.digital_twin_name}-iothub-${local.deployment_suffix}"
  azure_l1_plan_name        = "${var.digital_twin_name}-l1-plan"
  azure_l1_functions_name   = "${var.digital_twin_name}-l1-functions-${local.deployment_suffix}"
  azure_l1_content_share    = "${var.digital_twin_name}-l1-content"
  azure_iothub_events_name  = "${var.digital_twin_name}-iothub-events"
  azure_iothub_subscription = "${var.digital_twin_name}-iothub-subscription"

  # L2 Compute
  azure_l2_plan_name        = "${var.digital_twin_name}-l2-plan"
  azure_l2_functions_name   = "${var.digital_twin_name}-l2-functions-${local.deployment_suffix}"
  azure_l2_content_share    = "${var.digital_twin_name}-l2-content"
  azure_user_functions_name = "${var.digital_twin_name}-user-functions-${local.deployment_suffix}"
  azure_user_content_share  = "${var.digital_twin_name}-user-content"
  azure_event_workflow_name = "${var.digital_twin_name}-event-workflow"
  azure_logic_app_name      = "${var.digital_twin_name}-logic-app-definition"

  # L3 Storage
  azure_cosmos_account_name   = "${var.digital_twin_name}-cosmos-${local.deployment_suffix}"
  azure_cosmos_db_name        = "${var.digital_twin_name}-db"
  azure_cosmos_container_name = local.storage_tier_hot # Uses cross-provider constant
  azure_l3_plan_name          = "${var.digital_twin_name}-l3-plan"
  azure_l3_functions_name     = "${var.digital_twin_name}-l3-functions-${local.deployment_suffix}"
  azure_l3_content_share      = "${var.digital_twin_name}-l3-content"

  # L4 ADT
  azure_adt_name = "${var.digital_twin_name}-adt"
  # Note: uses local.scenes_container_name from cross_cloud.tf

  # L5 Grafana
  azure_grafana_name = "${var.digital_twin_name}-grafana"

  # ===========================================================================
  # Azure URLs - Centralized function app URLs
  # ===========================================================================

  azure_l0_glue_url        = "https://${local.azure_l0_glue_name}.azurewebsites.net"
  azure_l1_functions_url   = "https://${local.azure_l1_functions_name}.azurewebsites.net"
  azure_l2_functions_url   = "https://${local.azure_l2_functions_name}.azurewebsites.net"
  azure_user_functions_url = "https://${local.azure_user_functions_name}.azurewebsites.net"
  # ADT URL must use the actual host_name from the resource (not string-constructed)
  # Azure's format is: name.api.region-code.digitaltwins.azure.net (e.g., .api.weu.)
  azure_adt_url = try("https://${azurerm_digital_twins_instance.main[0].host_name}", "")

  # L0 is an implementation host, not a provider-wide foundation resource. Keep
  # this condition aligned with function_registry.get_l0_for_config().
  azure_cross_cloud_receiver_required = (
    (var.layer_1_provider != var.layer_2_provider && var.layer_2_provider == "azure") ||
    (var.layer_2_provider != var.layer_3_hot_provider && var.layer_3_hot_provider == "azure") ||
    (var.layer_3_hot_provider != var.layer_3_cold_provider && var.layer_3_cold_provider == "azure") ||
    (var.layer_3_cold_provider != var.layer_3_archive_provider && var.layer_3_archive_provider == "azure") ||
    (var.layer_4_provider != var.layer_3_hot_provider && var.layer_3_hot_provider == "azure")
  )
  azure_l0_enabled = local.azure_cross_cloud_receiver_required || var.layer_4_provider == "azure"
  azure_l0_function_plan_sku = (
    var.layer_4_provider == "azure"
    ? var.azure_l4_function_plan_sku
    : var.azure_glue_function_plan_sku
  )

  azure_blob_storage_enabled = (
    var.layer_3_cold_provider == "azure" ||
    var.layer_3_archive_provider == "azure"
  )
  # Function Apps require a host storage account even when Azure does not own a
  # costed Blob slot. Standard/LRS is the explicit support-resource invariant.
  azure_effective_storage_account_tier = (
    local.azure_blob_storage_enabled
    ? coalesce(var.azure_storage_account_tier, "Standard")
    : "Standard"
  )
  azure_effective_storage_replication_type = (
    local.azure_blob_storage_enabled
    ? coalesce(var.azure_storage_replication_type, "LRS")
    : "LRS"
  )
}

# Fail before provider execution if an active Azure component is missing its
# immutable optimizer-owned deployment selection.
resource "terraform_data" "azure_deployment_specification_guard" {
  count = local.deploy_azure ? 1 : 0

  input = {
    iot_hub_sku                    = var.azure_iot_hub_sku
    iot_hub_capacity               = var.azure_iot_hub_capacity
    l1_function_plan_sku           = var.azure_l1_function_plan_sku
    l2_function_plan_sku           = var.azure_l2_function_plan_sku
    cosmos_capacity_mode           = var.azure_cosmos_capacity_mode
    l3_function_plan_sku           = var.azure_l3_function_plan_sku
    storage_account_tier           = var.azure_storage_account_tier
    storage_replication_type       = var.azure_storage_replication_type
    l3_cool_blob_tier              = var.azure_l3_cool_blob_tier
    hot_to_cool_timer_schedule     = var.azure_hot_to_cool_timer_schedule
    l3_archive_blob_tier           = var.azure_l3_archive_blob_tier
    cool_to_archive_timer_schedule = var.azure_cool_to_archive_timer_schedule
    l4_function_plan_sku           = var.azure_l4_function_plan_sku
    grafana_sku                    = var.azure_grafana_sku
    glue_function_plan_sku         = var.azure_glue_function_plan_sku
  }

  lifecycle {
    precondition {
      condition = var.layer_1_provider != "azure" || (
        var.azure_iot_hub_sku != null &&
        var.azure_iot_hub_capacity != null &&
        var.azure_l1_function_plan_sku != null
      )
      error_message = "Azure L1 requires IoT Hub SKU/capacity and Function plan selections from the resolved deployment specification."
    }
    precondition {
      condition = var.layer_1_provider != "azure" || (
        var.azure_iot_hub_sku == "F1" ? var.azure_iot_hub_capacity == 1 :
        var.azure_iot_hub_sku == "S1" ? var.azure_iot_hub_capacity >= 1 && var.azure_iot_hub_capacity <= 200 :
        var.azure_iot_hub_sku == "S2" ? var.azure_iot_hub_capacity >= 1 && var.azure_iot_hub_capacity <= 200 :
        var.azure_iot_hub_sku == "S3" ? var.azure_iot_hub_capacity >= 1 && var.azure_iot_hub_capacity <= 10 :
        false
      )
      error_message = "Azure IoT Hub SKU/capacity combination is outside the resolved deployment contract."
    }
    precondition {
      condition     = var.layer_2_provider != "azure" || var.azure_l2_function_plan_sku != null
      error_message = "Azure L2 requires azure_l2_function_plan_sku from the resolved deployment specification."
    }
    precondition {
      condition = var.layer_3_hot_provider != "azure" || (
        var.azure_cosmos_capacity_mode != null &&
        var.azure_l3_function_plan_sku != null &&
        var.azure_hot_to_cool_timer_schedule != null
      )
      error_message = "Azure L3 hot requires Cosmos, Function plan, and hot-to-cool schedule selections from the resolved deployment specification."
    }
    precondition {
      condition = var.layer_3_cold_provider != "azure" || (
        var.azure_storage_account_tier != null &&
        var.azure_storage_replication_type != null &&
        var.azure_l3_cool_blob_tier != null &&
        var.azure_l3_function_plan_sku != null &&
        var.azure_cool_to_archive_timer_schedule != null
      )
      error_message = "Azure L3 cool requires storage, Blob tier, Function plan, and cool-to-archive schedule selections from the resolved deployment specification."
    }
    precondition {
      condition = var.layer_3_archive_provider != "azure" || (
        var.azure_storage_account_tier != null &&
        var.azure_storage_replication_type != null &&
        var.azure_l3_archive_blob_tier != null
      )
      error_message = "Azure L3 archive requires storage and Blob tier selections from the resolved deployment specification."
    }
    precondition {
      condition     = var.layer_4_provider != "azure" || var.azure_l4_function_plan_sku != null
      error_message = "Azure L4 requires azure_l4_function_plan_sku from the resolved deployment specification."
    }
    precondition {
      condition     = var.layer_5_provider != "azure" || var.azure_grafana_sku != null
      error_message = "Azure L5 requires azure_grafana_sku from the resolved deployment specification."
    }
    precondition {
      condition     = !local.azure_cross_cloud_receiver_required || var.azure_glue_function_plan_sku != null
      error_message = "Azure cross-cloud receivers require azure_glue_function_plan_sku from the resolved deployment specification."
    }
    precondition {
      condition = (
        var.azure_l4_function_plan_sku == null ||
        var.azure_glue_function_plan_sku == null ||
        var.azure_l4_function_plan_sku == var.azure_glue_function_plan_sku
      )
      error_message = "Azure L4 pusher and cross-cloud receivers share one L0 Function plan and must select the same SKU."
    }
  }
}

# ==============================================================================
# Resource Group
# ==============================================================================

resource "azurerm_resource_group" "main" {
  count    = local.deploy_azure ? 1 : 0
  name     = local.azure_resource_group_name
  location = var.azure_region

  tags = local.common_tags
}

# ==============================================================================
# User-Assigned Managed Identity
# ==============================================================================

resource "azurerm_user_assigned_identity" "main" {
  count               = local.deploy_azure ? 1 : 0
  name                = local.azure_identity_name
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location

  tags = local.common_tags
}

# ==============================================================================
# Storage Account (for Function App deployments)
# ==============================================================================

resource "azurerm_storage_account" "main" {
  count                    = local.deploy_azure ? 1 : 0
  name                     = local.azure_storage_account_name
  resource_group_name      = azurerm_resource_group.main[0].name
  location                 = azurerm_resource_group.main[0].location
  account_tier             = local.azure_effective_storage_account_tier
  account_replication_type = local.azure_effective_storage_replication_type
  min_tls_version          = "TLS1_2"

  # CORS configuration for Azure 3D Scenes Studio
  # Required for the 3D visualization to access GLB assets from the storage account
  blob_properties {
    cors_rule {
      allowed_origins = ["https://explorer.digitaltwins.azure.net"]
      # Include write methods for 3D Scene building (PUT for saving configs)
      allowed_methods    = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "DELETE"]
      allowed_headers    = ["*"]
      exposed_headers    = ["*"]
      max_age_in_seconds = 3600
    }
  }

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
