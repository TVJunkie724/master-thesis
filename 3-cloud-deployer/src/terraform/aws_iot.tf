# AWS L1 Data Acquisition Layer (IoT Core)
#
# This file creates the L1 layer infrastructure for data ingestion.
# L1 receives telemetry from IoT devices and routes to processing.
#
# Resources Created:
# - IoT Topic Rule: Triggers dispatcher on telemetry messages
# - Dispatcher Lambda: Routes messages to appropriate processors
# - IAM Roles: Lambda execution and IoT permissions
#
# Note: IoT Thing/Device registration is handled by Python SDK
# as it requires dynamic configuration per device.

# ==============================================================================
# L1 Locals
# ==============================================================================

locals {
  l1_aws_enabled = var.layer_1_provider == "aws"
  
  # Pre-built Lambda packages directory
  l1_lambda_build_dir = "${path.module}/.build/aws"
}

# ==============================================================================
# IAM Role for Dispatcher Lambda
# ==============================================================================

resource "aws_iam_role" "l1_dispatcher" {
  count = local.l1_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l1-dispatcher-role"

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
resource "aws_iam_role_policy_attachment" "l1_dispatcher_logs" {
  count      = local.l1_aws_enabled ? 1 : 0
  role       = aws_iam_role.l1_dispatcher[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda invoke policy (to call L2 functions)
resource "aws_iam_role_policy" "l1_dispatcher_invoke" {
  count = local.l1_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l1-dispatcher-invoke-policy"
  role  = aws_iam_role.l1_dispatcher[0].id

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
# Dispatcher Lambda Function
# ==============================================================================

resource "aws_lambda_function" "l1_dispatcher" {
  count         = local.l1_aws_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l1-dispatcher"
  role          = aws_iam_role.l1_dispatcher[0].arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l1_lambda_build_dir}/dispatcher.zip"
  source_code_hash = filebase64sha256("${local.l1_lambda_build_dir}/dispatcher.zip")

  environment {
    variables = {
      DIGITAL_TWIN_NAME = var.digital_twin_name
      L2_PROVIDER       = var.layer_2_provider
    }
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# IoT Topic Rule (triggers dispatcher on telemetry)
# ==============================================================================

resource "aws_iot_topic_rule" "dispatcher" {
  count       = local.l1_aws_enabled ? 1 : 0
  name        = replace("${var.digital_twin_name}_telemetry_rule", "-", "_")
  description = "Routes telemetry messages to dispatcher Lambda"
  enabled     = true
  sql         = "SELECT * FROM 'dt/${var.digital_twin_name}/+/telemetry'"
  sql_version = "2016-03-23"

  lambda {
    function_arn = aws_lambda_function.l1_dispatcher[0].arn
  }

  tags = local.aws_common_tags
}

# Allow IoT to invoke the Lambda
resource "aws_lambda_permission" "l1_iot_invoke" {
  count         = local.l1_aws_enabled ? 1 : 0
  statement_id  = "AllowIoTInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.l1_dispatcher[0].function_name
  principal     = "iot.amazonaws.com"
  source_arn    = aws_iot_topic_rule.dispatcher[0].arn
}

# ==============================================================================
# IAM Role for IoT Topic Rule
# ==============================================================================

resource "aws_iam_role" "l1_iot_rule" {
  count = local.l1_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l1-iot-rule-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "iot.amazonaws.com"
        }
      }
    ]
  })

  tags = local.aws_common_tags
}

resource "aws_iam_role_policy" "l1_iot_rule_lambda" {
  count = local.l1_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l1-iot-rule-lambda-policy"
  role  = aws_iam_role.l1_iot_rule[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = aws_lambda_function.l1_dispatcher[0].arn
      }
    ]
  })
}
