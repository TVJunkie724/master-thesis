# Input Variables
#
# These variables are populated from config_credentials.json and config_providers.json
# via the tfvars_generator.py script.

# ==============================================================================
# Core Configuration
# ==============================================================================

variable "digital_twin_name" {
  description = "Name prefix for all resources (from config.json digital_twin_name)"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.digital_twin_name))
    error_message = "digital_twin_name must be lowercase alphanumeric with hyphens, 2-21 chars."
  }
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_path" {
  description = "Absolute path to the project directory (for function code paths)"
  type        = string
}

variable "digital_twin_info_json" {
  description = "JSON string containing full Digital Twin configuration (config, config_iot_devices, config_providers, config_events)"
  type        = string
  default     = "{}"
}

# ==============================================================================
# Layer Provider Mapping (from config_providers.json)
# ==============================================================================


variable "layer_1_provider" {
  description = "Cloud provider for L1 (IoT/Data Acquisition)"
  type        = string
  default     = "azure"

  validation {
    condition     = contains(["aws", "azure", "google"], var.layer_1_provider)
    error_message = "layer_1_provider must be 'aws', 'azure', or 'google'."
  }
}

variable "layer_2_provider" {
  description = "Cloud provider for L2 (Data Processing)"
  type        = string
  default     = "azure"
}

variable "layer_3_hot_provider" {
  description = "Cloud provider for L3 Hot Storage"
  type        = string
  default     = "azure"
}

variable "layer_3_cold_provider" {
  description = "Cloud provider for L3 Cold Storage"
  type        = string
  default     = "azure"
}

variable "layer_3_archive_provider" {
  description = "Cloud provider for L3 Archive Storage"
  type        = string
  default     = "azure"
}

variable "layer_4_provider" {
  description = "Cloud provider for L4 (Digital Twins)"
  type        = string
  default     = "azure"
}

variable "layer_5_provider" {
  description = "Cloud provider for L5 (Visualization)"
  type        = string
  default     = "azure"
}

# ==============================================================================
# Resolved Deployment Specification - AWS
# ==============================================================================

variable "aws_l1_lambda_memory_mb" {
  description = "Specification-selected memory for AWS L1 Lambda functions"
  type        = number
  default     = null

  validation {
    condition     = var.aws_l1_lambda_memory_mb == null || var.aws_l1_lambda_memory_mb == 256
    error_message = "aws_l1_lambda_memory_mb must be 256 when provided."
  }
}

variable "aws_l2_lambda_memory_mb" {
  description = "Specification-selected memory for AWS L2 Lambda functions"
  type        = number
  default     = null

  validation {
    condition     = var.aws_l2_lambda_memory_mb == null || var.aws_l2_lambda_memory_mb == 256
    error_message = "aws_l2_lambda_memory_mb must be 256 when provided."
  }
}

variable "aws_dynamodb_billing_mode" {
  description = "Specification-selected billing mode for AWS L3 hot storage"
  type        = string
  default     = null

  validation {
    condition     = var.aws_dynamodb_billing_mode == null || var.aws_dynamodb_billing_mode == "PAY_PER_REQUEST"
    error_message = "aws_dynamodb_billing_mode must be PAY_PER_REQUEST when provided."
  }
}

variable "aws_l3_reader_lambda_memory_mb" {
  description = "Specification-selected memory for AWS L3 reader Lambda functions"
  type        = number
  default     = null

  validation {
    condition     = var.aws_l3_reader_lambda_memory_mb == null || var.aws_l3_reader_lambda_memory_mb == 256
    error_message = "aws_l3_reader_lambda_memory_mb must be 256 when provided."
  }
}

variable "aws_l3_cool_storage_class" {
  description = "Specification-selected S3 storage class for AWS L3 cool storage"
  type        = string
  default     = null

  validation {
    condition     = var.aws_l3_cool_storage_class == null || var.aws_l3_cool_storage_class == "STANDARD_IA"
    error_message = "aws_l3_cool_storage_class must be STANDARD_IA when provided."
  }
}

