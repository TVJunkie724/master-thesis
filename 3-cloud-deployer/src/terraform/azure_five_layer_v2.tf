# Azure implementation of the mandatory embedded event responsibilities in
# five-layer-baseline@2. Event Hubs exists only for reviewed remote telemetry
# edges; Service Bus remains the ordered low-rate domain/control broker.

locals {
  azure_v2_l1_enabled      = local.azure_v2_enabled && var.layer_1_provider == "azure"
  azure_v2_l2_enabled      = local.azure_v2_enabled && var.layer_2_provider == "azure"
  azure_v2_hot_enabled     = local.azure_v2_enabled && var.layer_3_hot_provider == "azure"
  azure_v2_cool_enabled    = local.azure_v2_enabled && var.layer_3_cold_provider == "azure"
  azure_v2_archive_enabled = local.azure_v2_enabled && var.layer_3_archive_provider == "azure"
  azure_v2_l4_enabled      = local.azure_v2_enabled && var.layer_4_provider == "azure"
  azure_v2_l5_enabled      = local.azure_v2_enabled && var.layer_5_provider == "azure"

  azure_v2_event_enabled = (
    local.azure_v2_l1_enabled || local.azure_v2_l2_enabled ||
    local.azure_v2_hot_enabled || local.azure_v2_l4_enabled ||
    local.azure_event_enabled
  )
  azure_v2_embedded_event_enabled = (
    local.azure_v2_event_enabled &&
    !(local.six_layer_eventing_enabled && var.event_layer_provider == "azure")
  )
  azure_v2_service_bus_enabled = (
    local.azure_v2_embedded_event_enabled ||
    local.azure_v2_remote_control_outbound ||
    local.azure_v2_remote_control_inbound
  )
  azure_v2_function_infrastructure_enabled = (
    local.azure_v2_event_enabled || local.azure_v2_l5_enabled || local.azure_event_enabled
  )
  azure_v2_outbound_event_routes = {
    for route in var.resolved_cross_cloud_routes : route.route_id => route
    if local.five_layer_v2_enabled && route.execution_kind == "source_event_forwarder" && route.source_provider == "azure"
  }
  azure_v2_inbound_event_routes = {
    for route in var.resolved_cross_cloud_routes : route.route_id => route
    if local.five_layer_v2_enabled && route.execution_kind == "source_event_forwarder" && route.destination_provider == "azure"
  }
  azure_v2_remote_telemetry_outbound = anytrue([
    for route in values(local.azure_v2_outbound_event_routes) :
    route.channel_class == "telemetry" && !startswith(route.logical_edge_id, "edge.eventing-to-")
  ])
  azure_v2_event_remote_telemetry_outbound = anytrue([
    for route in values(local.azure_v2_outbound_event_routes) :
    route.channel_class == "telemetry" && startswith(route.logical_edge_id, "edge.eventing-to-")
  ])
  azure_v2_remote_telemetry_inbound = anytrue([
    for route in values(local.azure_v2_inbound_event_routes) :
    route.channel_class == "telemetry" && !endswith(route.logical_edge_id, "-to-eventing")
  ])
  azure_v2_remote_telemetry_routes = {
    for direction, enabled in {
      inbound  = local.azure_v2_remote_telemetry_inbound
      outbound = local.azure_v2_remote_telemetry_outbound
    } : direction => direction if enabled
  }
  azure_v2_remote_telemetry_enabled = length(local.azure_v2_remote_telemetry_routes) > 0
  azure_v2_remote_control_outbound = anytrue([
    for route in values(local.azure_v2_outbound_event_routes) :
    route.channel_class == "control" && !startswith(route.logical_edge_id, "edge.eventing-to-")
  ])
  azure_v2_event_remote_control_outbound = anytrue([
    for route in values(local.azure_v2_outbound_event_routes) :
    route.channel_class == "control" && startswith(route.logical_edge_id, "edge.eventing-to-")
  ])
  azure_v2_remote_control_inbound = anytrue([
    for route in values(local.azure_v2_inbound_event_routes) :
    route.channel_class == "control" && !endswith(route.logical_edge_id, "-to-eventing")
  ])
  azure_v2_remote_control_routes = {
    for direction, enabled in {
      inbound  = local.azure_v2_remote_control_inbound
      outbound = local.azure_v2_remote_control_outbound
    } : direction => direction if enabled
  }
  azure_v2_object_store_enabled = local.azure_v2_cool_enabled || local.azure_v2_archive_enabled
  azure_v2_storage_mover_enabled = local.five_layer_v2_enabled && (
    local.azure_v2_hot_enabled ||
    (local.azure_v2_cool_enabled && var.layer_3_archive_provider != "azure")
  )
  azure_v2_storage_task_count = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.azure.azure.container-apps-scheduled-storage-job.task_count",
    "0",
  ))
  azure_v2_storage_jobs = merge(
    local.azure_v2_hot_enabled ? {
      hot-to-cool = {
        source_provider      = "azure"
        destination_provider = var.layer_3_cold_provider
        schedule             = "*/5 * * * *"
        code                 = "hc"
      }
    } : {},
    local.azure_v2_cool_enabled && var.layer_3_archive_provider != "azure" ? {
      cool-to-archive = {
        source_provider      = "azure"
        destination_provider = var.layer_3_archive_provider
        schedule             = "0 0 * * *"
        code                 = "ca"
      }
    } : {},
  )
  azure_v2_storage_schedule_tasks = {
    for item in flatten([
      for transition, job in local.azure_v2_storage_jobs : [
        for task_index in range(local.azure_v2_storage_task_count) : {
          key         = "${transition}-${format("%03d", task_index)}"
          transition  = transition
          task_index  = task_index
          source      = job.source_provider
          destination = job.destination_provider
          schedule    = job.schedule
          code        = job.code
        }
      ]
    ]) : item.key => item
  }

  azure_v2_cosmos_capacity_mode = lookup(
    var.resolved_component_dimensions,
    "dimension.azure.azure.cosmos-db-nosql-raw-and-rollup.capacity_mode",
    "serverless",
  )
  azure_v2_cosmos_autoscale_max_ru = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.azure.azure.cosmos-db-nosql-raw-and-rollup.autoscale_max_ru_per_second",
    "0",
  ))

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
  azure_v2_iot_devices = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.azure.azure.iot-hub.connected_devices",
    "100",
  ))
  azure_v2_iot_sku      = local.azure_v2_iot_devices <= 100 ? "S1" : local.azure_v2_iot_devices <= 4000 ? "S2" : "S3"
  azure_v2_iot_capacity = local.azure_v2_iot_devices <= 100 ? 1 : local.azure_v2_iot_devices <= 4000 ? 3 : 1
  azure_v2_iot_partitions = (
    local.azure_v2_iot_devices <= 100 ? 4 :
    local.azure_v2_iot_devices <= 4000 ? 16 : 32
  )

  azure_v2_name = substr(replace(lower(var.digital_twin_name), "_", "-"), 0, 22)
  azure_v2_acr_name = substr(
    replace("${local.azure_v2_name}v2${local.deployment_suffix}", "-", ""),
    0,
    50,
  )
  azure_v2_runtime_package = (
    var.azure_v2_zip_path != ""
    ? var.azure_v2_zip_path
    : local.six_layer_eventing_enabled
    ? "${var.project_path}/.build/azure/six-layer-domain.zip"
    : "${var.project_path}/.build/azure/five-layer-v2.zip"
  )
  azure_v2_tags = merge(local.common_tags, {
    ArchitectureProfile = "${var.architecture_profile_id}@${var.architecture_profile_version}"
  })
  azure_v2_processor_extensions = local.azure_v2_l2_enabled ? {
    for package in var.validated_extension_packages : package.artifact_id => package
    if package.slot_id == "processor.telemetry" && package.slot_version == "1"
  } : {}
}

