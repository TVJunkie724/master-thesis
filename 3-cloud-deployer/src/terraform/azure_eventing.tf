# Azure implementation of the independent six-layer-eventing@1 responsibility.
# The thesis PoC uses two replayable telemetry logs, one explicit failure log,
# ordered Service Bus control, one Flex worker, and one bounded log workspace.

locals {
  azure_event_enabled = (
    local.six_layer_eventing_enabled &&
    var.event_layer_provider == "azure"
  )
  azure_event_l1_local   = local.azure_event_enabled && var.layer_1_provider == "azure"
  azure_event_l2_local   = local.azure_event_enabled && var.layer_2_provider == "azure"
  azure_event_hot_local  = local.azure_event_enabled && var.layer_3_hot_provider == "azure"
  azure_event_twin_local = local.azure_event_enabled && var.layer_4_provider == "azure"
  azure_event_name       = substr(replace(lower(var.digital_twin_name), "_", "-"), 0, 22)

  azure_event_standard_tu_hours = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.azure.azure.event-hubs-standard-small-medium.throughput_unit_hours",
    "0",
  ))
  azure_event_dedicated_cu_hours = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.azure.azure.event-hubs-dedicated-large.capacity_unit_hours",
    "0",
  ))
  azure_event_dedicated_capacity_units = (
    local.azure_event_dedicated_cu_hours > 0
    ? ceil(local.azure_event_dedicated_cu_hours / 730)
    : var.azure_event_hubs_dedicated_capacity_units
  )
  azure_event_throughput_units = (
    local.azure_event_standard_tu_hours > 0
    ? ceil(local.azure_event_standard_tu_hours / 730)
    : var.azure_event_hubs_throughput_units
  )
  azure_event_dedicated = local.azure_event_dedicated_capacity_units > 0
  azure_event_partitions = (
    local.azure_event_dedicated ? 200 :
    local.azure_event_throughput_units > 1 ? 16 :
    var.azure_event_partitions
  )
  azure_event_retention_hours = (
    local.azure_event_dedicated || local.azure_event_throughput_units > 1
    ? 168
    : var.azure_event_retention_hours
  )
  azure_event_retention_iso = local.azure_event_retention_hours == 24 ? "P1D" : "P7D"
  azure_event_hub_names = {
    received  = "domain-telemetry-received"
    processed = "domain-telemetry-processed"
    failure   = "domain-telemetry-failure"
  }
  azure_event_processed_consumer_roles = local.azure_event_dedicated ? toset([
    "historical-persistence",
    "twin-state-update",
    "rule-evaluator",
    "audit",
    "realtime-visualization",
    ]) : toset([
    "historical-persistence",
    "twin-state-update",
    "rule-evaluator",
  ])
  azure_event_consumer_groups = merge(
    { telemetry-processor = { hub = "received" } },
    {
      for role in local.azure_event_processed_consumer_roles : role => {
        hub = "processed"
      }
    },
  )
  azure_event_local_processed_roles = concat(
    local.azure_event_hot_local ? ["historical-persistence"] : [],
    local.azure_event_twin_local ? ["twin-state-update"] : [],
    local.azure_event_l2_local ? ["rule-evaluator"] : [],
    local.azure_event_dedicated ? ["audit", "realtime-visualization"] : [],
  )
  azure_event_local_control_event_types = concat(
    local.azure_event_l2_local ? [
      "event.matched.v1",
      "notification.requested.v1",
      "extension.action.outcome.v1",
      "notification.workflow.outcome.v1",
      "device.command.outcome.v1",
    ] : [],
    local.azure_event_l1_local ? ["device.command.requested.v1"] : [],
  )
  azure_event_control_filter = length(local.azure_event_local_control_event_types) == 0 ? "1 = 0" : format(
    "event_type IN ('%s')",
    join("','", local.azure_event_local_control_event_types),
  )
  azure_event_domain_target_enabled = (
    local.azure_event_l1_local || local.azure_event_l2_local ||
    local.azure_event_hot_local || local.azure_event_twin_local
  )
  azure_event_namespace_name = try(one(concat(
    azurerm_eventhub_namespace.eventing_standard[*].name,
    azurerm_eventhub_namespace.eventing_dedicated[*].name,
  )), "")
  azure_event_package = (
    var.azure_event_zip_path != ""
    ? var.azure_event_zip_path
    : "${var.project_path}/.build/azure/six-layer-eventing.zip"
  )
  azure_event_tags = merge(local.common_tags, {
    ArchitectureProfile = "six-layer-eventing@1"
    Responsibility      = "eventing"
  })
}

