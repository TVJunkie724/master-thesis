# AWS L2 Data Processing Layer
#
# This file creates the L2 layer infrastructure for data processing.
# L2 receives telemetry and processes it for storage and analysis.
#
# Resources Created:
# - Persister Lambda: Writes processed data to storage
# - Event Checker Lambda: Anomaly detection (optional)
# - Step Functions State Machine: Event workflow (optional)
# - IAM Roles: Lambda execution and DynamoDB/S3 access
#
# Note: Lambda function CODE is deployed separately via Python SDK.

# ==============================================================================
# L2 Locals
# ==============================================================================

locals {
  l2_aws_enabled = var.layer_2_provider == "aws"
  
  # Pre-built Lambda packages directory
  l2_lambda_build_dir = "${path.module}/.build/aws"
}

# ==============================================================================
# IAM Role for L2 Lambda Functions
# ==============================================================================

resource "aws_iam_role" "l2_lambda" {
  count = local.l2_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l2-lambda-role"

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

# CloudWatch Logs policy
resource "aws_iam_role_policy_attachment" "l2_lambda_logs" {
  count      = local.l2_aws_enabled ? 1 : 0
  role       = aws_iam_role.l2_lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access for Persister
resource "aws_iam_role_policy" "l2_dynamodb" {
  count = local.l2_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l2-dynamodb-policy"
  role  = aws_iam_role.l2_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem",
          "dynamodb:Query"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:table/${var.digital_twin_name}-*"
      }
    ]
  })
}

# S3 access for Cold/Archive storage
resource "aws_iam_role_policy" "l2_s3" {
  count = local.l2_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l2-s3-policy"
  role  = aws_iam_role.l2_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "arn:aws:s3:::${var.digital_twin_name}-*/*"
      }
    ]
  })
}

# ==============================================================================
# Persister Lambda Function
# ==============================================================================

resource "aws_lambda_function" "l2_persister" {
  count         = local.l2_aws_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l2-persister"
  role          = aws_iam_role.l2_lambda[0].arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l2_lambda_build_dir}/persister.zip"
  source_code_hash = filebase64sha256("${local.l2_lambda_build_dir}/persister.zip")

  environment {
    variables = {
      DIGITAL_TWIN_NAME = var.digital_twin_name
      L3_HOT_PROVIDER   = var.layer_3_hot_provider
      DYNAMODB_TABLE    = "${var.digital_twin_name}-hot"
    }
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# Event Checker Lambda Function (Optional - for anomaly detection)
# ==============================================================================

resource "aws_lambda_function" "l2_event_checker" {
  count         = local.l2_aws_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l2-event-checker"
  role          = aws_iam_role.l2_lambda[0].arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l2_lambda_build_dir}/event-checker.zip"
  source_code_hash = filebase64sha256("${local.l2_lambda_build_dir}/event-checker.zip")

  environment {
    variables = {
      DIGITAL_TWIN_NAME = var.digital_twin_name
    }
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# Step Functions State Machine (Optional - for event workflow)
# ==============================================================================

resource "aws_iam_role" "l2_step_functions" {
  count = local.l2_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l2-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })

  tags = local.aws_common_tags
}

resource "aws_iam_role_policy" "l2_sfn_lambda" {
  count = local.l2_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l2-sfn-lambda-policy"
  role  = aws_iam_role.l2_step_functions[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = [
          aws_lambda_function.l2_event_checker[0].arn
        ]
      }
    ]
  })
}

resource "aws_sfn_state_machine" "l2_event_workflow" {
  count    = local.l2_aws_enabled ? 1 : 0
  name     = "${var.digital_twin_name}-l2-event-workflow"
  role_arn = aws_iam_role.l2_step_functions[0].arn

  definition = jsonencode({
    Comment = "Event processing workflow for ${var.digital_twin_name}"
    StartAt = "CheckEvent"
    States = {
      CheckEvent = {
        Type     = "Task"
        Resource = aws_lambda_function.l2_event_checker[0].arn
        End      = true
      }
    }
  })

  tags = local.aws_common_tags
}