resource "terraform_data" "azure_v2_processor_extension_guard" {
  count = local.azure_v2_l2_enabled ? 1 : 0

  input = {
    package_count = length(local.azure_v2_processor_extensions)
  }

  lifecycle {
    precondition {
      condition     = length(local.azure_v2_processor_extensions) == 1
      error_message = "Azure Five-layer v2 requires exactly one validated processor.telemetry@1 package."
    }
  }
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

resource "terraform_data" "azure_v2_cosmos_capacity_guard" {
  count = local.azure_v2_hot_enabled ? 1 : 0

  input = {
    capacity_mode               = local.azure_v2_cosmos_capacity_mode
    autoscale_max_ru_per_second = local.azure_v2_cosmos_autoscale_max_ru
  }

  lifecycle {
    precondition {
      condition = (
        (local.azure_v2_cosmos_capacity_mode == "serverless" && local.azure_v2_cosmos_autoscale_max_ru == 0) ||
        (
          local.azure_v2_cosmos_capacity_mode == "autoscale" &&
          local.azure_v2_cosmos_autoscale_max_ru >= 1000 &&
          local.azure_v2_cosmos_autoscale_max_ru % 1000 == 0
        )
      )
      error_message = "Azure L3 hot must use reviewed Serverless capacity or a positive 1,000-RU-rounded Large autoscale fixture."
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

resource "azurerm_iothub" "azure_azure_iot_hub" {
  count               = local.azure_v2_l1_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-iot-${local.deployment_suffix}"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = local.azure_iothub_region

  sku {
    name     = local.azure_v2_iot_sku
    capacity = local.azure_v2_iot_capacity
  }

  event_hub_partition_count   = local.azure_v2_iot_partitions
  event_hub_retention_in_days = 1

  cloud_to_device {
    default_ttl        = "PT1H"
    max_delivery_count = 10
    feedback {
      lock_duration      = "PT1M"
      max_delivery_count = 10
      time_to_live       = "PT1H"
    }
  }

  tags = local.azure_v2_tags
}

resource "azurerm_cosmosdb_account" "azure_azure_cosmos_db_nosql_raw_and_rollup" {
  count                         = local.azure_v2_hot_enabled ? 1 : 0
  name                          = "${local.azure_v2_name}-v2-cosmos-${local.deployment_suffix}"
  location                      = azurerm_resource_group.main[0].location
  resource_group_name           = azurerm_resource_group.main[0].name
  offer_type                    = "Standard"
  kind                          = "GlobalDocumentDB"
  automatic_failover_enabled    = false
  local_authentication_disabled = true
  public_network_access_enabled = true

  dynamic "capabilities" {
    for_each = local.azure_v2_cosmos_capacity_mode == "serverless" ? [1] : []
    content {
      name = "EnableServerless"
    }
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.main[0].location
    failover_priority = 0
  }

  tags = local.azure_v2_tags
}

resource "azurerm_cosmosdb_sql_database" "azure_azure_cosmos_db_nosql_raw_and_rollup" {
  count               = local.azure_v2_hot_enabled ? 1 : 0
  name                = "twin-history"
  resource_group_name = azurerm_resource_group.main[0].name
  account_name        = azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name

  dynamic "autoscale_settings" {
    for_each = local.azure_v2_cosmos_capacity_mode == "autoscale" ? [1] : []
    content {
      max_throughput = local.azure_v2_cosmos_autoscale_max_ru
    }
  }
}

# Raw telemetry and hourly rollups intentionally share one container and
# /device_id partition. The item kind retains a single transactional-batch
# boundary without inventing another database for the thesis PoC.
resource "azurerm_cosmosdb_sql_container" "azure_azure_cosmos_db_nosql_raw_and_rollup" {
  count               = local.azure_v2_hot_enabled ? 1 : 0
  name                = "telemetry-history"
  resource_group_name = azurerm_resource_group.main[0].name
  account_name        = azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name
  database_name       = azurerm_cosmosdb_sql_database.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name
  partition_key_paths = ["/device_id"]
  partition_key_kind  = "Hash"
  default_ttl         = (var.layer_3_hot_to_cold_interval_days + 2) * 86400

  indexing_policy {
    indexing_mode = "consistent"
    included_path { path = "/device_id/?" }
    included_path { path = "/stored_at/?" }
    included_path { path = "/storage_window/?" }
    included_path { path = "/storage_task/?" }
    included_path { path = "/bucket_start/?" }
    included_path { path = "/kind/?" }
    included_path { path = "/metric/?" }
    excluded_path { path = "/*" }
  }
}

resource "azurerm_cosmosdb_sql_role_assignment" "azure_azure_cosmos_db_nosql_raw_and_rollup" {
  for_each = local.azure_v2_hot_enabled ? merge(
    {
      runtime_writer = {
        principal_id = azurerm_user_assigned_identity.main[0].principal_id
        role_id      = "00000000-0000-0000-0000-000000000002"
      }
    },
    local.azure_v2_l5_enabled ? {
      raw_history_reader = {
        principal_id = azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader[0].identity[0].principal_id
        role_id      = "00000000-0000-0000-0000-000000000001"
      }
    } : {},
  ) : {}

  resource_group_name = azurerm_resource_group.main[0].name
  account_name        = azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name
  role_definition_id  = "${azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].id}/sqlRoleDefinitions/${each.value.role_id}"
  principal_id        = each.value.principal_id
  scope               = azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].id
}

resource "azurerm_storage_container" "azure_azure_blob_cool" {
  count                 = local.azure_v2_object_store_enabled ? 1 : 0
  name                  = "history"
  storage_account_id    = azurerm_storage_account.main[0].id
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "azure_azure_blob_archive" {
  count              = local.azure_v2_archive_enabled ? 1 : 0
  storage_account_id = azurerm_storage_account.main[0].id

  rule {
    name    = "five-layer-v2-history"
    enabled = true
    filters {
      prefix_match = ["${azurerm_storage_container.azure_azure_blob_cool[0].name}/history/"]
      blob_types   = ["blockBlob"]
    }
    actions {
      base_blob {
        tier_to_archive_after_days_since_modification_greater_than = local.azure_v2_cool_enabled ? var.layer_3_cold_to_archive_interval_days - var.layer_3_hot_to_cold_interval_days : 0
        delete_after_days_since_modification_greater_than = local.azure_v2_cool_enabled ? (
          var.layer_3_archive_expiry_interval_days - var.layer_3_hot_to_cold_interval_days
          ) : (
          var.layer_3_archive_expiry_interval_days - var.layer_3_cold_to_archive_interval_days
        )
      }
    }
  }
}

resource "azurerm_container_registry" "azure_azure_acr_basic_if_container_selected" {
  count                         = local.azure_v2_storage_mover_enabled ? 1 : 0
  name                          = local.azure_v2_acr_name
  resource_group_name           = azurerm_resource_group.main[0].name
  location                      = azurerm_resource_group.main[0].location
  sku                           = "Basic"
  admin_enabled                 = false
  anonymous_pull_enabled        = false
  public_network_access_enabled = true
  tags                          = local.azure_v2_tags
}

resource "azurerm_container_app_environment" "azure_azure_container_apps_scheduled_storage_job" {
  count                      = local.azure_v2_storage_mover_enabled ? 1 : 0
  name                       = "${local.azure_v2_name}-v2-mover"
  resource_group_name        = azurerm_resource_group.main[0].name
  location                   = azurerm_resource_group.main[0].location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.azure_azure_log_analytics_shared_workspace[0].id
  tags                       = local.azure_v2_tags
}

resource "terraform_data" "azure_v2_storage_mover_guard" {
  count = local.azure_v2_storage_mover_enabled ? 1 : 0
  input = {
    image      = var.azure_v2_storage_mover_image
    task_count = local.azure_v2_storage_task_count
  }
  lifecycle {
    precondition {
      condition     = contains([1, 4, 30], local.azure_v2_storage_task_count)
      error_message = "Azure Five-layer v2 storage movement requires the exact reviewed 1/4/30 task_count capacity dimension."
    }
    precondition {
      condition = (
        var.azure_v2_storage_mover_image != "" &&
        startswith(var.azure_v2_storage_mover_image, "${azurerm_container_registry.azure_azure_acr_basic_if_container_selected[0].login_server}/storage-mover@sha256:")
      )
      error_message = "Azure Five-layer v2 storage movement requires a digest-pinned image from the deployment ACR."
    }
  }
}

resource "azurerm_container_app_job" "azure_azure_container_apps_scheduled_storage_job" {
  for_each                     = local.azure_v2_storage_schedule_tasks
  name                         = "${substr(local.azure_v2_name, 0, 12)}-v2-${each.value.code}-${format("%02d", each.value.task_index)}-${substr(local.deployment_suffix, 0, 6)}"
  resource_group_name          = azurerm_resource_group.main[0].name
  location                     = azurerm_resource_group.main[0].location
  container_app_environment_id = azurerm_container_app_environment.azure_azure_container_apps_scheduled_storage_job[0].id
  replica_timeout_in_seconds   = 1800
  replica_retry_limit          = 3

  schedule_trigger_config {
    cron_expression          = each.value.schedule
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main[0].id]
  }

  registry {
    server   = azurerm_container_registry.azure_azure_acr_basic_if_container_selected[0].login_server
    identity = azurerm_user_assigned_identity.main[0].id
  }

  template {
    container {
      name   = "storage-mover"
      image  = var.azure_v2_storage_mover_image
      cpu    = 1
      memory = "2Gi"

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "${var.architecture_profile_id}@${var.architecture_profile_version}"
      }
      env {
        name  = "DEPLOYMENT_ID"
        value = local.deployment_suffix
      }
      env {
        name  = "TRANSITION"
        value = each.value.transition
      }
      env {
        name  = "SOURCE_PROVIDER"
        value = each.value.source
      }
      env {
        name  = "DESTINATION_PROVIDER"
        value = each.value.destination
      }
      env {
        name  = "STORAGE_TASK_INDEX"
        value = tostring(each.value.task_index)
      }
      env {
        name  = "STORAGE_TASK_COUNT"
        value = tostring(local.azure_v2_storage_task_count)
      }
      env {
        name  = "HOT_BOUNDARY_DAYS"
        value = tostring(var.layer_3_hot_to_cold_interval_days)
      }
      env {
        name  = "COOL_BOUNDARY_DAYS"
        value = tostring(var.layer_3_cold_to_archive_interval_days)
      }
      env {
        name  = "ARCHIVE_BOUNDARY_DAYS"
        value = tostring(var.layer_3_archive_expiry_interval_days)
      }
      env {
        name  = "COSMOS_ENDPOINT"
        value = try(azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].endpoint, "")
      }
      env {
        name  = "COSMOS_DATABASE"
        value = try(azurerm_cosmosdb_sql_database.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name, "")
      }
      env {
        name  = "COSMOS_CONTAINER"
        value = try(azurerm_cosmosdb_sql_container.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name, "")
      }
      env {
        name  = "BLOB_ACCOUNT_URL"
        value = azurerm_storage_account.main[0].primary_blob_endpoint
      }
      env {
        name  = "BLOB_CONTAINER"
        value = try(azurerm_storage_container.azure_azure_blob_cool[0].name, "")
      }
      env {
        name  = "MANAGED_IDENTITY_CLIENT_ID"
        value = azurerm_user_assigned_identity.main[0].client_id
      }
    }
  }

  tags = local.azure_v2_tags

  depends_on = [
    azurerm_role_assignment.azure_azure_entra_layer_access_bindings,
    azurerm_cosmosdb_sql_role_assignment.azure_azure_cosmos_db_nosql_raw_and_rollup,
    terraform_data.azure_v2_storage_mover_guard,
  ]
}

resource "azurerm_servicebus_namespace" "azure_azure_service_bus_standard" {
  count                         = local.azure_v2_service_bus_enabled ? 1 : 0
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
  count                                   = local.azure_v2_embedded_event_enabled ? 1 : 0
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
  count                                   = local.azure_v2_embedded_event_enabled ? 1 : 0
  name                                    = "domain-control-events"
  namespace_id                            = azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].id
  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"
  default_message_ttl                     = "P14D"
}

