# Fixed research slice, not a generic partial-deployment mechanism. Full-profile
# admission remains owned by the existing manifest validator.
variable "evaluation_scope" {
  type        = string
  default     = "full"
  description = "full or the supervised Small core evaluation (L1-L3 + Event Layer)."
  validation {
    condition     = contains(["full", "core"], var.evaluation_scope)
    error_message = "Only full and core evaluation scopes are supported."
  }
}

locals {
  core_evaluation = var.evaluation_scope == "core"
  core_evaluation_edge_ids = toset([
    "edge.ingestion-to-eventing", "edge.eventing-to-ingestion",
  ])
  core_source = var.layer_1_provider == "google" ? "gcp" : var.layer_1_provider
  core_target = var.event_layer_provider == "google" ? "gcp" : var.event_layer_provider
  core_expected_channels = local.core_source == local.core_target ? toset([]) : toset([
    "edge.ingestion-to-eventing:telemetry:telemetry.received.v1",
    "edge.ingestion-to-eventing:control:device.command.outcome.v1",
    "edge.eventing-to-ingestion:control:device.command.requested.v1",
  ])
}

resource "terraform_data" "evaluation_scope_guard" {
  input = var.evaluation_scope
  lifecycle {
    precondition {
      condition = !local.core_evaluation || (
        local.six_layer_eventing_enabled &&
        var.layer_4_provider == "" && var.layer_5_provider == "" &&
        contains(["aws", "azure", "google"], var.event_layer_provider) &&
        var.layer_2_provider == var.event_layer_provider &&
        var.layer_3_hot_provider == var.event_layer_provider &&
        var.layer_3_cold_provider == var.event_layer_provider &&
        var.layer_3_archive_provider == var.event_layer_provider
      )
      error_message = "Core requires six-layer-eventing@1, absent L4/L5 and the reviewed ingestion-to-local-core placement."
    }
    precondition {
      condition = !local.core_evaluation || (alltrue([
        for route in var.resolved_cross_cloud_routes :
        contains(local.core_evaluation_edge_ids, route.logical_edge_id) &&
        route.execution_kind == "source_event_forwarder" &&
        route.source_provider == (route.logical_edge_id == "edge.ingestion-to-eventing" ? local.core_source : local.core_target) &&
        route.destination_provider == (route.logical_edge_id == "edge.ingestion-to-eventing" ? local.core_target : local.core_source)
        ]) && length(var.resolved_cross_cloud_routes) == length(local.core_expected_channels) && length(setsubtract(local.core_expected_channels, toset([
          for route in var.resolved_cross_cloud_routes : "${route.logical_edge_id}:${route.channel_class}:${join(",", route.event_types)}"
      ]))) == 0)
      error_message = "Core requires exactly the reviewed telemetry/outcome/command routes; no Twin/visualization routes."
    }
    precondition {
      condition = !local.core_evaluation || (
        (!local.aws_event_enabled || coalesce(var.aws_event_kinesis_shards, 0) == 1) &&
        (!local.azure_event_enabled || (!local.azure_event_dedicated && local.azure_event_throughput_units == 1)) &&
        (!local.azure_six_layer_hot_enabled || local.azure_six_layer_cosmos_capacity_mode == "serverless") &&
        !local.gcp_event_large &&
        (!local.gcp_six_layer_l1_enabled || (local.gcp_six_layer_bifromq_broker_nodes == 1 && local.gcp_six_layer_bifromq_integration_nodes == 1)) &&
        alltrue([
          for key, value in var.resolved_component_dimensions :
          !endswith(key, ".task_count") || value == "1"
        ])
      )
      error_message = "Core evaluation admits only the reviewed Small allocation, not Medium/Large."
    }
    precondition {
      condition = local.core_evaluation || (
        contains(["aws", "azure", "google"], var.layer_4_provider) &&
        contains(["aws", "azure", "google"], var.layer_5_provider)
      )
      error_message = "Omitting L4/L5 is allowed only in the explicit core evaluation scope."
    }
  }
}

output "evaluation_scope" {
  description = "Selected scope only; not successful runtime or full-architecture verification evidence."
  value = {
    scope                = var.evaluation_scope
    includes_all_layers  = !local.core_evaluation
    excluded_layers      = local.core_evaluation ? ["L4", "L5"] : []
    storage_reader_is_l5 = false
  }
}