resource "terraform_data" "azure_eventing_capacity_guard" {
  count = local.azure_event_enabled ? 1 : 0

  input = {
    dedicated_capacity_units = local.azure_event_dedicated_capacity_units
    throughput_units         = local.azure_event_throughput_units
    partitions               = local.azure_event_partitions
    retention_hours          = local.azure_event_retention_hours
  }

  lifecycle {
    precondition {
      condition = (
        (local.azure_event_dedicated && local.azure_event_dedicated_capacity_units == 6 && local.azure_event_throughput_units == 1) ||
        (!local.azure_event_dedicated && contains([1, 11], local.azure_event_throughput_units))
      )
      error_message = "Azure Event Layer capacity differs from the reviewed Small, Medium, or Large allocation."
    }
    precondition {
      condition = (
        (local.azure_event_dedicated && local.azure_event_partitions == 200) ||
        (!local.azure_event_dedicated && local.azure_event_throughput_units == 11 && local.azure_event_partitions == 16) ||
        (!local.azure_event_dedicated && local.azure_event_throughput_units == 1 && local.azure_event_partitions == 4)
      )
      error_message = "Azure Event Layer partition count differs from its reviewed capacity tier."
    }
  }
}

resource "azapi_resource" "event_hubs_dedicated_cluster" {
  count     = local.azure_event_enabled && local.azure_event_dedicated ? 1 : 0
  type      = "Microsoft.EventHub/clusters@2024-01-01"
  parent_id = azurerm_resource_group.main[0].id
  name      = "${local.azure_event_name}-event-ehc-${local.deployment_suffix}"
  location  = azurerm_resource_group.main[0].location
  tags      = local.azure_event_tags
  body = {
    sku = {
      name     = "Dedicated"
      capacity = local.azure_event_dedicated_capacity_units
    }
    properties = {
      supportsScaling = true
    }
  }
}

resource "azurerm_eventhub_namespace" "eventing_standard" {
  count                         = local.azure_event_enabled && !local.azure_event_dedicated ? 1 : 0
  name                          = "${local.azure_event_name}-event-eh-${local.deployment_suffix}"
  location                      = azurerm_resource_group.main[0].location
  resource_group_name           = azurerm_resource_group.main[0].name
  sku                           = "Standard"
  capacity                      = local.azure_event_throughput_units
  local_authentication_enabled  = false
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true
  tags                          = local.azure_event_tags
}

resource "azurerm_eventhub_namespace" "eventing_dedicated" {
  count                         = local.azure_event_enabled && local.azure_event_dedicated ? 1 : 0
  name                          = "${local.azure_event_name}-event-eh-${local.deployment_suffix}"
  location                      = azurerm_resource_group.main[0].location
  resource_group_name           = azurerm_resource_group.main[0].name
  sku                           = "Standard"
  capacity                      = 1
  dedicated_cluster_id          = azapi_resource.event_hubs_dedicated_cluster[0].id
  local_authentication_enabled  = false
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true
  tags                          = local.azure_event_tags
}

resource "azurerm_eventhub" "domain_telemetry_standard" {
  for_each        = local.azure_event_enabled && !local.azure_event_dedicated ? local.azure_event_hub_names : {}
  name            = each.value
  namespace_id    = azurerm_eventhub_namespace.eventing_standard[0].id
  partition_count = local.azure_event_partitions

  retention_description {
    cleanup_policy          = "Delete"
    retention_time_in_hours = local.azure_event_retention_hours
  }
}

