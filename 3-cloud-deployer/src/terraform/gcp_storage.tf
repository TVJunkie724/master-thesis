# GCP L3 Storage Layer (Hot/Cold/Archive)
#
# This file creates the L3 layer infrastructure for tiered data storage.
# L3 stores telemetry data with automatic tiering based on age.
#
# Resources Created:
# - Firestore Database (Native): Hot storage for real-time queries
# - Cloud Storage Bucket (Nearline): Cold storage
# - Cloud Storage Bucket (Archive): Archive storage
# - Cloud Scheduler + Function: Source-owned storage transitions
#
# Storage Tiers:
# - Hot: Firestore (< 30 days by default)
# - Cold: Cloud Storage Nearline (30-90 days by default)
# - Archive: Cloud Storage Archive (> 90 days by default)
#
# Each transition is owned by exactly one scheduled source-side mover.

# ==============================================================================
# Firestore Database (Hot Storage)
# ==============================================================================

resource "google_firestore_database" "main" {
  count   = local.gcp_l3_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  # Use unique database ID per digital twin with shared deployment suffix
  # Note: Database IDs must be 1-63 chars, lowercase letters, numbers, hyphens
  name        = local.gcp_l3_firestore_database
  location_id = var.gcp_region
  type        = var.gcp_firestore_mode

  # Allow deletion without protection
  deletion_policy = "DELETE"

  depends_on = [google_project_service.firestore]
}

# ==============================================================================
# Firestore Composite Index (Required for hot-reader queries)
# ==============================================================================
# Standard index for time-series IoT queries: filter by device, sort by time
# Same pattern as DynamoDB (partition key + sort key) and Cosmos DB (partition key)

