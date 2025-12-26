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
  l4_lambda_build_dir = "${var.project_path}/.build/aws"
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

# S3/DynamoDB/Lambda access for TwinMaker workspace
# Note: Uses exact permissions from AWS TwinMaker documentation:
# https://docs.aws.amazon.com/iot-twinmaker/latest/guide/twinmaker-gs-service-role.html
resource "aws_iam_role_policy" "l4_twinmaker_s3" {
  count = local.l4_aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-l4-twinmaker-s3-policy"
  role  = aws_iam_role.l4_twinmaker[0].id

  # AWS TwinMaker requires access to S3 for workspace resources
  # Per official docs, this requires broad S3 access (arn:aws:s3:::*)
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetBucket*",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ]
        Resource = ["arn:aws:s3:::*"]
      },
      {
        Effect = "Allow"
        Action = ["s3:DeleteObject"]
        Resource = ["arn:aws:s3:::*/DO_NOT_DELETE_WORKSPACE_*"]
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

# CORS configuration for TwinMaker S3 bucket
# Required for Grafana Scene Viewer to access scene assets
resource "aws_s3_bucket_cors_configuration" "l4_twinmaker" {
  count  = local.l4_aws_enabled ? 1 : 0
  bucket = aws_s3_bucket.l4_twinmaker[0].id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# ==============================================================================
# IAM Propagation Delay
# ==============================================================================
# AWS IAM role propagation can take 10-30 seconds across all regions.
# TwinMaker validates the role by assuming it at creation time, so we need
# to wait for propagation to complete before creating the workspace.

resource "time_sleep" "l4_iam_propagation" {
  count           = local.l4_aws_enabled ? 1 : 0
  create_duration = "30s"

  depends_on = [
    aws_iam_role.l4_twinmaker,
    aws_iam_role_policy.l4_twinmaker_s3,
    aws_iam_role_policy.l4_twinmaker_lambda,
    aws_s3_bucket.l4_twinmaker  # Ensure bucket exists before TwinMaker
  ]
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

  depends_on = [time_sleep.l4_iam_propagation]
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
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  # Pre-built by Python before terraform apply
  filename         = "${local.l4_lambda_build_dir}/digital-twin-data-connector.zip"
  source_code_hash = filebase64sha256("${local.l4_lambda_build_dir}/digital-twin-data-connector.zip")

  environment {
    variables = {
      DIGITAL_TWIN_INFO = var.digital_twin_info_json
      WORKSPACE_ID      = var.digital_twin_name

      # Single-cloud mode: L3=AWS, invokes local Hot Reader Lambda
      LOCAL_HOT_READER_NAME = var.layer_3_hot_provider == "aws" ? "${var.digital_twin_name}-l0-hot-reader" : ""

      # Multi-cloud mode: L3≠AWS, calls remote Hot Reader via HTTP
      REMOTE_READER_URL = var.layer_3_hot_provider != "aws" ? (
        var.layer_3_hot_provider == "azure" ? "https://${try(azurerm_linux_function_app.l3_storage[0].default_hostname, "")}/api/hot-reader" :
        var.layer_3_hot_provider == "google" ? try(google_cloudfunctions2_function.hot_reader[0].url, "") : ""
      ) : ""

      INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, "")
    }
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# 3D Scene Assets (conditional on needs_3d_model)
# ==============================================================================

locals {
  l4_scene_enabled = local.l4_aws_enabled && var.needs_3d_model && var.scene_assets_path != ""
  scene_assets_aws = var.scene_assets_path != "" ? "${var.scene_assets_path}/aws" : ""
}

# Upload GLB model to S3
resource "aws_s3_object" "scene_glb" {
  count  = local.l4_scene_enabled ? 1 : 0
  bucket = aws_s3_bucket.l4_twinmaker[0].id
  key    = "scene_assets/scene.glb"
  source = "${local.scene_assets_aws}/scene.glb"
  etag   = filemd5("${local.scene_assets_aws}/scene.glb")
  
  content_type = "model/gltf-binary"
  
  tags = local.aws_common_tags
  
  depends_on = [awscc_iottwinmaker_workspace.main]
}

# Upload scene.json config to S3
resource "aws_s3_object" "scene_json" {
  count  = local.l4_scene_enabled ? 1 : 0
  bucket = aws_s3_bucket.l4_twinmaker[0].id
  key    = "scene_assets/scene.json"
  source = "${local.scene_assets_aws}/scene.json"
  etag   = filemd5("${local.scene_assets_aws}/scene.json")
  
  content_type = "application/json"
  
  tags = local.aws_common_tags
  
  depends_on = [awscc_iottwinmaker_workspace.main]
}

# Create TwinMaker Scene
resource "awscc_iottwinmaker_scene" "main" {
  count            = local.l4_scene_enabled ? 1 : 0
  workspace_id     = awscc_iottwinmaker_workspace.main[0].workspace_id
  scene_id         = "main-scene"
  content_location = "s3://${aws_s3_bucket.l4_twinmaker[0].bucket}/scene_assets/scene.json"
  
  tags = {
    for key, value in local.aws_common_tags : key => value
  }
  
  depends_on = [
    aws_s3_object.scene_glb,
    aws_s3_object.scene_json
  ]
}

