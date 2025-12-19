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
  project  = local.gcp_project_id

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
  project  = local.gcp_project_id

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
      GCP_PROJECT_ID         = local.gcp_project_id
      FIRESTORE_COLLECTION   = "${var.digital_twin_name}-hot-data"
      INTER_CLOUD_TOKEN      = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
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
      DIGITAL_TWIN_INFO     = local.digital_twin_info_json
      GCP_PROJECT_ID        = local.gcp_project_id
      INTER_CLOUD_TOKEN     = var.inter_cloud_token != "" ? var.inter_cloud_token : (
        local.deploy_azure ? random_password.inter_cloud_token[0].result : ""
      )
      # Feedback function URL (if enabled)
      FEEDBACK_FUNCTION_URL = var.return_feedback_to_device ? (
        try(google_cloudfunctions2_function.user_functions[0].url, "")
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
# User Functions Source (Event Actions, Processors, Feedback)
# ==============================================================================

resource "google_storage_bucket_object" "user_functions_source" {
  count  = local.gcp_l2_enabled ? 1 : 0
  name   = "user-functions-${filemd5("${var.project_path}/.build/gcp/user-functions.zip")}.zip"
  bucket = google_storage_bucket.function_source[0].name
  source = "${var.project_path}/.build/gcp/user-functions.zip"
}

# ==============================================================================
# User Functions Cloud Function (Event Actions, Processors, Feedback)
# ==============================================================================

resource "google_cloudfunctions2_function" "user_functions" {
  count    = local.gcp_l2_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-user-functions"
  location = var.gcp_region
  project  = local.gcp_project_id

  build_config {
    runtime     = "python311"
    entry_point = "main"
    
    source {
      storage_source {
        bucket = google_storage_bucket.function_source[0].name
        object = google_storage_bucket_object.user_functions_source[0].name
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
      GCP_PROJECT_ID       = local.gcp_project_id
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
    google_project_iam_member.functions_custom_role
  ]
}

# ==============================================================================
# IAM: Allow authenticated invocations of user functions
# ==============================================================================

resource "google_cloud_run_service_iam_member" "user_functions_invoker" {
  count    = local.gcp_l2_enabled ? 1 : 0
  project  = local.gcp_project_id
  location = var.gcp_region
  service  = google_cloudfunctions2_function.user_functions[0].name
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
