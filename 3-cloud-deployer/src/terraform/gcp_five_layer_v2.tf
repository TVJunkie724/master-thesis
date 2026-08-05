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

  gcp_v2_event_enabled = (
    local.gcp_v2_l1_enabled || local.gcp_v2_l2_enabled ||
    local.gcp_v2_hot_enabled || local.gcp_v2_l4_enabled
  )
  gcp_v2_domain_enabled = local.gcp_v2_event_enabled
  gcp_v2_container_enabled = (
    local.gcp_v2_l1_enabled || local.gcp_v2_l2_enabled ||
    local.gcp_v2_hot_enabled || local.gcp_v2_cool_enabled ||
    local.gcp_v2_l4_enabled || local.gcp_v2_l5_enabled
  )
  gcp_v2_storage_mover_enabled = (
    local.gcp_v2_hot_enabled ||
    (local.gcp_v2_cool_enabled && var.layer_3_archive_provider != "google")
  )
  gcp_v2_timestamp_shards = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.gcp.gcp.firestore-native-standard-raw-and-rollup.timestamp_shards",
    "1",
  ))

  gcp_v2_required_apis = local.gcp_v2_any_enabled ? toset(compact([
    local.gcp_v2_container_enabled ? "artifactregistry.googleapis.com" : "",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    local.gcp_v2_l1_enabled || local.gcp_v2_l5_enabled ? "compute.googleapis.com" : "",
    local.gcp_v2_l1_enabled || local.gcp_v2_l5_enabled ? "container.googleapis.com" : "",
    local.gcp_v2_hot_enabled || local.gcp_v2_l4_enabled ? "firestore.googleapis.com" : "",
    local.gcp_v2_cool_enabled || local.gcp_v2_archive_enabled ? "storage.googleapis.com" : "",
    local.gcp_v2_l2_enabled ? "workflows.googleapis.com" : "",
    local.gcp_v2_storage_mover_enabled ? "cloudscheduler.googleapis.com" : "",
    local.gcp_v2_l4_enabled || local.gcp_v2_l5_enabled ? "iap.googleapis.com" : "",
    local.gcp_v2_l5_enabled ? "secretmanager.googleapis.com" : "",
  ])) : toset([])

  gcp_v2_name          = substr(replace(lower(var.digital_twin_name), "_", "-"), 0, 24)
  gcp_v2_workflow_name = "${local.gcp_v2_name}-v2-event-workflow"
  gcp_v2_registry_prefix = (
    "${var.gcp_region}-docker.pkg.dev/${local.gcp_project_id}/${local.gcp_v2_name}-v2/"
  )
  gcp_v2_labels = merge(local.gcp_common_labels, {
    architecture-profile = "five-layer-v2"
  })

  gcp_v2_processor_extensions = local.gcp_v2_l2_enabled ? {
    for package in var.validated_extension_packages : package.artifact_id => package
    if package.slot_id == "processor.telemetry" && package.slot_version == "1"
  } : {}

  gcp_v2_topics = local.gcp_v2_event_enabled ? merge(
    { failure = "${local.gcp_v2_name}-v2-failure" },
    local.gcp_v2_l1_enabled || local.gcp_v2_l2_enabled ? {
      received = "${local.gcp_v2_name}-v2-telemetry-received"
    } : {},
    local.gcp_v2_l2_enabled || local.gcp_v2_hot_enabled ? {
      processed = "${local.gcp_v2_name}-v2-telemetry-processed"
    } : {},
    local.gcp_v2_domain_enabled ? {
      domain = "${local.gcp_v2_name}-v2-domain-control"
    } : {},
    local.gcp_v2_l1_enabled ? {
      command = "${local.gcp_v2_name}-v2-device-command"
    } : {},
  ) : {}

  gcp_v2_event_adapters = merge(
    local.gcp_v2_l1_enabled ? { ingress = "event-adapter" } : {},
    local.gcp_v2_hot_enabled ? { persistence = "persistence" } : {},
    local.gcp_v2_domain_enabled ? { domain = "domain-consumer" } : {},
  )
  gcp_v2_subscriptions = merge(
    local.gcp_v2_l2_enabled ? {
      processor = {
        topic = "received"
        role  = "processor"
      }
    } : {},
    local.gcp_v2_hot_enabled ? {
      persistence = {
        topic = "processed"
        role  = "persistence"
      }
    } : {},
    local.gcp_v2_domain_enabled ? {
      domain = {
        topic = "domain"
        role  = "domain"
      }
    } : {},
    local.gcp_v2_l4_enabled ? {
      twin = {
        topic = "domain"
        role  = "twin"
      }
    } : {},
  )
  gcp_v2_storage_jobs = merge(
    local.gcp_v2_hot_enabled ? {
      hot-to-cool = {
        source_provider      = "google"
        destination_provider = var.layer_3_cold_provider
        schedule             = "0 2 * * *"
      }
    } : {},
    local.gcp_v2_cool_enabled && var.layer_3_archive_provider != "google" ? {
      cool-to-archive = {
        source_provider      = "google"
        destination_provider = var.layer_3_archive_provider
        schedule             = "0 3 * * 0"
      }
    } : {},
  )
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
    precondition {
      condition     = !local.gcp_v2_container_enabled || var.gcp_v2_platform_image != ""
      error_message = "GCP Five-layer v2 container components require a content-addressed platform image."
    }
    precondition {
      condition = (
        !local.gcp_v2_container_enabled ||
        startswith(var.gcp_v2_platform_image, local.gcp_v2_registry_prefix)
      )
      error_message = "GCP Five-layer v2 platform images must come from the deployment Artifact Registry repository."
    }
    precondition {
      condition     = !local.gcp_v2_storage_mover_enabled || var.gcp_v2_storage_mover_image != ""
      error_message = "GCP Five-layer v2 storage movement requires a content-addressed storage-mover image."
    }
    precondition {
      condition = (
        !local.gcp_v2_storage_mover_enabled ||
        startswith(var.gcp_v2_storage_mover_image, local.gcp_v2_registry_prefix)
      )
      error_message = "GCP Five-layer v2 storage-mover images must come from the deployment Artifact Registry repository."
    }
  }
}

