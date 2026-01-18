# ============================================================================
# AWS TwinMaker (L4) Focused E2E Test - Terraform Configuration
# ============================================================================
# 
# Purpose:
#   Deploys ONLY Layer 4 resources (AWS IoT TwinMaker + 3D Scene Assets)
#   for rapid testing of TwinMaker deployment without the full infrastructure
#   stack (L0-L3, L5).
#
# What this tests:
#   1. TwinMaker Workspace creation
#   2. S3 bucket for scenes and workspace data
#   3. GLB model file upload  
#   4. scene.json configuration upload
#   5. TwinMaker Scene creation
#   6. IAM roles and permissions for TwinMaker
#
# Usage:
#   This file is used by tests/e2e/aws/test_aws_twinmaker_integrated_e2e.py
#   Run via: python tests/e2e/run_e2e_test.py aws-twinmaker-full
#
# Note:
#   TwinMaker Component Types and Entities are created by Python SDK after
#   Terraform, as they are generated dynamically from aws_hierarchy.json.
#   This test verifies the infrastructure is ready for that step.
# ============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
  }
}

# ============================================================================
# Variables
# ============================================================================

variable "aws_access_key_id" {
  description = "AWS Access Key ID"
  type        = string
}

variable "aws_secret_access_key" {
  description = "AWS Secret Access Key"
  type        = string
  sensitive   = true
}

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-west-1"
}

variable "test_name_suffix" {
  description = "Suffix for test resources to ensure uniqueness"
  type        = string
  default     = "e2e"
}

variable "scene_assets_path" {
  description = "Path to scene assets directory containing aws/scene.glb and aws/scene.json"
  type        = string
  default     = ""
}

# ============================================================================
# Provider Configuration
# ============================================================================

provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
}

provider "awscc" {
  region     = var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
}

# ============================================================================
# Random suffix for unique naming
# ============================================================================

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# ============================================================================
# Locals
# ============================================================================

locals {
  resource_prefix     = "tm-${var.test_name_suffix}"
  unique_suffix       = random_string.suffix.result
  workspace_id        = "${local.resource_prefix}-${local.unique_suffix}"
  scene_assets_aws    = var.scene_assets_path != "" ? "${var.scene_assets_path}/aws" : ""
  has_scene_assets    = var.scene_assets_path != ""
  
  common_tags = {
    Purpose   = "twinmaker-e2e-test"
    ManagedBy = "terraform"
  }
}

# ============================================================================
# Data Source: AWS Account ID
# ============================================================================

data "aws_caller_identity" "current" {}

# ============================================================================
# IAM Role for TwinMaker
# ============================================================================

resource "aws_iam_role" "twinmaker" {
  name = "${local.workspace_id}-twinmaker-role"

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

  tags = local.common_tags
}

# S3 access policy for TwinMaker workspace
resource "aws_iam_role_policy" "twinmaker_s3" {
  name = "${local.workspace_id}-twinmaker-s3-policy"
  role = aws_iam_role.twinmaker.id

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
        Resource = [
          aws_s3_bucket.twinmaker.arn,
          "${aws_s3_bucket.twinmaker.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:DeleteObject"]
        Resource = ["${aws_s3_bucket.twinmaker.arn}/DO_NOT_DELETE_WORKSPACE_*"]
      }
    ]
  })
}

# Lambda invocation policy for data connectors
resource "aws_iam_role_policy" "twinmaker_lambda" {
  name = "${local.workspace_id}-twinmaker-lambda-policy"
  role = aws_iam_role.twinmaker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.workspace_id}-*"
      }
    ]
  })
}

# ============================================================================
# S3 Bucket for TwinMaker Workspace Data
# ============================================================================

resource "aws_s3_bucket" "twinmaker" {
  bucket = "${local.workspace_id}-twinmaker"
  
  tags = local.common_tags
}

