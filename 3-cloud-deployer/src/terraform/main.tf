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
    # Permanently delete Log Analytics workspaces instead of soft-delete
    log_analytics_workspace {
      permanently_delete_on_destroy = true
    }
  }

  # Disable auto-registration of resource providers (requires elevated permissions)
  resource_provider_registrations = "none"

  # Disable all fallback auth methods — use only service principal credentials.
  # Without these, Terraform falls back to Azure CLI / MSI / OIDC when any
  # credential variable is empty (e.g. AWS-only or GCP-only deployments).
  use_cli  = false
  use_msi  = false
  use_oidc = false

  # azurerm v4 requires subscription_id/client_id/tenant_id to be non-empty even
  # when the provider is unused. Fall back to a zero-UUID placeholder — the provider
  # initializes but no actual API calls are made unless a resource is created.
  subscription_id = var.azure_subscription_id != "" ? var.azure_subscription_id : "00000000-0000-0000-0000-000000000000"
  client_id       = var.azure_client_id != "" ? var.azure_client_id : "00000000-0000-0000-0000-000000000000"
  client_secret   = var.azure_client_secret != "" ? var.azure_client_secret : "placeholder-secret-not-used"
  tenant_id       = var.azure_tenant_id != "" ? var.azure_tenant_id : "00000000-0000-0000-0000-000000000000"
}

# Azure AD Provider (for Entra ID user management - Grafana admin users)
# Uses same service principal credentials as azurerm
provider "azuread" {
  # Same fallback auth suppression as azurerm — prevents Azure CLI lookup on
  # deployments that don't use Azure layers.
  use_cli  = false
  use_msi  = false
  use_oidc = false

  client_id     = var.azure_client_id != "" ? var.azure_client_id : "00000000-0000-0000-0000-000000000000"
  client_secret = var.azure_client_secret != "" ? var.azure_client_secret : "placeholder-secret-not-used"
  tenant_id     = var.azure_tenant_id != "" ? var.azure_tenant_id : "00000000-0000-0000-0000-000000000000"
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

# AWS Cloud Control Provider (for TwinMaker)
# Only used when layer_4_provider = "aws". Resources have count conditions.
provider "awscc" {
  region     = var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
}

# AWS Provider for IAM Identity Center (SSO)
# SSO is region-specific and may be enabled in a different region than main resources.
# For example, SSO might be in us-east-1 while resources are in eu-central-1.
provider "aws" {
  alias      = "sso"
  region     = var.aws_sso_region != "" ? var.aws_sso_region : var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key

  # Skip validation when AWS credentials are not provided
  skip_credentials_validation = var.aws_access_key_id == "" ? true : false
  skip_requesting_account_id  = var.aws_access_key_id == "" ? true : false
}

# Google Cloud Provider (for multi-cloud deployments)
# Note: Project reference uses var.digital_twin_name directly here since
# locals.gcp_project_name isn't resolved yet during provider configuration
provider "google" {
  project = local.deploy_gcp ? "${var.digital_twin_name}-project" : "placeholder-not-used"
  region  = var.gcp_region != "" ? var.gcp_region : "us-central1"
  # Use dummy credentials when none provided to prevent Application Default Credentials
  # lookup (which fails in containers without gcloud CLI).
  credentials = var.gcp_credentials_json != "" ? var.gcp_credentials_json : "{\"type\":\"service_account\",\"project_id\":\"placeholder\",\"private_key_id\":\"\",\"private_key\":\"\",\"client_email\":\"placeholder@placeholder.iam.gserviceaccount.com\",\"client_id\":\"\",\"auth_uri\":\"https://accounts.google.com/o/oauth2/auth\",\"token_uri\":\"https://oauth2.googleapis.com/token\"}"
}

# ==============================================================================
# Local Values
# ==============================================================================

# ==============================================================================
# Shared Deployment Suffix
# ==============================================================================
# Single random suffix for all resources that need uniqueness on rapid redeploy.
# Replaces separate random_ids for TwinMaker, Firestore, Grafana, IAM roles.

resource "random_id" "deployment_suffix" {
  byte_length = 2
}

locals {
  # Shared deployment suffix - used by resources that need unique names
  deployment_suffix = random_id.deployment_suffix.hex

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

  deploy_gcp = contains([
    var.layer_1_provider,
    var.layer_2_provider,
    var.layer_3_hot_provider,
    var.layer_3_cold_provider,
    var.layer_3_archive_provider
    # TODO(GCP-L4L5): L4/L5 not supported for GCP (no managed services).
    # When GCP L4/L5 is implemented, add var.layer_4_provider and var.layer_5_provider here.
  ], "google")

  # Azure region to use for IoT Hub (may differ from main region)
  azure_iothub_region = var.azure_region_iothub != "" ? var.azure_region_iothub : var.azure_region
}