resource "azurerm_servicebus_subscription" "azure_azure_service_bus_standard" {
  count                                     = local.azure_v2_embedded_event_enabled ? 1 : 0
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

# Cross-cloud control traffic is directionally isolated from the embedded
# domain topic. Inbound events can only flow into the local domain queue;
# outbound events enter a bridge-only queue and can never be re-exported after
# landing. This is the Service Bus equivalent of the directional Kinesis/SNS
# and Pub/Sub resources used by AWS and GCP.
resource "azurerm_servicebus_topic" "azure_v2_remote_control" {
  for_each                                = local.azure_v2_remote_control_routes
  name                                    = "remote-control-${each.key}"
  namespace_id                            = azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].id
  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"
  default_message_ttl                     = "P14D"
}

resource "azurerm_servicebus_queue" "azure_v2_remote_control_outbound" {
  count                                   = local.azure_v2_remote_control_outbound ? 1 : 0
  name                                    = "remote-control-outbound-bridge"
  namespace_id                            = azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].id
  requires_session                        = true
  requires_duplicate_detection            = true
  duplicate_detection_history_time_window = "PT10M"
  dead_lettering_on_message_expiration    = true
  default_message_ttl                     = "P14D"
  lock_duration                           = "PT1M"
  max_delivery_count                      = 6
}

