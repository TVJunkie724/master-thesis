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

variable "architecture_profile_id" {
  description = "Resolved immutable architecture profile identifier"
  type        = string
  default     = "five-layer-baseline"
}

variable "architecture_profile_version" {
  description = "Resolved immutable architecture profile version"
  type        = string
  default     = "1"

  validation {
    condition     = contains(["1", "2"], var.architecture_profile_version)
    error_message = "architecture_profile_version must be a supported immutable version."
  }
}

variable "event_layer_provider" {
  description = "Cloud provider for the independent Six-layer Eventing responsibility"
  type        = string
  default     = ""

  validation {
    condition     = contains(["", "aws", "azure", "google"], var.event_layer_provider)
    error_message = "event_layer_provider must be empty, 'aws', 'azure', or 'google'."
  }
}

variable "digital_twin_info_json" {
  description = "JSON string containing full Digital Twin configuration (config, config_iot_devices, config_providers, config_events)"
  type        = string
  default     = "{}"
}

variable "resolved_component_dimensions" {
  description = "Validated component capacity and usage dimensions projected from the resolved graph"
  type        = map(string)
  default     = {}
}

# ==============================================================================
# Six-layer Eventing: AWS bundle inputs
# ==============================================================================

variable "aws_event_kinesis_shards" {
  description = "Optimizer-derived shards per Event Layer telemetry stream"
  type        = number
  default     = null

  validation {
    condition     = var.aws_event_kinesis_shards == null ? true : contains([1, 6, 200], var.aws_event_kinesis_shards)
    error_message = "aws_event_kinesis_shards must match the reviewed Small, Medium, or Large allocation."
  }
}

variable "aws_event_retention_hours" {
  description = "Optional reviewed Kinesis retention override; null derives it from the selected shard allocation"
  type        = number
  default     = null

  validation {
    condition     = var.aws_event_retention_hours == null ? true : contains([24, 168], var.aws_event_retention_hours)
    error_message = "aws_event_retention_hours must be 24 or 168."
  }
}

variable "aws_event_control_archive_hours" {
  description = "SNS FIFO control replay window"
  type        = number
  default     = 168

  validation {
    condition     = contains([24, 168], var.aws_event_control_archive_hours)
    error_message = "aws_event_control_archive_hours must be 24 or 168."
  }
}

variable "aws_event_max_receive_count" {
  description = "SQS receive count at which control delivery writes the safe terminal record"
  type        = number
  default     = 6

  validation {
    condition     = var.aws_event_max_receive_count == 6
    error_message = "aws_event_max_receive_count is frozen to the reviewed PoC value 6."
  }
}

variable "aws_event_dlq_retention_hours" {
  description = "Retention of terminal Event Layer failures in S3"
  type        = number
  default     = 168

  validation {
    condition     = contains([24, 168], var.aws_event_dlq_retention_hours)
    error_message = "aws_event_dlq_retention_hours must be 24 or 168."
  }
}

variable "aws_event_runtime_memory_mib" {
  description = "Memory allocation of the AWS Event Layer delivery adapter"
  type        = number
  default     = 256

  validation {
    condition     = var.aws_event_runtime_memory_mib == 256
    error_message = "aws_event_runtime_memory_mib is frozen to the reviewed PoC value 256."
  }
}

variable "aws_event_runtime_batch_max" {
  description = "Maximum Event Layer delivery batch"
  type        = number
  default     = 10

  validation {
    condition     = var.aws_event_runtime_batch_max == 10
    error_message = "aws_event_runtime_batch_max is frozen to the reviewed PoC value 10."
  }
}

variable "aws_event_log_retention_days" {
  description = "CloudWatch log retention for the independent Event Layer"
  type        = number
  default     = 30

  validation {
    condition     = var.aws_event_log_retention_days == 30
    error_message = "aws_event_log_retention_days is frozen to the reviewed PoC value 30."
  }
}

# ==============================================================================
# Six-layer Eventing: Azure bundle inputs
# ==============================================================================

variable "azure_event_hubs_dedicated_capacity_units" {
  description = "Optimizer-derived Event Hubs Dedicated capacity units"
  type        = number
  default     = 0

  validation {
    condition     = contains([0, 6], var.azure_event_hubs_dedicated_capacity_units)
    error_message = "azure_event_hubs_dedicated_capacity_units must be 0 or the reviewed Large allocation 6."
  }
}

variable "azure_event_hubs_throughput_units" {
  description = "Optimizer-derived Event Hubs Standard throughput units"
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 11], var.azure_event_hubs_throughput_units)
    error_message = "azure_event_hubs_throughput_units must match the reviewed Small or Medium allocation."
  }
}

