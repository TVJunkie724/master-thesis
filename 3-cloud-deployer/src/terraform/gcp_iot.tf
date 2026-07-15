# GCP L1 IoT Layer (Data Acquisition)
#
# This file creates the L1 layer infrastructure for IoT data acquisition via Pub/Sub.
# L1 receives telemetry from IoT devices (via HTTP/gRPC) and dispatches to L2 processing.
#
# Resources Created:
# - Pub/Sub Topic: Telemetry ingestion point (devices publish here)
# - Pub/Sub Subscription: Push subscription triggers dispatcher
# - Cloud Function Gen2 (Dispatcher): Routes telemetry to L2
#
# Architecture:
#     IoT Devices → HTTP/gRPC → Pub/Sub Topic → Eventarc → Dispatcher Function → L2
#
# Note: Unlike AWS IoT Core or Azure IoT Hub, GCP Pub/Sub doesn't have native MQTT.
# Devices should use HTTP REST or gRPC to publish messages.

# ==============================================================================
# Pub/Sub Topic for Telemetry
# ==============================================================================

resource "google_pubsub_topic" "telemetry" {
  count   = local.gcp_l1_enabled ? 1 : 0
  project = local.gcp_project_id
  name    = local.gcp_l1_telemetry_topic

  labels = local.gcp_common_labels

  depends_on = [google_project_service.pubsub]
}

# ==============================================================================
# Pub/Sub Topic for Events (Event Processing)
# ==============================================================================

resource "google_pubsub_topic" "events" {
  count   = local.gcp_l1_enabled ? 1 : 0
  project = local.gcp_project_id
  name    = local.gcp_l1_events_topic

  labels = local.gcp_common_labels

  depends_on = [google_project_service.pubsub]
}

# ==============================================================================
# Cloud Function Storage (for dispatcher source)
# ==============================================================================

resource "google_storage_bucket_object" "dispatcher_source" {
  count  = local.gcp_l1_enabled ? 1 : 0
  name   = "dispatcher-${filemd5("${var.project_path}/cloud_functions/dispatcher/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/dispatcher.zip"

  depends_on = [google_storage_bucket.function_source]
}

# ==============================================================================
# L1 Dispatcher Cloud Function (Gen2)
# ==============================================================================

resource "google_cloudfunctions2_function" "dispatcher" {
  count    = local.gcp_l1_enabled ? 1 : 0
  name     = local.gcp_l1_dispatcher_name
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = local.python_runtime_gcp
    entry_point = "main"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.dispatcher_source[0].name
      }
    }
  }

  service_config {
    max_instance_count    = 10
    min_instance_count    = 0
    available_memory      = "256M"
    timeout_seconds       = 60
    service_account_email = google_service_account.functions[0].email

    environment_variables = {
      DIGITAL_TWIN_NAME = var.digital_twin_name
      DIGITAL_TWIN_INFO = var.digital_twin_info_json
      EVENTS_TOPIC      = google_pubsub_topic.events[0].id
      FUNCTION_BASE_URL = local.gcp_function_base_url
      INTER_CLOUD_TOKEN = local.inter_cloud_token_value
      # Multi-cloud L1→L2: Route to connector when L2 is on a different cloud
      TARGET_FUNCTION_SUFFIX = local.target_function_suffix
    }
  }

  event_trigger {
    trigger_region = var.gcp_region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.telemetry[0].id
    retry_policy   = "RETRY_POLICY_DO_NOT_RETRY"
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_service.eventarc,
    google_project_service.cloudbuild,
    google_project_iam_member.functions_custom_role
  ]
}

# ==============================================================================
# IAM: Allow Pub/Sub to invoke the dispatcher function
# ==============================================================================

resource "google_cloud_run_service_iam_member" "dispatcher_invoker" {
  count    = local.gcp_l1_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.dispatcher[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# IoT Simulator Runtime Identity and Configuration
# ==============================================================================
#
# GCP uses Pub/Sub for IoT messaging. A dedicated service account is created for
# the downloadable simulator and can publish only to this twin's telemetry topic.
# The deployment/bootstrap service-account key is never copied into a package.
#
# Note: Azure and AWS simulator configs are generated by SDK because they
# require device connection strings that are only available AFTER registering
# the device in IoT Hub/IoT Core respectively.
#
resource "google_service_account" "simulator" {
  count        = local.gcp_l1_enabled ? 1 : 0
  project      = local.gcp_project_id
  account_id   = local.gcp_l1_simulator_sa_id
  display_name = "${var.digital_twin_name} simulator publisher"
  description  = "Least-privilege standalone simulator identity for ${var.digital_twin_name}"
}

resource "google_pubsub_topic_iam_member" "simulator_publisher" {
  count   = local.gcp_l1_enabled ? 1 : 0
  project = local.gcp_project_id
  topic   = google_pubsub_topic.telemetry[0].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.simulator[0].email}"
}

resource "google_service_account_key" "simulator" {
  count              = local.gcp_l1_enabled ? 1 : 0
  service_account_id = google_service_account.simulator[0].name
  public_key_type    = "TYPE_X509_PEM_FILE"
}

resource "local_sensitive_file" "gcp_simulator_key" {
  count = local.gcp_l1_enabled ? 1 : 0

  filename        = "${var.project_path}/iot_device_simulator/google/_runtime/service_account.json"
  content         = base64decode(google_service_account_key.simulator[0].private_key)
  file_permission = "0600"
}

resource "local_file" "gcp_simulator_config" {
  for_each = local.gcp_l1_enabled ? {
    for d in var.iot_devices : d.id => d
  } : {}

  filename = "${var.project_path}/iot_device_simulator/google/${each.key}/config_generated.json"

  content = jsonencode({
    project_id                      = local.gcp_project_id
    topic_name                      = local.gcp_l1_telemetry_topic
    device_id                       = each.key
    digital_twin_name               = var.digital_twin_name
    payload_path                    = "../../payloads.json"
    auth_method                     = "service_account"
    service_account_key_path        = "../../_runtime/service_account.json"
    simulator_service_account_email = google_service_account.simulator[0].email
    credential_class                = "gcp_pubsub_topic_publisher"
    credential_contract_version     = 1
  })

  file_permission = "0644"

  depends_on = [
    google_pubsub_topic_iam_member.simulator_publisher,
    local_sensitive_file.gcp_simulator_key,
  ]
}
