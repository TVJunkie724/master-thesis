# AWS L3 Storage Layer
#
# This file creates the L3 layer infrastructure for data storage.
# L3 provides tiered storage: Hot (DynamoDB), Cold (S3 IA), Archive (S3 Glacier).
#
# Resources Created:
# - DynamoDB Table: Hot storage for recent data
# - S3 Buckets: Cold and Archive storage
# - Hot Reader Lambda: Queries hot data for TwinMaker
# - Mover Lambdas: Move data between tiers
# - EventBridge Rules: Scheduled triggers for movers
#
# Note: Lambda function CODE is deployed separately via Python SDK.

# ==============================================================================
# L3 Locals
# ==============================================================================

locals {
  l3_hot_aws_enabled     = var.layer_3_hot_provider == "aws"
  l3_cold_aws_enabled    = var.layer_3_cold_provider == "aws"
  l3_archive_aws_enabled = var.layer_3_archive_provider == "aws"
  l3_any_aws_enabled     = local.l3_hot_aws_enabled || local.l3_cold_aws_enabled || local.l3_archive_aws_enabled
  
  # Pre-built Lambda packages directory
  l3_lambda_build_dir = "${var.project_path}/.build/aws"
}

# ==============================================================================
# L3 Hot Storage - DynamoDB Table
# ==============================================================================

resource "aws_dynamodb_table" "l3_hot" {
  count        = local.l3_hot_aws_enabled ? 1 : 0
  name         = "${var.digital_twin_name}-hot"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "device_id"
  range_key    = "timestamp"

  attribute {
    name = "device_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  # TTL for automatic expiration (data moves to cold storage)
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# IAM Role for L3 Lambda Functions
# ==============================================================================

resource "aws_iam_role" "l3_lambda" {
  count = local.l3_any_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l3-lambda-role"

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
resource "aws_iam_role_policy_attachment" "l3_lambda_logs" {
  count      = local.l3_any_aws_enabled ? 1 : 0
  role       = aws_iam_role.l3_lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# DynamoDB access
resource "aws_iam_role_policy" "l3_dynamodb" {
  count = local.l3_hot_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l3-dynamodb-policy"
  role  = aws_iam_role.l3_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:GetItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.l3_hot[0].arn
      }
    ]
  })
}

# S3 access for Cold/Archive
resource "aws_iam_role_policy" "l3_s3" {
  count = local.l3_cold_aws_enabled || local.l3_archive_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l3-s3-policy"
  role  = aws_iam_role.l3_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.digital_twin_name}-cold",
          "arn:aws:s3:::${var.digital_twin_name}-cold/*",
          "arn:aws:s3:::${var.digital_twin_name}-archive",
          "arn:aws:s3:::${var.digital_twin_name}-archive/*"
        ]
      }
    ]
  })
}

# ==============================================================================
# L3 Hot Reader Lambda
# ==============================================================================

resource "aws_lambda_function" "l3_hot_reader" {
  count         = local.l3_hot_aws_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l3-hot-reader"
  role          = aws_iam_role.l3_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l3_lambda_build_dir}/hot-reader.zip"
  source_code_hash = filebase64sha256("${local.l3_lambda_build_dir}/hot-reader.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO   = var.digital_twin_info_json
      DYNAMODB_TABLE_NAME = aws_dynamodb_table.l3_hot[0].name
    }
  }

  tags = local.aws_common_tags
}

resource "aws_lambda_function_url" "l3_hot_reader" {
  count              = local.l3_hot_aws_enabled ? 1 : 0
  function_name      = aws_lambda_function.l3_hot_reader[0].function_name
  authorization_type = "NONE"
}

# ==============================================================================
# L3 Cold Storage - S3 Bucket
# ==============================================================================

resource "aws_s3_bucket" "l3_cold" {
  count  = local.l3_cold_aws_enabled ? 1 : 0
  bucket = "${var.digital_twin_name}-cold"

  tags = local.aws_common_tags
}

resource "aws_s3_bucket_lifecycle_configuration" "l3_cold" {
  count  = local.l3_cold_aws_enabled ? 1 : 0
  bucket = aws_s3_bucket.l3_cold[0].id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    filter {}

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
  }
}

# ==============================================================================
# Hot-to-Cold Mover Lambda
# ==============================================================================

resource "aws_lambda_function" "l3_hot_to_cold_mover" {
  count         = local.l3_hot_aws_enabled && local.l3_cold_aws_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l3-hot-to-cold-mover"
  role          = aws_iam_role.l3_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  # Pre-built by Python before terraform apply
  filename         = "${local.l3_lambda_build_dir}/hot-to-cold-mover.zip"
  source_code_hash = filebase64sha256("${local.l3_lambda_build_dir}/hot-to-cold-mover.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO      = var.digital_twin_info_json
      DYNAMODB_TABLE_NAME    = aws_dynamodb_table.l3_hot[0].name
      COLD_S3_BUCKET_NAME    = aws_s3_bucket.l3_cold[0].bucket

      # Multi-cloud Hot→Cold: When AWS L3 Hot sends to remote Cold
      REMOTE_COLD_WRITER_URL = var.layer_3_hot_provider == "aws" && var.layer_3_cold_provider != "aws" ? (
        var.layer_3_cold_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/api/cold-writer" :
        var.layer_3_cold_provider == "google" ? try(google_cloudfunctions2_function.cold_writer[0].url, "") : ""
      ) : ""

      # Inter-cloud token
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")
    }
  }

  tags = local.aws_common_tags
}

