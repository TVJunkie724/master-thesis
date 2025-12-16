# AWS Setup Layer
#
# This file creates the foundation infrastructure for AWS deployments.
# The Setup Layer is deployed FIRST and provides resource organization.
#
# Resources Created:
# - Resource Group: Tag-based grouping for all twin resources
#
# Note: Unlike Azure Resource Groups, AWS Resource Groups are query-based
# and do not contain resources - they provide a logical grouping view.

# ==============================================================================
# Locals for AWS
# ==============================================================================

locals {
  aws_common_tags = {
    DigitalTwin = var.digital_twin_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
  
  # Determine if any layer uses AWS
  aws_enabled = (
    var.layer_1_provider == "aws" ||
    var.layer_2_provider == "aws" ||
    var.layer_3_hot_provider == "aws" ||
    var.layer_3_cold_provider == "aws" ||
    var.layer_3_archive_provider == "aws" ||
    var.layer_4_provider == "aws" ||
    var.layer_5_provider == "aws"
  )
}

# ==============================================================================
# AWS Resource Group (Tag-based Query)
# ==============================================================================

resource "aws_resourcegroups_group" "main" {
  count = local.aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-rg"

  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]
      TagFilters = [
        {
          Key    = "DigitalTwin"
          Values = [var.digital_twin_name]
        }
      ]
    })
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# Data Sources
# ==============================================================================

# Get current AWS account ID and region
data "aws_caller_identity" "current" {
  count = local.aws_enabled ? 1 : 0
}

data "aws_region" "current" {
  count = local.aws_enabled ? 1 : 0
}
