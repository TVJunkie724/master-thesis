# Azure implementation of the mandatory embedded event responsibilities in
# five-layer-baseline@2. Event Hubs exists only for reviewed remote telemetry
# edges; Service Bus remains the ordered low-rate domain/control broker.

locals {
  azure_v2_l1_enabled  = local.azure_v2_enabled && var.layer_1_provider == "azure"
  azure_v2_l2_enabled  = local.azure_v2_enabled && var.layer_2_provider == "azure"
  azure_v2_hot_enabled = local.azure_v2_enabled && var.layer_3_hot_provider == "azure"
  azure_v2_l4_enabled  = local.azure_v2_enabled && var.layer_4_provider == "azure"

  azure_v2_event_enabled = (
    local.azure_v2_l1_enabled || local.azure_v2_l2_enabled ||
    local.azure_v2_hot_enabled || local.azure_v2_l4_enabled
  )
  azure_v2_remote_telemetry_outbound = local.five_layer_v2_enabled && (
    (var.layer_1_provider == "azure" && var.layer_2_provider != "azure") ||
    (var.layer_2_provider == "azure" && var.layer_3_hot_provider != "azure") ||
    (var.layer_3_hot_provider == "azure" && var.layer_4_provider != "azure")
  )
  azure_v2_remote_telemetry_inbound = local.five_layer_v2_enabled && (
    (var.layer_1_provider != "azure" && var.layer_2_provider == "azure") ||
    (var.layer_2_provider != "azure" && var.layer_3_hot_provider == "azure") ||
    (var.layer_3_hot_provider != "azure" && var.layer_4_provider == "azure")
  )
  azure_v2_remote_telemetry_routes = {
    for direction, enabled in {
      inbound  = local.azure_v2_remote_telemetry_inbound
      outbound = local.azure_v2_remote_telemetry_outbound
    } : direction => direction if enabled
  }
  azure_v2_remote_telemetry_enabled = length(local.azure_v2_remote_telemetry_routes) > 0
  azure_v2_remote_control_outbound  = local.five_layer_v2_enabled && var.layer_2_provider == "azure" && var.layer_1_provider != "azure"
  azure_v2_remote_control_inbound   = local.five_layer_v2_enabled && var.layer_2_provider != "azure" && var.layer_1_provider == "azure"

  azure_v2_event_hubs_tu_hours = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.azure.azure.event-hubs-only-for-reviewed-remote-telemetry-edge.throughput_unit_hours",
    "0",
  ))
  azure_v2_event_hubs_cu_hours = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.azure.azure.event-hubs-only-for-reviewed-remote-telemetry-edge.capacity_unit_hours",
    "0",
  ))
  azure_v2_event_hubs_dedicated = local.azure_v2_remote_telemetry_enabled && local.azure_v2_event_hubs_cu_hours > 0
  azure_v2_event_hubs_tu        = max(1, ceil(local.azure_v2_event_hubs_tu_hours / 730))
  azure_v2_event_hubs_cu        = max(1, ceil(local.azure_v2_event_hubs_cu_hours / 730))
  azure_v2_event_hub_partitions = (
    local.azure_v2_event_hubs_dedicated ? 200 :
    local.azure_v2_event_hubs_tu > 1 ? 16 : 4
  )

  azure_v2_name = substr(replace(lower(var.digital_twin_name), "_", "-"), 0, 22)
  azure_v2_runtime_package = (
    var.azure_v2_zip_path != ""
    ? var.azure_v2_zip_path
    : "${var.project_path}/.build/azure/five-layer-v2.zip"
  )
  azure_v2_tags = merge(local.common_tags, {
    ArchitectureProfile = "five-layer-baseline@2"
  })
}

resource "terraform_data" "azure_v2_event_capacity_guard" {
  count = local.azure_v2_remote_telemetry_enabled ? 1 : 0

  input = {
    throughput_units = local.azure_v2_event_hubs_tu
    capacity_units   = local.azure_v2_event_hubs_cu
    dedicated        = local.azure_v2_event_hubs_dedicated
  }

  lifecycle {
    precondition {
      condition = (
        (local.azure_v2_event_hubs_dedicated && local.azure_v2_event_hubs_cu == 6 && local.azure_v2_event_hubs_tu_hours == 0) ||
        (!local.azure_v2_event_hubs_dedicated && local.azure_v2_event_hubs_tu >= 1 && local.azure_v2_event_hubs_tu <= 40 && local.azure_v2_event_hubs_cu_hours == 0)
      )
      error_message = "Azure remote telemetry must resolve to Standard 1-40 TU or the reviewed Dedicated 6-CU Large allocation."
    }
  }
}