variable "aws_hot_to_cool_mover_memory_mb" {
  description = "Specification-selected memory for the AWS hot-to-cool mover"
  type        = number
  default     = null

  validation {
    condition     = var.aws_hot_to_cool_mover_memory_mb == null || var.aws_hot_to_cool_mover_memory_mb == 512
    error_message = "aws_hot_to_cool_mover_memory_mb must be 512 when provided."
  }
}

variable "aws_hot_to_cool_schedule_expression" {
  description = "Specification-selected EventBridge schedule for the AWS hot-to-cool mover"
  type        = string
  default     = null

  validation {
    condition     = var.aws_hot_to_cool_schedule_expression == null || var.aws_hot_to_cool_schedule_expression == "rate(1 day)"
    error_message = "aws_hot_to_cool_schedule_expression must be rate(1 day) when provided."
  }
}

variable "aws_l3_archive_storage_class" {
  description = "Specification-selected S3 storage class for AWS L3 archive storage"
  type        = string
  default     = null

  validation {
    condition     = var.aws_l3_archive_storage_class == null || var.aws_l3_archive_storage_class == "DEEP_ARCHIVE"
    error_message = "aws_l3_archive_storage_class must be DEEP_ARCHIVE when provided."
  }
}

variable "aws_cool_to_archive_mover_memory_mb" {
  description = "Specification-selected memory for the AWS cool-to-archive mover"
  type        = number
  default     = null

  validation {
    condition     = var.aws_cool_to_archive_mover_memory_mb == null || var.aws_cool_to_archive_mover_memory_mb == 512
    error_message = "aws_cool_to_archive_mover_memory_mb must be 512 when provided."
  }
}

variable "aws_cool_to_archive_schedule_expression" {
  description = "Specification-selected EventBridge schedule for the AWS cool-to-archive mover"
  type        = string
  default     = null

  validation {
    condition     = var.aws_cool_to_archive_schedule_expression == null || var.aws_cool_to_archive_schedule_expression == "rate(7 days)"
    error_message = "aws_cool_to_archive_schedule_expression must be rate(7 days) when provided."
  }
}

variable "aws_l4_lambda_memory_mb" {
  description = "Specification-selected memory for the AWS L4 connector Lambda"
  type        = number
  default     = null

  validation {
    condition     = var.aws_l4_lambda_memory_mb == null || var.aws_l4_lambda_memory_mb == 256
    error_message = "aws_l4_lambda_memory_mb must be 256 when provided."
  }
}

variable "aws_glue_lambda_memory_mb" {
  description = "Specification-selected memory for cross-cloud AWS glue Lambdas"
  type        = number
  default     = null

  validation {
    condition     = var.aws_glue_lambda_memory_mb == null || var.aws_glue_lambda_memory_mb == 256
    error_message = "aws_glue_lambda_memory_mb must be 256 when provided."
  }
}

# ==============================================================================
# Resolved Deployment Specification - Azure
# ==============================================================================

variable "azure_iot_hub_sku" {
  description = "Specification-selected Azure IoT Hub SKU"
  type        = string
  default     = null

  validation {
    condition     = var.azure_iot_hub_sku == null || contains(["F1", "S1", "S2", "S3"], var.azure_iot_hub_sku)
    error_message = "azure_iot_hub_sku must be F1, S1, S2, or S3 when provided."
  }
}

variable "azure_iot_hub_capacity" {
  description = "Specification-selected Azure IoT Hub unit capacity"
  type        = number
  default     = null

  validation {
    condition = (
      var.azure_iot_hub_capacity == null ||
      (
        var.azure_iot_hub_capacity >= 1 &&
        var.azure_iot_hub_capacity <= 200 &&
        floor(var.azure_iot_hub_capacity) == var.azure_iot_hub_capacity
      )
    )
    error_message = "azure_iot_hub_capacity must be an integer between 1 and 200 when provided."
  }
}

variable "azure_l1_function_plan_sku" {
  description = "Specification-selected Azure L1 Function plan SKU"
  type        = string
  default     = null

  validation {
    condition     = var.azure_l1_function_plan_sku == null || var.azure_l1_function_plan_sku == "Y1"
    error_message = "azure_l1_function_plan_sku must be Y1 when provided."
  }
}

