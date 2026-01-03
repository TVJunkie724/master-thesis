# AWS Step Functions Isolated E2E Test
#
# This Terraform config replicates the PRODUCTION deployment pattern:
# 1. Creates IAM role for Step Functions
# 2. Creates Step Functions state machine with definition from JSON file
#
# This matches the production code in aws_compute.tf
#
# Usage:
#   cd tests/e2e/aws_stepfunctions_test
#   terraform init
#   terraform plan -var-file=test.tfvars.json
#   terraform apply -var-file=test.tfvars.json
#   terraform destroy -var-file=test.tfvars.json

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "aws_access_key_id" {
  description = "AWS Access Key ID"
  type        = string
  sensitive   = true
}

variable "aws_secret_access_key" {
  description = "AWS Secret Access Key"
  type        = string
  sensitive   = true
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "eu-central-1"
}

variable "test_name" {
  description = "Name for the test resources (must be globally unique)"
  type        = string
  default     = "sfn-iso-e2e"
}

variable "state_machine_definition_file" {
  description = "Path to state machine definition JSON file (optional, uses default if empty)"
  type        = string
  default     = ""
}

# =============================================================================
# Provider
# =============================================================================

provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key_id
  secret_key = var.aws_secret_access_key
}

# =============================================================================
# IAM Role for Step Functions
# =============================================================================

resource "aws_iam_role" "step_functions" {
  name = "${var.test_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })

  tags = {
    Purpose = "step-functions-isolated-e2e-test"
  }
}

# Lambda invoke policy (allows invoking functions for test workflows)
resource "aws_iam_role_policy" "step_functions_lambda" {
  name = "${var.test_name}-lambda-policy"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "lambda:InvokeFunction"
      ]
      Resource = "*"
    }]
  })
}

# =============================================================================
# Step Functions State Machine
# =============================================================================

resource "aws_sfn_state_machine" "test" {
  name     = var.test_name
  role_arn = aws_iam_role.step_functions.arn

  # Load definition from file if provided, otherwise use default (matches production pattern)
  definition = var.state_machine_definition_file != "" ? file(var.state_machine_definition_file) : jsonencode({
    Comment = "Test Step Functions workflow"
    StartAt = "PassState"
    States = {
      PassState = {
        Type   = "Pass"
        Result = { message = "Hello from Step Functions E2E Test!" }
        End    = true
      }
    }
  })

  tags = {
    Purpose = "step-functions-isolated-e2e-test"
  }
}

# =============================================================================
# Outputs
# =============================================================================

output "state_machine_arn" {
  description = "ARN of the created state machine"
  value       = aws_sfn_state_machine.test.arn
}

output "state_machine_name" {
  description = "Name of the created state machine"
  value       = aws_sfn_state_machine.test.name
}

output "state_machine_status" {
  description = "Status of the state machine"
  value       = aws_sfn_state_machine.test.status
}

output "iam_role_arn" {
  description = "ARN of the IAM role for Step Functions"
  value       = aws_iam_role.step_functions.arn
}

output "console_url" {
  description = "AWS Console URL for the state machine"
  value       = "https://${var.aws_region}.console.aws.amazon.com/states/home?region=${var.aws_region}#/statemachines/view/${aws_sfn_state_machine.test.arn}"
}

output "test_summary" {
  description = "Summary of the test"
  value = <<-EOT
    
    ============================================================
    AWS STEP FUNCTIONS ISOLATED E2E TEST COMPLETE
    ============================================================
    
    State Machine: ${aws_sfn_state_machine.test.name}
    ARN: ${aws_sfn_state_machine.test.arn}
    Status: ${aws_sfn_state_machine.test.status}
    Region: ${var.aws_region}
    
    VERIFICATION:
    1. Open the Console URL below
    2. Verify the state machine shows the workflow
    3. Optionally run an execution to test
    
    Console URL:
    https://${var.aws_region}.console.aws.amazon.com/states/home?region=${var.aws_region}#/statemachines/view/${aws_sfn_state_machine.test.arn}
    
    CLI Execution:
    aws stepfunctions start-execution --state-machine-arn ${aws_sfn_state_machine.test.arn}
    
    ============================================================
  EOT
}
