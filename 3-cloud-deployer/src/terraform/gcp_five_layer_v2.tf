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
  for_each = local.gcp_v2_event_enabled ? merge(
    local.gcp_v2_l1_enabled ? { ingress = "ingress" } : {},
    local.gcp_v2_l2_enabled ? {
      processor = "processor"
      extension = "extension"
      workflow  = "workflow"
    } : {},
  ) : {}
  project      = local.gcp_project_id
  account_id   = substr("${local.gcp_v2_name}-v2-${each.value}", 0, 30)
  display_name = "${var.digital_twin_name} v2 ${each.value}"

  depends_on = [google_project_service.iam]
}

resource "google_cloud_run_v2_service" "gcp_gcp_cloud_run_event_adapter" {
  count               = local.gcp_v2_l1_enabled ? 1 : 0
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = "${local.gcp_v2_name}-v2-event-adapter"
  description         = "Authenticated Five-layer v2 MQTT/PubSub event adapter"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.gcp_v2_labels

  template {
    service_account                  = google_service_account.gcp_v2_runtime["ingress"].email
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
        value = "event-adapter"
      }
      env {
        name  = "RECEIVED_TOPIC"
        value = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["received"].id
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

resource "google_service_account_iam_member" "gcp_v2_pubsub_push_token_creator" {
  count              = local.gcp_v2_l2_enabled ? 1 : 0
  service_account_id = google_service_account.gcp_v2_runtime["processor"].name
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

resource "google_pubsub_subscription" "gcp_gcp_pubsub_separated_embedded_topics" {
  count   = local.gcp_v2_l2_enabled ? 1 : 0
  project = local.gcp_project_id
  name    = "${local.gcp_v2_name}-v2-processor"
  topic   = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["received"].id

  ack_deadline_seconds       = 60
  message_retention_duration = "1209600s"
  enable_message_ordering    = true
  retain_acked_messages      = false
  labels                     = local.gcp_v2_labels

  push_config {
    push_endpoint = google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].uri
    oidc_token {
      service_account_email = google_service_account.gcp_v2_runtime["processor"].email
      audience              = google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].uri
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

  depends_on = [google_cloud_run_v2_service_iam_member.gcp_v2_processor_push_invoker]
}

resource "google_pubsub_topic_iam_member" "gcp_v2_failure_service_agent_publisher" {
  count   = local.gcp_v2_l2_enabled ? 1 : 0
  project = local.gcp_project_id
  topic   = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["failure"].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "gcp_v2_failure_service_agent_subscriber" {
  count        = local.gcp_v2_l2_enabled ? 1 : 0
  project      = local.gcp_project_id
  subscription = google_pubsub_subscription.gcp_gcp_pubsub_separated_embedded_topics[0].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.gcp_v2_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
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