resource "azurerm_log_analytics_workspace" "azure_azure_log_analytics_shared_workspace" {
  count               = local.azure_v2_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-logs-${local.deployment_suffix}"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name
  sku                 = "PerGB2018"
  retention_in_days   = max(30, var.log_retention_days)
  tags                = local.azure_v2_tags
}

resource "azurerm_servicebus_namespace" "azure_azure_service_bus_standard" {
  count                         = local.azure_v2_event_enabled ? 1 : 0
  name                          = "${local.azure_v2_name}-v2-sb-${local.deployment_suffix}"
  location                      = azurerm_resource_group.main[0].location
  resource_group_name           = azurerm_resource_group.main[0].name
  sku                           = "Standard"
  local_auth_enabled            = false
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true
  tags                          = local.azure_v2_tags
}

resource "azurerm_servicebus_queue" "azure_azure_service_bus_standard" {
  count                                   = local.azure_v2_event_enabled ? 1 : 0
  name                                    = "domain-events"
  namespace_id                            = azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].id
  requires_session                        = true
  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"
  dead_lettering_on_message_expiration    = true
  default_message_ttl                     = "P14D"
  lock_duration                           = "PT1M"
  max_delivery_count                      = 5
}

resource "azurerm_servicebus_topic" "azure_azure_service_bus_standard" {
  count                                   = local.azure_v2_event_enabled ? 1 : 0
  name                                    = "domain-control-events"
  namespace_id                            = azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].id
  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"
  default_message_ttl                     = "P14D"
}

resource "azurerm_servicebus_subscription" "azure_azure_service_bus_standard" {
  count                                     = local.azure_v2_event_enabled ? 1 : 0
  name                                      = "domain-consumer"
  topic_id                                  = azurerm_servicebus_topic.azure_azure_service_bus_standard[0].id
  max_delivery_count                        = 5
  requires_session                          = true
  dead_lettering_on_message_expiration      = true
  dead_lettering_on_filter_evaluation_error = true
  default_message_ttl                       = "P14D"
  lock_duration                             = "PT1M"
  forward_to                                = azurerm_servicebus_queue.azure_azure_service_bus_standard[0].name
}

resource "azurerm_eventhub_cluster" "azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge" {
  count               = local.azure_v2_event_hubs_dedicated ? 1 : 0
  name                = "${local.azure_v2_name}-v2-ehc-${local.deployment_suffix}"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  sku_name            = "Dedicated_1"
  tags                = local.azure_v2_tags
}

resource "azapi_update_resource" "azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge" {
  count       = local.azure_v2_event_hubs_dedicated ? 1 : 0
  type        = "Microsoft.EventHub/clusters@2024-01-01"
  resource_id = azurerm_eventhub_cluster.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].id
  body = {
    sku = {
      name     = "Dedicated"
      capacity = local.azure_v2_event_hubs_cu
    }
  }
}

resource "azurerm_eventhub_namespace" "azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge" {
  count                         = local.azure_v2_remote_telemetry_enabled ? 1 : 0
  name                          = "${local.azure_v2_name}-v2-eh-${local.deployment_suffix}"
  location                      = azurerm_resource_group.main[0].location
  resource_group_name           = azurerm_resource_group.main[0].name
  # A namespace inside a Dedicated cluster still uses the Standard namespace
  # SKU; the cluster association supplies the dedicated capacity boundary.
  sku                           = "Standard"
  capacity                      = local.azure_v2_event_hubs_dedicated ? 1 : local.azure_v2_event_hubs_tu
  dedicated_cluster_id          = local.azure_v2_event_hubs_dedicated ? azurerm_eventhub_cluster.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].id : null
  local_authentication_enabled  = false
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true
  tags                          = local.azure_v2_tags

  depends_on = [azapi_update_resource.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge]
}

resource "azurerm_eventhub" "azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge" {
  for_each          = local.azure_v2_remote_telemetry_routes
  name              = "remote-telemetry-${each.key}"
  namespace_id      = azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].id
  partition_count   = local.azure_v2_event_hub_partitions
  message_retention = 1
}

resource "azurerm_storage_container" "azure_v2_function_package" {
  count                 = local.azure_v2_event_enabled ? 1 : 0
  name                  = "five-layer-v2-functions"
  storage_account_id    = azurerm_storage_account.main[0].id
  container_access_type = "private"
}