variable "azure_event_partitions" {
  description = "Partitions per Event Layer telemetry hub"
  type        = number
  default     = 4

  validation {
    condition     = contains([4, 16, 200], var.azure_event_partitions)
    error_message = "azure_event_partitions must match the reviewed Small, Medium, or Large allocation."
  }
}

variable "azure_event_retention_hours" {
  description = "Event Hubs and Service Bus replay window"
  type        = number
  default     = 24

  validation {
    condition     = contains([24, 168], var.azure_event_retention_hours)
    error_message = "azure_event_retention_hours must be 24 or 168."
  }
}

variable "azure_event_max_delivery_count" {
  description = "Service Bus delivery count before native dead-lettering"
  type        = number
  default     = 6

  validation {
    condition     = var.azure_event_max_delivery_count == 6
    error_message = "azure_event_max_delivery_count is frozen to the reviewed PoC value 6."
  }
}

variable "azure_event_runtime_memory_mib" {
  description = "Memory allocation of the Azure Event Layer Function app"
  type        = number
  default     = 2048

  validation {
    condition     = var.azure_event_runtime_memory_mib == 2048
    error_message = "azure_event_runtime_memory_mib is frozen to the reviewed PoC value 2048."
  }
}

variable "azure_event_runtime_batch_max" {
  description = "Maximum Event Layer delivery batch"
  type        = number
  default     = 10

  validation {
    condition     = var.azure_event_runtime_batch_max == 10
    error_message = "azure_event_runtime_batch_max is frozen to the reviewed PoC value 10."
  }
}

variable "azure_event_log_retention_days" {
  description = "Log Analytics retention for the independent Event Layer"
  type        = number
  default     = 30

  validation {
    condition     = var.azure_event_log_retention_days == 30
    error_message = "azure_event_log_retention_days is frozen to the reviewed PoC value 30."
  }
}

variable "gcp_event_retention_seconds" {
  description = "Reviewed Pub/Sub topic and subscription retention for the independent GCP Event Layer"
  type        = number
  default     = 86400

  validation {
    condition     = contains([86400, 604800], var.gcp_event_retention_seconds)
    error_message = "gcp_event_retention_seconds must be the reviewed one- or seven-day value."
  }
}

variable "gcp_event_max_delivery_attempts" {
  description = "Approximate Pub/Sub attempts before native dead-letter forwarding"
  type        = number
  default     = 6

  validation {
    condition     = var.gcp_event_max_delivery_attempts == 6
    error_message = "gcp_event_max_delivery_attempts is frozen to the reviewed six-attempt budget."
  }
}

variable "gcp_event_runtime_cpu" {
  description = "Cloud Run event service vCPU allocation"
  type        = number
  default     = 1

  validation {
    condition     = var.gcp_event_runtime_cpu == 1
    error_message = "gcp_event_runtime_cpu is frozen to one vCPU for the thesis PoC."
  }
}

variable "gcp_event_runtime_memory_mib" {
  description = "Cloud Run event service memory in MiB"
  type        = number
  default     = 512

  validation {
    condition     = var.gcp_event_runtime_memory_mib == 512
    error_message = "gcp_event_runtime_memory_mib is frozen to 512 MiB for the thesis PoC."
  }
}

variable "gcp_event_worker_count" {
  description = "Total optimizer-derived Large telemetry StreamingPull worker instances"
  type        = number
  default     = 0

  validation {
    condition = (
      var.gcp_event_worker_count == 0 ||
      (
        var.gcp_event_worker_count <= 126 &&
        var.gcp_event_worker_count % 21 == 0
      )
    )
    error_message = "gcp_event_worker_count must be zero or a reviewed 21-instance-per-subscription Large allocation up to 126."
  }
}

variable "gcp_event_worker_cpu" {
  description = "Cloud Run event worker vCPU allocation"
  type        = number
  default     = 1

  validation {
    condition     = var.gcp_event_worker_cpu == 1
    error_message = "gcp_event_worker_cpu is frozen to one vCPU for the thesis PoC."
  }
}

variable "gcp_event_worker_memory_mib" {
  description = "Cloud Run event worker memory in MiB"
  type        = number
  default     = 512

  validation {
    condition     = var.gcp_event_worker_memory_mib == 512
    error_message = "gcp_event_worker_memory_mib is frozen to 512 MiB for the thesis PoC."
  }
}

variable "gcp_event_log_retention_days" {
  description = "Dedicated Cloud Logging bucket retention for Event Layer evidence"
  type        = number
  default     = 30

  validation {
    condition     = var.gcp_event_log_retention_days == 30
    error_message = "gcp_event_log_retention_days is frozen to 30 days for the thesis PoC."
  }
}

