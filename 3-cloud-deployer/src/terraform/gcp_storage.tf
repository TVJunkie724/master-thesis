# GCP L3 Storage Layer (Hot/Cold/Archive)
#
# This file creates the L3 layer infrastructure for tiered data storage.
# L3 stores telemetry data with automatic tiering based on age.
#
# Resources Created:
# - Firestore Database (Native): Hot storage for real-time queries
# - Cloud Storage Bucket (Nearline): Cold storage
# - Cloud Storage Bucket (Archive): Archive storage
# - Lifecycle Policies: Automatic cold->archive transitions
# - Cloud Scheduler + Function: Hot-to-cold mover
#
# Storage Tiers:
# - Hot: Firestore (< 30 days by default)
# - Cold: Cloud Storage Nearline (30-90 days by default)
# - Archive: Cloud Storage Archive (> 90 days by default)
#
# Note: Cold->Archive transition uses lifecycle policies (no function needed).

# ==============================================================================
# Firestore Database (Hot Storage)
# ==============================================================================

resource "google_firestore_database" "main" {
  count      = local.gcp_l3_hot_enabled ? 1 : 0
  project    = google_project.main[0].project_id
  name       = "(default)"
  location_id = var.gcp_region
  type       = "FIRESTORE_NATIVE"
  
  depends_on = [google_project_service.firestore]
}

# ==============================================================================
# Cloud Storage Bucket (Cold Storage - Nearline)
# ==============================================================================

resource "google_storage_bucket" "cold" {
  count         = local.gcp_l3_cold_enabled ? 1 : 0
  name          = "${google_project.main[0].project_id}-${var.digital_twin_name}-cold"
  location      = var.gcp_region
  storage_class = "NEARLINE"
  force_destroy = true
  
  uniform_bucket_level_access = true
  
  # Lifecycle: Move to Archive after cold_to_archive_interval_days
  lifecycle_rule {
    condition {
      age = var.layer_3_cold_to_archive_interval_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }
  
  labels = local.gcp_common_labels
  
  depends_on = [google_project_service.storage]
}

# ==============================================================================
# Cloud Storage Bucket (Archive Storage)
# ==============================================================================

resource "google_storage_bucket" "archive" {
  count         = local.gcp_l3_archive_enabled && !local.gcp_l3_cold_enabled ? 1 : 0
  name          = "${google_project.main[0].project_id}-${var.digital_twin_name}-archive"
  location      = var.gcp_region
  storage_class = "ARCHIVE"
  force_destroy = true
  
  uniform_bucket_level_access = true
  
  labels = local.gcp_common_labels
  
  depends_on = [google_project_service.storage]
}

# ==============================================================================
# Hot Reader Function Source
# ==============================================================================

resource "google_storage_bucket_object" "hot_reader_source" {
  count  = local.gcp_l3_hot_enabled ? 1 : 0
  name   = "hot-reader-${filemd5("${var.project_path}/cloud_functions/hot-reader/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/hot-reader.zip"
}

# ==============================================================================
# Hot-to-Cold Mover Function Source
# ==============================================================================

resource "google_storage_bucket_object" "hot_to_cold_mover_source" {
  count  = local.gcp_l3_hot_enabled && local.gcp_l3_cold_enabled ? 1 : 0
  name   = "hot-to-cold-mover-${filemd5("${var.project_path}/cloud_functions/hot-to-cold-mover/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/hot-to-cold-mover.zip"
}

# ==============================================================================
# L3 Hot Reader Cloud Function (Gen2) - HTTP Trigger
# ==============================================================================

resource "google_cloudfunctions2_function" "hot_reader" {
  count    = local.gcp_l3_hot_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-hot-reader"
  location = var.gcp_region
  project  = google_project.main[0].project_id

  build_config {
    runtime     = "python311"
    entry_point = "hot_reader_handler"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.hot_reader_source[0].name
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
    google_firestore_database.main,
    google_project_iam_member.functions_custom_role
  ]
}

# ==============================================================================
# L3 Hot-to-Cold Mover Cloud Function (Gen2) - Scheduled
# ==============================================================================

resource "google_cloudfunctions2_function" "hot_to_cold_mover" {
  count    = local.gcp_l3_hot_enabled && local.gcp_l3_cold_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-hot-to-cold-mover"
  location = var.gcp_region
  project  = google_project.main[0].project_id

  build_config {
    runtime     = "python311"
    entry_point = "mover_handler"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.hot_to_cold_mover_source[0].name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    min_instance_count    = 0
    available_memory      = "512M"
    timeout_seconds       = 540  # 9 minutes for batch processing
    service_account_email = google_service_account.functions[0].email
    
    environment_variables = {
      DIGITAL_TWIN_NAME    = var.digital_twin_name
      GCP_PROJECT_ID       = google_project.main[0].project_id
      FIRESTORE_COLLECTION = "${var.digital_twin_name}-hot-data"
      COLD_BUCKET          = google_storage_bucket.cold[0].name
      HOT_TO_COLD_DAYS     = var.layer_3_hot_to_cold_interval_days
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_firestore_database.main,
    google_storage_bucket.cold,
    google_project_iam_member.functions_custom_role
  ]
}

# ==============================================================================
# Cloud Scheduler for Hot-to-Cold Mover
# ==============================================================================

resource "google_cloud_scheduler_job" "hot_to_cold" {
  count    = local.gcp_l3_hot_enabled && local.gcp_l3_cold_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-hot-to-cold-schedule"
  project  = google_project.main[0].project_id
  region   = var.gcp_region
  schedule = "0 2 * * *"  # Run daily at 2 AM
  
  http_target {
    uri         = google_cloudfunctions2_function.hot_to_cold_mover[0].url
    http_method = "POST"
    
    oidc_token {
      service_account_email = google_service_account.functions[0].email
    }
  }
  
  depends_on = [google_project_service.cloudscheduler]
}

# ==============================================================================
# IAM: Allow authenticated invocations
# ==============================================================================

resource "google_cloud_run_service_iam_member" "hot_reader_invoker" {
  count    = local.gcp_l3_hot_enabled ? 1 : 0
  project  = google_project.main[0].project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.hot_reader[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

resource "google_cloud_run_service_iam_member" "hot_to_cold_mover_invoker" {
  count    = local.gcp_l3_hot_enabled && local.gcp_l3_cold_enabled ? 1 : 0
  project  = google_project.main[0].project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.hot_to_cold_mover[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}