variable "azure_l2_function_plan_sku" {
  description = "Specification-selected Azure L2 Function plan SKU"
  type        = string
  default     = null

  validation {
    condition     = var.azure_l2_function_plan_sku == null || var.azure_l2_function_plan_sku == "Y1"
    error_message = "azure_l2_function_plan_sku must be Y1 when provided."
  }
}

variable "azure_cosmos_capacity_mode" {
  description = "Specification-selected Azure Cosmos DB capacity mode"
  type        = string
  default     = null

  validation {
    condition     = var.azure_cosmos_capacity_mode == null || var.azure_cosmos_capacity_mode == "serverless"
    error_message = "azure_cosmos_capacity_mode must be serverless when provided."
  }
}

variable "azure_l3_function_plan_sku" {
  description = "Specification-selected shared Azure L3 Function plan SKU"
  type        = string
  default     = null

  validation {
    condition     = var.azure_l3_function_plan_sku == null || var.azure_l3_function_plan_sku == "Y1"
    error_message = "azure_l3_function_plan_sku must be Y1 when provided."
  }
}

variable "azure_storage_account_tier" {
  description = "Specification-selected Azure Blob storage account tier"
  type        = string
  default     = null

  validation {
    condition     = var.azure_storage_account_tier == null || var.azure_storage_account_tier == "Standard"
    error_message = "azure_storage_account_tier must be Standard when provided."
  }
}

variable "azure_storage_replication_type" {
  description = "Specification-selected Azure Blob storage replication type"
  type        = string
  default     = null

  validation {
    condition     = var.azure_storage_replication_type == null || var.azure_storage_replication_type == "LRS"
    error_message = "azure_storage_replication_type must be LRS when provided."
  }
}

variable "azure_l3_cool_blob_tier" {
  description = "Specification-selected Azure L3 cool Blob access tier"
  type        = string
  default     = null

  validation {
    condition     = var.azure_l3_cool_blob_tier == null || var.azure_l3_cool_blob_tier == "Cool"
    error_message = "azure_l3_cool_blob_tier must be Cool when provided."
  }
}

variable "azure_hot_to_cool_timer_schedule" {
  description = "Specification-selected Azure hot-to-cool NCRONTAB schedule"
  type        = string
  default     = null

  validation {
    condition     = var.azure_hot_to_cool_timer_schedule == null || var.azure_hot_to_cool_timer_schedule == "0 0 0 * * *"
    error_message = "azure_hot_to_cool_timer_schedule must be 0 0 0 * * * when provided."
  }
}

variable "azure_l3_archive_blob_tier" {
  description = "Specification-selected Azure L3 archive Blob access tier"
  type        = string
  default     = null

  validation {
    condition     = var.azure_l3_archive_blob_tier == null || var.azure_l3_archive_blob_tier == "Archive"
    error_message = "azure_l3_archive_blob_tier must be Archive when provided."
  }
}

variable "azure_cool_to_archive_timer_schedule" {
  description = "Specification-selected Azure cool-to-archive NCRONTAB schedule"
  type        = string
  default     = null

  validation {
    condition     = var.azure_cool_to_archive_timer_schedule == null || var.azure_cool_to_archive_timer_schedule == "0 0 0 * * 0"
    error_message = "azure_cool_to_archive_timer_schedule must be 0 0 0 * * 0 when provided."
  }
}

variable "azure_l4_function_plan_sku" {
  description = "Specification-selected Azure L4 pusher Function plan SKU"
  type        = string
  default     = null

  validation {
    condition     = var.azure_l4_function_plan_sku == null || var.azure_l4_function_plan_sku == "Y1"
    error_message = "azure_l4_function_plan_sku must be Y1 when provided."
  }
}

variable "azure_grafana_sku" {
  description = "Specification-selected Azure Managed Grafana SKU"
  type        = string
  default     = null

  validation {
    condition     = var.azure_grafana_sku == null || var.azure_grafana_sku == "Standard"
    error_message = "azure_grafana_sku must be Standard when provided."
  }
}