variable "gcp_event_runtime_image" {
  description = "Content-addressed GCP Six-layer Event Layer runtime image"
  type        = string
  default     = ""

  validation {
    condition = (
      var.gcp_event_runtime_image == "" ||
      can(regex("^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$", var.gcp_event_runtime_image))
    )
    error_message = "gcp_event_runtime_image must be an Artifact Registry image pinned by sha256 digest."
  }
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

variable "aws_v2_storage_mover_image" {
  description = "Content-addressed AWS Five-layer v2 finite storage-mover image"
  type        = string
  default     = ""

  validation {
    condition = (
      var.aws_v2_storage_mover_image == "" ||
      can(regex("^[0-9]+\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$", var.aws_v2_storage_mover_image))
    )
    error_message = "aws_v2_storage_mover_image must be an ECR image pinned by sha256 digest."
  }
}

variable "aws_v2_bridge_image" {
  description = "Content-addressed AWS Five-layer v2 outbound event-bridge Lambda image"
  type        = string
  default     = ""

  validation {
    condition = (
      var.aws_v2_bridge_image == "" ||
      can(regex("^[0-9]+\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$", var.aws_v2_bridge_image))
    )
    error_message = "aws_v2_bridge_image must be an ECR image pinned by sha256 digest."
  }
}

variable "azure_v2_storage_mover_image" {
  description = "Content-addressed Azure Five-layer v2 finite storage-mover image"
  type        = string
  default     = ""

  validation {
    condition = (
      var.azure_v2_storage_mover_image == "" ||
      can(regex("^[a-z0-9]+\\.azurecr\\.io/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$", var.azure_v2_storage_mover_image))
    )
    error_message = "azure_v2_storage_mover_image must be an ACR image pinned by sha256 digest."
  }
}

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
    condition     = var.azure_iot_hub_sku == null ? true : contains(["F1", "S1", "S2", "S3"], var.azure_iot_hub_sku)
    error_message = "azure_iot_hub_sku must be F1, S1, S2, or S3 when provided."
  }
}