# EventBridge Rule - Schedule hot-to-cold mover
resource "aws_cloudwatch_event_rule" "l3_hot_to_cold" {
  count               = local.l3_hot_aws_enabled && local.l3_cold_aws_enabled ? 1 : 0
  name                = "${var.digital_twin_name}-l3-hot-to-cold-schedule"
  description         = "Trigger hot-to-cold data mover daily"
  schedule_expression = "rate(1 day)"

  tags = local.aws_common_tags
}

resource "aws_cloudwatch_event_target" "l3_hot_to_cold" {
  count     = local.l3_hot_aws_enabled && local.l3_cold_aws_enabled ? 1 : 0
  rule      = aws_cloudwatch_event_rule.l3_hot_to_cold[0].name
  target_id = "HotToColdMover"
  arn       = aws_lambda_function.l3_hot_to_cold_mover[0].arn
}

resource "aws_lambda_permission" "l3_hot_to_cold" {
  count         = local.l3_hot_aws_enabled && local.l3_cold_aws_enabled ? 1 : 0
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.l3_hot_to_cold_mover[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.l3_hot_to_cold[0].arn
}

# ==============================================================================
# L3 Archive Storage - S3 Bucket (Glacier)
# ==============================================================================

resource "aws_s3_bucket" "l3_archive" {
  count  = local.l3_archive_aws_enabled ? 1 : 0
  bucket = "${var.digital_twin_name}-archive"

  tags = local.aws_common_tags
}

resource "aws_s3_bucket_lifecycle_configuration" "l3_archive" {
  count  = local.l3_archive_aws_enabled ? 1 : 0
  bucket = aws_s3_bucket.l3_archive[0].id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    filter {}

    transition {
      days          = 0
      storage_class = "GLACIER"
    }
  }
}

# ==============================================================================
# Cold-to-Archive Mover Lambda
# ==============================================================================

resource "aws_lambda_function" "l3_cold_to_archive_mover" {
  count         = local.l3_cold_aws_enabled && local.l3_archive_aws_enabled ? 1 : 0
  function_name = "${var.digital_twin_name}-l3-cold-to-archive-mover"
  role          = aws_iam_role.l3_lambda[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 300
  memory_size   = 512

  # Pre-built by Python before terraform apply
  filename         = "${local.l3_lambda_build_dir}/cold-to-archive-mover.zip"
  source_code_hash = filebase64sha256("${local.l3_lambda_build_dir}/cold-to-archive-mover.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO         = var.digital_twin_info_json
      COLD_S3_BUCKET_NAME       = aws_s3_bucket.l3_cold[0].bucket
      ARCHIVE_S3_BUCKET_NAME    = aws_s3_bucket.l3_archive[0].bucket

      # Multi-cloud Cold→Archive: When AWS L3 Cold sends to remote Archive
      REMOTE_ARCHIVE_WRITER_URL = var.layer_3_cold_provider == "aws" && var.layer_3_archive_provider != "aws" ? (
        var.layer_3_archive_provider == "azure" ? "https://${try(azurerm_linux_function_app.l0_glue[0].default_hostname, "")}/api/archive-writer" :
        var.layer_3_archive_provider == "google" ? try(google_cloudfunctions2_function.archive_writer[0].url, "") : ""
      ) : ""

      # Inter-cloud token
      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")
    }
  }

  tags = local.aws_common_tags
}

# EventBridge Rule - Schedule cold-to-archive mover
resource "aws_cloudwatch_event_rule" "l3_cold_to_archive" {
  count               = local.l3_cold_aws_enabled && local.l3_archive_aws_enabled ? 1 : 0
  name                = "${var.digital_twin_name}-l3-cold-to-archive-schedule"
  description         = "Trigger cold-to-archive data mover weekly"
  schedule_expression = "rate(7 days)"

  tags = local.aws_common_tags
}

resource "aws_cloudwatch_event_target" "l3_cold_to_archive" {
  count     = local.l3_cold_aws_enabled && local.l3_archive_aws_enabled ? 1 : 0
  rule      = aws_cloudwatch_event_rule.l3_cold_to_archive[0].name
  target_id = "ColdToArchiveMover"
  arn       = aws_lambda_function.l3_cold_to_archive_mover[0].arn
}

resource "aws_lambda_permission" "l3_cold_to_archive" {
  count         = local.l3_cold_aws_enabled && local.l3_archive_aws_enabled ? 1 : 0
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.l3_cold_to_archive_mover[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.l3_cold_to_archive[0].arn
}
