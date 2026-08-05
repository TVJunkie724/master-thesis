# Terraform and Provider Versions
#
# This file pins Terraform and provider versions to ensure reproducible deployments.

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    # Azure Resource Manager provider
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }

    # Event Hubs Dedicated exposes cluster creation through azurerm, but its
    # evaluated six-CU capacity is set through the ARM API surface.
    azapi = {
      source  = "Azure/azapi"
      version = "= 2.10.0"
    }

    # Azure AD provider (for Entra ID user management)
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.47"
    }


    # AWS provider (for multi-cloud deployments)
    # NOTE: v5.92+ required for aws_identitystore_users data source
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.92"
    }

    # AWS Cloud Control provider (for TwinMaker entities/components)
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }

    # Google Cloud provider (for multi-cloud deployments)
    google = {
      source  = "hashicorp/google"
      version = ">= 7.22.0, < 8.0.0"
    }

    # GKE workloads are applied in the reviewed post-cluster Terraform stage.
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.38.0, < 3.0.0"
    }

    # Generates the self-signed certificate for the CIDR-scoped GCP Grafana
    # PoC endpoint. The private key remains in Terraform state/Kubernetes.
    tls = {
      source  = "hashicorp/tls"
      version = ">= 4.3.0, < 5.0.0"
    }

    # Archive provider for creating ZIP files
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }

    # Random provider for generating unique identifiers
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }

    # Time provider for delays (e.g., waiting for function sync)
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }

    # Local provider for generated, permission-restricted simulator artifacts.
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}