resource "azurerm_servicebus_subscription" "azure_v2_remote_control_inbound" {
  count                                     = local.azure_v2_remote_control_inbound ? 1 : 0
  name                                      = "local-domain-landing"
  topic_id                                  = azurerm_servicebus_topic.azure_v2_remote_control["inbound"].id
  max_delivery_count                        = 5
  requires_session                          = true
  dead_lettering_on_message_expiration      = true
  dead_lettering_on_filter_evaluation_error = true
  default_message_ttl                       = "P14D"
  lock_duration                             = "PT1M"
  forward_to                                = azurerm_servicebus_queue.azure_azure_service_bus_standard[0].name
}

resource "azurerm_servicebus_subscription" "azure_v2_remote_control_outbound" {
  count                                     = local.azure_v2_remote_control_outbound ? 1 : 0
  name                                      = "cross-cloud-bridge"
  topic_id                                  = azurerm_servicebus_topic.azure_v2_remote_control["outbound"].id
  max_delivery_count                        = 5
  requires_session                          = true
  dead_lettering_on_message_expiration      = true
  dead_lettering_on_filter_evaluation_error = true
  default_message_ttl                       = "P14D"
  lock_duration                             = "PT1M"
  forward_to                                = azurerm_servicebus_queue.azure_v2_remote_control_outbound[0].name
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
  count               = local.azure_v2_remote_telemetry_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-eh-${local.deployment_suffix}"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name
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
  count                 = local.azure_v2_function_infrastructure_enabled ? 1 : 0
  name                  = "five-layer-v2-functions"
  storage_account_id    = azurerm_storage_account.main[0].id
  container_access_type = "private"
}

