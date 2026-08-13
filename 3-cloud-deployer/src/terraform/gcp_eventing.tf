# GCP implementation of the independent six-layer-eventing@1 responsibility.
# Two telemetry topics preserve the received/processed replay boundaries,
# Pub/Sub owns ordered fan-out and native dead letters, Cloud Run services own
# Small/Medium delivery plus control, and fixed worker pools own Large telemetry.

locals {
  gcp_event_enabled = (
    local.six_layer_eventing_enabled &&
    var.event_layer_provider == "google"
  )
  gcp_event_l1_local  = local.gcp_event_enabled && var.layer_1_provider == "google"
  gcp_event_l2_local  = local.gcp_event_enabled && var.layer_2_provider == "google"
  gcp_event_hot_local = local.gcp_event_enabled && var.layer_3_hot_provider == "google"
  gcp_event_name      = substr(replace(lower(var.digital_twin_name), "_", "-"), 0, 24)

  gcp_event_resolved_worker_count = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.gcp.gcp.cloud-run-worker-pool-fixed-large.resource_count",
    tostring(var.gcp_event_worker_count),
  ))
  gcp_event_publish_bytes = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.gcp.gcp.pubsub-separated-event-layer-topics.publish_bytes",
    "0",
  ))
  gcp_event_large             = local.gcp_event_resolved_worker_count > 0
  gcp_event_retention_seconds = local.gcp_event_publish_bytes > 10000000000 ? 604800 : var.gcp_event_retention_seconds
  gcp_event_topics = {
    received  = "${local.gcp_event_name}-event-telemetry-received"
    processed = "${local.gcp_event_name}-event-telemetry-processed"
    control   = "${local.gcp_event_name}-event-control"
    failure   = "${local.gcp_event_name}-event-failure"
  }
  gcp_event_local_processed_roles = concat(
    local.gcp_event_hot_local ? [
      "historical-persistence",
      "twin-state-update",
    ] : [],
    local.gcp_event_l2_local ? ["rule-evaluator"] : [],
    local.gcp_event_large ? ["audit", "realtime-visualization"] : [],
  )
  gcp_event_local_control_event_types = concat(
    local.gcp_event_l2_local ? [
      "event.matched.v1",
      "notification.requested.v1",
    ] : [],
    local.gcp_event_hot_local ? [
      "extension.action.outcome.v1",
      "notification.workflow.outcome.v1",
      "device.command.outcome.v1",
    ] : [],
    local.gcp_event_l1_local ? ["device.command.requested.v1"] : [],
  )
  gcp_event_telemetry_subscriptions = merge(
    local.gcp_event_l2_local ? {
      telemetry-processor = {
        topic = "received"
        role  = "telemetry-processor"
      }
    } : {},
    {
      for role in local.gcp_event_local_processed_roles : role => {
        topic = "processed"
        role  = role
      }
    },
  )
  gcp_event_subscriptions = merge(
    local.gcp_event_telemetry_subscriptions,
    length(local.gcp_event_local_control_event_types) > 0 ? {
      control-router = {
        topic = "control"
        role  = "control-router"
      }
    } : {},
  )
  gcp_event_worker_subscriptions = local.gcp_event_large ? local.gcp_event_telemetry_subscriptions : {}
  gcp_event_push_subscriptions = {
    for key, value in local.gcp_event_subscriptions : key => value
    if !local.gcp_event_large || value.topic == "control"
  }
  gcp_event_workers_per_subscription = (
    length(local.gcp_event_worker_subscriptions) == 0 ? 0 :
    floor(local.gcp_event_resolved_worker_count / length(local.gcp_event_worker_subscriptions))
  )
  gcp_event_delivery_targets = merge(
    local.gcp_event_l2_local ? {
      telemetry-processor = google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].uri
      rule-evaluator      = google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].uri
    } : {},
    local.gcp_event_hot_local ? {
      historical-persistence = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["persistence"].uri
      twin-state-update      = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["persistence"].uri
    } : {},
    length(local.gcp_event_local_control_event_types) > 0 ? {
      control-router = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["domain"].uri
    } : {},
  )
  gcp_event_target_services = merge(
    local.gcp_event_l2_local ? {
      processor = google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].name
    } : {},
    local.gcp_event_hot_local ? {
      persistence = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["persistence"].name
    } : {},
    length(local.gcp_event_local_control_event_types) > 0 ? {
      domain = google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter["domain"].name
    } : {},
  )
  gcp_event_labels = merge(local.gcp_common_labels, {
    architecture-profile = "six-layer-eventing-v1"
    responsibility       = "eventing"
  })
}