resource "azurerm_eventhub" "domain_telemetry_dedicated" {
  for_each        = local.azure_event_enabled && local.azure_event_dedicated ? local.azure_event_hub_names : {}
  name            = each.value
  namespace_id    = azurerm_eventhub_namespace.eventing_dedicated[0].id
  partition_count = local.azure_event_partitions

  retention_description {
    cleanup_policy          = "Delete"
    retention_time_in_hours = local.azure_event_retention_hours
  }
}

resource "azurerm_eventhub_consumer_group" "domain_standard" {
  for_each            = local.azure_event_enabled && !local.azure_event_dedicated ? local.azure_event_consumer_groups : {}
  name                = each.key
  namespace_name      = azurerm_eventhub_namespace.eventing_standard[0].name
  eventhub_name       = azurerm_eventhub.domain_telemetry_standard[each.value.hub].name
  resource_group_name = azurerm_resource_group.main[0].name
  user_metadata       = "six-layer-eventing@1 independent consumer"
}

resource "azurerm_eventhub_consumer_group" "domain_dedicated" {
  for_each            = local.azure_event_enabled && local.azure_event_dedicated ? local.azure_event_consumer_groups : {}
  name                = each.key
  namespace_name      = azurerm_eventhub_namespace.eventing_dedicated[0].name
  eventhub_name       = azurerm_eventhub.domain_telemetry_dedicated[each.value.hub].name
  resource_group_name = azurerm_resource_group.main[0].name
  user_metadata       = "six-layer-eventing@1 independent consumer"
}

resource "azurerm_servicebus_namespace" "eventing" {
  count                         = local.azure_event_enabled ? 1 : 0
  name                          = "${local.azure_event_name}-event-sb-${local.deployment_suffix}"
  location                      = azurerm_resource_group.main[0].location
  resource_group_name           = azurerm_resource_group.main[0].name
  sku                           = "Standard"
  local_auth_enabled            = false
  minimum_tls_version           = "1.2"
  public_network_access_enabled = true
  tags                          = local.azure_event_tags
}

resource "azurerm_servicebus_topic" "domain_control" {
  count                                   = local.azure_event_enabled ? 1 : 0
  name                                    = "domain-control"
  namespace_id                            = azurerm_servicebus_namespace.eventing[0].id
  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"
  default_message_ttl                     = local.azure_event_retention_iso
}

resource "azurerm_servicebus_subscription" "domain_control" {
  count                                     = local.azure_event_enabled ? 1 : 0
  name                                      = "local-domain-consumer"
  topic_id                                  = azurerm_servicebus_topic.domain_control[0].id
  max_delivery_count                        = var.azure_event_max_delivery_count
  requires_session                          = true
  dead_lettering_on_message_expiration      = true
  dead_lettering_on_filter_evaluation_error = true
  default_message_ttl                       = local.azure_event_retention_iso
  lock_duration                             = "PT1M"
}

resource "azurerm_servicebus_subscription_rule" "domain_control" {
  count           = local.azure_event_enabled ? 1 : 0
  name            = "$Default"
  subscription_id = azurerm_servicebus_subscription.domain_control[0].id
  filter_type     = "SqlFilter"
  sql_filter      = local.azure_event_control_filter
}

resource "azurerm_log_analytics_workspace" "eventing" {
  count               = local.azure_event_enabled ? 1 : 0
  name                = "${local.azure_event_name}-event-logs-${local.deployment_suffix}"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name
  sku                 = "PerGB2018"
  retention_in_days   = var.azure_event_log_retention_days
  tags                = local.azure_event_tags
}

resource "azurerm_storage_container" "azure_event_function_package" {
  count                 = local.azure_event_enabled ? 1 : 0
  name                  = "six-layer-eventing-functions"
  storage_account_id    = azurerm_storage_account.main[0].id
  container_access_type = "private"
}