resource "azurerm_service_plan" "azure_v2_flex" {
  count               = local.azure_v2_event_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-flex"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  os_type             = "Linux"
  sku_name            = "FC1"
  tags                = local.azure_v2_tags
}

resource "azurerm_function_app_flex_consumption" "azure_azure_functions_flex_event_adapter" {
  count               = local.azure_v2_event_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-events-${local.deployment_suffix}"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.azure_v2_flex[0].id

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.main[0].primary_blob_endpoint}${azurerm_storage_container.azure_v2_function_package[0].name}"
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.main[0].primary_access_key

  runtime_name    = "python"
  runtime_version = "3.12"
  zip_deploy_file = local.azure_v2_runtime_package

  maximum_instance_count                         = 100
  instance_memory_in_mb                          = 2048
  https_only                                     = true
  public_network_access_enabled                  = true
  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main[0].id]
  }

  site_config {
    minimum_tls_version              = "1.2"
    scm_minimum_tls_version          = "1.2"
    runtime_scale_monitoring_enabled = true
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME                     = "python"
    WEBSITE_RUN_FROM_PACKAGE                     = "1"
    ARCHITECTURE_PROFILE                         = "five-layer-baseline@2"
    DEPLOYMENT_ID                                = local.deployment_suffix
    V2_DOMAIN_QUEUE_NAME                         = azurerm_servicebus_queue.azure_azure_service_bus_standard[0].name
    V2_DOMAIN_TOPIC_NAME                         = azurerm_servicebus_topic.azure_azure_service_bus_standard[0].name
    V2_SERVICE_BUS__fullyQualifiedNamespace      = "${azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].name}.servicebus.windows.net"
    V2_SERVICE_BUS__credential                   = "managedidentity"
    V2_SERVICE_BUS__clientId                     = azurerm_user_assigned_identity.main[0].client_id
    V2_REMOTE_TELEMETRY_ENABLED                  = tostring(local.azure_v2_remote_telemetry_inbound)
    V2_REMOTE_TELEMETRY_HUB_NAME                 = try(azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].name, "disabled")
    V2_REMOTE_TELEMETRY__fullyQualifiedNamespace = local.azure_v2_remote_telemetry_enabled ? "${azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].name}.servicebus.windows.net" : "disabled.servicebus.windows.net"
    V2_REMOTE_TELEMETRY__credential              = "managedidentity"
    V2_REMOTE_TELEMETRY__clientId                = azurerm_user_assigned_identity.main[0].client_id
  }

  tags = local.azure_v2_tags

  lifecycle {
    precondition {
      condition     = fileexists(local.azure_v2_runtime_package)
      error_message = "Azure Five-layer v2 requires its validated content-addressed Function package."
    }
  }
}

locals {
  azure_v2_event_role_bindings = merge(
    local.azure_v2_event_enabled ? {
      service_bus_receiver = {
        scope = azurerm_servicebus_queue.azure_azure_service_bus_standard[0].id
        role  = "Azure Service Bus Data Receiver"
      }
      service_bus_sender = {
        scope = azurerm_servicebus_topic.azure_azure_service_bus_standard[0].id
        role  = "Azure Service Bus Data Sender"
      }
    } : {},
    local.azure_v2_remote_telemetry_inbound ? {
      event_hubs_receiver = {
        scope = azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].id
        role  = "Azure Event Hubs Data Receiver"
      }
    } : {},
    local.azure_v2_remote_telemetry_outbound ? {
      event_hubs_sender = {
        scope = azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["outbound"].id
        role  = "Azure Event Hubs Data Sender"
      }
    } : {},
  )
}

resource "azurerm_role_assignment" "azure_azure_entra_layer_access_bindings" {
  for_each             = local.azure_v2_event_role_bindings
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.main[0].principal_id
  principal_type       = "ServicePrincipal"
}

locals {
  azure_v2_diagnostic_targets = merge(
    local.azure_v2_event_enabled ? {
      service_bus = azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].id
      function    = azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter[0].id
    } : {},
    local.azure_v2_remote_telemetry_enabled ? {
      event_hubs = azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].id
    } : {},
  )
}

resource "azurerm_monitor_diagnostic_setting" "azure_azure_monitor" {
  for_each                   = local.azure_v2_diagnostic_targets
  name                       = "five-layer-v2-${each.key}"
  target_resource_id         = each.value
  log_analytics_workspace_id = azurerm_log_analytics_workspace.azure_azure_log_analytics_shared_workspace[0].id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