resource "terraform_data" "gcp_v2_processor_extension_guard" {
  count = local.gcp_v2_l2_enabled ? 1 : 0

  input = {
    package_count = length(local.gcp_v2_processor_extensions)
    image         = var.gcp_v2_processor_extension_image
  }

  lifecycle {
    precondition {
      condition     = length(local.gcp_v2_processor_extensions) == 1
      error_message = "GCP Five-layer v2 requires exactly one validated processor.telemetry@1 package."
    }
    precondition {
      condition     = var.gcp_v2_processor_extension_image != ""
      error_message = "GCP Five-layer v2 requires the content-addressed processor.telemetry@1 adapter image."
    }
    precondition {
      condition     = startswith(var.gcp_v2_processor_extension_image, local.gcp_v2_registry_prefix)
      error_message = "GCP Five-layer v2 processor images must come from the deployment Artifact Registry repository."
    }
  }
}

resource "terraform_data" "gcp_v2_hot_capacity_guard" {
  count = local.gcp_v2_hot_enabled ? 1 : 0

  input = {
    timestamp_shards = local.gcp_v2_timestamp_shards
  }

  lifecycle {
    precondition {
      condition     = contains([1, 16], local.gcp_v2_timestamp_shards)
      error_message = "GCP Five-layer v2 Firestore hot storage requires the reviewed one- or sixteen-shard capacity selection."
    }
  }
}

resource "google_artifact_registry_repository" "gcp_gcp_artifact_registry_if_container_selected" {
  count         = local.gcp_v2_container_enabled ? 1 : 0
  project       = local.gcp_project_id
  location      = var.gcp_region
  repository_id = "${local.gcp_v2_name}-v2"
  description   = "Twin2MultiCloud Five-layer v2 content-addressed PoC images"
  format        = "DOCKER"
  labels        = local.gcp_v2_labels

  docker_config {
    immutable_tags = true
  }

  depends_on = [
    google_project_service.gcp_v2_required,
    terraform_data.gcp_v2_foundation_guard,
  ]
}

resource "google_pubsub_topic" "gcp_gcp_pubsub_separated_embedded_topics" {
  for_each                   = local.gcp_v2_topics
  project                    = local.gcp_project_id
  name                       = each.value
  message_retention_duration = "1209600s"
  labels                     = local.gcp_v2_labels

  message_storage_policy {
    allowed_persistence_regions = [var.gcp_region]
    enforce_in_transit          = true
  }

  depends_on = [google_project_service.pubsub]
}

data "google_project" "gcp_v2_current" {
  count      = local.gcp_v2_event_enabled ? 1 : 0
  project_id = local.gcp_project_id

  depends_on = [google_project_service.pubsub]
}

resource "google_service_account" "gcp_v2_runtime" {
  for_each = merge(
    local.gcp_v2_l1_enabled ? { ingress = "ingress" } : {},
    local.gcp_v2_l2_enabled ? {
      processor = "processor"
      extension = "extension"
      workflow  = "workflow"
      action    = "action"
    } : {},
    local.gcp_v2_hot_enabled ? { persistence = "persistence" } : {},
    local.gcp_v2_domain_enabled ? { domain = "domain" } : {},
    local.gcp_v2_l4_enabled ? {
      twin     = "twin"
      explorer = "explorer"
    } : {},
    local.gcp_v2_storage_mover_enabled ? {
      storage   = "storage"
      scheduler = "scheduler"
    } : {},
  )
  project      = local.gcp_project_id
  account_id   = substr("${local.gcp_v2_name}-v2-${each.value}", 0, 30)
  display_name = "${var.digital_twin_name} v2 ${each.value}"

  depends_on = [google_project_service.iam]
}

