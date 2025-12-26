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
# Persister Function Source
# ==============================================================================

resource "google_storage_bucket_object" "persister_source" {
  count  = local.gcp_l2_enabled ? 1 : 0
  name   = "persister-${filemd5("${var.project_path}/cloud_functions/persister/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/persister.zip"
}

# ==============================================================================
# L2 Persister Cloud Function (Gen2) - HTTP Trigger
# ==============================================================================

resource "google_cloudfunctions2_function" "persister" {
  count    = local.gcp_l2_enabled && local.gcp_l3_hot_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-persister"
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "main"
    
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
      DIGITAL_TWIN_INFO      = var.digital_twin_info_json
      GCP_PROJECT_ID         = local.gcp_project_id
      FIRESTORE_COLLECTION   = "${var.digital_twin_name}-hot-data"
      FIRESTORE_DATABASE     = var.digital_twin_name
      INTER_CLOUD_TOKEN      = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        try(random_password.inter_cloud_token[0].result, "")
      )

      # Multi-cloud L2→L3: When GCP L2 sends to remote L3
      REMOTE_WRITER_URL = var.layer_2_provider == "google" && var.layer_3_hot_provider != "google" ? (
        var.layer_3_hot_provider == "aws" ? try(aws_lambda_function_url.l0_hot_writer[0].function_url, "") :
        var.layer_3_hot_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/api/hot-writer" : ""
      ) : ""
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
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.persister[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# L1 Connector Function Source (Multi-Cloud Only)
# ==============================================================================

resource "google_storage_bucket_object" "connector_source" {
  count  = local.gcp_l1_enabled && var.layer_2_provider != "google" ? 1 : 0
  name   = "connector-${filemd5("${var.project_path}/cloud_functions/connector/main.py")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/connector.zip"
}

# ==============================================================================
# L1 Connector Cloud Function (Gen2) - Multi-Cloud Only
# ==============================================================================

resource "google_cloudfunctions2_function" "connector" {
  count    = local.gcp_l1_enabled && var.layer_2_provider != "google" ? 1 : 0
  name     = "${var.digital_twin_name}-connector"
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "main"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.connector_source[0].name
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
      DIGITAL_TWIN_INFO = var.digital_twin_info_json
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        try(random_password.inter_cloud_token[0].result, "")
      )
      # Multi-cloud L1→L2: Remote ingestion endpoint
      REMOTE_INGESTION_URL = var.layer_2_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/api/ingestion" : (
        var.layer_2_provider == "aws" ? try(aws_lambda_function_url.l0_ingestion[0].function_url, "") : ""
      )
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_iam_member.functions_custom_role,
    # Cross-cloud L2 targets (ensure they exist before connector deployment)
    azurerm_linux_function_app.l0_glue,
    aws_lambda_function_url.l0_ingestion
  ]
}

# ==============================================================================
# IAM: Allow authenticated invocations of connector
# ==============================================================================

resource "google_cloud_run_service_iam_member" "connector_invoker" {
  count    = local.gcp_l1_enabled && var.layer_2_provider != "google" ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.connector[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# Event Checker Function Source (Optional)
# ==============================================================================

resource "google_storage_bucket_object" "event_checker_source" {
  count  = local.gcp_l2_enabled && var.use_event_checking ? 1 : 0
  name   = "event-checker-${filemd5("${var.project_path}/.build/gcp/event-checker.zip")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/event-checker.zip"
}

# ==============================================================================
# L2 Event Checker Cloud Function (Optional)
# ==============================================================================

resource "google_cloudfunctions2_function" "event_checker" {
  count    = local.gcp_l2_enabled && var.use_event_checking ? 1 : 0
  name     = "${var.digital_twin_name}-event-checker"
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "main"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.event_checker_source[0].name
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
      DIGITAL_TWIN_NAME     = var.digital_twin_name
      DIGITAL_TWIN_INFO     = var.digital_twin_info_json
      GCP_PROJECT_ID        = local.gcp_project_id
      INTER_CLOUD_TOKEN     = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        try(random_password.inter_cloud_token[0].result, "")
      )
      # Feedback function URL (if enabled)
      FEEDBACK_FUNCTION_URL = var.return_feedback_to_device ? (
        try(google_cloudfunctions2_function.processor[0].url, "")
      ) : ""
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_iam_member.functions_custom_role
  ]
}

# ==============================================================================
# Cloud Workflows API (Required for Event Workflows)
# ==============================================================================

resource "google_project_service" "workflows" {
  count   = local.gcp_l2_enabled && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
  project = local.gcp_project_id
  service = "workflows.googleapis.com"
  
  disable_on_destroy = false
}

# ==============================================================================
# Cloud Workflow for Event Processing (Optional)
# ==============================================================================

resource "google_workflows_workflow" "event_workflow" {
  count    = local.gcp_l2_enabled && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
  name     = "${var.digital_twin_name}-event-workflow"
  region   = var.gcp_region
  project  = local.gcp_project_id
  
  service_account = google_service_account.functions[0].email
  
  source_contents = <<-EOT
    main:
      params: [args]
      steps:
        - log_event:
            call: sys.log
            args:
              text: ${"Event received for ${var.digital_twin_name}"}
        - process_event:
            call: http.post
            args:
              url: ${google_cloudfunctions2_function.event_checker[0].url}
              body: $${args}
              auth:
                type: OIDC
            result: process_result
        - return_result:
            return: $${process_result}
  EOT

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.workflows
  ]
}


# ==============================================================================
# GCP Processor Wrapper Cloud Function (Routes to user processors)
# ==============================================================================