resource "terraform_data" "gcp_eventing_capacity_guard" {
  count = local.gcp_event_enabled ? 1 : 0

  input = {
    worker_count             = local.gcp_event_resolved_worker_count
    telemetry_subscriptions  = length(local.gcp_event_worker_subscriptions)
    workers_per_subscription = local.gcp_event_workers_per_subscription
    retention_seconds        = local.gcp_event_retention_seconds
  }

  lifecycle {
    precondition {
      condition = (
        local.gcp_event_resolved_worker_count == 0 ||
        (
          local.gcp_event_resolved_worker_count <= 126 &&
          local.gcp_event_resolved_worker_count % 21 == 0
        )
      )
      error_message = "GCP Event Layer worker count must be zero or a reviewed 21-instance-per-subscription Large allocation."
    }
    precondition {
      condition = (
        !local.gcp_event_large ||
        (
          length(local.gcp_event_worker_subscriptions) > 0 &&
          local.gcp_event_resolved_worker_count % length(local.gcp_event_worker_subscriptions) == 0 &&
          local.gcp_event_workers_per_subscription == 21
        )
      )
      error_message = "GCP Large requires exactly 21 StreamingPull workers per local telemetry subscription."
    }
    precondition {
      condition     = contains([86400, 604800], local.gcp_event_retention_seconds)
      error_message = "GCP Event Layer retention differs from the reviewed one- or seven-day allocation."
    }
  }
}

data "google_project" "gcp_event_current" {
  count      = local.gcp_event_enabled ? 1 : 0
  project_id = local.gcp_project_id

  depends_on = [google_project_service.pubsub]
}

resource "google_service_account" "event_runtime" {
  count        = local.gcp_event_enabled ? 1 : 0
  project      = local.gcp_project_id
  account_id   = substr("${local.gcp_event_name}-event-runtime", 0, 30)
  display_name = "${var.digital_twin_name} Six-layer Event Layer"

  depends_on = [google_project_service.iam]
}

resource "google_pubsub_topic" "domain_events" {
  for_each                   = local.gcp_event_enabled ? local.gcp_event_topics : {}
  project                    = local.gcp_project_id
  name                       = each.value
  message_retention_duration = "${local.gcp_event_retention_seconds}s"
  labels                     = local.gcp_event_labels

  message_storage_policy {
    allowed_persistence_regions = [var.gcp_region]
    enforce_in_transit          = true
  }

  depends_on = [
    google_project_service.pubsub,
    terraform_data.gcp_eventing_capacity_guard,
  ]
}