resource "google_cloud_run_v2_service" "gcp_gcp_cloud_run_event_adapter" {
  for_each            = local.gcp_v2_event_adapters
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = "${local.gcp_v2_name}-v2-${each.value}"
  description         = "Authenticated Five-layer v2 ${each.value}"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.gcp_v2_labels

  template {
    service_account                  = google_service_account.gcp_v2_runtime[each.key].email
    timeout                          = "30s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0
      max_instance_count = 100
    }

    containers {
      image = var.gcp_v2_platform_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "five-layer-baseline@2"
      }
      env {
        name  = "DEPLOYMENT_ID"
        value = local.deployment_suffix
      }
      env {
        name  = "RUNTIME_ROLE"
        value = each.value
      }
      env {
        name  = "RECEIVED_TOPIC"
        value = try(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["received"].id, "")
      }
      env {
        name  = "PROCESSED_TOPIC"
        value = try(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["processed"].id, "")
      }
      env {
        name  = "DOMAIN_TOPIC"
        value = try(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["domain"].id, "")
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = try(google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name, "")
      }
      env {
        name  = "HOT_BOUNDARY_DAYS"
        value = tostring(var.layer_3_hot_to_cold_interval_days)
      }
      env {
        name  = "TIMESTAMP_SHARDS"
        value = tostring(local.gcp_v2_timestamp_shards)
      }
      env {
        name  = "ACTION_URL"
        value = try(google_cloud_run_v2_service.gcp_v2_action_sink[0].uri, "")
      }
      env {
        name  = "WORKFLOW_NAME"
        value = local.gcp_v2_l2_enabled ? "projects/${local.gcp_project_id}/locations/${var.gcp_region}/workflows/${local.gcp_v2_workflow_name}" : ""
      }
      env {
        name  = "COMMAND_TOPIC"
        value = try(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["command"].id, "")
      }
      env {
        name  = "L1_PROVIDER"
        value = var.layer_1_provider
      }
      env {
        name  = "L2_PROVIDER"
        value = var.layer_2_provider
      }
      env {
        name  = "HOT_PROVIDER"
        value = var.layer_3_hot_provider
      }
      env {
        name  = "TWIN_PROVIDER"
        value = var.layer_4_provider
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected,
    google_project_service.run,
  ]
}

resource "google_cloud_run_v2_service" "gcp_v2_processor_extension" {
  count               = local.gcp_v2_l2_enabled ? 1 : 0
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = "${local.gcp_v2_name}-v2-processor-extension"
  description         = "Validated processor.telemetry@1 GCP adapter"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  labels              = local.gcp_v2_labels

  template {
    service_account                  = google_service_account.gcp_v2_runtime["extension"].email
    timeout                          = "30s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0
      max_instance_count = 100
    }

    containers {
      image = var.gcp_v2_processor_extension_image

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "five-layer-baseline@2"
      }
    }
  }

  lifecycle {
    precondition {
      condition = (
        one(values(local.gcp_v2_processor_extensions)).adapter_id == "adapter.gcp.python311" &&
        one(values(local.gcp_v2_processor_extensions)).adapter_version == "1"
      )
      error_message = "GCP Five-layer v2 requires the reviewed processor.telemetry@1 GCP adapter."
    }
  }

  depends_on = [
    google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected,
    terraform_data.gcp_v2_processor_extension_guard,
    terraform_data.validated_extension_package,
  ]
}

resource "google_cloud_run_v2_service" "gcp_gcp_cloud_run_service" {
  count               = local.gcp_v2_l2_enabled ? 1 : 0
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = "${local.gcp_v2_name}-v2-processor"
  description         = "Five-layer v2 telemetry processor and rule evaluator"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.gcp_v2_labels

  template {
    service_account                  = google_service_account.gcp_v2_runtime["processor"].email
    timeout                          = "60s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0
      max_instance_count = 100
    }

    containers {
      image = var.gcp_v2_platform_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "five-layer-baseline@2"
      }
      env {
        name  = "DEPLOYMENT_ID"
        value = local.deployment_suffix
      }
      env {
        name  = "RUNTIME_ROLE"
        value = "processor"
      }
      env {
        name  = "PROCESSOR_EXTENSION_URL"
        value = google_cloud_run_v2_service.gcp_v2_processor_extension[0].uri
      }
      env {
        name  = "PROCESSED_TOPIC"
        value = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["processed"].id
      }
      env {
        name  = "DOMAIN_TOPIC"
        value = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["domain"].id
      }
      env {
        name  = "RULES_JSON"
        value = jsonencode(var.events)
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected,
    google_cloud_run_v2_service.gcp_v2_processor_extension,
  ]
}

