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
  gcp_v2_container_enabled = (
    local.gcp_v2_l1_enabled || local.gcp_v2_l2_enabled ||
    local.gcp_v2_hot_enabled || local.gcp_v2_cool_enabled ||
    local.gcp_v2_l4_enabled || local.gcp_v2_l5_enabled
  )
  gcp_v2_storage_mover_enabled = (
    local.gcp_v2_hot_enabled ||
    (local.gcp_v2_cool_enabled && var.layer_3_archive_provider != "google")
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
    local.gcp_v2_l2_enabled || local.gcp_v2_hot_enabled || local.gcp_v2_l4_enabled ? {
      processed = "${local.gcp_v2_name}-v2-telemetry-processed"
    } : {},
    local.gcp_v2_l2_enabled ? {
      domain = "${local.gcp_v2_name}-v2-domain-control"
    } : {},
  ) : {}

  gcp_v2_event_adapters = merge(
    local.gcp_v2_l1_enabled ? { ingress = "event-adapter" } : {},
    local.gcp_v2_hot_enabled ? { persistence = "persistence" } : {},
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
    } : {},
    local.gcp_v2_hot_enabled ? { persistence = "persistence" } : {},
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
    service_account                  = google_service_account.gcp_v2_runtime["workflow"].email
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

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_processor_extension_invoker" {
  count    = local.gcp_v2_l2_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_v2_processor_extension[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["processor"].email}"
}

resource "google_cloud_run_v2_service_iam_member" "gcp_v2_action_sink_invoker" {
  count    = local.gcp_v2_l2_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.gcp_v2_action_sink[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.gcp_v2_runtime["workflow"].email}"
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

resource "google_service_account_iam_member" "gcp_v2_pubsub_push_token_creator" {
  for_each           = local.gcp_v2_subscriptions
  service_account_id = google_service_account.gcp_v2_runtime[each.value.role].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "gcp_v2_processor_workflow_invoker" {
  count   = local.gcp_v2_l2_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["processor"].email}"
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

resource "google_project_iam_member" "gcp_v2_persistence_firestore_writer" {
  count   = local.gcp_v2_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["persistence"].email}"
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
      : google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter[each.key].uri
    )
    oidc_token {
      service_account_email = google_service_account.gcp_v2_runtime[each.value.role].email
      audience = (
        each.key == "processor"
        ? google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].uri
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
    google_project_iam_member.gcp_v2_persistence_firestore_writer,
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

# L3 Hot intentionally uses one Firestore database with separate raw and
# hourly-rollup collections. This preserves the thesis comparison boundary
# without paying for or operating a second PoC database.
resource "google_firestore_database" "gcp_gcp_firestore_native_standard_raw_and_rollup" {
  count                       = local.gcp_v2_hot_enabled ? 1 : 0
  project                     = local.gcp_project_id
  name                        = "${local.gcp_v2_name}-v2-l3-${local.deployment_suffix}"
  location_id                 = var.gcp_region
  type                        = "FIRESTORE_NATIVE"
  database_edition            = "STANDARD"
  concurrency_mode            = "PESSIMISTIC"
  app_engine_integration_mode = "DISABLED"
  delete_protection_state     = "DELETE_PROTECTION_DISABLED"
  deletion_policy             = "DELETE"

  depends_on = [google_project_service.gcp_v2_required]
}

resource "google_firestore_field" "gcp_v2_hot_ttl" {
  for_each = local.gcp_v2_hot_enabled ? toset([
    "telemetry_raw",
    "telemetry_hourly_rollups",
  ]) : toset([])

  project    = local.gcp_project_id
  database   = google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name
  collection = each.value
  field      = "expires_at"

  ttl_config {}
}

resource "google_firestore_index" "gcp_v2_hot_query" {
  for_each = local.gcp_v2_hot_enabled ? {
    raw = {
      collection = "telemetry_raw"
      time_field = "stored_at"
    }
    rollup = {
      collection = "telemetry_hourly_rollups"
      time_field = "bucket_start"
    }
  } : {}

  project     = local.gcp_project_id
  database    = google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup[0].name
  collection  = each.value.collection
  query_scope = "COLLECTION"

  fields {
    field_path = "device_id"
    order      = "ASCENDING"
  }
  fields {
    field_path = "metric"
    order      = "ASCENDING"
  }
  fields {
    field_path = each.value.time_field
    order      = "DESCENDING"
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

# Firestore's predefined data role is project-scoped. The mover needs reads
# plus post-copy deletes, so roles/datastore.user is the narrow managed role
# that covers its complete finite-window operation.
resource "google_project_iam_member" "gcp_v2_storage_firestore_operator" {
  count   = local.gcp_v2_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.gcp_v2_runtime["storage"].email}"
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
  name            = "${local.gcp_v2_name}-v2-event-workflow"
  description     = "Fixed four-action Five-layer v2 notification workflow"
  service_account = google_service_account.gcp_v2_runtime["workflow"].id
  labels          = local.gcp_v2_labels

  source_contents = yamlencode({
    main = {
      params = ["args"]
      steps = [
        { validate_notification = { assign = [{ notification = "$${args}" }] } },
        { prepare_delivery = { assign = [{ request = "$${notification}" }] } },
        { deliver_notification = {
          call = "http.post"
          args = {
            url  = google_cloud_run_v2_service.gcp_v2_action_sink[0].uri
            auth = { type = "OIDC" }
            body = "$${request}"
          }
          result = "delivery_result"
        } },
        { record_success = { return = "$${delivery_result.body}" } },
      ]
    }
  })

  depends_on = [
    google_cloud_run_v2_service_iam_member.gcp_v2_action_sink_invoker,
    google_project_service.gcp_v2_required,
  ]
}