resource "google_storage_bucket_object" "processor_wrapper_source" {
  count  = local.gcp_l2_enabled ? 1 : 0
  
  name   = "processor-wrapper-${filemd5("${var.project_path}/.build/gcp/processor_wrapper.zip")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/processor_wrapper.zip"
}

resource "google_cloudfunctions2_function" "processor_wrapper" {
  count    = local.gcp_l2_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-processor"
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "main"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.processor_wrapper_source[0].name
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
      DIGITAL_TWIN_INFO      = var.digital_twin_info_json
      GCP_PROJECT_ID         = local.gcp_project_id
      FUNCTION_BASE_URL      = "https://${var.gcp_region}-${local.gcp_project_id}.cloudfunctions.net"
      PERSISTER_FUNCTION_URL = local.gcp_l3_hot_enabled ? google_cloudfunctions2_function.persister[0].url : ""
      INTER_CLOUD_TOKEN      = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        try(random_password.inter_cloud_token[0].result, "")
      )
    }
  }

  labels = local.gcp_common_labels
}

# ==============================================================================
# GCP Processor Cloud Functions (Individual per processor)
# ==============================================================================

resource "google_storage_bucket_object" "processor_source" {
  for_each = { for p in var.gcp_processors : p.name => p }
  
  name   = "processor-${each.value.name}-${filemd5(each.value.zip_path)}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = each.value.zip_path
}

resource "google_cloudfunctions2_function" "processor" {
  for_each = { for p in var.gcp_processors : p.name => p }
  
  name     = "${var.digital_twin_name}-${each.value.name}-processor"
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "main"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.processor_source[each.key].name
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
      DIGITAL_TWIN_INFO      = var.digital_twin_info_json
      GCP_PROJECT_ID         = local.gcp_project_id
      FIRESTORE_COLLECTION   = "${var.digital_twin_name}-hot-data"
      FIRESTORE_DATABASE     = var.digital_twin_name
      PERSISTER_FUNCTION_URL = local.gcp_l3_hot_enabled ? google_cloudfunctions2_function.persister[0].url : ""
      INTER_CLOUD_TOKEN      = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        try(random_password.inter_cloud_token[0].result, "")
      )
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_iam_member.functions_custom_role
  ]
}

resource "google_cloud_run_service_iam_member" "processor_invoker" {
  for_each = { for p in var.gcp_processors : p.name => p }
  
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.processor[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# GCP Event Action Cloud Functions (Individual per event action)
# ==============================================================================

resource "google_storage_bucket_object" "event_action_source" {
  for_each = { for a in var.gcp_event_actions : a.name => a }
  
  name   = "event-action-${each.value.name}-${filemd5(each.value.zip_path)}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = each.value.zip_path
}

resource "google_cloudfunctions2_function" "event_action" {
  for_each = { for a in var.gcp_event_actions : a.name => a }
  
  name     = "${var.digital_twin_name}-event-action-${each.value.name}"
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "main"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.event_action_source[each.key].name
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
      DIGITAL_TWIN_INFO      = var.digital_twin_info_json
      GCP_PROJECT_ID         = local.gcp_project_id
      FIRESTORE_COLLECTION   = "${var.digital_twin_name}-hot-data"
      FIRESTORE_DATABASE     = var.digital_twin_name
      INTER_CLOUD_TOKEN      = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        try(random_password.inter_cloud_token[0].result, "")
      )
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_iam_member.functions_custom_role
  ]
}

resource "google_cloud_run_service_iam_member" "event_action_invoker" {
  for_each = { for a in var.gcp_event_actions : a.name => a }
  
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.event_action[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# GCP Event Feedback Cloud Function
# ==============================================================================

resource "google_storage_bucket_object" "event_feedback_source" {
  count  = var.gcp_event_feedback_enabled ? 1 : 0
  
  name   = "event-feedback-${filemd5(var.gcp_event_feedback_zip_path)}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = var.gcp_event_feedback_zip_path
}

resource "google_cloudfunctions2_function" "event_feedback" {
  count    = var.gcp_event_feedback_enabled ? 1 : 0
  
  name     = "${var.digital_twin_name}-event-feedback"
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "main"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.event_feedback_source[0].name
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
      DIGITAL_TWIN_INFO      = var.digital_twin_info_json
      GCP_PROJECT_ID         = local.gcp_project_id
      FIRESTORE_COLLECTION   = "${var.digital_twin_name}-hot-data"
      FIRESTORE_DATABASE     = var.digital_twin_name
      INTER_CLOUD_TOKEN      = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        try(random_password.inter_cloud_token[0].result, "")
      )
      
      # IoT Core vars - required for event_feedback_wrapper to send commands to devices
      GCP_IOT_REGION              = var.gcp_region
      GCP_IOT_REGISTRY_ID         = "${var.digital_twin_name}-registry"
      EVENT_FEEDBACK_FUNCTION_URL = "https://${var.gcp_region}-${local.gcp_project_id}.cloudfunctions.net/${var.digital_twin_name}-event-feedback"
    }
  }

  labels = local.gcp_common_labels

  depends_on = [
    google_project_service.cloudfunctions,
    google_project_service.run,
    google_project_iam_member.functions_custom_role
  ]
}

resource "google_cloud_run_service_iam_member" "event_feedback_invoker" {
  count    = var.gcp_event_feedback_enabled ? 1 : 0
  
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.event_feedback[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# IAM: Allow authenticated invocations of event checker
# ==============================================================================

resource "google_cloud_run_service_iam_member" "event_checker_invoker" {
  count    = local.gcp_l2_enabled && var.use_event_checking ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.event_checker[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.functions[0].email}"
}
