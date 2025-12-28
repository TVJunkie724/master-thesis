# AWS Managed Grafana E2E Test
# 
# This is a focused Terraform config to test ONLY:
# - IAM Identity Center (SSO) detection across regions
# - AWS Managed Grafana workspace creation
# - IAM Identity Center user provisioning
#
# Usage:
#   cd tests/e2e/aws_grafana_test
#   terraform init
#   terraform plan -var-file=test.tfvars.json
#   terraform apply -var-file=test.tfvars.json
#   terraform destroy -var-file=test.tfvars.json

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "aws_access_key_id" {
  description = "AWS Access Key ID"
  type        = string
  sensitive   = true
}

variable "aws_secret_access_key" {
  description = "AWS Secret Access Key"
  type        = string
  sensitive   = true
}

variable "aws_region" {
  description = "AWS region for Grafana workspace"
  type        = string
  default     = "eu-central-1"
}

variable "aws_sso_region" {
  description = "AWS region where IAM Identity Center (SSO) is enabled. Leave empty to use aws_region."
  type        = string
  default     = ""
}

variable "grafana_admin_email" {
  description = "Email for the Grafana admin user (created in IAM Identity Center)"
  type        = string
}

variable "grafana_admin_first_name" {
  description = "First name for the Grafana admin user"
  type        = string
  default     = "Grafana"
}

variable "grafana_admin_last_name" {
  description = "Last name for the Grafana admin user"
  type        = string
  default     = "Admin"
}

variable "test_name_suffix" {
  description = "Suffix for resource names (for unique naming)"
  type        = string
  default     = "e2e"
}

# =============================================================================
# Providers
# =============================================================================

# Main AWS provider for Grafana resources
provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
}

# Separate provider for SSO (may be in different region)
provider "aws" {
  alias      = "sso"
  region     = var.aws_sso_region != "" ? var.aws_sso_region : var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
}

# =============================================================================
# IAM Identity Center (SSO) Detection
# =============================================================================

# Get SSO instance from the correct region
data "aws_ssoadmin_instances" "main" {
  provider = aws.sso
}

locals {
  # Check if SSO is available
  sso_available     = length(data.aws_ssoadmin_instances.main.identity_store_ids) > 0
  identity_store_id = local.sso_available ? tolist(data.aws_ssoadmin_instances.main.identity_store_ids)[0] : ""
  instance_arn      = local.sso_available ? tolist(data.aws_ssoadmin_instances.main.arns)[0] : ""
  
  # Unique naming
  name_prefix = "grafana-${var.test_name_suffix}"
}

# =============================================================================
# AWS Managed Grafana
# =============================================================================

# IAM role for Grafana workspace
resource "aws_iam_role" "grafana" {
  name = "${local.name_prefix}-workspace-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "grafana.amazonaws.com"
      }
    }]
  })
  
  tags = {
    Purpose = "grafana-e2e-test"
  }
}

# Minimal policy for Grafana workspace
resource "aws_iam_role_policy" "grafana" {
  name = "${local.name_prefix}-policy"
  role = aws_iam_role.grafana.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["cloudwatch:DescribeAlarmsForMetric", "cloudwatch:ListMetrics"]
      Resource = "*"
    }]
  })
}

# Grafana workspace
resource "aws_grafana_workspace" "test" {
  name                      = local.name_prefix
  account_access_type       = "CURRENT_ACCOUNT"
  authentication_providers  = ["AWS_SSO"]
  permission_type           = "SERVICE_MANAGED"
  role_arn                  = aws_iam_role.grafana.arn
  
  # No data sources needed for this test
  data_sources = []
  
  tags = {
    Purpose = "grafana-e2e-test"
  }
}

# =============================================================================
# IAM Identity Center User
# =============================================================================

# Create admin user in IAM Identity Center
resource "aws_identitystore_user" "grafana_admin" {
  provider = aws.sso
  
  identity_store_id = local.identity_store_id
  display_name      = "${var.grafana_admin_first_name} ${var.grafana_admin_last_name}"
  user_name         = var.grafana_admin_email
  
  name {
    given_name  = var.grafana_admin_first_name
    family_name = var.grafana_admin_last_name
  }
  
  emails {
    value   = var.grafana_admin_email
    primary = true
  }
}

# Assign user as Grafana admin
resource "aws_grafana_role_association" "admin" {
  role         = "ADMIN"
  user_ids     = [aws_identitystore_user.grafana_admin.user_id]
  workspace_id = aws_grafana_workspace.test.id
}

# =============================================================================
# Outputs
# =============================================================================

output "sso_region_used" {
  description = "Region used for SSO queries"
  value       = var.aws_sso_region != "" ? var.aws_sso_region : var.aws_region
}

output "sso_available" {
  description = "Whether IAM Identity Center was detected"
  value       = local.sso_available
}

output "identity_store_id" {
  description = "IAM Identity Center Identity Store ID"
  value       = local.identity_store_id
}

output "grafana_workspace_id" {
  description = "Grafana workspace ID"
  value       = aws_grafana_workspace.test.id
}

output "grafana_endpoint" {
  description = "Grafana workspace URL"
  value       = aws_grafana_workspace.test.endpoint
}

output "grafana_admin_user_id" {
  description = "IAM Identity Center user ID for the admin"
  value       = aws_identitystore_user.grafana_admin.user_id
}

output "test_summary" {
  description = "Summary of the test"
  value = <<-EOT
    ✅ AWS Grafana E2E Test Complete
    
    SSO Region: ${var.aws_sso_region != "" ? var.aws_sso_region : var.aws_region}
    SSO Detected: ${local.sso_available}
    Grafana URL: ${aws_grafana_workspace.test.endpoint}
    Admin Email: ${var.grafana_admin_email}
    
    The Grafana admin user has been created in IAM Identity Center.
    They will receive an email to set up their SSO password.
  EOT
}