# CORS configuration for TwinMaker S3 bucket
# Required for Grafana Scene Viewer to access scene assets
resource "aws_s3_bucket_cors_configuration" "twinmaker" {
  bucket = aws_s3_bucket.twinmaker.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# ============================================================================
# IAM Propagation Delay
# ============================================================================
# AWS IAM role propagation can take 10-30 seconds across all regions.
# TwinMaker validates the role by assuming it at creation time.

resource "time_sleep" "iam_propagation" {
  create_duration = "30s"

  depends_on = [
    aws_iam_role.twinmaker,
    aws_iam_role_policy.twinmaker_s3,
    aws_iam_role_policy.twinmaker_lambda,
    aws_s3_bucket.twinmaker
  ]
}

# ============================================================================
# TwinMaker Workspace (using awscc provider)
# ============================================================================

resource "awscc_iottwinmaker_workspace" "main" {
  workspace_id = local.workspace_id
  description  = "TwinMaker E2E Test workspace - ${local.workspace_id}"
  role         = aws_iam_role.twinmaker.arn
  s3_location  = "arn:aws:s3:::${aws_s3_bucket.twinmaker.bucket}"

  # awscc_iottwinmaker_workspace expects tags as map of string
  tags = local.common_tags

  depends_on = [time_sleep.iam_propagation]
}

# ============================================================================
# 3D Scene Assets (conditional on scene_assets_path)
# ============================================================================

# Upload GLB model to S3
resource "aws_s3_object" "scene_glb" {
  count  = local.has_scene_assets ? 1 : 0
  bucket = aws_s3_bucket.twinmaker.id
  key    = "scene_assets/scene.glb"
  source = "${local.scene_assets_aws}/scene.glb"
  etag   = filemd5("${local.scene_assets_aws}/scene.glb")
  
  content_type = "model/gltf-binary"
  
  tags = local.common_tags
  
  depends_on = [awscc_iottwinmaker_workspace.main]
}

# Upload scene.json config to S3 - using templatefile to replace S3 bucket placeholder
# FIX: Issue #1 & #2 - Dynamic URL replacement and correct GLB filename
resource "aws_s3_object" "scene_json" {
  count  = local.has_scene_assets ? 1 : 0
  bucket = aws_s3_bucket.twinmaker.id
  key    = "scene_assets/scene.json"
  
  # Use templatefile to dynamically replace S3 bucket URL in scene.json
  # The template file should use ${s3_bucket} placeholder
  content = replace(
    file("${local.scene_assets_aws}/scene.json"),
    "s3://YOUR_TWINMAKER_S3_BUCKET/scene_assets/digital_twin_scene.glb",
    "s3://${aws_s3_bucket.twinmaker.bucket}/scene_assets/scene.glb"
  )
  
  content_type = "application/json"
  
  tags = local.common_tags
  
  depends_on = [awscc_iottwinmaker_workspace.main]
}

# Create TwinMaker Scene
resource "awscc_iottwinmaker_scene" "main" {
  count            = local.has_scene_assets ? 1 : 0
  workspace_id     = awscc_iottwinmaker_workspace.main.workspace_id
  scene_id         = "main-scene"
  content_location = "s3://${aws_s3_bucket.twinmaker.bucket}/scene_assets/scene.json"
  
  # awscc_iottwinmaker_scene expects tags as map of string
  tags = local.common_tags
  
  depends_on = [
    aws_s3_object.scene_glb,
    aws_s3_object.scene_json
  ]
}

# ============================================================================
# Outputs
# ============================================================================

output "workspace_id" {
  value       = awscc_iottwinmaker_workspace.main.workspace_id
  description = "TwinMaker Workspace ID"
}

output "workspace_arn" {
  value       = awscc_iottwinmaker_workspace.main.arn
  description = "TwinMaker Workspace ARN"
}

output "s3_bucket_name" {
  value       = aws_s3_bucket.twinmaker.bucket
  description = "S3 bucket for TwinMaker workspace data"
}

output "s3_bucket_arn" {
  value       = aws_s3_bucket.twinmaker.arn
  description = "S3 bucket ARN"
}

output "scene_glb_url" {
  value       = local.has_scene_assets ? "s3://${aws_s3_bucket.twinmaker.bucket}/scene_assets/scene.glb" : ""
  description = "S3 URL of uploaded GLB model"
}

output "scene_json_url" {
  value       = local.has_scene_assets ? "s3://${aws_s3_bucket.twinmaker.bucket}/scene_assets/scene.json" : ""
  description = "S3 URL of uploaded scene.json configuration"
}

output "scene_id" {
  value       = local.has_scene_assets ? awscc_iottwinmaker_scene.main[0].scene_id : null
  description = "TwinMaker Scene ID"
}

output "iam_role_arn" {
  value       = aws_iam_role.twinmaker.arn
  description = "IAM Role ARN for TwinMaker"
}

output "test_summary" {
  value = <<-EOT
============================================================
✅ AWS TwinMaker E2E Test Complete
    
Workspace ID: ${awscc_iottwinmaker_workspace.main.workspace_id}
S3 Bucket: ${aws_s3_bucket.twinmaker.bucket}
Region: ${var.aws_region}

Scene Assets:
  GLB: ${local.has_scene_assets ? "scene.glb uploaded" : "N/A (no scene assets)"}
  Config: ${local.has_scene_assets ? "scene.json uploaded" : "N/A"}
  Scene ID: ${local.has_scene_assets ? "main-scene" : "N/A"}

IAM Role: ${aws_iam_role.twinmaker.name}

Next step: Use Python SDK to create component types and entities.
============================================================
EOT
  description = "Test summary"
}

# ============================================================================
# Console Links (for manual inspection)
# ============================================================================

output "aws_twinmaker_console_url" {
  description = "Direct link to AWS TwinMaker console for this workspace"
  value = "https://${var.aws_region}.console.aws.amazon.com/iottwinmaker/home?region=${var.aws_region}#/workspaces/${awscc_iottwinmaker_workspace.main.workspace_id}"
}

output "aws_s3_console_url" {
  description = "AWS Console link to S3 bucket"
  value = "https://s3.console.aws.amazon.com/s3/buckets/${aws_s3_bucket.twinmaker.bucket}?region=${var.aws_region}"
}

output "aws_access_instructions" {
  description = "How to access AWS TwinMaker and Scene Viewer"
  value = <<-EOT
========== AWS TwinMaker Access ==========
Workspace ID: ${awscc_iottwinmaker_workspace.main.workspace_id}
Region: ${var.aws_region}

TwinMaker Console: 
  https://${var.aws_region}.console.aws.amazon.com/iottwinmaker/home?region=${var.aws_region}

Scene Viewer (requires Grafana with TwinMaker plugin):
  Workspace ID: ${awscc_iottwinmaker_workspace.main.workspace_id}
  Scene ID: ${local.has_scene_assets ? "main-scene" : "N/A"}

S3 Console: 
  https://s3.console.aws.amazon.com/s3/buckets/${aws_s3_bucket.twinmaker.bucket}
===========================================
EOT
}