resource "azurerm_service_plan" "azure_v2_flex" {
  count               = local.azure_v2_function_infrastructure_enabled ? 1 : 0
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
    FUNCTIONS_WORKER_RUNTIME                         = "python"
    WEBSITE_RUN_FROM_PACKAGE                         = "1"
    ARCHITECTURE_PROFILE                             = "${var.architecture_profile_id}@${var.architecture_profile_version}"
    DEPLOYMENT_ID                                    = local.deployment_suffix
    V2_DOMAIN_QUEUE_NAME                             = try(azurerm_servicebus_queue.azure_azure_service_bus_standard[0].name, "")
    V2_DOMAIN_TOPIC_NAME                             = try(azurerm_servicebus_topic.azure_azure_service_bus_standard[0].name, "")
    V2_SERVICE_BUS__fullyQualifiedNamespace          = try("${azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].name}.servicebus.windows.net", "disabled.servicebus.windows.net")
    V2_SERVICE_BUS__credential                       = "managedidentity"
    V2_SERVICE_BUS__clientId                         = azurerm_user_assigned_identity.main[0].client_id
    V2_MANAGED_IDENTITY_CLIENT_ID                    = azurerm_user_assigned_identity.main[0].client_id
    V2_DOMAIN_CONSUMER_ENABLED                       = tostring(!local.azure_v2_l2_enabled && local.azure_v2_embedded_event_enabled)
    V2_IOT_PROCESSOR_ENABLED                         = tostring(local.azure_v2_l1_enabled)
    V2_IOT_HUB_NAME                                  = try(azurerm_iothub.azure_azure_iot_hub[0].event_hub_events_path, "disabled")
    V2_IOT_HUB__fullyQualifiedNamespace              = local.azure_v2_l1_enabled ? "${azurerm_iothub.azure_azure_iot_hub[0].event_hub_events_namespace}.servicebus.windows.net" : "disabled.servicebus.windows.net"
    V2_IOT_HUB__credential                           = "managedidentity"
    V2_IOT_HUB__clientId                             = azurerm_user_assigned_identity.main[0].client_id
    V2_IOT_HUB_HOSTNAME                              = try(azurerm_iothub.azure_azure_iot_hub[0].hostname, "")
    V2_REMOTE_TELEMETRY_ENABLED                      = tostring(local.azure_v2_remote_telemetry_inbound)
    V2_REMOTE_TELEMETRY_HUB_NAME                     = try(azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].name, "disabled")
    V2_REMOTE_TELEMETRY__fullyQualifiedNamespace     = local.azure_v2_remote_telemetry_enabled ? "${azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].name}.servicebus.windows.net" : "disabled.servicebus.windows.net"
    V2_REMOTE_TELEMETRY__credential                  = "managedidentity"
    V2_REMOTE_TELEMETRY__clientId                    = azurerm_user_assigned_identity.main[0].client_id
    V2_BRIDGE_TELEMETRY_ENABLED                      = tostring(local.azure_v2_remote_telemetry_outbound)
    V2_BRIDGE_TELEMETRY_HUB_NAME                     = try(azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["outbound"].name, "disabled")
    V2_BRIDGE_TELEMETRY__fullyQualifiedNamespace     = local.azure_v2_remote_telemetry_outbound ? "${azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].name}.servicebus.windows.net" : "disabled.servicebus.windows.net"
    V2_BRIDGE_TELEMETRY__credential                  = "managedidentity"
    V2_BRIDGE_TELEMETRY__clientId                    = azurerm_user_assigned_identity.main[0].client_id
    V2_BRIDGE_CONTROL_ENABLED                        = tostring(local.azure_v2_remote_control_outbound)
    V2_BRIDGE_CONTROL_QUEUE_NAME                     = try(azurerm_servicebus_queue.azure_v2_remote_control_outbound[0].name, "disabled")
    V2_BRIDGE_CONTROL_TOPIC_NAME                     = try(azurerm_servicebus_topic.azure_v2_remote_control["outbound"].name, "disabled")
    V2_BRIDGE_EVENT_RECEIVED_ENABLED                 = tostring(local.azure_event_bridge_received_enabled)
    V2_BRIDGE_EVENT_PROCESSED_ENABLED                = tostring(local.azure_event_bridge_processed_enabled)
    V2_BRIDGE_EVENT_CONTROL_ENABLED                  = tostring(local.azure_v2_event_remote_control_outbound)
    V2_EVENTING_DELIVERY_ENDPOINT_ENABLED            = tostring(local.azure_event_enabled)
    V2_EVENTING_RECEIVED_HUB_NAME                    = try(local.azure_event_hub_names.received, "")
    V2_EVENTING_PROCESSED_HUB_NAME                   = try(local.azure_event_hub_names.processed, "")
    V2_EVENTING__fullyQualifiedNamespace             = try("${local.azure_event_namespace_name}.servicebus.windows.net", "disabled.servicebus.windows.net")
    V2_EVENTING_SERVICE_BUS__fullyQualifiedNamespace = try("${azurerm_servicebus_namespace.eventing[0].name}.servicebus.windows.net", "disabled.servicebus.windows.net")
    V2_EVENTING_CONTROL_TOPIC_NAME                   = try(azurerm_servicebus_topic.domain_control[0].name, "")
    V2_EVENTING_BRIDGE_CONTROL_SUBSCRIPTION_NAME     = try(azurerm_servicebus_subscription.event_bridge_control[0].name, "disabled")
    V2_EVENT_LAYER_PROVIDER                          = var.event_layer_provider
    BRIDGE_ROUTES_JSON                               = jsonencode(values(local.azure_v2_outbound_event_routes))
    BRIDGE_DESTINATIONS_JSON                         = jsonencode(local.azure_v2_bridge_destinations)
    BRIDGE_IDENTITIES_JSON                           = jsonencode(local.azure_v2_bridge_identities)
    BRIDGE_SOURCE_IDENTITY_JSON                      = jsonencode({ managed_identity_client_id = azurerm_user_assigned_identity.main[0].client_id })
    BRIDGE_FAILURE_DESTINATION_JSON                  = jsonencode(local.azure_v2_bridge_failure_destination)
    V2_L2_PROVIDER                                   = var.layer_2_provider
    V2_L1_PROVIDER                                   = var.layer_1_provider
    V2_HOT_PROVIDER                                  = var.layer_3_hot_provider
    V2_TWIN_PROVIDER                                 = var.layer_4_provider
    V2_ADT_ENDPOINT                                  = local.azure_v2_l4_enabled ? "https://${azurerm_digital_twins_instance.azure_azure_digital_twins[0].host_name}" : ""
    V2_ADT_MODEL_ID                                  = "dtmi:twin2multicloud:poc:TwinNode;1"
    V2_COSMOS_ENDPOINT                               = try(azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].endpoint, "")
    V2_COSMOS_DATABASE                               = try(azurerm_cosmosdb_sql_database.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name, "")
    V2_COSMOS_CONTAINER                              = try(azurerm_cosmosdb_sql_container.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name, "")
    V2_HOT_BOUNDARY_DAYS                             = tostring(var.layer_3_hot_to_cold_interval_days)
    V2_STORAGE_TASK_COUNT                            = tostring(local.azure_v2_storage_task_count)
    V2_DEFAULT_METRIC                                = "temperature"
  }

  tags = local.azure_v2_tags

  lifecycle {
    precondition {
      condition     = fileexists(local.azure_v2_runtime_package)
      error_message = "Azure Five-layer v2 requires its validated content-addressed Function package."
    }
  }

  depends_on = [
    azuread_app_role_assignment.azure_v2_bridge_source,
    aws_iam_role_policy.aws_v2_bridge_target_from_azure,
    google_service_account_iam_member.gcp_v2_bridge_from_azure,
    google_pubsub_topic_iam_member.gcp_v2_bridge_from_azure,
    azurerm_role_assignment.azure_azure_entra_layer_access_bindings,
  ]
}

