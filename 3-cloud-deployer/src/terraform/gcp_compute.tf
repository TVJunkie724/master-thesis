# GCP L2 Compute Layer (Data Processing)
#
# This file creates the L2 layer infrastructure for data processing.
# L2 receives telemetry from L1 and persists to L3 storage.
#
# Resources Created:
# - Cloud Function Gen2 (Processor): Processes device telemetry
# - Cloud Function Gen2 (Persister): Writes to L3 Hot storage (Firestore)
# - Cloud Function Gen2 (Event Checker): Validates events
#
# Architecture:
#     L1 Dispatcher → Events Topic → Processor → Persister → L3 Firestore

# ==============================================================================
# Processor Function Source
# ==============================================================================

resource "google_storage_bucket_object" "processor_source" {
  count  = local.gcp_l2_enabled ? 1 : 0
  name   = "processor-${filemd5("${var.project_path}/cloud_functions/processor_wrapper/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/processor.zip"
}

# ==============================================================================
# Persister Function Source
# ==============================================================================

resource "google_storage_bucket_object" "persister_source" {
  count  = local.gcp_l2_enabled ? 1 : 0
  name   = "persister-${filemd5("${var.project_path}/cloud_functions/persister/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/persister.zip"
}

# ==============================================================================
# L2 Processor Cloud Function (Gen2)
# ==============================================================================

resource "google_cloudfunctions2_function" "processor" {
  count    = local.gcp_l2_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-processor"
  location = var.gcp_region
  project  = var.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "processor_handler"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.processor_source[0].name
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
      PERSISTER_URL     = local.gcp_l2_enabled && local.gcp_l3_hot_enabled ? google_cloudfunctions2_function.persister[0].url : ""
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
      )
    }
  }

  event_trigger {
    trigger_region = var.gcp_region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = google_pubsub_topic.events[0].id
    retry_policy   = "RETRY_POLICY_DO_NOT_RETRY"
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_service.eventarc,
    google_project_iam_member.functions_custom_role
  ]
}

# ==============================================================================
# L2 Persister Cloud Function (Gen2) - HTTP Trigger
# ==============================================================================

resource "google_cloudfunctions2_function" "persister" {
  count    = local.gcp_l2_enabled && local.gcp_l3_hot_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-persister"
  location = var.gcp_region
  project  = var.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "persister_handler"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.persister_source[0].name
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
      DIGITAL_TWIN_NAME      = var.digital_twin_name
      GCP_PROJECT_ID         = var.gcp_project_id
      FIRESTORE_COLLECTION   = "${var.digital_twin_name}-hot-data"
      INTER_CLOUD_TOKEN      = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
      )
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_service.firestore,
    google_project_iam_member.functions_custom_role
  ]
}

# ==============================================================================
# IAM: Allow authenticated invocations of persister
# ==============================================================================

resource "google_cloud_run_service_iam_member" "persister_invoker" {
  count    = local.gcp_l2_enabled && local.gcp_l3_hot_enabled ? 1 : 0
  project  = var.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.persister[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}
