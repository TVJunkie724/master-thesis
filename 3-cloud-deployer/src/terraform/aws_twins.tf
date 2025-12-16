# AWS L4 Twin Management Layer (TwinMaker)
#
# This file creates the L4 layer infrastructure for Digital Twin management.
# L4 provides a semantic layer for modeling physical entities.
#
# Resources Created (via Terraform):
# - TwinMaker Workspace: Container for twin model
#
# Resources Created (via SDK post-deployment):
# - Component Types: Sensor definitions
# - Entities: Twin instances
# - Relationships: Entity connections
#
# Note: TwinMaker entities and component types have limited Terraform support.
# The workspace is created by Terraform, entities by Python SDK.

# ==============================================================================
# L4 Locals
# ==============================================================================

locals {
  l4_aws_enabled = var.layer_4_provider == "aws"
  
  # Pre-built Lambda packages directory
  l4_lambda_build_dir = "${path.module}/.build/aws"
}

# ==============================================================================
# IAM Role for TwinMaker
# ==============================================================================

resource "aws_iam_role" "l4_twinmaker" {
  count = local.l4_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l4-twinmaker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "iottwinmaker.amazonaws.com"
        }
      }
    ]
  })

  tags = local.aws_common_tags
}

# S3 access for TwinMaker workspace data
resource "aws_iam_role_policy" "l4_twinmaker_s3" {
  count = local.l4_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l4-twinmaker-s3-policy"
  role  = aws_iam_role.l4_twinmaker[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.l4_twinmaker[0].arn,
          "${aws_s3_bucket.l4_twinmaker[0].arn}/*"
        ]
      }
    ]
  })
}

# Lambda invocation for data connectors
resource "aws_iam_role_policy" "l4_twinmaker_lambda" {
  count = local.l4_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l4-twinmaker-lambda-policy"
  role  = aws_iam_role.l4_twinmaker[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:function:${var.digital_twin_name}-*"
      }
    ]
  })
}

# ==============================================================================
# S3 Bucket for TwinMaker Workspace Data
# ==============================================================================

resource "aws_s3_bucket" "l4_twinmaker" {
  count  = local.l4_aws_enabled ? 1 : 0
  bucket = "${var.digital_twin_name}-twinmaker"

  tags = local.aws_common_tags
}

# ==============================================================================
# TwinMaker Workspace (using awscc provider)
# ==============================================================================

resource "awscc_iottwinmaker_workspace" "main" {
  count        = local.l4_aws_enabled ? 1 : 0
  workspace_id = var.digital_twin_name
  description  = "Digital Twin workspace for ${var.digital_twin_name}"
  role         = aws_iam_role.l4_twinmaker[0].arn
  s3_location  = "arn:aws:s3:::${aws_s3_bucket.l4_twinmaker[0].bucket}"

  tags = {
    for key, value in local.aws_common_tags : key => value
  }
}

# ==============================================================================
# Data Connector Lambda (provides hot data to TwinMaker)
# ==============================================================================

resource "aws_iam_role" "l4_connector_lambda" {
  count = local.l4_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l4-connector-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.aws_common_tags
}

resource "aws_iam_role_policy_attachment" "l4_connector_logs" {
  count      = local.l4_aws_enabled ? 1 : 0
  role       = aws_iam_role.l4_connector_lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access for connector
resource "aws_iam_role_policy" "l4_connector_dynamodb" {
  count = local.l4_aws_enabled && local.l3_hot_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l4-connector-dynamodb-policy"
  role  = aws_iam_role.l4_connector_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:GetItem"
        ]
        Resource = aws_dynamodb_table.l3_hot[0].arn
      }
    ]
  })
}

resource "aws_lambda_function" "l4_connector" {
  count         = local.l4_aws_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l4-connector"
  role          = aws_iam_role.l4_connector_lambda[0].arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l4_lambda_build_dir}/digital-twin-data-connector.zip"
  source_code_hash = filebase64sha256("${local.l4_lambda_build_dir}/digital-twin-data-connector.zip")

  environment {
    variables = {
      DIGITAL_TWIN_NAME = var.digital_twin_name
      WORKSPACE_ID      = var.digital_twin_name
      L3_HOT_PROVIDER   = var.layer_3_hot_provider
    }
  }

  tags = local.aws_common_tags
}
