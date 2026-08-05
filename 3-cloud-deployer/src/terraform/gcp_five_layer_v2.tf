# GCP foundation for five-layer-baseline@2.
#
# Provider APIs are shared deployment support, while every runtime and data
# resource remains conditional on its selected scientific responsibility.

locals {
  gcp_v2_l1_enabled      = local.five_layer_v2_enabled && var.layer_1_provider == "google"
  gcp_v2_l2_enabled      = local.five_layer_v2_enabled && var.layer_2_provider == "google"
  gcp_v2_hot_enabled     = local.five_layer_v2_enabled && var.layer_3_hot_provider == "google"
  gcp_v2_cool_enabled    = local.five_layer_v2_enabled && var.layer_3_cold_provider == "google"
  gcp_v2_archive_enabled = local.five_layer_v2_enabled && var.layer_3_archive_provider == "google"
  gcp_v2_l4_enabled      = local.five_layer_v2_enabled && var.layer_4_provider == "google"
  gcp_v2_l5_enabled      = local.five_layer_v2_enabled && var.layer_5_provider == "google"

  gcp_v2_any_enabled = (
    local.gcp_v2_l1_enabled || local.gcp_v2_l2_enabled ||
    local.gcp_v2_hot_enabled || local.gcp_v2_cool_enabled ||
    local.gcp_v2_archive_enabled || local.gcp_v2_l4_enabled ||
    local.gcp_v2_l5_enabled
  )

  gcp_v2_required_apis = local.gcp_v2_any_enabled ? toset(compact([
    "artifactregistry.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    local.gcp_v2_l1_enabled || local.gcp_v2_l5_enabled ? "compute.googleapis.com" : "",
    local.gcp_v2_l1_enabled || local.gcp_v2_l5_enabled ? "container.googleapis.com" : "",
    local.gcp_v2_hot_enabled || local.gcp_v2_l4_enabled ? "firestore.googleapis.com" : "",
    local.gcp_v2_cool_enabled || local.gcp_v2_archive_enabled ? "storage.googleapis.com" : "",
    local.gcp_v2_l2_enabled ? "workflows.googleapis.com" : "",
    local.gcp_v2_hot_enabled || local.gcp_v2_cool_enabled ? "cloudscheduler.googleapis.com" : "",
    local.gcp_v2_l4_enabled || local.gcp_v2_l5_enabled ? "iap.googleapis.com" : "",
    local.gcp_v2_l5_enabled ? "secretmanager.googleapis.com" : "",
  ])) : toset([])

  gcp_v2_name = substr(replace(lower(var.digital_twin_name), "_", "-"), 0, 24)
  gcp_v2_labels = merge(local.gcp_common_labels, {
    architecture-profile = "five-layer-v2"
  })
}

resource "google_project_service" "gcp_v2_required" {
  for_each = local.gcp_v2_required_apis
  project  = local.gcp_project_id
  service  = each.value

  disable_on_destroy = false
  depends_on         = [google_project_service.cloudresourcemanager]
}

resource "terraform_data" "gcp_v2_foundation_guard" {
  count = local.gcp_v2_any_enabled ? 1 : 0

  input = {
    project_id = local.gcp_project_id
    region     = var.gcp_region
    api_count  = length(local.gcp_v2_required_apis)
  }

  lifecycle {
    precondition {
      condition     = local.gcp_project_id != ""
      error_message = "GCP Five-layer v2 requires an existing project or organization billing account."
    }
    precondition {
      condition     = var.gcp_region != ""
      error_message = "GCP Five-layer v2 requires an explicit region."
    }
  }
}