resource "google_cloud_run_v2_service" "event_runtime" {
  count               = local.gcp_event_enabled ? 1 : 0
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = "${local.gcp_event_name}-event-runtime"
  description         = "Authenticated Six-layer Event Layer push and control runtime"
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"
  labels              = local.gcp_event_labels

  template {
    service_account                  = google_service_account.event_runtime[0].email
    timeout                          = "60s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0
      max_instance_count = 100
    }

    containers {
      image = var.gcp_event_runtime_image

      resources {
        limits = {
          cpu    = tostring(var.gcp_event_runtime_cpu)
          memory = "${var.gcp_event_runtime_memory_mib}Mi"
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
        value = "six-layer-eventing@1"
      }
      env {
        name  = "EVENT_TARGETS_JSON"
        value = jsonencode(local.gcp_event_delivery_targets)
      }
      env {
        name  = "EVENT_LOCAL_CONTROL_TYPES_JSON"
        value = jsonencode(local.gcp_event_local_control_event_types)
      }
    }
  }

  lifecycle {
    precondition {
      condition     = var.gcp_event_runtime_image != ""
      error_message = "GCP Event Layer requires its validated content-addressed runtime image."
    }
    precondition {
      condition     = startswith(var.gcp_event_runtime_image, local.gcp_v2_registry_prefix)
      error_message = "GCP Event Layer runtime images must come from the deployment Artifact Registry repository."
    }
  }

  depends_on = [
    google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected,
    google_project_service.run,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "event_pubsub_invoker" {
  count    = local.gcp_event_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = google_cloud_run_v2_service.event_runtime[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.event_runtime[0].email}"
}

resource "google_service_account_iam_member" "event_push_token_creator" {
  count              = local.gcp_event_enabled ? 1 : 0
  service_account_id = google_service_account.event_runtime[0].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.gcp_event_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_cloud_run_v2_service_iam_member" "event_domain_invoker" {
  for_each = local.gcp_event_target_services
  project  = local.gcp_project_id
  location = var.gcp_region
  name     = each.value
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.event_runtime[0].email}"
}

resource "google_pubsub_subscription" "domain_events" {
  for_each = local.gcp_event_enabled ? local.gcp_event_subscriptions : {}
  project  = local.gcp_project_id
  name     = "${local.gcp_event_name}-event-${each.key}"
  topic    = google_pubsub_topic.domain_events[each.value.topic].id

  ack_deadline_seconds       = 60
  message_retention_duration = "${local.gcp_event_retention_seconds}s"
  enable_message_ordering    = true
  retain_acked_messages      = false
  # Control has its own topic, so an additional attribute filter would add no
  # isolation and would exceed Pub/Sub's 256-byte filter limit for all ten
  # reviewed control/projection variants.
  filter = ""
  labels = local.gcp_event_labels

  dynamic "push_config" {
    for_each = contains(keys(local.gcp_event_push_subscriptions), each.key) ? [1] : []
    content {
      push_endpoint = "${google_cloud_run_v2_service.event_runtime[0].uri}/deliver/${each.value.role}"
      oidc_token {
        service_account_email = google_service_account.event_runtime[0].email
        audience              = google_cloud_run_v2_service.event_runtime[0].uri
      }
    }
  }

  retry_policy {
    minimum_backoff = "1s"
    maximum_backoff = "32s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.domain_events["failure"].id
    max_delivery_attempts = var.gcp_event_max_delivery_attempts
  }

  depends_on = [
    google_cloud_run_v2_service_iam_member.event_pubsub_invoker,
    google_service_account_iam_member.event_push_token_creator,
    google_cloud_run_v2_service_iam_member.event_domain_invoker,
  ]
}

resource "google_cloud_run_v2_worker_pool" "event_telemetry" {
  for_each            = local.gcp_event_enabled ? local.gcp_event_worker_subscriptions : {}
  project             = local.gcp_project_id
  location            = var.gcp_region
  name                = substr("${local.gcp_event_name}-event-${each.key}", 0, 49)
  description         = "Fixed Large StreamingPull worker for ${each.value.role}"
  deletion_protection = false
  launch_stage        = "BETA"
  labels              = local.gcp_event_labels

  scaling {
    scaling_mode          = "MANUAL"
    manual_instance_count = local.gcp_event_workers_per_subscription
  }

  template {
    service_account = google_service_account.event_runtime[0].email

    containers {
      image   = var.gcp_event_runtime_image
      command = ["python", "app.py"]

      resources {
        limits = {
          cpu    = tostring(var.gcp_event_worker_cpu)
          memory = "${var.gcp_event_worker_memory_mib}Mi"
        }
      }

      env {
        name  = "EVENT_RUNTIME_MODE"
        value = "worker"
      }
      env {
        name  = "EVENT_CONSUMER_ROLE"
        value = each.value.role
      }
      env {
        name  = "EVENT_SUBSCRIPTION"
        value = google_pubsub_subscription.domain_events[each.key].id
      }
      env {
        name  = "EVENT_TARGETS_JSON"
        value = jsonencode(local.gcp_event_delivery_targets)
      }
      env {
        name  = "EVENT_LOCAL_CONTROL_TYPES_JSON"
        value = jsonencode(local.gcp_event_local_control_event_types)
      }
    }
  }

  depends_on = [google_pubsub_subscription_iam_member.event_runtime_subscriber]
}

resource "google_pubsub_subscription_iam_member" "event_runtime_subscriber" {
  for_each     = local.gcp_event_enabled ? local.gcp_event_worker_subscriptions : {}
  project      = local.gcp_project_id
  subscription = google_pubsub_subscription.domain_events[each.key].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.event_runtime[0].email}"
}

