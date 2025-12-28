# AWS Step Functions E2E Test
# 
# This is a focused Terraform config to test ONLY:
# - AWS Step Functions state machine creation
# - State machine definition file upload
# - IAM role and policy for Step Functions
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

variable "test_name_suffix" {
  description = "Suffix for resource names (for unique naming)"
  type        = string
  default     = "e2e"
}

variable "state_machine_definition" {
  description = "Path to state machine definition JSON file (optional, uses default if not provided)"
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
# Locals
# =============================================================================

locals {
  name_prefix = "sfn-${var.test_name_suffix}"
  
  # Default state machine definition if not provided via file
  default_definition = {
    Comment = "E2E Test State Machine"
    StartAt = "WaitState"
    States = {
      WaitState = {
        Type    = "Wait"
        Seconds = 1
        Next    = "PassState"
      }
      PassState = {
        Type   = "Pass"
        Result = {
          message = "Hello from Step Functions E2E Test!"
          timestamp = "$$.State.EnteredTime"
        }
        End = true
      }
    }
  }
  
  # Load from file if provided, otherwise use default
  state_machine_definition = var.state_machine_definition != "" ? file(var.state_machine_definition) : jsonencode(local.default_definition)
}

# =============================================================================
# IAM Role for Step Functions
# =============================================================================

resource "aws_iam_role" "step_functions" {
  name = "${local.name_prefix}-role"

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
    Purpose = "step-functions-e2e-test"
  }
}

# CloudWatch Logs policy for Step Functions
resource "aws_iam_role_policy" "step_functions_logs" {
  name = "${local.name_prefix}-logs-policy"
  role = aws_iam_role.step_functions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogDelivery",
        "logs:GetLogDelivery",
        "logs:UpdateLogDelivery",
        "logs:DeleteLogDelivery",
        "logs:ListLogDeliveries",
        "logs:PutResourcePolicy",
        "logs:DescribeResourcePolicies",
        "logs:DescribeLogGroups"
      ]
      Resource = "*"
    }]
  })
}

# =============================================================================
# CloudWatch Log Group for Step Functions
# =============================================================================

resource "aws_cloudwatch_log_group" "step_functions" {
  name              = "/aws/states/${local.name_prefix}"
  retention_in_days = 1  # Minimal retention for test
  
  tags = {
    Purpose = "step-functions-e2e-test"
  }
}

# =============================================================================
# Step Functions State Machine
# =============================================================================

resource "aws_sfn_state_machine" "test" {
  name     = local.name_prefix
  role_arn = aws_iam_role.step_functions.arn
  type     = "STANDARD"  # or "EXPRESS" for short-duration workflows

  definition = local.state_machine_definition

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.step_functions.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tags = {
    Purpose = "step-functions-e2e-test"
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

output "log_group_name" {
  description = "CloudWatch Log Group for state machine logs"
  value       = aws_cloudwatch_log_group.step_functions.name
}

output "test_summary" {
  description = "Summary of the test"
  value = <<-EOT
    ✅ AWS Step Functions E2E Test Complete
    
    State Machine Name: ${aws_sfn_state_machine.test.name}
    State Machine ARN: ${aws_sfn_state_machine.test.arn}
    Status: ${aws_sfn_state_machine.test.status}
    Region: ${var.aws_region}
    
    You can execute the state machine from the AWS Console or CLI:
    aws stepfunctions start-execution --state-machine-arn ${aws_sfn_state_machine.test.arn}
  EOT
}