resource "azurerm_user_assigned_identity" "event_runtime" {
  count               = local.azure_event_enabled ? 1 : 0
  name                = "${local.azure_event_name}-event-runtime-${local.deployment_suffix}"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name
  tags                = local.azure_event_tags
}

data "azurerm_function_app_host_keys" "azure_event_domain_target" {
  count = local.azure_event_domain_target_enabled ? 1 : 0
  name = (
    local.azure_event_l2_local
    ? azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[0].name
    : azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter[0].name
  )
  resource_group_name = azurerm_resource_group.main[0].name
}

resource "azurerm_function_app_flex_consumption" "event_runtime" {
  count               = local.azure_event_enabled ? 1 : 0
  name                = "${local.azure_event_name}-event-runtime-${local.deployment_suffix}"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.azure_v2_flex[0].id

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.main[0].primary_blob_endpoint}${azurerm_storage_container.azure_event_function_package[0].name}"
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.main[0].primary_access_key

  runtime_name    = "python"
  runtime_version = "3.12"
  zip_deploy_file = local.azure_event_package

  maximum_instance_count                         = 100
  instance_memory_in_mb                          = var.azure_event_runtime_memory_mib
  https_only                                     = true
  public_network_access_enabled                  = true
  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.event_runtime[0].id]
  }

  site_config {
    minimum_tls_version              = "1.2"
    scm_minimum_tls_version          = "1.2"
    runtime_scale_monitoring_enabled = true
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME                   = "python"
    WEBSITE_RUN_FROM_PACKAGE                   = "1"
    ARCHITECTURE_PROFILE                       = "six-layer-eventing@1"
    EVENT_HUBS__fullyQualifiedNamespace        = "${local.azure_event_namespace_name}.servicebus.windows.net"
    EVENT_HUBS__credential                     = "managedidentity"
    EVENT_HUBS__clientId                       = azurerm_user_assigned_identity.event_runtime[0].client_id
    EVENT_SERVICE_BUS__fullyQualifiedNamespace = "${azurerm_servicebus_namespace.eventing[0].name}.servicebus.windows.net"
    EVENT_SERVICE_BUS__credential              = "managedidentity"
    EVENT_SERVICE_BUS__clientId                = azurerm_user_assigned_identity.event_runtime[0].client_id
    EVENT_MANAGED_IDENTITY_CLIENT_ID           = azurerm_user_assigned_identity.event_runtime[0].client_id
    EVENT_RECEIVED_HUB_NAME                    = local.azure_event_hub_names.received
    EVENT_PROCESSED_HUB_NAME                   = local.azure_event_hub_names.processed
    EVENT_FAILURE_HUB_NAME                     = local.azure_event_hub_names.failure
    EVENT_CONTROL_TOPIC_NAME                   = azurerm_servicebus_topic.domain_control[0].name
    EVENT_CONTROL_SUBSCRIPTION_NAME            = azurerm_servicebus_subscription.domain_control[0].name
    EVENT_LOCAL_PROCESSING_ENABLED             = tostring(local.azure_event_l2_local)
    EVENT_LOCAL_CONTROL_ENABLED                = tostring(local.azure_event_l1_local || local.azure_event_l2_local)
    EVENT_LOCAL_PROCESSED_ROLES_JSON           = jsonencode(local.azure_event_local_processed_roles)
    EVENT_DOMAIN_DELIVERY_URL = local.azure_event_domain_target_enabled ? format(
      "https://%s/api/eventing-delivery/v1",
      local.azure_event_l2_local
      ? azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[0].default_hostname
      : azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter[0].default_hostname,
    ) : ""
    EVENT_DOMAIN_DELIVERY_KEY = local.azure_event_domain_target_enabled ? data.azurerm_function_app_host_keys.azure_event_domain_target[0].default_function_key : ""
  }

  tags = local.azure_event_tags

  lifecycle {
    precondition {
      condition     = fileexists(local.azure_event_package)
      error_message = "Azure Event Layer requires its validated content-addressed Function package."
    }
    precondition {
      condition     = var.azure_event_runtime_batch_max == 10
      error_message = "Azure Event Layer host package is frozen to a maximum batch of 10."
    }
  }

  depends_on = [
    azurerm_role_assignment.azure_event_runtime,
    azurerm_role_assignment.azure_event_publishers,
    terraform_data.azure_eventing_capacity_guard,
  ]
}

