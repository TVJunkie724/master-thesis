# Main Terraform Configuration
#
# This is the entry point for the Digital Twin infrastructure deployment.
# Provider configuration and module orchestration happens here.
#
# Usage:
#   1. Generate tfvars.json from project configs
#   2. Run: terraform -chdir=src/terraform init
#   3. Run: terraform -chdir=src/terraform plan -var-file=<project>/generated.tfvars.json
#   4. Run: terraform -chdir=src/terraform apply -var-file=<project>/generated.tfvars.json

# ==============================================================================
# Provider Configuration
# ==============================================================================

# Azure Provider
# Credentials are passed via variables (from config_credentials.json)
provider "azurerm" {
  features {
    # Prevent accidental deletion of resource groups with resources
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }

  # Skip auto-registration of resource providers (requires elevated permissions)
  skip_provider_registration = true

  subscription_id = var.azure_subscription_id
  client_id       = var.azure_client_id
  client_secret   = var.azure_client_secret
  tenant_id       = var.azure_tenant_id
}

# AWS Provider (for multi-cloud deployments)
provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key

  # Skip validation when AWS credentials are not provided (Azure-only deployment)
  skip_credentials_validation = var.aws_access_key_id == "" ? true : false
  skip_requesting_account_id  = var.aws_access_key_id == "" ? true : false
}

# Google Cloud Provider (for multi-cloud deployments)
provider "google" {
  project     = var.gcp_project_id
  region      = var.gcp_region
  credentials = var.gcp_credentials_json != "" ? var.gcp_credentials_json : null
}

# ==============================================================================
# Local Values
# ==============================================================================

locals {
  # Common tags for all resources
  common_tags = {
    ManagedBy   = "terraform"
    DigitalTwin = var.digital_twin_name
    Environment = var.environment
  }

  # Provider-to-layer mapping for conditional deployments
  deploy_azure = contains([
    var.layer_1_provider,
    var.layer_2_provider,
    var.layer_3_hot_provider,
    var.layer_3_cold_provider,
    var.layer_3_archive_provider,
    var.layer_4_provider,
    var.layer_5_provider
  ], "azure")

  deploy_aws = contains([
    var.layer_1_provider,
    var.layer_2_provider,
    var.layer_3_hot_provider,
    var.layer_3_cold_provider,
    var.layer_3_archive_provider,
    var.layer_4_provider,
    var.layer_5_provider
  ], "aws")
  
  # Azure region to use for IoT Hub (may differ from main region)
  azure_iothub_region = var.azure_region_iothub != "" ? var.azure_region_iothub : var.azure_region
}
