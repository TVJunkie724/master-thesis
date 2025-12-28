# AWS L5 Visualization Layer (Grafana)
#
# This file creates the L5 layer infrastructure for data visualization.
# L5 provides dashboards for monitoring Digital Twin data.
#
# Resources Created (via Terraform):
# - Amazon Managed Grafana Workspace
# - IAM Role: Grafana service role
# - API Key: For SDK to configure datasources
#
# Resources Created (via SDK post-deployment):
# - Datasources: JSON API connection to Hot Reader
# - Dashboards: Visualization panels
#
# Note: Grafana datasources and dashboards are configured via Grafana API
# using the API key created by Terraform.

# ==============================================================================
# L5 Locals
# ==============================================================================

locals {
  l5_aws_enabled = var.layer_5_provider == "aws"
}

# ==============================================================================
# IAM Role for Managed Grafana
# ==============================================================================

resource "aws_iam_role" "l5_grafana" {
  count = local.l5_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l5-grafana-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "grafana.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current[0].account_id
          }
        }
      }
    ]
  })

  tags = local.aws_common_tags
}

# CloudWatch access for Grafana (optional datasource)
resource "aws_iam_role_policy_attachment" "l5_grafana_cloudwatch" {
  count      = local.l5_aws_enabled ? 1 : 0
  role       = aws_iam_role.l5_grafana[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonGrafanaCloudWatchAccess"
}

# ==============================================================================
# Amazon Managed Grafana Workspace
# ==============================================================================

resource "aws_grafana_workspace" "main" {
  count                     = local.l5_aws_enabled ? 1 : 0
  name                      = "${var.digital_twin_name}-grafana"
  description               = "Grafana workspace for ${var.digital_twin_name} Digital Twin"
  account_access_type       = "CURRENT_ACCOUNT"
  authentication_providers  = ["AWS_SSO"]
  permission_type           = "SERVICE_MANAGED"
  role_arn                  = aws_iam_role.l5_grafana[0].arn
  grafana_version           = "10.4"

  # Enable required data sources
  data_sources = ["CLOUDWATCH", "PROMETHEUS"]

  tags = local.aws_common_tags
}

# ==============================================================================
# Grafana API Key (for SDK to configure datasources)
# ==============================================================================

resource "aws_grafana_workspace_api_key" "admin" {
  count           = local.l5_aws_enabled ? 1 : 0
  key_name        = "${var.digital_twin_name}-admin-key"
  key_role        = "ADMIN"
  seconds_to_live = 2592000  # 30 days
  workspace_id    = aws_grafana_workspace.main[0].id
}

# ==============================================================================
# IAM Identity Center User Management
# ==============================================================================

# Get IAM Identity Center instance
# Uses the SSO provider alias to query from the correct region (may differ from main region)
data "aws_ssoadmin_instances" "main" {
  provider = aws.sso
  count    = local.l5_aws_enabled ? 1 : 0
}

locals {
  # Check if SSO is available (identity_store_ids is not empty)
  # Used for warning output, but admin user creation remains mandatory
  sso_available = local.l5_aws_enabled && try(
    length(tolist(data.aws_ssoadmin_instances.main[0].identity_store_ids)) > 0,
    false
  )
  identity_store_id = try(tolist(data.aws_ssoadmin_instances.main[0].identity_store_ids)[0], "")
  # Admin user creation is MANDATORY when L5=AWS and email is provided
  # If SSO is not detected, Terraform will fail with empty identity_store_id (as intended)
  grafana_admin_enabled = local.l5_aws_enabled && var.grafana_admin_email != ""
}

# ==============================================================================
# Create IAM Identity Center User
# NOTE: If user already exists, Terraform will error with clear message.
#       User can then use: terraform import aws_identitystore_user.grafana_admin[0] <store_id>/<user_id>
# ==============================================================================

resource "aws_identitystore_user" "grafana_admin" {
  count = local.grafana_admin_enabled ? 1 : 0
  
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

# ==============================================================================
# Assign User to Grafana Workspace
# ==============================================================================

resource "aws_grafana_role_association" "admin" {
  count = local.grafana_admin_enabled ? 1 : 0
  
  role         = "ADMIN"
  user_ids     = [aws_identitystore_user.grafana_admin[0].user_id]
  workspace_id = aws_grafana_workspace.main[0].id
}
