# Terraform and Provider Versions
#
# This file pins Terraform and provider versions to ensure reproducible deployments.

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    # Azure Resource Manager provider
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.85"
    }

    # AWS provider (for multi-cloud deployments)
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.31"
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
  }
}