variable "azure_glue_function_plan_sku" {
  description = "Specification-selected Azure cross-cloud receiver Function plan SKU"
  type        = string
  default     = null

  validation {
    condition     = var.azure_glue_function_plan_sku == null || var.azure_glue_function_plan_sku == "Y1"
    error_message = "azure_glue_function_plan_sku must be Y1 when provided."
  }
}

# ==============================================================================
# Resolved Deployment Specification - GCP
# ==============================================================================

variable "gcp_l1_function_memory_mb" {
  description = "Specification-selected memory for GCP L1 Cloud Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l1_function_memory_mb == null || var.gcp_l1_function_memory_mb == 256
    error_message = "gcp_l1_function_memory_mb must be 256 when provided."
  }
}

variable "gcp_l1_function_min_instances" {
  description = "Specification-selected minimum instances for GCP L1 Cloud Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l1_function_min_instances == null || var.gcp_l1_function_min_instances == 0
    error_message = "gcp_l1_function_min_instances must be 0 when provided."
  }
}

variable "gcp_l1_function_max_instances" {
  description = "Specification-selected maximum instances for GCP L1 Cloud Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l1_function_max_instances == null || var.gcp_l1_function_max_instances == 10
    error_message = "gcp_l1_function_max_instances must be 10 when provided."
  }
}

variable "gcp_l2_function_memory_mb" {
  description = "Specification-selected memory for GCP L2 Cloud Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l2_function_memory_mb == null || var.gcp_l2_function_memory_mb == 256
    error_message = "gcp_l2_function_memory_mb must be 256 when provided."
  }
}

variable "gcp_l2_function_min_instances" {
  description = "Specification-selected minimum instances for GCP L2 Cloud Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l2_function_min_instances == null || var.gcp_l2_function_min_instances == 0
    error_message = "gcp_l2_function_min_instances must be 0 when provided."
  }
}

variable "gcp_l2_function_max_instances" {
  description = "Specification-selected maximum instances for GCP L2 Cloud Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l2_function_max_instances == null || var.gcp_l2_function_max_instances == 10
    error_message = "gcp_l2_function_max_instances must be 10 when provided."
  }
}

variable "gcp_firestore_mode" {
  description = "Specification-selected Firestore database mode"
  type        = string
  default     = null

  validation {
    condition     = var.gcp_firestore_mode == null || var.gcp_firestore_mode == "FIRESTORE_NATIVE"
    error_message = "gcp_firestore_mode must be FIRESTORE_NATIVE when provided."
  }
}

variable "gcp_l3_reader_function_memory_mb" {
  description = "Specification-selected memory for the GCP L3 hot reader"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l3_reader_function_memory_mb == null || var.gcp_l3_reader_function_memory_mb == 256
    error_message = "gcp_l3_reader_function_memory_mb must be 256 when provided."
  }
}

variable "gcp_l3_reader_function_min_instances" {
  description = "Specification-selected minimum instances for the GCP L3 hot reader"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l3_reader_function_min_instances == null || var.gcp_l3_reader_function_min_instances == 0
    error_message = "gcp_l3_reader_function_min_instances must be 0 when provided."
  }
}

variable "gcp_l3_reader_function_max_instances" {
  description = "Specification-selected maximum instances for the GCP L3 hot reader"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_l3_reader_function_max_instances == null || var.gcp_l3_reader_function_max_instances == 10
    error_message = "gcp_l3_reader_function_max_instances must be 10 when provided."
  }
}

variable "gcp_l3_cool_storage_class" {
  description = "Specification-selected Cloud Storage class for GCP L3 cool storage"
  type        = string
  default     = null

  validation {
    condition     = var.gcp_l3_cool_storage_class == null || var.gcp_l3_cool_storage_class == "NEARLINE"
    error_message = "gcp_l3_cool_storage_class must be NEARLINE when provided."
  }
}

variable "gcp_hot_to_cool_mover_memory_mb" {
  description = "Specification-selected memory for the GCP hot-to-cool mover"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_hot_to_cool_mover_memory_mb == null || var.gcp_hot_to_cool_mover_memory_mb == 512
    error_message = "gcp_hot_to_cool_mover_memory_mb must be 512 when provided."
  }
}