locals {
  azure_event_runtime_role_bindings = local.azure_event_enabled ? {
    event_hubs_receiver = {
      scope = local.azure_event_dedicated ? azurerm_eventhub_namespace.eventing_dedicated[0].id : azurerm_eventhub_namespace.eventing_standard[0].id
      role  = "Azure Event Hubs Data Receiver"
    }
    event_failure_sender = {
      scope = local.azure_event_dedicated ? azurerm_eventhub.domain_telemetry_dedicated["failure"].id : azurerm_eventhub.domain_telemetry_standard["failure"].id
      role  = "Azure Event Hubs Data Sender"
    }
    control_receiver = {
      scope = azurerm_servicebus_subscription.domain_control[0].id
      role  = "Azure Service Bus Data Receiver"
    }
  } : {}
  azure_event_publisher_role_bindings = merge(
    local.azure_event_l1_local || local.azure_event_l2_local ? {
      telemetry_sender = {
        scope = local.azure_event_dedicated ? azurerm_eventhub_namespace.eventing_dedicated[0].id : azurerm_eventhub_namespace.eventing_standard[0].id
        role  = "Azure Event Hubs Data Sender"
      }
    } : {},
    local.azure_event_domain_target_enabled ? {
      control_sender = {
        scope = azurerm_servicebus_topic.domain_control[0].id
        role  = "Azure Service Bus Data Sender"
      }
    } : {},
  )
}

resource "azurerm_role_assignment" "azure_event_runtime" {
  for_each             = local.azure_event_runtime_role_bindings
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.event_runtime[0].principal_id
  principal_type       = "ServicePrincipal"

  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "azure_event_publishers" {
  for_each             = local.azure_event_publisher_role_bindings
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.main[0].principal_id
  principal_type       = "ServicePrincipal"

  skip_service_principal_aad_check = true
}

locals {
  azure_event_diagnostic_targets = local.azure_event_enabled ? {
    event_hubs  = local.azure_event_dedicated ? azurerm_eventhub_namespace.eventing_dedicated[0].id : azurerm_eventhub_namespace.eventing_standard[0].id
    service_bus = azurerm_servicebus_namespace.eventing[0].id
    function    = azurerm_function_app_flex_consumption.event_runtime[0].id
  } : {}
}

resource "azurerm_monitor_diagnostic_setting" "eventing" {
  for_each                   = local.azure_event_diagnostic_targets
  name                       = "six-layer-eventing-${each.key}"
  target_resource_id         = each.value
  log_analytics_workspace_id = azurerm_log_analytics_workspace.eventing[0].id

  enabled_log {
    category_group = "allLogs"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

output "azure_event_control_topic_id" {
  value = local.azure_event_enabled ? azurerm_servicebus_topic.domain_control[0].id : null
}

output "azure_event_hubs_standard_id" {
  value = local.azure_event_enabled && !local.azure_event_dedicated ? azurerm_eventhub_namespace.eventing_standard[0].id : null
}

output "azure_event_hubs_dedicated_id" {
  value = local.azure_event_enabled && local.azure_event_dedicated ? azurerm_eventhub_namespace.eventing_dedicated[0].id : null
}

output "azure_event_log_workspace_id" {
  value = local.azure_event_enabled ? azurerm_log_analytics_workspace.eventing[0].id : null
}

output "azure_event_runtime_id" {
  value = local.azure_event_enabled ? azurerm_function_app_flex_consumption.event_runtime[0].id : null
}
