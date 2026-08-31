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

# Azure preparation provider. Only condition-constrained role assignments use
# this alias; ordinary resources stay on the default deployment provider.
provider "azurerm" {
  alias = "preparation"

  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
    log_analytics_workspace {
      permanently_delete_on_destroy = true
    }
  }

  resource_provider_registrations = "none"
  use_cli                         = false
  use_msi                         = false
  use_oidc                        = false

  subscription_id = var.azure_subscription_id != "" ? var.azure_subscription_id : "00000000-0000-0000-0000-000000000000"
  client_id       = var.azure_preparation_client_id != "" ? var.azure_preparation_client_id : "00000000-0000-0000-0000-000000000000"
  client_secret   = var.azure_preparation_client_secret != "" ? var.azure_preparation_client_secret : "placeholder-secret-not-used"
  tenant_id       = var.azure_tenant_id != "" ? var.azure_tenant_id : "00000000-0000-0000-0000-000000000000"
}

provider "azapi" {
  use_cli  = false
  use_msi  = false
  use_oidc = false

  subscription_id = var.azure_subscription_id != "" ? var.azure_subscription_id : "00000000-0000-0000-0000-000000000000"
  client_id       = var.azure_client_id != "" ? var.azure_client_id : "00000000-0000-0000-0000-000000000000"
  client_secret   = var.azure_client_secret != "" ? var.azure_client_secret : "placeholder-secret-not-used"
  tenant_id       = var.azure_tenant_id != "" ? var.azure_tenant_id : "00000000-0000-0000-0000-000000000000"
}