resource "google_pubsub_topic_iam_member" "event_failure_service_agent_publisher" {
  count   = local.gcp_event_enabled ? 1 : 0
  project = local.gcp_project_id
  topic   = google_pubsub_topic.domain_events["failure"].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.gcp_event_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "event_failure_service_agent_subscriber" {
  for_each     = local.gcp_event_enabled ? local.gcp_event_subscriptions : {}
  project      = local.gcp_project_id
  subscription = google_pubsub_subscription.domain_events[each.key].name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.gcp_event_current[0].number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

locals {
  gcp_event_topic_publishers = merge(
    local.gcp_event_l1_local ? {
      ingress-received = {
        topic  = "received"
        member = google_service_account.gcp_v2_runtime["ingress"].email
      }
      ingress-control = {
        topic  = "control"
        member = google_service_account.gcp_v2_runtime["ingress"].email
      }
    } : {},
    local.gcp_event_l2_local ? {
      processor-processed = {
        topic  = "processed"
        member = google_service_account.gcp_v2_runtime["processor"].email
      }
      processor-control = {
        topic  = "control"
        member = google_service_account.gcp_v2_runtime["processor"].email
      }
    } : {},
    local.gcp_event_hot_local ? {
      persistence-control = {
        topic  = "control"
        member = google_service_account.gcp_v2_runtime["persistence"].email
      }
    } : {},
    length(local.gcp_event_local_control_event_types) > 0 ? {
      domain-control = {
        topic  = "control"
        member = google_service_account.gcp_v2_runtime["domain"].email
      }
    } : {},
  )
}

resource "google_pubsub_topic_iam_member" "event_platform_publishers" {
  for_each = local.gcp_event_topic_publishers
  project  = local.gcp_project_id
  topic    = google_pubsub_topic.domain_events[each.value.topic].name
  role     = "roles/pubsub.publisher"
  member   = "serviceAccount:${each.value.member}"
}

resource "google_logging_project_bucket_config" "eventing" {
  count          = local.gcp_event_enabled ? 1 : 0
  project        = local.gcp_project_id
  location       = var.gcp_region
  bucket_id      = "${local.gcp_event_name}-eventing"
  retention_days = var.gcp_event_log_retention_days
  description    = "Bounded Six-layer Event Layer evidence logs"

  depends_on = [google_project_service.gcp_v2_required["logging.googleapis.com"]]
}

resource "google_logging_project_sink" "eventing" {
  count                  = local.gcp_event_enabled ? 1 : 0
  project                = local.gcp_project_id
  name                   = "${local.gcp_event_name}-eventing"
  destination            = "logging.googleapis.com/${google_logging_project_bucket_config.eventing[0].id}"
  unique_writer_identity = true
  # Cloud Run uses a distinct monitored-resource type for worker pools. Keep
  # both the push/control service and the fixed Large telemetry consumers in
  # the bounded Event Layer evidence bucket.
  filter = format(
    "(resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"%s\") OR resource.type=\"cloud_run_workerpool\"",
    "${local.gcp_event_name}-event-runtime",
  )
}

resource "google_project_iam_member" "eventing_sink_writer" {
  count   = local.gcp_event_enabled ? 1 : 0
  project = local.gcp_project_id
  role    = "roles/logging.bucketWriter"
  member  = google_logging_project_sink.eventing[0].writer_identity
}

output "gcp_event_log_bucket" {
  value = local.gcp_event_enabled ? google_logging_project_bucket_config.eventing[0].id : null
}

output "gcp_event_runtime_uri" {
  value = local.gcp_event_enabled ? google_cloud_run_v2_service.event_runtime[0].uri : null
}

output "gcp_event_topic_id" {
  value = local.gcp_event_enabled ? google_pubsub_topic.domain_events["received"].id : null
}

output "gcp_event_worker_pool_id" {
  value = local.gcp_event_enabled ? jsonencode({
    for role, pool in google_cloud_run_v2_worker_pool.event_telemetry : role => pool.id
  }) : null
}
