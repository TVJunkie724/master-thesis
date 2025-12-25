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

    # Azure AD provider (for Entra ID user management)
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.47"
    }


    # AWS provider (for multi-cloud deployments)
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.31"
    }

    # AWS Cloud Control provider (for TwinMaker entities/components)
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }

    # Google Cloud provider (for multi-cloud deployments)
    google = {
      source  = "hashicorp/google"
      version = "~> 5.12"
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
  }
}
