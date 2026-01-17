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
  l1_lambda_build_dir = "${var.project_path}/.build/aws"
}

# ==============================================================================
# AWS IoT Endpoint Data Source (for E2E tests)
# ==============================================================================

data "aws_iot_endpoint" "main" {
  count         = local.l1_aws_enabled ? 1 : 0
  endpoint_type = "iot:Data-ATS"
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
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l1_lambda_build_dir}/dispatcher.zip"
  source_code_hash = filebase64sha256("${local.l1_lambda_build_dir}/dispatcher.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO      = var.digital_twin_info_json
      TARGET_FUNCTION_SUFFIX = var.layer_2_provider == "aws" ? "-processor" : "-connector"

      # Multi-cloud L1→L2: When AWS L1 sends to remote L2
      REMOTE_INGESTION_URL = var.layer_1_provider == "aws" && var.layer_2_provider != "aws" ? (
        var.layer_2_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/api/ingestion" :
        var.layer_2_provider == "google" ? try(google_cloudfunctions2_function.ingestion[0].url, "") : ""
      ) : ""

      # Inter-cloud token for cross-cloud authentication
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")
    }
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# L1 Connector Lambda (Multi-Cloud Only)
# ==============================================================================

resource "aws_iam_role" "l1_connector" {
  count = local.l1_aws_enabled && var.layer_2_provider != "aws" ? 1 : 0
  name  = "${var.digital_twin_name}-l1-connector-role"

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

resource "aws_iam_role_policy_attachment" "l1_connector_logs" {
  count      = local.l1_aws_enabled && var.layer_2_provider != "aws" ? 1 : 0
  role       = aws_iam_role.l1_connector[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "l1_connector" {
  count         = local.l1_aws_enabled && var.layer_2_provider != "aws" ? 1 : 0
  function_name = "${var.digital_twin_name}-connector"
  role          = aws_iam_role.l1_connector[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l1_lambda_build_dir}/connector.zip"
  source_code_hash = filebase64sha256("${local.l1_lambda_build_dir}/connector.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO = var.digital_twin_info_json
      # Multi-cloud L1→L2: Remote ingestion endpoint
      REMOTE_INGESTION_URL = var.layer_2_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/api/ingestion" : (
        var.layer_2_provider == "google" ? try(google_cloudfunctions2_function.ingestion[0].url, "") : ""
      )
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")
    }
  }

  tags = local.aws_common_tags

  depends_on = [
    # Cross-cloud L2 targets (ensure they exist before connector deployment)
    azurerm_linux_function_app.l0_glue,
    google_cloudfunctions2_function.ingestion
  ]
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

# ==============================================================================
# E2E Test IoT Publish Permission
# ==============================================================================
# This section grants the IAM user running Terraform permission to publish
# to IoT Core topics. Required for E2E tests that simulate device telemetry.
#
# AWS IoT Core has a separate authorization layer from standard IAM.
# Even admin IAM users need explicit iot:Publish permission on topic ARNs.
#
# LIMITATION: This permission is only granted when Terraform is run by an
# IAM User (not an assumed role, SSO session, or federated identity).
# 
# Supported:
#   - IAM User with static access keys (aws_access_key_id/aws_secret_access_key)
#
# NOT Supported (policy will not be created):
#   - Assumed roles (AWS SSO, CI/CD pipelines with OIDC)
#   - EC2 instance profiles
#   - Lambda execution contexts
#   - Federated/cross-account access
#
# For this thesis project, IAM User credentials are the expected access method.
# If using assumed roles, manually add iot:Publish permission to the role.

locals {
  # Parse caller identity to determine if running as IAM user
  caller_arn = try(data.aws_caller_identity.current[0].arn, "")
  
  # Check if caller is a user (not a role or assumed role)
  # IAM User ARN format: arn:aws:iam::ACCOUNT:user/USERNAME
  is_iam_user = local.l1_aws_enabled && can(regex(":user/", local.caller_arn))
  
  # Extract user name from ARN (only valid if is_iam_user is true)
  iam_user_name = local.is_iam_user ? regex(":user/(.+)$", local.caller_arn)[0] : null
}

# IAM Policy for E2E test IoT publishing
resource "aws_iam_policy" "e2e_iot_publish" {
  count       = local.is_iam_user ? 1 : 0
  name        = "${var.digital_twin_name}-e2e-iot-publish"
  description = "Allows publishing to IoT Core topics for E2E testing"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowIoTPublish"
        Effect = "Allow"
        Action = [
          "iot:Publish",
          "iot:Receive"
        ]
        # Allow publishing to any topic under this digital twin's namespace
        Resource = "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:topic/dt/${var.digital_twin_name}/*"
      }
    ]
  })

  tags = local.aws_common_tags
}

# Attach the IoT publish policy to the current IAM user
resource "aws_iam_user_policy_attachment" "e2e_iot_publish" {
  count      = local.is_iam_user ? 1 : 0
  user       = local.iam_user_name
  policy_arn = aws_iam_policy.e2e_iot_publish[0].arn
}
