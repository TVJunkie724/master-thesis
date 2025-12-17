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
  project = var.gcp_project_id
  name    = "${var.digital_twin_name}-telemetry"
  
  labels = local.gcp_common_labels
  
  depends_on = [google_project_service.pubsub]
}

# ==============================================================================
# Pub/Sub Topic for Events (Event Processing)
# ==============================================================================

resource "google_pubsub_topic" "events" {
  count   = local.gcp_l1_enabled ? 1 : 0
  project = var.gcp_project_id
  name    = "${var.digital_twin_name}-events"
  
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
  name     = "${var.digital_twin_name}-dispatcher"
  location = var.gcp_region
  project  = var.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "dispatcher_handler"
    
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
      EVENTS_TOPIC      = google_pubsub_topic.events[0].id
      # L2_PROCESSOR_URL set by orchestrator after L2 deployment
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
      )
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
  project  = var.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.dispatcher[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# IoT Simulator Configuration (Local File)
# ==============================================================================
#
# Unlike Azure IoT Hub and AWS IoT Core, GCP uses Pub/Sub for IoT messaging.
# There's no device registry to manage, so we can generate the simulator
# configuration directly via Terraform's local_file resource.
#
# Note: Azure and AWS simulator configs are generated by SDK because they
# require device connection strings that are only available AFTER registering
# the device in IoT Hub/IoT Core respectively.

resource "local_file" "gcp_simulator_config" {
  for_each = local.gcp_l1_enabled ? { for device in var.iot_devices : device.id => device } : {}
  
  filename = "${var.project_path}/iot_device_simulator/gcp/config_generated_${each.key}.json"
  
  content = jsonencode({
    project_id              = var.gcp_project_id
    topic_name              = "dt/${var.digital_twin_name}/telemetry"
    device_id               = each.key
    digital_twin_name       = var.digital_twin_name
    payload_path            = "../payloads.json"
    auth_method             = "service_account"
    service_account_key_path = "service_account.json"
  })
  
  file_permission = "0644"
}