resource "google_cloud_run_v2_service" "gcp_v2_action_sink" {
  count               = local.gcp_v2_l2_enabled ? 1 : 0
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = "${local.gcp_v2_name}-v2-poc-action"
  description         = "Fixed side-effect-free Five-layer v2 action boundary"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  labels              = local.gcp_v2_labels

  template {
    service_account                  = google_service_account.gcp_v2_runtime["action"].email
    timeout                          = "30s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0
      max_instance_count = 20
    }

    containers {
      image = var.gcp_v2_platform_image

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "five-layer-baseline@2"
      }
      env {
        name  = "RUNTIME_ROLE"
        value = "poc-boundary"
      }
    }
  }

  depends_on = [google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected]
}

resource "google_cloud_run_v2_service" "gcp_gcp_cloud_run_twin_api_materializer" {
  count               = local.gcp_v2_l4_enabled ? 1 : 0
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = "${local.gcp_v2_name}-v2-twin-api"
  description         = "Bounded Five-layer v2 Twin API and materializer"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.gcp_v2_labels

  template {
    service_account                  = google_service_account.gcp_v2_runtime["twin"].email
    timeout                          = "30s"
    max_instance_request_concurrency = 8

    scaling {
      min_instance_count = 0
      max_instance_count = 100
    }

    containers {
      image = var.gcp_v2_platform_image

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      startup_probe {
        initial_delay_seconds = 0
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 12

        http_get {
          path = "/healthz"
          port = 8080
        }
      }

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "five-layer-baseline@2"
      }
      env {
        name  = "RUNTIME_ROLE"
        value = "twin-materializer"
      }
      env {
        name  = "DEPLOYMENT_ID"
        value = local.deployment_suffix
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name
      }
      env {
        name  = "IOT_DEVICES_JSON"
        value = jsonencode(var.iot_devices)
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected,
    google_firestore_index.gcp_gcp_firestore_native_standard_bounded_twin,
    google_project_iam_member.gcp_v2_twin_firestore_operator,
  ]
}

resource "google_cloud_run_v2_service" "gcp_gcp_cloud_run_iap_twin_explorer" {
  count                = local.gcp_v2_l4_enabled ? 1 : 0
  project              = local.gcp_project_id
  location             = var.gcp_region
  name                 = "${local.gcp_v2_name}-v2-twin-explorer"
  description          = "Read-only Five-layer v2 Twin Explorer"
  deletion_protection  = false
  ingress              = "INGRESS_TRAFFIC_ALL"
  iap_enabled          = true
  invoker_iam_disabled = false
  default_uri_disabled = false
  labels               = local.gcp_v2_labels

  template {
    service_account                  = google_service_account.gcp_v2_runtime["explorer"].email
    timeout                          = "30s"
    max_instance_request_concurrency = 8

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = var.gcp_v2_platform_image

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "ARCHITECTURE_PROFILE"
        value = "five-layer-baseline@2"
      }
      env {
        name  = "RUNTIME_ROLE"
        value = "twin-explorer"
      }
      env {
        name  = "DEPLOYMENT_ID"
        value = local.deployment_suffix
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected,
    google_firestore_index.gcp_gcp_firestore_native_standard_bounded_twin,
    google_project_iam_member.gcp_v2_explorer_firestore_reader,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_processor_extension_invoker" {
  count    = local.gcp_v2_l2_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_v2_processor_extension[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["processor"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_action_sink_invoker" {
  for_each = local.gcp_v2_l2_enabled ? {
    domain   = google_service_account.gcp_v2_runtime["domain"].email
    workflow = google_service_account.gcp_v2_runtime["workflow"].email
  } : {}
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_v2_action_sink[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${each.value}"
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_processor_push_invoker" {
  count    = local.gcp_v2_l2_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["processor"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_persistence_push_invoker" {
  count    = local.gcp_v2_hot_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["persistence"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["persistence"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_domain_push_invoker" {
  count    = local.gcp_v2_domain_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["domain"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["domain"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_workflow_callback_invoker" {
  count    = local.gcp_v2_l2_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["domain"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["workflow"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_twin_push_invoker" {
  count    = local.gcp_v2_l4_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_gcp_cloud_run_twin_api_materializer[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["twin"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gcp_gcp_cloud_run_iap_twin_explorer" {
  count    = local.gcp_v2_l4_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_gcp_cloud_run_iap_twin_explorer[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-iap.iam.gserviceaccount.com"

  depends_on = [google_project_service.gcp_v2_required]
}

resource "google_iap_web_cloud_run_service_iam_member" "gcp_gcp_cloud_run_iap_twin_explorer" {
  count                  = local.gcp_v2_l4_enabled ? 1 : 0
  project                = local.gcp_project_id
  location               = var.gcp_region
  cloud_run_service_name = google_cloud_run_v2_service.gcp_gcp_cloud_run_iap_twin_explorer[0].name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = "user:${var.platform_user_email}"

  depends_on = [google_cloud_run_v2_service_iam_member.gcp_gcp_cloud_run_iap_twin_explorer]
}

resource "google_service_account_iam_member" "gcp_v2_pubsub_push_token_creator" {
  for_each           = local.gcp_v2_subscriptions
  service_account_id = google_service_account.gcp_v2_runtime[each.value.role].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "gcp_v2_domain_workflow_invoker" {
  count   = local.gcp_v2_l2_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["domain"].email}"
}

resource "google_pubsub_topic_iam_member" "gcp_v2_ingress_publisher" {
  count   = local.gcp_v2_l1_enabled ? 1 : 0
  project = local.gcp_project_id
  topic   = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["received"].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["ingress"].email}"
}

resource "google_pubsub_topic_iam_member" "gcp_v2_processor_publishers" {
  for_each = local.gcp_v2_l2_enabled ? {
    processed = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["processed"].name
    domain    = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["domain"].name
  } : {}
  project = local.gcp_project_id
  topic   = each.value
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["processor"].email}"
}

resource "google_pubsub_topic_iam_member" "gcp_v2_persistence_domain_publisher" {
  count   = local.gcp_v2_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  topic   = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["domain"].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["persistence"].email}"
}

resource "google_pubsub_topic_iam_member" "gcp_v2_domain_publishers" {
  for_each = local.gcp_v2_domain_enabled ? merge(
    {
      domain = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["domain"].name
    },
    local.gcp_v2_l1_enabled ? {
      command = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["command"].name
    } : {},
  ) : {}
  project = local.gcp_project_id
  topic   = each.value
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["domain"].email}"
}

resource "google_project_iam_member" "gcp_v2_domain_firestore_operator" {
  count   = local.gcp_v2_domain_enabled && local.gcp_v2_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["domain"].email}"

  condition {
    title       = "five-layer-v2-domain-database"
    description = "Limit the domain consumer to the deployment Firestore database"
    expression = format(
      "resource.name == %q || resource.name.startsWith(%q)",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}/documents/",
    )
  }
}

resource "google_project_iam_member" "gcp_v2_twin_firestore_operator" {
  count   = local.gcp_v2_l4_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["twin"].email}"

  condition {
    title       = "five-layer-v2-twin-database"
    description = "Limit the Twin API and materializer to the deployment Firestore database"
    expression = format(
      "resource.name == %q || resource.name.startsWith(%q)",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}/documents/",
    )
  }
}

resource "google_project_iam_member" "gcp_v2_explorer_firestore_reader" {
  count   = local.gcp_v2_l4_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["explorer"].email}"

  condition {
    title       = "five-layer-v2-explorer-database"
    description = "Limit the read-only Twin Explorer to the deployment Firestore database"
    expression = format(
      "resource.name == %q || resource.name.startsWith(%q)",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}/documents/",
    )
  }
}

resource "google_project_iam_member" "gcp_v2_persistence_firestore_writer" {
  count   = local.gcp_v2_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["persistence"].email}"

  condition {
    title       = "five-layer-v2-l3-database"
    description = "Limit the persistence runtime to the deployment Firestore database"
    expression = format(
      "resource.name == %q || resource.name.startsWith(%q)",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}/documents/",
    )
  }
}

resource "google_pubsub_subscription" "gcp_gcp_pubsub_separated_embedded_topics" {
  for_each = local.gcp_v2_subscriptions
  project  = local.gcp_project_id
  name     = "${local.gcp_v2_name}-v2-${each.key}"
  topic    = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics[each.value.topic].id

  ack_deadline_seconds       = 60
  message_retention_duration = "1209600s"
  enable_message_ordering    = true
  retain_acked_messages      = false
  labels                     = local.gcp_v2_labels

  push_config {
    push_endpoint = (
      each.key == "processor"
      ? google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].uri
      : each.key == "twin"
      ? google_cloud_run_v2_service.gcp_gcp_cloud_run_twin_api_materializer[0].uri
      : google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter[each.key].uri
    )
    oidc_token {
      service_account_email = google_service_account.gcp_v2_runtime[each.value.role].email
      audience = (
        each.key == "processor"
        ? google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].uri
        : each.key == "twin"
        ? google_cloud_run_v2_service.gcp_gcp_cloud_run_twin_api_materializer[0].uri
        : google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter[each.key].uri
      )
    }
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["failure"].id
    max_delivery_attempts = 5
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.gcp_v2_processor_push_invoker,
    google_cloud_run_v2_service_iam_member.gcp_v2_persistence_push_invoker,
    google_cloud_run_v2_service_iam_member.gcp_v2_domain_push_invoker,
    google_cloud_run_v2_service_iam_member.gcp_v2_twin_push_invoker,
    google_pubsub_topic_iam_member.gcp_v2_persistence_domain_publisher,
    google_pubsub_topic_iam_member.gcp_v2_domain_publishers,
    google_project_iam_member.gcp_v2_persistence_firestore_writer,
    google_project_iam_member.gcp_v2_domain_firestore_operator,
    google_project_iam_member.gcp_v2_twin_firestore_operator,
    google_project_iam_member.gcp_v2_explorer_firestore_reader,
    google_project_iam_member.gcp_v2_domain_workflow_invoker,
    google_service_account_iam_member.gcp_v2_pubsub_push_token_creator,
  ]
}

resource "google_pubsub_topic_iam_member" "gcp_v2_failure_service_agent_publisher" {
  count   = length(local.gcp_v2_subscriptions) > 0 ? 1 : 0
  project = local.gcp_project_id
  topic   = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["failure"].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "gcp_v2_failure_service_agent_subscriber" {
  for_each     = local.gcp_v2_subscriptions
  project      = local.gcp_project_id
  subscription = google_pubsub_subscription.gcp_gcp_pubsub_separated_embedded_topics[each.key].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# GCP L3 and L4 share one deployment Firestore database when both are selected.
# Their collections, indexes, runtimes, and cost ownership remain separate.
resource "google_firestore_database" "gcp_gcp_firestore_native_standard_raw_and_rollup" {
  count                       = local.gcp_v2_hot_enabled || local.gcp_v2_l4_enabled ? 1 : 0
  project                     = local.gcp_project_id
  name                        = "${local.gcp_v2_name}-v2-data-${local.deployment_suffix}"
  location_id                 = var.gcp_region
  type                        = "FIRESTORE_NATIVE"
  database_edition            = "STANDARD"
  concurrency_mode            = "PESSIMISTIC"
  app_engine_integration_mode = "DISABLED"
  delete_protection_state     = "DELETE_PROTECTION_DISABLED"
  deletion_policy             = "DELETE"

  depends_on = [google_project_service.gcp_v2_required]
}

resource "google_firestore_field" "gcp_gcp_firestore_native_standard_raw_and_rollup" {
  for_each = local.gcp_v2_hot_enabled ? {
    telemetry_ttl = {
      collection       = "telemetry"
      field            = "expires_at"
      ttl              = true
      disable_indexing = false
    }
    rollup_ttl = {
      collection       = "hourly_rollups"
      field            = "expires_at"
      ttl              = true
      disable_indexing = false
    }
    outcome_ttl = {
      collection       = "outcomes"
      field            = "expires_at"
      ttl              = true
      disable_indexing = false
    }
    raw_stored_at = {
      collection       = "telemetry"
      field            = "stored_at"
      ttl              = false
      disable_indexing = true
    }
    raw_event_time = {
      collection       = "telemetry"
      field            = "event_time"
      ttl              = false
      disable_indexing = true
    }
    raw_timestamp_shard = {
      collection       = "telemetry"
      field            = "timestamp_shard"
      ttl              = false
      disable_indexing = true
    }
    rollup_bucket_start = {
      collection       = "hourly_rollups"
      field            = "bucket_start"
      ttl              = false
      disable_indexing = true
    }
  } : {}

  project    = local.gcp_project_id
  database   = google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name
  collection = each.value.collection
  field      = each.value.field

  dynamic "ttl_config" {
    for_each = each.value.ttl ? [1] : []
    content {}
  }

  dynamic "index_config" {
    for_each = each.value.disable_indexing ? [1] : []
    content {}
  }
}

resource "google_firestore_index" "gcp_gcp_firestore_native_standard_raw_and_rollup" {
  for_each = local.gcp_v2_hot_enabled ? {
    raw_history = {
      collection = "telemetry"
      fields = [
        { field_path = "device_id", order = "ASCENDING" },
        { field_path = "metric", order = "ASCENDING" },
        { field_path = "timestamp_shard", order = "ASCENDING" },
        { field_path = "stored_at", order = "DESCENDING" },
      ]
    }
    raw_mover = {
      collection = "telemetry"
      fields = [
        { field_path = "timestamp_shard", order = "ASCENDING" },
        { field_path = "stored_at", order = "ASCENDING" },
      ]
    }
    rollup_history = {
      collection = "hourly_rollups"
      fields = [
        { field_path = "device_id", order = "ASCENDING" },
        { field_path = "metric", order = "ASCENDING" },
        { field_path = "bucket_start", order = "ASCENDING" },
      ]
    }
  } : {}

  project     = local.gcp_project_id
  database    = google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name
  collection  = each.value.collection
  query_scope = "COLLECTION"

  dynamic "fields" {
    for_each = each.value.fields
    content {
      field_path = fields.value.field_path
      order      = fields.value.order
    }
  }
}

resource "google_firestore_index" "gcp_gcp_firestore_native_standard_bounded_twin" {
  for_each = local.gcp_v2_l4_enabled ? {
    outgoing = "from_id"
    incoming = "to_id"
  } : {}

  project     = local.gcp_project_id
  database    = google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name
  collection  = "relationships"
  query_scope = "COLLECTION"

  fields {
    field_path = each.value
    order      = "ASCENDING"
  }
  fields {
    field_path = "type"
    order      = "ASCENDING"
  }
}

# A single Nearline bucket owns the cool tier. When GCP also owns archive,
# Cloud Storage performs the second transition natively; a second bucket and
# a permanent worker would add no thesis value.
resource "google_storage_bucket" "gcp_gcp_cloud_storage_nearline" {
  count                       = local.gcp_v2_cool_enabled ? 1 : 0
  project                     = local.gcp_project_id
  name                        = "${local.gcp_v2_name}-v2-history-${local.deployment_suffix}"
  location                    = var.gcp_region
  storage_class               = "NEARLINE"
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = local.gcp_v2_labels

  soft_delete_policy {
    retention_duration_seconds = 0
  }

  dynamic "lifecycle_rule" {
    for_each = local.gcp_v2_archive_enabled ? [1] : []
    content {
      action {
        type          = "SetStorageClass"
        storage_class = "ARCHIVE"
      }
      condition {
        age                   = var.layer_3_cold_to_archive_interval_days - var.layer_3_hot_to_cold_interval_days
        matches_storage_class = ["NEARLINE"]
      }
    }
  }

  lifecycle_rule {
    action { type = "Delete" }
    condition {
      age = local.gcp_v2_archive_enabled ? (
        var.layer_3_archive_expiry_interval_days - var.layer_3_hot_to_cold_interval_days
        ) : (
        var.layer_3_cold_to_archive_interval_days - var.layer_3_hot_to_cold_interval_days + 2
      )
    }
  }

  depends_on = [google_project_service.gcp_v2_required]
}

# GCP creates a dedicated Archive bucket only when a remote cool-tier mover
# lands objects directly in GCP. The same-provider path uses the bucket above.
resource "google_storage_bucket" "gcp_gcp_cloud_storage_archive" {
  count                       = local.gcp_v2_archive_enabled && !local.gcp_v2_cool_enabled ? 1 : 0
  project                     = local.gcp_project_id
  name                        = "${local.gcp_v2_name}-v2-archive-${local.deployment_suffix}"
  location                    = var.gcp_region
  storage_class               = "ARCHIVE"
  force_destroy               = true
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = local.gcp_v2_labels

  soft_delete_policy {
    retention_duration_seconds = 0
  }

  lifecycle_rule {
    action { type = "Delete" }
    condition {
      age = var.layer_3_archive_expiry_interval_days - var.layer_3_cold_to_archive_interval_days
    }
  }

  depends_on = [google_project_service.gcp_v2_required]
}

# The mover needs reads plus post-copy deletes. The predefined data role is
# therefore narrowed to this deployment database with an IAM condition.
resource "google_project_iam_member" "gcp_v2_storage_firestore_operator" {
  count   = local.gcp_v2_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["storage"].email}"

  condition {
    title       = "five-layer-v2-l3-storage-database"
    description = "Limit the storage mover to the deployment Firestore database"
    expression = format(
      "resource.name == %q || resource.name.startsWith(%q)",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}",
      "projects/${local.gcp_project_id}/databases/${google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name}/documents/",
    )
  }
}

resource "google_storage_bucket_iam_member" "gcp_v2_storage_bucket_operator" {
  count  = local.gcp_v2_cool_enabled && local.gcp_v2_storage_mover_enabled ? 1 : 0
  bucket = google_storage_bucket.gcp_gcp_cloud_storage_nearline[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gcp_v2_runtime["storage"].email}"
}

# Exactly one finite execution is scheduled for each source-owned transition.
# The job exits after a bounded age window; no long-running tiering service,
# checkpoint database, or enterprise orchestration layer is introduced.
resource "google_cloud_run_v2_job" "gcp_gcp_cloud_run_storage_job" {
  for_each            = local.gcp_v2_storage_jobs
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = substr("${local.gcp_v2_name}-v2-${each.key}", 0, 49)
  deletion_protection = false
  labels              = local.gcp_v2_labels

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.gcp_v2_runtime["storage"].email
      max_retries     = 1
      timeout         = "900s"

      containers {
        image = var.gcp_v2_storage_mover_image

        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }

        env {
          name  = "ARCHITECTURE_PROFILE"
          value = "five-layer-baseline@2"
        }
        env {
          name  = "TRANSITION"
          value = each.key
        }
        env {
          name  = "SOURCE_PROVIDER"
          value = each.value.source_provider
        }
        env {
          name  = "DESTINATION_PROVIDER"
          value = each.value.destination_provider
        }
        env {
          name  = "FIRESTORE_DATABASE"
          value = try(google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name, "")
        }
        env {
          name  = "HISTORY_BUCKET"
          value = try(google_storage_bucket.gcp_gcp_cloud_storage_nearline[0].name, "")
        }
        env {
          name  = "ARCHIVE_BUCKET"
          value = try(google_storage_bucket.gcp_gcp_cloud_storage_archive[0].name, "")
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
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected,
    google_project_iam_member.gcp_v2_storage_firestore_operator,
    google_storage_bucket_iam_member.gcp_v2_storage_bucket_operator,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "gcp_v2_scheduler_job_invoker" {
  for_each = local.gcp_v2_storage_jobs
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_job.gcp_gcp_cloud_run_storage_job[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["scheduler"].email}"
}

resource "google_cloud_scheduler_job" "gcp_gcp_cloud_scheduler" {
  for_each         = local.gcp_v2_storage_jobs
  project          = local.gcp_project_id
  region           = var.gcp_region
  name             = substr("${local.gcp_v2_name}-v2-${each.key}", 0, 49)
  description      = "Run the finite Five-layer v2 ${each.key} storage window"
  schedule         = each.value.schedule
  time_zone        = "Etc/UTC"
  attempt_deadline = "900s"

  retry_config {
    retry_count          = 1
    min_backoff_duration = "30s"
    max_backoff_duration = "300s"
    max_doublings        = 1
  }

  http_target {
    uri         = "https://run.googleapis.com/v2/projects/${local.gcp_project_id}/locations/${var.gcp_region}/jobs/${google_cloud_run_v2_job.gcp_gcp_cloud_run_storage_job[each.key].name}:run"
    http_method = "POST"
    oauth_token {
      service_account_email = google_service_account.gcp_v2_runtime["scheduler"].email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.gcp_v2_scheduler_job_invoker]
}

resource "google_workflows_workflow" "gcp_gcp_workflows" {
  count           = local.gcp_v2_l2_enabled ? 1 : 0
  project         = local.gcp_project_id
  region          = var.gcp_region
  name            = local.gcp_v2_workflow_name
  description     = "Fixed four-action Five-layer v2 notification workflow"
  service_account = google_service_account.gcp_v2_runtime["workflow"].id
  labels          = local.gcp_v2_labels

  source_contents = yamlencode({
    main = {
      params = ["args"]
      steps = [
        { validate_notification = { assign = [
          { notification = "$${args}" },
          { outcome_status = "SUCCEEDED" },
        ] } },
        { deliver_notification = {
          try = {
            call = "http.post"
            args = {
              url  = google_cloud_run_v2_service.gcp_v2_action_sink[0].uri
              auth = { type = "OIDC" }
              body = "$${notification}"
            }
            result = "delivery_result"
          }
          except = {
            as = "delivery_error"
            steps = [{ mark_failed = { assign = [
              { outcome_status = "FAILED" },
            ] } }]
          }
        } },
        { record_outcome = {
          call = "http.post"
          args = {
            url  = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["domain"].uri
            auth = { type = "OIDC" }
            body = {
              schema_version   = "workflow-outcome.v1"
              workflow_request = "$${notification}"
              status           = "$${outcome_status}"
            }
          }
          result = "outcome_result"
        } },
        { record_success = { return = "$${outcome_result.body}" } },
      ]
    }
  })

  depends_on = [
    google_cloud_run_v2_service_iam_member.gcp_v2_action_sink_invoker,
    google_cloud_run_v2_service_iam_member.gcp_v2_workflow_callback_invoker,
    google_project_service.gcp_v2_required,
  ]
}

output "gcp_component_twin_state_output" {
  description = "Safe Five-layer v2 GCP L4 browser access and deterministic content evidence"
  value = local.gcp_v2_l4_enabled ? {
    service                 = "Cloud Run Twin API + read-only IAP Twin Explorer"
    materializer_service_id = google_cloud_run_v2_service.gcp_gcp_cloud_run_twin_api_materializer[0].id
    explorer_url            = google_cloud_run_v2_service.gcp_gcp_cloud_run_iap_twin_explorer[0].uri
    principal_label         = var.platform_user_email
    authentication          = "Google Identity-Aware Proxy"
    capabilities            = ["models", "twins", "current-source-state", "direct-relationships"]
    limitations             = ["read-only", "bounded-queries", "no-scenes", "no-raw-telemetry"]
    seed_revision           = "gcp-l4-seed.v1"
    seed_input_digest       = sha256(jsonencode(var.iot_devices))
  } : null
}