resource "google_firestore_index" "hot_data_device_id" {
  count      = local.gcp_l3_hot_enabled ? 1 : 0
  project    = local.gcp_project_id
  database   = google_firestore_database.main[0].name
  collection = local.gcp_l3_firestore_collection

  fields {
    field_path = "device_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "timestamp"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.main]
}

# ==============================================================================
# Cloud Storage Bucket (Cold Storage - Nearline)
# ==============================================================================

resource "google_storage_bucket" "cold" {
  count         = local.gcp_l3_cold_enabled ? 1 : 0
  project       = local.gcp_project_id
  name          = local.gcp_l3_cold_bucket
  location      = var.gcp_region
  storage_class = var.gcp_l3_cool_storage_class
  force_destroy = true

  uniform_bucket_level_access = true

  # Disable soft-delete to allow immediate bucket name reuse
  soft_delete_policy {
    retention_duration_seconds = 0
  }

  labels = local.gcp_common_labels

  depends_on = [google_project_service.storage]
}

# ==============================================================================
# Cloud Storage Bucket (Archive Storage)
# ==============================================================================

resource "google_storage_bucket" "archive" {
  count         = local.gcp_l3_archive_enabled ? 1 : 0
  project       = local.gcp_project_id
  name          = local.gcp_l3_archive_bucket
  location      = var.gcp_region
  storage_class = var.gcp_l3_archive_storage_class
  force_destroy = true

  uniform_bucket_level_access = true

  # Disable soft-delete to allow immediate bucket name reuse
  soft_delete_policy {
    retention_duration_seconds = 0
  }

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
  count  = local.gcp_l3_hot_enabled ? 1 : 0
  name   = "hot-to-cold-mover-${filemd5("${var.project_path}/cloud_functions/hot-to-cold-mover/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/hot-to-cold-mover.zip"
}

# ==============================================================================
# L3 Hot Reader Cloud Function (Gen2) - HTTP Trigger
# ==============================================================================

resource "google_cloudfunctions2_function" "hot_reader" {
  count    = local.gcp_l3_hot_enabled ? 1 : 0
  name     = local.gcp_l3_hot_reader_name
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = local.python_runtime_gcp
    entry_point = "main"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.hot_reader_source[0].name
      }
    }
  }

  service_config {
    max_instance_count    = var.gcp_l3_reader_function_max_instances
    min_instance_count    = var.gcp_l3_reader_function_min_instances
    available_memory      = "${var.gcp_l3_reader_function_memory_mb}M"
    timeout_seconds       = 60
    service_account_email = google_service_account.functions[0].email

    environment_variables = {
      DIGITAL_TWIN_NAME    = var.digital_twin_name
      DIGITAL_TWIN_INFO    = var.digital_twin_info_json
      GCP_PROJECT_ID       = local.gcp_project_id
      FIRESTORE_COLLECTION = local.gcp_l3_firestore_collection
      FIRESTORE_DATABASE   = local.gcp_firestore_database_name
      INTER_CLOUD_TOKEN    = local.inter_cloud_token_value
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
  count    = local.gcp_l3_hot_enabled ? 1 : 0
  name     = local.gcp_l3_hot_to_cold_mover
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = local.python_runtime_gcp
    entry_point = "main"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.hot_to_cold_mover_source[0].name
      }
    }
  }

  service_config {
    max_instance_count    = var.gcp_hot_to_cool_mover_max_instances
    min_instance_count    = var.gcp_hot_to_cool_mover_min_instances
    available_memory      = "${var.gcp_hot_to_cool_mover_memory_mb}M"
    timeout_seconds       = 540 # 9 minutes for batch processing
    service_account_email = google_service_account.functions[0].email

    environment_variables = {
      DIGITAL_TWIN_NAME    = var.digital_twin_name
      DIGITAL_TWIN_INFO    = var.digital_twin_info_json
      GCP_PROJECT_ID       = local.gcp_project_id
      FIRESTORE_COLLECTION = local.gcp_l3_firestore_collection
      FIRESTORE_DATABASE   = local.gcp_firestore_database_name
      COLD_BUCKET_NAME     = try(google_storage_bucket.cold[0].name, "")
      COLD_STORAGE_CLASS   = local.gcp_l3_cold_enabled ? var.gcp_l3_cool_storage_class : ""
      HOT_RETENTION_DAYS   = var.layer_3_hot_to_cold_interval_days

      # Multi-cloud Hot→Cold: When GCP L3 Hot sends to remote Cold
      REMOTE_COLD_WRITER_URL = var.layer_3_hot_provider == "google" && var.layer_3_cold_provider != "google" ? (
        var.layer_3_cold_provider == "aws" ? try(aws_lambda_function_url.l0_cold_writer[0].function_url, "") :
        var.layer_3_cold_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/${local.api_paths.cold_writer}" : ""
      ) : ""

      # Inter-cloud token
      INTER_CLOUD_TOKEN = local.inter_cloud_token_value
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
# Cloud Scheduler for Hot-to-Cold Mover
# ==============================================================================

resource "google_cloud_scheduler_job" "hot_to_cold" {
  count    = local.gcp_l3_hot_enabled ? 1 : 0
  name     = local.gcp_l3_hot_to_cold_schedule
  project  = local.gcp_project_id
  region   = var.gcp_region
  schedule = var.gcp_hot_to_cool_scheduler_cron

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
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.hot_reader[0].name
  role     = "roles/run.invoker"
  member   = "allUsers" # Publicly accessible, protected by inter-cloud-token in application logic
}

resource "google_cloud_run_service_iam_member" "hot_to_cold_mover_invoker" {
  count    = local.gcp_l3_hot_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.hot_to_cold_mover[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# Cold-to-Archive Mover Function Source
# ==============================================================================

resource "google_storage_bucket_object" "cold_to_archive_mover_source" {
  count  = local.gcp_l3_cold_enabled ? 1 : 0
  name   = "cold-to-archive-mover-${filemd5("${var.project_path}/cloud_functions/cold-to-archive-mover/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/cold-to-archive-mover.zip"
}

# ==============================================================================
# L3 Cold-to-Archive Mover Cloud Function (Gen2) - Scheduled
# ==============================================================================

resource "google_cloudfunctions2_function" "cold_to_archive_mover" {
  count    = local.gcp_l3_cold_enabled ? 1 : 0
  name     = local.gcp_l3_cold_to_archive_mover
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = local.python_runtime_gcp
    entry_point = "main"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.cold_to_archive_mover_source[0].name
      }
    }
  }

  service_config {
    max_instance_count    = var.gcp_cool_to_archive_mover_max_instances
    min_instance_count    = var.gcp_cool_to_archive_mover_min_instances
    available_memory      = "${var.gcp_cool_to_archive_mover_memory_mb}M"
    timeout_seconds       = 540 # 9 minutes for batch processing
    service_account_email = google_service_account.functions[0].email

    environment_variables = {
      DIGITAL_TWIN_NAME     = var.digital_twin_name
      DIGITAL_TWIN_INFO     = var.digital_twin_info_json
      GCP_PROJECT_ID        = local.gcp_project_id
      COLD_BUCKET_NAME      = google_storage_bucket.cold[0].name
      ARCHIVE_BUCKET_NAME   = local.gcp_l3_archive_enabled ? google_storage_bucket.archive[0].name : ""
      ARCHIVE_STORAGE_CLASS = local.gcp_l3_archive_enabled ? var.gcp_l3_archive_storage_class : ""
      COLD_RETENTION_DAYS   = var.layer_3_cold_to_archive_interval_days

      # Multi-cloud Cold→Archive: When GCP L3 Cold sends to remote Archive
      REMOTE_ARCHIVE_WRITER_URL = var.layer_3_cold_provider == "google" && var.layer_3_archive_provider != "google" ? (
        var.layer_3_archive_provider == "aws" ? try(aws_lambda_function_url.l0_archive_writer[0].function_url, "") :
        var.layer_3_archive_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/${local.api_paths.archive_writer}" : ""
      ) : ""

      # Inter-cloud token
      INTER_CLOUD_TOKEN = local.inter_cloud_token_value
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_storage_bucket.cold,
    google_storage_bucket.archive,
    google_project_iam_member.functions_custom_role
  ]
}

# ==============================================================================
# Cloud Scheduler for Cold-to-Archive Mover
# ==============================================================================

resource "google_cloud_scheduler_job" "cold_to_archive" {
  count    = local.gcp_l3_cold_enabled ? 1 : 0
  name     = local.gcp_l3_cold_to_archive_schedule
  project  = local.gcp_project_id
  region   = var.gcp_region
  schedule = var.gcp_cool_to_archive_scheduler_cron

  http_target {
    uri         = google_cloudfunctions2_function.cold_to_archive_mover[0].url
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

resource "google_cloud_run_service_iam_member" "cold_to_archive_mover_invoker" {
  count    = local.gcp_l3_cold_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.cold_to_archive_mover[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}