variable "gcp_hot_to_cool_mover_min_instances" {
  description = "Specification-selected minimum instances for the GCP hot-to-cool mover"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_hot_to_cool_mover_min_instances == null || var.gcp_hot_to_cool_mover_min_instances == 0
    error_message = "gcp_hot_to_cool_mover_min_instances must be 0 when provided."
  }
}

variable "gcp_hot_to_cool_mover_max_instances" {
  description = "Specification-selected maximum instances for the GCP hot-to-cool mover"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_hot_to_cool_mover_max_instances == null || var.gcp_hot_to_cool_mover_max_instances == 1
    error_message = "gcp_hot_to_cool_mover_max_instances must be 1 when provided."
  }
}

variable "gcp_hot_to_cool_scheduler_cron" {
  description = "Specification-selected Cloud Scheduler cron for the GCP hot-to-cool mover"
  type        = string
  default     = null

  validation {
    condition     = var.gcp_hot_to_cool_scheduler_cron == null || var.gcp_hot_to_cool_scheduler_cron == "0 2 * * *"
    error_message = "gcp_hot_to_cool_scheduler_cron must be 0 2 * * * when provided."
  }
}

variable "gcp_l3_archive_storage_class" {
  description = "Specification-selected Cloud Storage class for GCP L3 archive storage"
  type        = string
  default     = null

  validation {
    condition     = var.gcp_l3_archive_storage_class == null || var.gcp_l3_archive_storage_class == "ARCHIVE"
    error_message = "gcp_l3_archive_storage_class must be ARCHIVE when provided."
  }
}

variable "gcp_cool_to_archive_mover_memory_mb" {
  description = "Specification-selected memory for the GCP cool-to-archive mover"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_cool_to_archive_mover_memory_mb == null || var.gcp_cool_to_archive_mover_memory_mb == 512
    error_message = "gcp_cool_to_archive_mover_memory_mb must be 512 when provided."
  }
}

variable "gcp_cool_to_archive_mover_min_instances" {
  description = "Specification-selected minimum instances for the GCP cool-to-archive mover"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_cool_to_archive_mover_min_instances == null || var.gcp_cool_to_archive_mover_min_instances == 0
    error_message = "gcp_cool_to_archive_mover_min_instances must be 0 when provided."
  }
}

variable "gcp_cool_to_archive_mover_max_instances" {
  description = "Specification-selected maximum instances for the GCP cool-to-archive mover"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_cool_to_archive_mover_max_instances == null || var.gcp_cool_to_archive_mover_max_instances == 1
    error_message = "gcp_cool_to_archive_mover_max_instances must be 1 when provided."
  }
}

variable "gcp_cool_to_archive_scheduler_cron" {
  description = "Specification-selected Cloud Scheduler cron for the GCP cool-to-archive mover"
  type        = string
  default     = null

  validation {
    condition     = var.gcp_cool_to_archive_scheduler_cron == null || var.gcp_cool_to_archive_scheduler_cron == "0 3 * * 0"
    error_message = "gcp_cool_to_archive_scheduler_cron must be 0 3 * * 0 when provided."
  }
}

variable "gcp_glue_function_memory_mb" {
  description = "Specification-selected memory for cross-cloud GCP receiver Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_glue_function_memory_mb == null || var.gcp_glue_function_memory_mb == 256
    error_message = "gcp_glue_function_memory_mb must be 256 when provided."
  }
}

variable "gcp_glue_function_min_instances" {
  description = "Specification-selected minimum instances for cross-cloud GCP receiver Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_glue_function_min_instances == null || var.gcp_glue_function_min_instances == 0
    error_message = "gcp_glue_function_min_instances must be 0 when provided."
  }
}

variable "gcp_glue_function_max_instances" {
  description = "Specification-selected maximum instances for cross-cloud GCP receiver Functions"
  type        = number
  default     = null

  validation {
    condition     = var.gcp_glue_function_max_instances == null || var.gcp_glue_function_max_instances == 10
    error_message = "gcp_glue_function_max_instances must be 10 when provided."
  }
}

