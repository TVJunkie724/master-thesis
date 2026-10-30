# Fixed research cut. Existing L3 runtime, independent read-only L5 consumer.
terraform {
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.92" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
variable "prefix" { type = string }
variable "region" { type = string }
variable "package_path" { type = string }
provider "aws" { region = var.region }
resource "random_password" "cursor" {
  length  = 64
  special = false
}
resource "aws_dynamodb_table" "raw" {
  name         = "${var.prefix}-raw"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "device_id"
  range_key    = "event_id"
  attribute {
    name = "device_id"
    type = "S"
  }
  attribute {
    name = "event_id"
    type = "S"
  }
  attribute {
    name = "stored_at_event_id"
    type = "S"
  }
  global_secondary_index {
    name            = "device-stored-at-index"
    hash_key        = "device_id"
    range_key       = "stored_at_event_id"
    projection_type = "ALL"
  }
}
resource "aws_dynamodb_table" "rollup" {
  name         = "${var.prefix}-rollup"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "device_metric"
  range_key    = "bucket_start"
  attribute {
    name = "device_metric"
    type = "S"
  }
  attribute {
    name = "bucket_start"
    type = "S"
  }
}
resource "aws_iam_role" "runtime" {
  for_each           = toset(["reader", "visualization"])
  name               = "${var.prefix}-${each.key}"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_cloudwatch_log_group" "runtime" {
  for_each          = toset(["reader", "visualization"])
  name              = "/aws/lambda/${var.prefix}-${each.key}"
  retention_in_days = 1
}
resource "aws_iam_role_policy" "logs" {
  for_each = toset(["reader", "visualization"])
  name     = "logs"
  role     = aws_iam_role.runtime[each.key].id
  policy   = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.runtime[each.key].arn}:*" }] })
}
resource "aws_iam_role_policy" "reader" {
  name   = "query-history"
  role   = aws_iam_role.runtime["reader"].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["dynamodb:Query"], Resource = [aws_dynamodb_table.raw.arn, "${aws_dynamodb_table.raw.arn}/index/*", aws_dynamodb_table.rollup.arn] }] })
}
resource "aws_lambda_function" "reader" {
  function_name                  = "${var.prefix}-reader"
  role                           = aws_iam_role.runtime["reader"].arn
  filename                       = var.package_path
  source_code_hash               = filebase64sha256(var.package_path)
  handler                        = "handler.raw_history_reader"
  runtime                        = "python3.12"
  timeout                        = 15
  memory_size                    = 512
  reserved_concurrent_executions = 2
  environment {
    variables = { RAW_TABLE_NAME = aws_dynamodb_table.raw.name, ROLLUP_TABLE_NAME = aws_dynamodb_table.rollup.name, CURSOR_HMAC_KEY = random_password.cursor.result }
  }
  depends_on = [aws_iam_role_policy.reader, aws_iam_role_policy.logs]
}
resource "aws_lambda_function_url" "reader" {
  function_name      = aws_lambda_function.reader.function_name
  authorization_type = "AWS_IAM"
}
resource "aws_iam_role_policy" "visualization" {
  name   = "invoke-reader-only"
  role   = aws_iam_role.runtime["visualization"].id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"], Resource = aws_lambda_function.reader.arn }] })
}
resource "aws_lambda_function" "visualization" {
  function_name                  = "${var.prefix}-visualization"
  role                           = aws_iam_role.runtime["visualization"].arn
  filename                       = var.package_path
  source_code_hash               = filebase64sha256(var.package_path)
  handler                        = "handler.visualization"
  runtime                        = "python3.12"
  timeout                        = 30
  memory_size                    = 512
  reserved_concurrent_executions = 2
  environment {
    variables = { L3_READER_URL = aws_lambda_function_url.reader.function_url, L5_DEVICE_ID = "l5-device", L5_METRIC = "temperature" }
  }
  depends_on = [aws_iam_role_policy.visualization, aws_iam_role_policy.logs]
}
resource "aws_lambda_function_url" "visualization" {
  function_name      = aws_lambda_function.visualization.function_name
  authorization_type = "AWS_IAM"
}
output "reader_url" { value = aws_lambda_function_url.reader.function_url }
output "visualization_url" { value = aws_lambda_function_url.visualization.function_url }