resource "azurerm_function_app_flex_consumption" "azure_azure_functions_flex_consumption" {
  count               = local.azure_v2_l2_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-process-${local.deployment_suffix}"
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
    FUNCTIONS_WORKER_RUNTIME                         = "python"
    WEBSITE_RUN_FROM_PACKAGE                         = "1"
    ARCHITECTURE_PROFILE                             = "${var.architecture_profile_id}@${var.architecture_profile_version}"
    DEPLOYMENT_ID                                    = local.deployment_suffix
    V2_DOMAIN_CONSUMER_ENABLED                       = tostring(local.azure_v2_embedded_event_enabled)
    V2_IOT_PROCESSOR_ENABLED                         = "false"
    V2_REMOTE_TELEMETRY_ENABLED                      = "false"
    V2_DOMAIN_QUEUE_NAME                             = try(azurerm_servicebus_queue.azure_azure_service_bus_standard[0].name, "")
    V2_DOMAIN_TOPIC_NAME                             = try(azurerm_servicebus_topic.azure_azure_service_bus_standard[0].name, "")
    V2_SERVICE_BUS__fullyQualifiedNamespace          = try("${azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].name}.servicebus.windows.net", "disabled.servicebus.windows.net")
    V2_SERVICE_BUS__credential                       = "managedidentity"
    V2_SERVICE_BUS__clientId                         = azurerm_user_assigned_identity.main[0].client_id
    V2_MANAGED_IDENTITY_CLIENT_ID                    = azurerm_user_assigned_identity.main[0].client_id
    V2_PROCESSOR_EXTENSION_URL                       = try("https://${one(values(azurerm_function_app_flex_consumption.azure_v2_processor_extension)).name}.azurewebsites.net/api/extension", "")
    V2_PROCESSOR_EXTENSION_KEY                       = try(one(values(data.azurerm_function_app_host_keys.azure_v2_processor_extension)).default_function_key, "")
    V2_ACTION_FUNCTION_URL                           = "https://${azurerm_function_app_flex_consumption.azure_v2_extension_action[0].name}.azurewebsites.net/api/extension-action/v1"
    V2_ACTION_FUNCTION_KEY                           = data.azurerm_function_app_host_keys.azure_v2_extension_action[0].default_function_key
    V2_EVENTING_DELIVERY_ENDPOINT_ENABLED            = tostring(local.azure_event_enabled)
    V2_EVENTING_PROCESSED_HUB_NAME                   = try(local.azure_event_hub_names.processed, "")
    V2_EVENTING__fullyQualifiedNamespace             = try("${local.azure_event_namespace_name}.servicebus.windows.net", "disabled.servicebus.windows.net")
    V2_EVENTING_SERVICE_BUS__fullyQualifiedNamespace = try("${azurerm_servicebus_namespace.eventing[0].name}.servicebus.windows.net", "disabled.servicebus.windows.net")
    V2_EVENTING_CONTROL_TOPIC_NAME                   = try(azurerm_servicebus_topic.domain_control[0].name, "")
    V2_LOGIC_APP_CALLBACK_URL                        = azurerm_logic_app_trigger_http_request.azure_azure_logic_apps_consumption[0].callback_url
    V2_IOT_HUB_HOSTNAME                              = try(azurerm_iothub.azure_azure_iot_hub[0].hostname, "")
    V2_RULES_JSON                                    = jsonencode(var.events)
    V2_L2_PROVIDER                                   = var.layer_2_provider
    V2_L1_PROVIDER                                   = var.layer_1_provider
    V2_HOT_PROVIDER                                  = var.layer_3_hot_provider
    V2_TWIN_PROVIDER                                 = var.layer_4_provider
    V2_ADT_ENDPOINT                                  = local.azure_v2_l4_enabled ? "https://${azurerm_digital_twins_instance.azure_azure_digital_twins[0].host_name}" : ""
    V2_ADT_MODEL_ID                                  = "dtmi:twin2multicloud:poc:TwinNode;1"
    V2_COSMOS_ENDPOINT                               = try(azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].endpoint, "")
    V2_COSMOS_DATABASE                               = try(azurerm_cosmosdb_sql_database.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name, "")
    V2_COSMOS_CONTAINER                              = try(azurerm_cosmosdb_sql_container.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name, "")
    V2_HOT_BOUNDARY_DAYS                             = tostring(var.layer_3_hot_to_cold_interval_days)
    V2_STORAGE_TASK_COUNT                            = tostring(local.azure_v2_storage_task_count)
  }

  tags = local.azure_v2_tags

  lifecycle {
    precondition {
      condition     = fileexists(local.azure_v2_runtime_package)
      error_message = "Azure Five-layer v2 requires its validated content-addressed Function package."
    }
  }
}

resource "azurerm_function_app_flex_consumption" "azure_v2_processor_extension" {
  for_each            = local.azure_v2_processor_extensions
  name                = "${local.azure_v2_name}-v2-extension-${local.deployment_suffix}"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.azure_v2_flex[0].id

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.main[0].primary_blob_endpoint}${azurerm_storage_container.azure_v2_function_package[0].name}"
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.main[0].primary_access_key

  runtime_name    = "python"
  runtime_version = "3.11"
  zip_deploy_file = each.value.package_path

  maximum_instance_count                         = 100
  instance_memory_in_mb                          = 2048
  https_only                                     = true
  public_network_access_enabled                  = true
  webdeploy_publish_basic_authentication_enabled = false

  site_config {
    minimum_tls_version     = "1.2"
    scm_minimum_tls_version = "1.2"
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME = "python"
    WEBSITE_RUN_FROM_PACKAGE = "1"
    ARCHITECTURE_PROFILE     = "${var.architecture_profile_id}@${var.architecture_profile_version}"
  }

  tags = local.azure_v2_tags

  lifecycle {
    precondition {
      condition     = each.value.adapter_id == "adapter.azure.python311" && each.value.adapter_version == "1"
      error_message = "Azure Five-layer v2 requires the reviewed processor.telemetry@1 Azure adapter."
    }
  }

  depends_on = [
    terraform_data.azure_v2_processor_extension_guard,
    terraform_data.validated_extension_package,
  ]
}

data "azurerm_function_app_host_keys" "azure_v2_processor_extension" {
  for_each            = azurerm_function_app_flex_consumption.azure_v2_processor_extension
  name                = each.value.name
  resource_group_name = each.value.resource_group_name
}

# A separate fixed Function invocation keeps the mandatory extension-action
# event and cost visible without executing the retired unvalidated action ZIPs.
resource "azurerm_function_app_flex_consumption" "azure_v2_extension_action" {
  count               = local.azure_v2_l2_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-action-${local.deployment_suffix}"
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

  site_config {
    minimum_tls_version     = "1.2"
    scm_minimum_tls_version = "1.2"
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME    = "python"
    WEBSITE_RUN_FROM_PACKAGE    = "1"
    ARCHITECTURE_PROFILE        = "${var.architecture_profile_id}@${var.architecture_profile_version}"
    V2_ACTION_ENDPOINT_ENABLED  = "true"
    V2_DOMAIN_CONSUMER_ENABLED  = "false"
    V2_IOT_PROCESSOR_ENABLED    = "false"
    V2_REMOTE_TELEMETRY_ENABLED = "false"
    V2_RAW_HISTORY_ENABLED      = "false"
  }

  tags = local.azure_v2_tags

  lifecycle {
    precondition {
      condition     = fileexists(local.azure_v2_runtime_package)
      error_message = "Azure Five-layer v2 requires its validated content-addressed Function package."
    }
  }
}

data "azurerm_function_app_host_keys" "azure_v2_extension_action" {
  count               = local.azure_v2_l2_enabled ? 1 : 0
  name                = azurerm_function_app_flex_consumption.azure_v2_extension_action[0].name
  resource_group_name = azurerm_function_app_flex_consumption.azure_v2_extension_action[0].resource_group_name
}

resource "azurerm_logic_app_workflow" "azure_azure_logic_apps_consumption" {
  count               = local.azure_v2_l2_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-notification"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name
  enabled             = true
  tags                = local.azure_v2_tags
}

resource "azurerm_logic_app_trigger_http_request" "azure_azure_logic_apps_consumption" {
  count        = local.azure_v2_l2_enabled ? 1 : 0
  name         = "canonical-notification-request"
  logic_app_id = azurerm_logic_app_workflow.azure_azure_logic_apps_consumption[0].id
  method       = "POST"
  schema = jsonencode({
    type = "object"
    required = [
      "schema_version",
      "event_id",
      "event_type",
      "deployment_id",
      "payload",
    ]
    properties = {
      schema_version = { type = "string" }
      event_id       = { type = "string" }
      event_type     = { type = "string" }
      deployment_id  = { type = "string" }
      payload        = { type = "object" }
    }
  })
}

