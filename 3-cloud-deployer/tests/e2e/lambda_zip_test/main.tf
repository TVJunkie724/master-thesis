
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  type    = string
  default = "eu-west-1"
}

variable "test_id" {
  type    = string
  default = "zip-test"
}

variable "lambda_zip_path" {
  type = string
}

provider "aws" {
  region = var.aws_region
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.test_id}-lambda-role"

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
}

# CloudWatch Logs policy
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda Function
resource "aws_lambda_function" "test_lambda" {
  function_name = "${var.test_id}-lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 128

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
}

# Function URL for easy testing
resource "aws_lambda_function_url" "test_url" {
  function_name      = aws_lambda_function.test_lambda.function_name
  authorization_type = "NONE"
}

# Outputs
output "lambda_function_name" {
  value = aws_lambda_function.test_lambda.function_name
}

output "lambda_function_arn" {
  value = aws_lambda_function.test_lambda.arn
}

output "lambda_function_url" {
  value = aws_lambda_function_url.test_url.function_url
}