# ==============================================================================
# Azure Credentials (from config_credentials.json)
# ==============================================================================

variable "azure_subscription_id" {
  description = "Azure Subscription ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_client_id" {
  description = "Azure Service Principal Client ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_client_secret" {
  description = "Azure Service Principal Client Secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_tenant_id" {
  description = "Azure Tenant ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "azure_region" {
  description = "Azure region for resources"
  type        = string
  default     = "westeurope"
}

variable "azure_region_iothub" {
  description = "Azure region for IoT Hub (may differ from main region)"
  type        = string
  default     = ""
}

# ==============================================================================
# AWS Credentials (from config_credentials.json)
# ==============================================================================

variable "aws_access_key_id" {
  description = "AWS Access Key ID"
  type        = string
  default     = ""
  sensitive   = true
}

variable "aws_secret_access_key" {
  description = "AWS Secret Access Key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-central-1"
}

variable "aws_sso_region" {
  description = "AWS region where IAM Identity Center (SSO) is enabled. Defaults to aws_region if not specified. SSO is region-specific and may be in a different region (e.g., us-east-1)."
  type        = string
  default     = ""
}

# ==============================================================================
# Platform User (Required when layer_4_provider=azure OR layer_5_provider=aws/azure)
# ==============================================================================

variable "platform_user_email" {
  description = "Email for platform admin user. Required when L4=Azure (ADT access) or L5=AWS/Azure (Grafana access). For Azure: use format 'user@TENANT.onmicrosoft.com'"
  type        = string
  default     = ""
}

variable "platform_user_first_name" {
  description = "First name for platform user"
  type        = string
  default     = "Platform"
}

variable "platform_user_last_name" {
  description = "Last name for platform user"
  type        = string
  default     = "Admin"
}

# ==============================================================================
# GCP Credentials (from config_credentials.json)
# ==============================================================================

# GCP supports two modes:
# 1. Private Account Mode: Provide gcp_project_id to use an existing project
# 2. Organization Account Mode: Provide gcp_billing_account to auto-create a new project
# At least one of these must be provided. If gcp_project_id is provided, it takes precedence.

variable "gcp_project_id" {
  description = "GCP Project ID for existing project (for private accounts without organization)"
  type        = string
  default     = ""
}

variable "gcp_credentials_json" {
  description = "GCP Service Account credentials JSON (contents, not path)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "gcp_region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-west1"
}

variable "gcp_billing_account" {
  description = "GCP Billing Account ID for project creation (for organization accounts)"
  type        = string
  default     = ""
  sensitive   = true
}

# ==============================================================================
# Storage Configuration (from config.json)
# ==============================================================================

variable "layer_3_hot_to_cold_interval_days" {
  description = "Days before moving data from hot to cold storage"
  type        = number
  default     = 30
}

variable "layer_3_cold_to_archive_interval_days" {
  description = "Days before moving data from cold to archive storage"
  type        = number
  default     = 90
}

# ==============================================================================
# Feature Flags (from config_optimization.json inputParamsUsed)
# ==============================================================================

variable "trigger_notification_workflow" {
  description = "Enable notification workflows (Logic Apps/Step Functions)"
  type        = bool
  default     = false # Disabled by default for testing
}

variable "logic_app_definition_file" {
  description = "Path to the Logic App workflow definition JSON file (set by tfvars_generator.py)"
  type        = string
  default     = "" # Set dynamically based on project path
}

variable "step_function_definition_file" {
  description = "Path to the AWS Step Functions definition JSON file (set by tfvars_generator.py)"
  type        = string
  default     = "" # Set dynamically based on project path
}

variable "gcp_workflow_definition_file" {
  description = "Path to the GCP Workflows definition YAML file (set by tfvars_generator.py)"
  type        = string
  default     = "" # Set dynamically based on project path
}

variable "use_event_checking" {
  description = "Enable event checking and user event actions"
  type        = bool
  default     = true
}

variable "return_feedback_to_device" {
  description = "Enable feedback functions to send responses to IoT devices"
  type        = bool
  default     = false
}

variable "needs_3d_model" {
  description = "Deploy 3D scene assets (GLB + scene config) for visualization"
  type        = bool
  default     = false
}

variable "scene_assets_path" {
  description = "Absolute path to scene_assets directory (set when needs_3d_model=true)"
  type        = string
  default     = ""
}

# ==============================================================================
# IoT Devices (from config_iot_devices.json)
# ==============================================================================

variable "iot_devices" {
  description = "List of IoT devices to register"
  type = list(object({
    id = string
    properties = list(object({
      name      = string
      dataType  = string
      initValue = optional(string)
    }))
  }))
  default = []
}

# ==============================================================================
# Events Configuration (from config_events.json)
# ==============================================================================

variable "events" {
  description = "List of event action definitions"
  type        = any
  default     = []
}

# ==============================================================================
# GCP User Functions (Processors, Event Actions, Event Feedback)
# ==============================================================================

variable "gcp_processors" {
  description = "List of processor configurations for GCP deployment"
  type = list(object({
    name     = string
    zip_path = string
  }))
  default = []
}

variable "gcp_event_actions" {
  description = "List of event action configurations for GCP deployment"
  type = list(object({
    name     = string
    zip_path = string
  }))
  default = []
}

variable "gcp_event_feedback_enabled" {
  description = "Enable event feedback function for GCP"
  type        = bool
  default     = false
}

variable "gcp_event_feedback_zip_path" {
  description = "Path to event feedback ZIP for GCP"
  type        = string
  default     = ""
}

# ==============================================================================
# AWS User Functions (Processors, Event Actions, Event Feedback)
# ==============================================================================

variable "aws_processors" {
  description = "List of processor configurations for AWS deployment"
  type = list(object({
    name     = string
    zip_path = string
  }))
  default = []
}

variable "aws_event_actions" {
  description = "List of event action configurations for AWS deployment"
  type = list(object({
    name     = string
    zip_path = string
  }))
  default = []
}

variable "aws_event_feedback_enabled" {
  description = "Enable event feedback function for AWS"
  type        = bool
  default     = false
}

variable "aws_event_feedback_zip_path" {
  description = "Path to event feedback ZIP for AWS"
  type        = string
  default     = ""
}


# ==============================================================================
# Cross-Cloud Configuration
# ==============================================================================

variable "inter_cloud_token" {
  description = "Token for cross-cloud authentication (generated if not provided)"
  type        = string
  default     = ""
  sensitive   = true
}

# ==============================================================================
# Azure Function ZIP Deployment Paths
# These paths are populated by tfvars_generator.py with pre-built function ZIPs.
# Using zip_deploy_file enables Terraform to deploy function code directly,
# ensuring functions exist before EventGrid subscriptions are created.
# ==============================================================================

variable "azure_l0_zip_path" {
  description = "Path to the L0 glue functions ZIP file"
  type        = string
  default     = ""
}

variable "azure_l1_zip_path" {
  description = "Path to the L1 (Dispatcher) functions ZIP file"
  type        = string
  default     = ""
}

variable "azure_l2_zip_path" {
  description = "Path to the L2 (Processor) functions ZIP file"
  type        = string
  default     = ""
}

variable "azure_l3_zip_path" {
  description = "Path to the L3 (Storage) functions ZIP file"
  type        = string
  default     = ""
}

variable "azure_user_zip_path" {
  description = "Path to user functions ZIP (processors, event_actions, event-feedback)"
  type        = string
  default     = ""
}

# ==============================================================================
# Observability Configuration
# ==============================================================================

variable "enable_aws_logging" {
  description = "Enable CloudWatch logging for AWS resources"
  type        = bool
  default     = true
}

variable "enable_gcp_logging" {
  description = "Enable Cloud Logging for GCP resources (placeholder)"
  type        = bool
  default     = true
}

variable "enable_azure_logging" {
  description = "Enable Log Analytics and App Insights for Azure resources"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Log retention period in days"
  type        = number
  default     = 7
}