resource "azurerm_logic_app_action_custom" "azure_v2_notification_normalize" {
  count        = local.azure_v2_l2_enabled ? 1 : 0
  name         = "normalize-canonical-notification"
  logic_app_id = azurerm_logic_app_workflow.azure_azure_logic_apps_consumption[0].id
  body = jsonencode({
    type = "Compose"
    inputs = {
      event_id       = "@{triggerBody()?['event_id']}"
      correlation_id = "@{triggerBody()?['correlation_id']}"
      message        = "@{triggerBody()?['payload']?['message']}"
    }
    runAfter = {}
  })
}

resource "azurerm_logic_app_action_custom" "azure_v2_notification_prepare" {
  count        = local.azure_v2_l2_enabled ? 1 : 0
  name         = "prepare-poc-notification-delivery"
  logic_app_id = azurerm_logic_app_workflow.azure_azure_logic_apps_consumption[0].id
  body = jsonencode({
    type   = "Compose"
    inputs = "@triggerBody()"
    runAfter = {
      (azurerm_logic_app_action_custom.azure_v2_notification_normalize[0].name) = ["Succeeded"]
    }
  })
}

resource "azurerm_logic_app_action_custom" "azure_v2_notification_deliver" {
  count        = local.azure_v2_l2_enabled ? 1 : 0
  name         = "deliver-external-poc-notification"
  logic_app_id = azurerm_logic_app_workflow.azure_azure_logic_apps_consumption[0].id
  body = jsonencode({
    type = "Http"
    inputs = {
      method = "POST"
      uri    = "https://${azurerm_function_app_flex_consumption.azure_v2_extension_action[0].name}.azurewebsites.net/api/notification-delivery/v1"
      headers = {
        "content-type"    = "application/json"
        "x-functions-key" = data.azurerm_function_app_host_keys.azure_v2_extension_action[0].default_function_key
      }
      body = "@triggerBody()"
    }
    runAfter = {
      (azurerm_logic_app_action_custom.azure_v2_notification_prepare[0].name) = ["Succeeded"]
    }
    runtimeConfiguration = {
      secureData = {
        properties = ["inputs"]
      }
    }
  })
}

resource "azurerm_logic_app_action_custom" "azure_v2_notification_complete" {
  count        = local.azure_v2_l2_enabled ? 1 : 0
  name         = "complete-poc-notification-workflow"
  logic_app_id = azurerm_logic_app_workflow.azure_azure_logic_apps_consumption[0].id
  body = jsonencode({
    type = "Response"
    inputs = {
      statusCode = 202
      body = {
        status   = "ACCEPTED"
        event_id = "@{triggerBody()?['event_id']}"
      }
    }
    runAfter = {
      (azurerm_logic_app_action_custom.azure_v2_notification_deliver[0].name) = ["Succeeded"]
    }
  })
}

# L4 remains independently placeable. Azure Digital Twins receives its state
# through the canonical projection boundary; Grafana never queries ADT.
resource "azurerm_digital_twins_instance" "azure_azure_digital_twins" {
  count               = local.azure_v2_l4_enabled ? 1 : 0
  name                = local.azure_adt_name
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location

  identity {
    type = "SystemAssigned"
  }

  tags = local.azure_v2_tags
}

# L5 reads only provider-local L3 hot data through this narrow HTTP contract.
# The cursor key protects continuation-token integrity and never leaves the
# Function app settings or Terraform state.
resource "random_password" "azure_v2_raw_history_cursor_hmac" {
  count   = local.azure_v2_l5_enabled ? 1 : 0
  length  = 64
  special = false
}

resource "azurerm_function_app_flex_consumption" "azure_azure_functions_flex_raw_history_reader" {
  count               = local.azure_v2_l5_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-history-${local.deployment_suffix}"
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

  maximum_instance_count                         = 20
  instance_memory_in_mb                          = 2048
  https_only                                     = true
  public_network_access_enabled                  = true
  webdeploy_publish_basic_authentication_enabled = false

  identity {
    type = "SystemAssigned"
  }

  site_config {
    minimum_tls_version              = "1.2"
    scm_minimum_tls_version          = "1.2"
    runtime_scale_monitoring_enabled = true
  }

  app_settings = {
    FUNCTIONS_WORKER_RUNTIME = "python"
    WEBSITE_RUN_FROM_PACKAGE = "1"
    ARCHITECTURE_PROFILE     = "${var.architecture_profile_id}@${var.architecture_profile_version}"
    DEPLOYMENT_ID            = local.deployment_suffix
    V2_RAW_HISTORY_ENABLED   = "true"
    V2_COSMOS_ENDPOINT       = azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].endpoint
    V2_COSMOS_DATABASE       = azurerm_cosmosdb_sql_database.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name
    V2_COSMOS_CONTAINER      = azurerm_cosmosdb_sql_container.azure_azure_cosmos_db_nosql_raw_and_rollup[0].name
    V2_CURSOR_HMAC_KEY       = random_password.azure_v2_raw_history_cursor_hmac[0].result
  }

  tags = local.azure_v2_tags

  lifecycle {
    precondition {
      condition     = fileexists(local.azure_v2_runtime_package)
      error_message = "Azure Five-layer v2 requires its validated content-addressed Function package."
    }
  }
}

resource "azurerm_dashboard_grafana" "azure_azure_managed_grafana_12_standard" {
  count                         = local.azure_v2_l5_enabled ? 1 : 0
  name                          = local.azure_grafana_name
  resource_group_name           = azurerm_resource_group.main[0].name
  location                      = azurerm_resource_group.main[0].location
  sku                           = "Standard"
  grafana_major_version         = "12"
  public_network_access_enabled = true
  zone_redundancy_enabled       = false

  identity {
    type = "SystemAssigned"
  }

  tags = local.azure_v2_tags
}

data "azurerm_client_config" "azure_v2_layer_access" {
  count = local.azure_v2_l4_enabled || local.azure_v2_l5_enabled ? 1 : 0
}

