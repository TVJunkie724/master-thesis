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

# ==============================================================================
# GCP Credentials (from config_credentials.json)
# ==============================================================================

variable "gcp_project_id" {
  description = "GCP Project ID"
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
# Cross-Cloud Configuration
# ==============================================================================

variable "inter_cloud_token" {
  description = "Token for cross-cloud authentication (generated if not provided)"
  type        = string
  default     = ""
  sensitive   = true
}