# Azure AD Provider for the bounded Entra objects required by directed federation.
# It intentionally uses the preparation principal, not the deployment principal.
provider "azuread" {
  # Same fallback auth suppression as azurerm — prevents Azure CLI lookup on
  # deployments that don't use Azure layers.
  use_cli  = false
  use_msi  = false
  use_oidc = false

  client_id     = var.azure_preparation_client_id != "" ? var.azure_preparation_client_id : "00000000-0000-0000-0000-000000000000"
  client_secret = var.azure_preparation_client_secret != "" ? var.azure_preparation_client_secret : "placeholder-secret-not-used"
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
provider "google" {
  project = local.deploy_gcp ? var.gcp_project_id : "placeholder-not-used"
  region  = var.gcp_region != "" ? var.gcp_region : "us-central1"
  # Use dummy credentials when none provided to prevent Application Default Credentials
  # lookup (which fails in containers without gcloud CLI).
  credentials = var.gcp_credentials_json != "" ? var.gcp_credentials_json : "{\"type\":\"service_account\",\"project_id\":\"placeholder\",\"private_key_id\":\"\",\"private_key\":\"\",\"client_email\":\"placeholder@placeholder.iam.gserviceaccount.com\",\"client_id\":\"\",\"auth_uri\":\"https://accounts.google.com/o/oauth2/auth\",\"token_uri\":\"https://oauth2.googleapis.com/token\"}"
}

# Six-layer GKE workloads are applied only after the Google resources in
# stage 1 expose a cluster endpoint and short-lived access token.
provider "kubernetes" {
  host = local.gcp_six_layer_gke_enabled ? (
    "https://${local.gcp_six_layer_gke_endpoint}"
  ) : "https://127.0.0.1"
  token = try(data.google_client_config.gcp_six_layer_kubernetes[0].access_token, "")
  cluster_ca_certificate = try(
    base64decode(local.gcp_six_layer_gke_ca_certificate),
    "",
  )
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

  six_layer_eventing_enabled = (
    var.architecture_profile_id == "six-layer-eventing" &&
    var.architecture_profile_version == "1"
  )

  six_layer_enabled = local.six_layer_eventing_enabled

  # Provider-to-layer mapping for conditional deployments
  deploy_azure = contains([
    var.layer_1_provider,
    var.layer_2_provider,
    var.layer_3_hot_provider,
    var.layer_3_cold_provider,
    var.layer_3_archive_provider,
    var.layer_4_provider,
    var.layer_5_provider,
    var.event_layer_provider
  ], "azure")

  azure_v1_enabled        = false
  azure_six_layer_enabled = local.deploy_azure && local.six_layer_enabled

  deploy_aws = contains([
    var.layer_1_provider,
    var.layer_2_provider,
    var.layer_3_hot_provider,
    var.layer_3_cold_provider,
    var.layer_3_archive_provider,
    var.layer_4_provider,
    var.layer_5_provider,
    var.event_layer_provider
  ], "aws")

  deploy_gcp = contains([
    var.layer_1_provider,
    var.layer_2_provider,
    var.layer_3_hot_provider,
    var.layer_3_cold_provider,
    var.layer_3_archive_provider,
    var.layer_4_provider,
    var.layer_5_provider,
    var.event_layer_provider
  ], "google")

  # Azure region to use for IoT Hub (may differ from main region)
  azure_iothub_region = var.azure_region_iothub != "" ? var.azure_region_iothub : var.azure_region
}

resource "terraform_data" "six_layer_retention_guard" {
  count = local.six_layer_enabled ? 1 : 0

  input = {
    hot_boundary_days     = var.layer_3_hot_to_cold_interval_days
    cool_boundary_days    = var.layer_3_cold_to_archive_interval_days
    archive_boundary_days = var.layer_3_archive_expiry_interval_days
  }

  lifecycle {
    precondition {
      condition = (
        var.layer_3_hot_to_cold_interval_days > 0 &&
        var.layer_3_hot_to_cold_interval_days < var.layer_3_cold_to_archive_interval_days &&
        var.layer_3_cold_to_archive_interval_days < var.layer_3_archive_expiry_interval_days
      )
      error_message = "Six-layer requires cumulative retention boundaries 0 < hot < cool < archive."
    }
    precondition {
      condition = (
        var.platform_user_email != "" &&
        var.platform_user_first_name != "" &&
        var.platform_user_last_name != ""
      )
      error_message = "Six-layer requires the platform user identity used to provision usable L4/L5 access."
    }
    precondition {
      condition = (
        !local.azure_six_layer_enabled ||
        (var.layer_4_provider != "azure" && var.layer_5_provider != "azure") ||
        (
          var.azure_layer_access_principal_object_id != "" &&
          var.azure_layer_access_principal_label != ""
        )
      )
      error_message = "Six-layer Azure L4/L5 requires an existing Entra principal object ID and label; create or choose the principal as a manual cloud prerequisite before deployment."
    }
  }
}

resource "terraform_data" "phase_8_fixed_region_guard" {
  count = local.six_layer_enabled ? 1 : 0

  input = {
    aws_region          = local.deploy_aws ? var.aws_region : null
    azure_region        = local.deploy_azure ? var.azure_region : null
    azure_iothub_region = var.layer_1_provider == "azure" ? local.azure_iothub_region : null
    gcp_region          = local.deploy_gcp ? var.gcp_region : null
  }

  lifecycle {
    precondition {
      condition     = !local.deploy_aws || var.aws_region == "eu-central-1"
      error_message = "Phase 8 comparison profiles fix AWS to eu-central-1."
    }
    precondition {
      condition     = !local.deploy_azure || var.azure_region == "westeurope"
      error_message = "Phase 8 comparison profiles fix Azure to westeurope."
    }
    precondition {
      condition     = var.layer_1_provider != "azure" || local.azure_iothub_region == "westeurope"
      error_message = "Phase 8 comparison profiles fix Azure IoT Hub to westeurope."
    }
    precondition {
      condition     = !local.deploy_gcp || var.gcp_region == "europe-west1"
      error_message = "Phase 8 comparison profiles fix GCP to europe-west1."
    }
  }
}