locals {
  azure_v2_event_role_bindings = merge(
    local.azure_v2_embedded_event_enabled ? {
      service_bus_receiver = {
        scope = azurerm_servicebus_queue.azure_azure_service_bus_standard[0].id
        role  = "Azure Service Bus Data Receiver"
      }
      service_bus_queue_sender = {
        scope = azurerm_servicebus_queue.azure_azure_service_bus_standard[0].id
        role  = "Azure Service Bus Data Sender"
      }
      service_bus_topic_sender = {
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
      bridge_telemetry_failure_sender = {
        scope = azurerm_eventhub.azure_v2_bridge_telemetry_failure[0].id
        role  = "Azure Event Hubs Data Sender"
      }
    } : {},
    local.azure_v2_remote_control_outbound ? {
      remote_control_topic_sender = {
        scope = azurerm_servicebus_topic.azure_v2_remote_control["outbound"].id
        role  = "Azure Service Bus Data Sender"
      }
      remote_control_queue_receiver = {
        scope = azurerm_servicebus_queue.azure_v2_remote_control_outbound[0].id
        role  = "Azure Service Bus Data Receiver"
      }
      bridge_control_failure_sender = {
        scope = azurerm_servicebus_queue.azure_v2_bridge_control_failure[0].id
        role  = "Azure Service Bus Data Sender"
      }
    } : {},
    local.azure_v2_l1_enabled ? {
      iot_hub_receiver = {
        scope = azurerm_iothub.azure_azure_iot_hub[0].id
        role  = "IoT Hub Data Receiver"
      }
      iot_hub_contributor = {
        scope = azurerm_iothub.azure_azure_iot_hub[0].id
        role  = "IoT Hub Data Contributor"
      }
    } : {},
    local.azure_v2_object_store_enabled ? {
      history_blob_contributor = {
        scope = azurerm_storage_account.main[0].id
        role  = "Storage Blob Data Contributor"
      }
    } : {},
    local.azure_v2_storage_mover_enabled ? {
      storage_mover_acr_pull = {
        scope = azurerm_container_registry.azure_azure_acr_basic_if_container_selected[0].id
        role  = "AcrPull"
      }
    } : {},
    local.azure_v2_l4_enabled ? {
      twin_projection_writer = {
        scope          = azurerm_digital_twins_instance.azure_azure_digital_twins[0].id
        role           = "Azure Digital Twins Data Owner"
        principal_id   = azurerm_user_assigned_identity.main[0].principal_id
        principal_type = "ServicePrincipal"
      }
      twin_seed_deployer = {
        scope          = azurerm_digital_twins_instance.azure_azure_digital_twins[0].id
        role           = "Azure Digital Twins Data Owner"
        principal_id   = data.azurerm_client_config.azure_v2_layer_access[0].object_id
        principal_type = "ServicePrincipal"
        skip_check     = true
      }
      twin_human_reader = {
        scope          = azurerm_digital_twins_instance.azure_azure_digital_twins[0].id
        role           = "Azure Digital Twins Data Reader"
        principal_id   = var.azure_layer_access_principal_object_id
        principal_type = "User"
      }
    } : {},
    local.azure_v2_l5_enabled ? {
      grafana_provisioner = {
        scope          = azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].id
        role           = "Grafana Admin"
        principal_id   = data.azurerm_client_config.azure_v2_layer_access[0].object_id
        principal_type = "ServicePrincipal"
        skip_check     = true
      }
      grafana_human_viewer = {
        scope          = azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].id
        role           = "Grafana Viewer"
        principal_id   = var.azure_layer_access_principal_object_id
        principal_type = "User"
      }
    } : {},
  )
}

resource "azurerm_role_assignment" "azure_azure_entra_layer_access_bindings" {
  for_each             = local.azure_v2_event_role_bindings
  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = try(each.value.principal_id, azurerm_user_assigned_identity.main[0].principal_id)
  principal_type       = try(each.value.principal_type, "ServicePrincipal")

  skip_service_principal_aad_check = try(each.value.skip_check, false)
}

locals {
  azure_v2_diagnostic_targets = merge(
    local.azure_v2_service_bus_enabled ? {
      service_bus = azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].id
    } : {},
    local.azure_v2_event_enabled ? {
      function = azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter[0].id
    } : {},
    local.azure_v2_l1_enabled ? {
      iot_hub = azurerm_iothub.azure_azure_iot_hub[0].id
    } : {},
    local.azure_v2_l2_enabled ? {
      processing = azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[0].id
      workflow   = azurerm_logic_app_workflow.azure_azure_logic_apps_consumption[0].id
    } : {},
    local.azure_v2_hot_enabled ? {
      cosmos = azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].id
    } : {},
    local.azure_v2_object_store_enabled ? {
      history_storage = azurerm_storage_account.main[0].id
    } : {},
    local.azure_v2_remote_telemetry_enabled ? {
      event_hubs = azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].id
    } : {},
    local.azure_v2_l4_enabled ? {
      digital_twins = azurerm_digital_twins_instance.azure_azure_digital_twins[0].id
    } : {},
    local.azure_v2_l5_enabled ? {
      raw_history_reader = azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader[0].id
      grafana            = azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].id
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

# Catalog-owned, secret-free browser handoff. The Function key used by Grafana
# is created and inserted into secureJsonData by the bounded post-apply step.
output "azure_component_twin_state_output" {
  value = local.azure_v2_l4_enabled ? {
    instance_name   = azurerm_digital_twins_instance.azure_azure_digital_twins[0].name
    endpoint        = "https://${azurerm_digital_twins_instance.azure_azure_digital_twins[0].host_name}"
    access_url      = "https://explorer.digitaltwins.azure.net/?tid=${nonsensitive(var.azure_tenant_id)}&eid=${azurerm_digital_twins_instance.azure_azure_digital_twins[0].host_name}"
    principal_label = var.azure_layer_access_principal_label
    access_role     = "Azure Digital Twins Data Reader"
    internal_evidence = {
      resource_ref        = azurerm_digital_twins_instance.azure_azure_digital_twins[0].id
      access_binding_refs = [azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_human_reader"].id]
      artifact_refs       = ["dtmi:twin2multicloud:poc:TwinNode;1"]
      content_revision    = "azure-l4-seed.v1"
      data_probe_revision = "azure-adt-readback.v1"
    }
  } : null
}

output "azure_component_visualization_output" {
  value = local.azure_v2_l5_enabled ? {
    workspace_name       = azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].name
    access_url           = "${trimsuffix(azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].endpoint, "/")}/d/t2mc-raw-rollups/raw-rollups"
    workspace_url        = azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].endpoint
    reader_url           = "https://${azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader[0].default_hostname}/api/raw-history/v1"
    reader_function_name = azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader[0].name
    principal_label      = var.azure_layer_access_principal_label
    access_role          = "Grafana Viewer"
    internal_evidence = {
      resource_ref        = azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].id
      access_binding_refs = [azurerm_role_assignment.azure_azure_entra_layer_access_bindings["grafana_human_viewer"].id]
      artifact_refs       = ["dashboard:t2mc-raw-rollups"]
      content_revision    = "grafana-raw-rollups.v1"
      data_probe_revision = "azure-grafana-bounded-readback.v1"
    }
  } : null
}