variable "azure_iot_hub_capacity" {
  description = "Specification-selected Azure IoT Hub unit capacity"
  type        = number
  default     = null

  validation {
    condition = var.azure_iot_hub_capacity == null ? true : (
      var.azure_iot_hub_capacity >= 1 &&
      var.azure_iot_hub_capacity <= 200 &&
      floor(var.azure_iot_hub_capacity) == var.azure_iot_hub_capacity
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

variable "aws_layer_access_principal_intent" {
  description = "Five-layer v2 AWS browser principal behavior: resolve an existing Identity Center user, or explicitly invite one in the built-in directory"
  type        = string
  default     = "existing"

  validation {
    condition     = contains(["existing", "invite_builtin"], var.aws_layer_access_principal_intent)
    error_message = "aws_layer_access_principal_intent must be existing or invite_builtin."
  }
}

variable "azure_layer_access_principal_object_id" {
  description = "Existing Entra principal object ID receiving Five-layer v2 ADT Reader and Grafana Viewer access; the platform never creates this principal"
  type        = string
  default     = ""

  validation {
    condition = (
      var.azure_layer_access_principal_object_id == "" ||
      can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.azure_layer_access_principal_object_id))
    )
    error_message = "azure_layer_access_principal_object_id must be an Entra object ID UUID when provided."
  }
}

variable "azure_layer_access_principal_label" {
  description = "Non-secret label or UPN shown with the existing Entra layer-access principal"
  type        = string
  default     = ""
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

variable "gcp_v2_platform_image" {
  description = "Content-addressed GCP Five-layer v2 platform runtime image"
  type        = string
  default     = ""

  validation {
    condition = (
      var.gcp_v2_platform_image == "" ||
      can(regex("^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$", var.gcp_v2_platform_image))
    )
    error_message = "gcp_v2_platform_image must be an Artifact Registry image pinned by sha256 digest."
  }
}

variable "gcp_v2_processor_extension_image" {
  description = "Content-addressed GCP processor.telemetry@1 adapter image"
  type        = string
  default     = ""

  validation {
    condition = (
      var.gcp_v2_processor_extension_image == "" ||
      can(regex("^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$", var.gcp_v2_processor_extension_image))
    )
    error_message = "gcp_v2_processor_extension_image must be an Artifact Registry image pinned by sha256 digest."
  }
}

variable "gcp_v2_storage_mover_image" {
  description = "Content-addressed GCP Five-layer v2 finite storage-mover image"
  type        = string
  default     = ""

  validation {
    condition = (
      var.gcp_v2_storage_mover_image == "" ||
      can(regex("^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$", var.gcp_v2_storage_mover_image))
    )
    error_message = "gcp_v2_storage_mover_image must be an Artifact Registry image pinned by sha256 digest."
  }
}

variable "gcp_v2_grafana_image" {
  description = "Content-addressed GCP Five-layer v2 Grafana image with the reviewed signed Infinity plugin"
  type        = string
  default     = ""

  validation {
    condition = (
      var.gcp_v2_grafana_image == "" ||
      can(regex("^[a-z0-9.-]+/[a-z0-9_./-]+@sha256:[0-9a-f]{64}$", var.gcp_v2_grafana_image))
    )
    error_message = "gcp_v2_grafana_image must be an Artifact Registry image pinned by sha256 digest."
  }
}

variable "gcp_v2_kubernetes_stage_enabled" {
  description = "Activate the automatic post-cluster Kubernetes apply stage for Five-layer v2"
  type        = bool
  default     = true
}

variable "gcp_grafana_source_cidrs" {
  description = "Non-empty researcher CIDR allowlist for the GCP Grafana TLS LoadBalancer"
  type        = list(string)
  default     = []

  validation {
    condition = alltrue([
      for cidr in var.gcp_grafana_source_cidrs :
      can(cidrhost(cidr, 0)) && !contains(["0.0.0.0/0", "::/0"], cidr)
    ])
    error_message = "gcp_grafana_source_cidrs must contain valid bounded CIDRs and must not contain a wildcard route."
  }
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

variable "layer_3_archive_expiry_interval_days" {
  description = "Cumulative age in days after which archived data expires"
  type        = number
  default     = 360
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

variable "aws_outbound_identity_required" {
  description = "Whether the resolved graph contains an AWS-to-Azure workload-identity route"
  type        = bool
  default     = false
}

variable "aws_outbound_identity_destinations" {
  description = "Remote providers that trust the account-scoped AWS outbound identity issuer"
  type        = list(string)
  default     = []
}

variable "aws_outbound_identity_issuer" {
  description = "Non-secret AWS outbound identity issuer discovered during preplan"
  type        = string
  default     = ""

  validation {
    condition     = var.aws_outbound_identity_issuer == "" || startswith(var.aws_outbound_identity_issuer, "https://")
    error_message = "The AWS outbound identity issuer must be empty or use HTTPS."
  }
}

variable "resolved_cross_cloud_routes" {
  description = "Non-secret directed edge contracts compiled from the immutable deployment graph"
  type = list(object({
    route_id                = string
    logical_edge_id         = string
    source_provider         = string
    destination_provider    = string
    execution_kind          = string
    channel_class           = string
    event_types             = list(string)
    source_broker_kind      = string
    destination_broker_kind = string
    identity_exchange       = string
    payload_contract_id     = string
    trust_contract_id       = string
  }))
  default = []

  validation {
    condition = alltrue([
      for route in var.resolved_cross_cloud_routes :
      contains(["aws", "azure", "gcp"], route.source_provider) &&
      contains(["aws", "azure", "gcp"], route.destination_provider) &&
      route.source_provider != route.destination_provider &&
      contains(["source_event_forwarder", "finite_storage_job"], route.execution_kind) &&
      contains(["telemetry", "control", "storage"], route.channel_class) &&
      contains(["telemetry_stream", "control_topic", "object_storage"], route.source_broker_kind) &&
      route.source_broker_kind == route.destination_broker_kind &&
      (
        (route.execution_kind == "finite_storage_job" && route.channel_class == "storage" && length(route.event_types) == 0 && route.source_broker_kind == "object_storage") ||
        (route.execution_kind == "source_event_forwarder" && route.channel_class != "storage" && length(route.event_types) > 0 && route.source_broker_kind != "object_storage")
      ) &&
      route.identity_exchange != "" &&
      route.payload_contract_id != "" &&
      route.trust_contract_id == "trust.workload-identity-federation"
    ])
    error_message = "Every resolved cross-cloud route must use a closed provider pair, execution kind, payload, and workload-identity trust."
  }
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

variable "azure_v2_zip_path" {
  description = "Content-addressed Five-layer v2 Azure Function App package"
  type        = string
  default     = ""
}

variable "azure_event_zip_path" {
  description = "Content-addressed Six-layer Azure Event Layer Function package"
  type        = string
  default     = ""
}

# ==============================================================================
# Validated User-Function Extension Packages
# Phase 8.3 provider catalogs bind these reviewed packages to executable slots.
# This prerequisite records and verifies immutable package references only.
# ==============================================================================

variable "validated_extension_packages" {
  description = "Contract-validated immutable extension package evidence"
  type = list(object({
    slot_id         = string
    slot_version    = string
    artifact_id     = string
    artifact_digest = string
    package_path    = string
    package_digest  = string
    adapter_id      = string
    adapter_version = string
  }))
  default = []
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
