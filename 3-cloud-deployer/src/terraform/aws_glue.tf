# AWS L0 Glue Layer
#
# This file creates the cross-cloud communication infrastructure.
# L0 is deployed BEFORE L1-L5 when cross-cloud boundaries exist.
#
# Resources Created:
# - Lambda Functions: Ingestion, Hot Writer, Hot Reader
# - IAM Roles: Lambda execution roles
# - Function URLs: HTTP endpoints for cross-cloud access
#
# Note: Lambda function CODE is deployed separately via Python SDK
# (similar to Azure Kudu deployment). Terraform creates the infrastructure.

# ==============================================================================
# L0 Locals
# ==============================================================================

locals {
  # L0 is deployed when this cloud receives data from another cloud
  l0_aws_enabled = local.aws_enabled && (
    # Ingestion: L1 is on another cloud, L2 is on AWS
    (var.layer_1_provider != "aws" && var.layer_2_provider == "aws") ||
    # Hot Writer: L2 is on another cloud, L3 hot is on AWS
    (var.layer_2_provider != "aws" && var.layer_3_hot_provider == "aws") ||
    # Hot Reader: L3 hot is on AWS, accessed from another cloud
    (var.layer_3_hot_provider == "aws" && var.layer_4_provider != "aws") ||
    # Cold Writer: L3 hot is on another cloud, L3 cold is on AWS
    (var.layer_3_hot_provider != "aws" && var.layer_3_cold_provider == "aws") ||
    # Archive Writer: L3 cold is on another cloud, L3 archive is on AWS
    (var.layer_3_cold_provider != "aws" && var.layer_3_archive_provider == "aws")
  )
  
  # Individual glue function conditions
  l0_ingestion_enabled   = var.layer_1_provider != "aws" && var.layer_2_provider == "aws"
  l0_hot_writer_enabled  = var.layer_2_provider != "aws" && var.layer_3_hot_provider == "aws"
  l0_hot_reader_enabled  = var.layer_3_hot_provider == "aws" && var.layer_4_provider != "aws"
  l0_cold_writer_enabled = var.layer_3_hot_provider != "aws" && var.layer_3_cold_provider == "aws"
  l0_archive_writer_enabled = var.layer_3_cold_provider != "aws" && var.layer_3_archive_provider == "aws"
  
  # Pre-built Lambda packages directory (built by Python before terraform apply)
  lambda_build_dir = "${var.project_path}/.build/aws"
}

# ==============================================================================
# IAM Role for L0 Lambda Functions
# ==============================================================================

resource "aws_iam_role" "l0_lambda" {
  count = local.l0_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l0-lambda-role"

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
resource "aws_iam_role_policy_attachment" "l0_lambda_logs" {
  count      = local.l0_aws_enabled ? 1 : 0
  role       = aws_iam_role.l0_lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access for Hot Writer/Reader
resource "aws_iam_role_policy" "l0_dynamodb" {
  count = local.l0_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l0-dynamodb-policy"
  role  = aws_iam_role.l0_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:table/${var.digital_twin_name}-*"
      }
    ]
  })
}

# ==============================================================================
# L0 Ingestion Lambda (receives data from L1 on another cloud)
# ==============================================================================

resource "aws_lambda_function" "l0_ingestion" {
  count         = local.l0_ingestion_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l0-ingestion"
  role          = aws_iam_role.l0_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.lambda_build_dir}/ingestion.zip"
  source_code_hash = filebase64sha256("${local.lambda_build_dir}/ingestion.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO   = local.digital_twin_info_json
      INTER_CLOUD_TOKEN   = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
    }
  }

  tags = local.aws_common_tags
}

resource "aws_lambda_function_url" "l0_ingestion" {
  count              = local.l0_ingestion_enabled ? 1 : 0
  function_name      = aws_lambda_function.l0_ingestion[0].function_name
  authorization_type = "NONE"
}

# ==============================================================================
# L0 Hot Writer Lambda (receives processed data from L2 on another cloud)
# ==============================================================================

resource "aws_lambda_function" "l0_hot_writer" {
  count         = local.l0_hot_writer_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l0-hot-writer"
  role          = aws_iam_role.l0_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.lambda_build_dir}/hot-writer.zip"
  source_code_hash = filebase64sha256("${local.lambda_build_dir}/hot-writer.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO   = local.digital_twin_info_json
      DYNAMODB_TABLE      = "${var.digital_twin_name}-hot"
      INTER_CLOUD_TOKEN   = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
    }
  }

  tags = local.aws_common_tags
}

resource "aws_lambda_function_url" "l0_hot_writer" {
  count              = local.l0_hot_writer_enabled ? 1 : 0
  function_name      = aws_lambda_function.l0_hot_writer[0].function_name
  authorization_type = "NONE"
}

# ==============================================================================
# L0 Hot Reader Lambda (provides data to L4 on another cloud)
# ==============================================================================

resource "aws_lambda_function" "l0_hot_reader" {
  count         = local.l0_hot_reader_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l0-hot-reader"
  role          = aws_iam_role.l0_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.lambda_build_dir}/hot-reader.zip"
  source_code_hash = filebase64sha256("${local.lambda_build_dir}/hot-reader.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO   = local.digital_twin_info_json
      DYNAMODB_TABLE      = "${var.digital_twin_name}-hot"
      INTER_CLOUD_TOKEN   = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
    }
  }

  tags = local.aws_common_tags
}

resource "aws_lambda_function_url" "l0_hot_reader" {
  count              = local.l0_hot_reader_enabled ? 1 : 0
  function_name      = aws_lambda_function.l0_hot_reader[0].function_name
  authorization_type = "NONE"
}

# ==============================================================================
# L0 Cold Writer Lambda (receives data from L3 Hot on another cloud)
# ==============================================================================

resource "aws_lambda_function" "l0_cold_writer" {
  count         = local.l0_cold_writer_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l0-cold-writer"
  role          = aws_iam_role.l0_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.lambda_build_dir}/cold-writer.zip"
  source_code_hash = filebase64sha256("${local.lambda_build_dir}/cold-writer.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO   = local.digital_twin_info_json
      S3_BUCKET           = "${var.digital_twin_name}-cold"
      INTER_CLOUD_TOKEN   = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
    }
  }

  tags = local.aws_common_tags
}

resource "aws_lambda_function_url" "l0_cold_writer" {
  count              = local.l0_cold_writer_enabled ? 1 : 0
  function_name      = aws_lambda_function.l0_cold_writer[0].function_name
  authorization_type = "NONE"
}

# ==============================================================================
# L0 Archive Writer Lambda (receives data from L3 Cold on another cloud)
# ==============================================================================

resource "aws_lambda_function" "l0_archive_writer" {
  count         = local.l0_archive_writer_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l0-archive-writer"
  role          = aws_iam_role.l0_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.lambda_build_dir}/archive-writer.zip"
  source_code_hash = filebase64sha256("${local.lambda_build_dir}/archive-writer.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO   = local.digital_twin_info_json
      S3_BUCKET           = "${var.digital_twin_name}-archive"
      INTER_CLOUD_TOKEN   = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
    }
  }

  tags = local.aws_common_tags
}

resource "aws_lambda_function_url" "l0_archive_writer" {
  count              = local.l0_archive_writer_enabled ? 1 : 0
  function_name      = aws_lambda_function.l0_archive_writer[0].function_name
  authorization_type = "NONE"
}
