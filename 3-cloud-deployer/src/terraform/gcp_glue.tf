# GCP L0 Glue Layer (Cross-Cloud Receiver Functions)
#
# This file creates the L0 Glue layer infrastructure for multi-cloud deployments.
# L0 functions receive data from other clouds and route to local GCP services.
#
# Resources Created (conditional on multi-cloud):
# - Ingestion Function: Receives from remote L1 → routes to local L2
# - Hot Writer: Receives from remote L2 → writes to local L3 Hot (Firestore)
# - Cold Writer: Receives from remote L3 Hot → writes to local L3 Cold
# - Archive Writer: Receives from remote L3 Cold → writes to local L3 Archive
# - Hot Reader: Already in gcp_storage.tf (used by remote L4/L5)
#
# Authentication:
# - Uses X-Inter-Cloud-Token header for cross-cloud authentication

# ==============================================================================
# Ingestion Function Source (receives from remote L1)
# ==============================================================================

resource "google_storage_bucket_object" "ingestion_source" {
  count  = local.gcp_needs_ingestion ? 1 : 0
  name   = "ingestion-${filemd5("${var.project_path}/cloud_functions/ingestion/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/ingestion.zip"
}

# ==============================================================================
# Ingestion Cloud Function (Gen2) - HTTP Trigger
# ==============================================================================

resource "google_cloudfunctions2_function" "ingestion" {
  count    = local.gcp_needs_ingestion ? 1 : 0
  name     = "${var.digital_twin_name}-ingestion"
  location = var.gcp_region
  project  = google_project.main[0].project_id

  build_config {
    runtime     = "python311"
    entry_point = "ingestion_handler"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.ingestion_source[0].name
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
      EVENTS_TOPIC      = local.gcp_l1_enabled ? google_pubsub_topic.events[0].id : ""
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
      )
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run
  ]
}

# ==============================================================================
# Hot Writer Function Source (receives from remote L2)
# ==============================================================================

resource "google_storage_bucket_object" "hot_writer_source" {
  count  = local.gcp_needs_hot_writer ? 1 : 0
  name   = "hot-writer-${filemd5("${var.project_path}/cloud_functions/hot-writer/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/hot-writer.zip"
}

# ==============================================================================
# Hot Writer Cloud Function (Gen2) - HTTP Trigger
# ==============================================================================

resource "google_cloudfunctions2_function" "hot_writer" {
  count    = local.gcp_needs_hot_writer ? 1 : 0
  name     = "${var.digital_twin_name}-hot-writer"
  location = var.gcp_region
  project  = google_project.main[0].project_id

  build_config {
    runtime     = "python311"
    entry_point = "hot_writer_handler"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.hot_writer_source[0].name
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
      DIGITAL_TWIN_NAME    = var.digital_twin_name
      GCP_PROJECT_ID       = google_project.main[0].project_id
      FIRESTORE_COLLECTION = "${var.digital_twin_name}-hot-data"
      INTER_CLOUD_TOKEN    = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
      )
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_firestore_database.main
  ]
}

# ==============================================================================
# Cold Writer Function Source (receives from remote L3 Hot)
# ==============================================================================

resource "google_storage_bucket_object" "cold_writer_source" {
  count  = local.gcp_needs_cold_writer ? 1 : 0
  name   = "cold-writer-${filemd5("${var.project_path}/cloud_functions/cold-writer/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/cold-writer.zip"
}

# ==============================================================================
# Cold Writer Cloud Function (Gen2) - HTTP Trigger
# ==============================================================================

resource "google_cloudfunctions2_function" "cold_writer" {
  count    = local.gcp_needs_cold_writer ? 1 : 0
  name     = "${var.digital_twin_name}-cold-writer"
  location = var.gcp_region
  project  = google_project.main[0].project_id

  build_config {
    runtime     = "python311"
    entry_point = "cold_writer_handler"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.cold_writer_source[0].name
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
      COLD_BUCKET       = local.gcp_l3_cold_enabled ? google_storage_bucket.cold[0].name : ""
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
      )
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_storage_bucket.cold
  ]
}

# ==============================================================================
# Archive Writer Function Source (receives from remote L3 Cold)
# ==============================================================================

resource "google_storage_bucket_object" "archive_writer_source" {
  count  = local.gcp_needs_archive_writer ? 1 : 0
  name   = "archive-writer-${filemd5("${var.project_path}/cloud_functions/archive-writer/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/archive-writer.zip"
}

# ==============================================================================
# Archive Writer Cloud Function (Gen2) - HTTP Trigger
# ==============================================================================

resource "google_cloudfunctions2_function" "archive_writer" {
  count    = local.gcp_needs_archive_writer ? 1 : 0
  name     = "${var.digital_twin_name}-archive-writer"
  location = var.gcp_region
  project  = google_project.main[0].project_id

  build_config {
    runtime     = "python311"
    entry_point = "archive_writer_handler"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.archive_writer_source[0].name
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
      ARCHIVE_BUCKET    = local.gcp_l3_cold_enabled ? google_storage_bucket.cold[0].name : (
        local.gcp_l3_archive_enabled ? google_storage_bucket.archive[0].name : ""
      )
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
      )
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run
  ]
}

# ==============================================================================
# IAM: Allow authenticated invocations for glue functions
# ==============================================================================

resource "google_cloud_run_service_iam_member" "ingestion_invoker" {
  count    = local.gcp_needs_ingestion ? 1 : 0
  project  = google_project.main[0].project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.ingestion[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"  # Allow unauthenticated for cross-cloud (token validation in function)
}

resource "google_cloud_run_service_iam_member" "hot_writer_invoker" {
  count    = local.gcp_needs_hot_writer ? 1 : 0
  project  = google_project.main[0].project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.hot_writer[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "cold_writer_invoker" {
  count    = local.gcp_needs_cold_writer ? 1 : 0
  project  = google_project.main[0].project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.cold_writer[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "archive_writer_invoker" {
  count    = local.gcp_needs_archive_writer ? 1 : 0
  project  = google_project.main[0].project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.archive_writer[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
