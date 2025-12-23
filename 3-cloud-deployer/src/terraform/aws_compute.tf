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
  l2_lambda_build_dir = "${var.project_path}/.build/aws"
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

# L2 Lambda Invocation (Wrapper calling User Processors)
resource "aws_iam_role_policy" "l2_invoke_lambda" {
  count = local.l2_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l2-invoke-policy"
  role  = aws_iam_role.l2_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        # Allow invoking any function starting with the digital twin name (processors, feedback, etc.)
        Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:function:${var.digital_twin_name}-*"
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
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l2_lambda_build_dir}/persister.zip"
  source_code_hash = filebase64sha256("${local.l2_lambda_build_dir}/persister.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO = local.digital_twin_info_json
      DYNAMODB_TABLE    = "${var.digital_twin_name}-hot"

      # Multi-cloud L2→L3: When AWS L2 sends to remote L3
      REMOTE_WRITER_URL = var.layer_2_provider == "aws" && var.layer_3_hot_provider != "aws" ? (
        var.layer_3_hot_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/api/hot-writer" :
        var.layer_3_hot_provider == "google" ? try(google_cloudfunctions2_function.hot_writer[0].url, "") : ""
      ) : ""

      # Multi-cloud L2→L4: When AWS L2 sends to Azure ADT (Azure-only feature)
      # ADT pusher is part of L0 Glue layer, like other cross-cloud receivers
      REMOTE_ADT_PUSHER_URL = var.layer_2_provider == "aws" && var.layer_4_provider == "azure" ? (
        "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/api/adt-pusher"
      ) : ""
      ADT_PUSHER_TOKEN = var.layer_4_provider == "azure" ? (
        var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")
      ) : ""

      # Inter-cloud token for cross-cloud authentication
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")
    }
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# Event Checker Lambda Function (Optional - for anomaly detection)
# Only deployed if use_event_checking is enabled
# ==============================================================================

resource "aws_lambda_function" "l2_event_checker" {
  count         = local.l2_aws_enabled && var.use_event_checking ? 1 : 0
  function_name = "${var.digital_twin_name}-l2-event-checker"
  role          = aws_iam_role.l2_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l2_lambda_build_dir}/event-checker.zip"
  source_code_hash = filebase64sha256("${local.l2_lambda_build_dir}/event-checker.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO = local.digital_twin_info_json
    }
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# Step Functions State Machine (Optional - for event workflow)
# Only deployed if trigger_notification_workflow is enabled
# ==============================================================================

resource "aws_iam_role" "l2_step_functions" {
  # Requires both flags since Step Functions invokes event_checker
  count = local.l2_aws_enabled && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
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
  # Requires both flags since Step Functions invokes event_checker
  count = local.l2_aws_enabled && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
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
  # Requires both flags since workflow invokes event_checker
  count    = local.l2_aws_enabled && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
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

# ==============================================================================
# AWS Processor Wrapper Lambda (Routes to user processors)
# ==============================================================================

resource "aws_lambda_function" "processor_wrapper" {
  count         = local.l2_aws_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-processor"
  role          = aws_iam_role.l2_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  filename         = "${local.l2_lambda_build_dir}/processor_wrapper.zip"
  source_code_hash = filebase64sha256("${local.l2_lambda_build_dir}/processor_wrapper.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO     = local.digital_twin_info_json
      PERSISTER_LAMBDA_NAME = aws_lambda_function.l2_persister[0].function_name
    }
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# AWS User Processor Lambda Functions (Individual per device)
# ==============================================================================

resource "aws_lambda_function" "user_processor" {
  for_each = { for p in var.aws_processors : p.name => p }
  
  function_name = "${var.digital_twin_name}-${each.value.name}-processor"
  role          = aws_iam_role.l2_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  filename         = each.value.zip_path
  source_code_hash = filebase64sha256(each.value.zip_path)

  environment {
    variables = {
      DIGITAL_TWIN_INFO = local.digital_twin_info_json
    }
  }

  tags = local.aws_common_tags
}
