# AWS implementation of the independent six-layer-eventing@1 responsibility.
# The bundle is intentionally static and bounded to the reviewed thesis PoC:
# Two Kinesis event logs, SNS/SQS FIFO control, bounded delivery Lambdas, one
# S3 telemetry failure store, and one shared CloudWatch log group.

locals {
  aws_event_enabled = (
    local.six_layer_eventing_enabled &&
    var.event_layer_provider == "aws"
  )
  aws_event_l1_local = local.aws_event_enabled && var.layer_1_provider == "aws"
  aws_event_l2_local = local.aws_event_enabled && var.layer_2_provider == "aws"
  aws_event_hot_local = (
    local.aws_event_enabled && var.layer_3_hot_provider == "aws"
  )
  aws_event_name    = substr(replace(lower(var.digital_twin_name), "_", "-"), 0, 32)
  aws_event_package = "${var.project_path}/.build/aws/six-layer-eventing.zip"
  aws_event_streams = {
    received  = "${local.aws_event_name}-domain-received"
    processed = "${local.aws_event_name}-domain-processed"
  }
  aws_event_stream_consumers = merge(
    local.aws_event_l2_local ? {
      telemetry-processor = { stream = "received" }
    } : {},
    {
      for role in local.aws_event_local_processed_roles : role => {
        stream = "processed"
      }
    },
    {
      for channel in keys(local.aws_six_layer_event_bridge_streams) :
      "bridge-${channel}" => { stream = channel }
    },
  )
  aws_event_local_processed_roles = concat(
    local.aws_event_hot_local ? [
      "historical-persistence",
      "twin-state-update",
    ] : [],
    local.aws_event_l2_local ? ["rule-evaluator"] : [],
    var.aws_event_kinesis_shards == 200 ? [
      "audit",
      "realtime-visualization",
    ] : [],
  )
  aws_event_runtime_roles = merge(
    local.aws_event_l2_local ? {
      telemetry-processor = local.aws_event_stream_consumers["telemetry-processor"]
    } : {},
    {
      for role in local.aws_event_local_processed_roles : role =>
      local.aws_event_stream_consumers[role]
    },
    local.aws_event_l1_local || local.aws_event_l2_local || local.aws_event_hot_local ? {
      control-router = { stream = null }
    } : {},
  )
  aws_event_local_control_event_types = concat(
    local.aws_event_l2_local ? [
      "event.matched.v1",
      "notification.requested.v1",
    ] : [],
    local.aws_event_hot_local ? [
      "extension.action.outcome.v1",
      "notification.workflow.outcome.v1",
      "device.command.outcome.v1",
    ] : [],
    local.aws_event_l1_local ? ["device.command.requested.v1"] : [],
  )
  aws_event_retention_hours = coalesce(
    var.aws_event_retention_hours,
    var.aws_event_kinesis_shards == 1 ? 24 : 168,
  )
  aws_event_tags = merge(local.aws_common_tags, {
    ArchitectureProfile = "six-layer-eventing@1"
    Responsibility      = "eventing"
  })
}

resource "terraform_data" "aws_eventing_capacity_guard" {
  count = local.aws_event_enabled ? 1 : 0

  input = {
    shards          = var.aws_event_kinesis_shards
    retention_hours = local.aws_event_retention_hours
  }

  lifecycle {
    precondition {
      condition     = var.aws_event_kinesis_shards != null
      error_message = "AWS Event Layer requires the optimizer-derived Kinesis shard allocation."
    }
  }
}

resource "aws_cloudwatch_log_group" "eventing" {
  count             = local.aws_event_enabled ? 1 : 0
  name              = "/twin2multicloud/${local.aws_event_name}/six-layer-eventing"
  retention_in_days = var.aws_event_log_retention_days
  tags              = local.aws_event_tags
}

resource "aws_kinesis_stream" "domain_telemetry" {
  for_each         = local.aws_event_enabled ? local.aws_event_streams : {}
  name             = each.value
  shard_count      = var.aws_event_kinesis_shards
  retention_period = local.aws_event_retention_hours

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }

  tags       = local.aws_event_tags
  depends_on = [terraform_data.aws_eventing_capacity_guard]
}

resource "aws_kinesis_stream_consumer" "domain_consumers" {
  for_each   = local.aws_event_enabled ? local.aws_event_stream_consumers : {}
  name       = "${local.aws_event_name}-${each.key}"
  stream_arn = aws_kinesis_stream.domain_telemetry[each.value.stream].arn
}

resource "aws_sns_topic" "domain_control" {
  count                       = local.aws_event_enabled ? 1 : 0
  name                        = "${local.aws_event_name}-domain-control.fifo"
  fifo_topic                  = true
  content_based_deduplication = false
  archive_policy = jsonencode({
    MessageRetentionPeriod = tostring(var.aws_event_control_archive_hours / 24)
  })
  tags = local.aws_event_tags
}

resource "aws_sqs_queue" "event_control_dlq" {
  count                       = local.aws_event_enabled ? 1 : 0
  name                        = "${local.aws_event_name}-domain-control-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  message_retention_seconds   = min(1209600, var.aws_event_dlq_retention_hours * 3600)
  tags                        = local.aws_event_tags
}

resource "aws_sqs_queue" "domain_control" {
  count                       = local.aws_event_enabled ? 1 : 0
  name                        = "${local.aws_event_name}-domain-control.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  message_retention_seconds   = min(1209600, local.aws_event_retention_hours * 3600)
  visibility_timeout_seconds  = 180
  receive_wait_time_seconds   = 20
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.event_control_dlq[0].arn
    maxReceiveCount     = var.aws_event_max_receive_count
  })
  tags = local.aws_event_tags
}

resource "aws_sqs_queue_redrive_allow_policy" "event_control" {
  count     = local.aws_event_enabled ? 1 : 0
  queue_url = aws_sqs_queue.event_control_dlq[0].id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.domain_control[0].arn]
  })
}

resource "aws_sqs_queue_policy" "event_control" {
  count     = local.aws_event_enabled ? 1 : 0
  queue_url = aws_sqs_queue.domain_control[0].url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowEventLayerControlTopic"
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.domain_control[0].arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_sns_topic.domain_control[0].arn
        }
      }
    }]
  })
}

resource "aws_sns_topic_subscription" "domain_control" {
  count                = length(local.aws_event_local_control_event_types) > 0 ? 1 : 0
  topic_arn            = aws_sns_topic.domain_control[0].arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.domain_control[0].arn
  raw_message_delivery = true
  filter_policy = jsonencode({
    event_type = local.aws_event_local_control_event_types
  })
  depends_on = [aws_sqs_queue_policy.event_control]
}

resource "aws_s3_bucket" "event_telemetry_dlq" {
  count         = local.aws_event_enabled ? 1 : 0
  bucket        = "${local.aws_event_name}-event-fail-${local.deployment_suffix}"
  force_destroy = true
  tags          = local.aws_event_tags
}

resource "aws_s3_bucket_public_access_block" "event_telemetry_dlq" {
  count                   = local.aws_event_enabled ? 1 : 0
  bucket                  = aws_s3_bucket.event_telemetry_dlq[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "event_telemetry_dlq" {
  count  = local.aws_event_enabled ? 1 : 0
  bucket = aws_s3_bucket.event_telemetry_dlq[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "event_telemetry_dlq" {
  count  = local.aws_event_enabled ? 1 : 0
  bucket = aws_s3_bucket.event_telemetry_dlq[0].id

  rule {
    id     = "expire-event-delivery-failures"
    status = "Enabled"

    filter {}

    expiration {
      days = var.aws_event_dlq_retention_hours / 24
    }
  }

  depends_on = [aws_s3_bucket_public_access_block.event_telemetry_dlq]
}

resource "aws_iam_role" "event_runtime" {
  count = local.aws_event_enabled ? 1 : 0
  name  = "${local.aws_event_name}-event-runtime-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.aws_event_tags
}

resource "aws_iam_role_policy_attachment" "event_runtime_logs" {
  count      = local.aws_event_enabled ? 1 : 0
  role       = aws_iam_role.event_runtime[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "event_runtime" {
  count = local.aws_event_enabled ? 1 : 0
  name  = "${local.aws_event_name}-event-runtime"
  role  = aws_iam_role.event_runtime[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [{
        Effect = "Allow"
        Action = [
          "kinesis:DescribeStream",
          "kinesis:DescribeStreamSummary",
          "kinesis:GetRecords",
          "kinesis:GetShardIterator",
          "kinesis:ListShards",
          "kinesis:SubscribeToShard",
        ]
        Resource = concat(
          [for stream in aws_kinesis_stream.domain_telemetry : stream.arn],
          [for consumer in aws_kinesis_stream_consumer.domain_consumers : consumer.arn],
        )
        }, {
        Effect = "Allow"
        Action = [
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ReceiveMessage",
        ]
        Resource = aws_sqs_queue.domain_control[0].arn
        }, {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.event_control_dlq[0].arn
        }, {
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:PutObject",
        ]
        Resource = [
          aws_s3_bucket.event_telemetry_dlq[0].arn,
          "${aws_s3_bucket.event_telemetry_dlq[0].arn}/*",
        ]
        Condition = {
          StringEquals = {
            "s3:ResourceAccount" = data.aws_caller_identity.current[0].account_id
          }
        }
      }],
      local.aws_event_l2_local ? [{
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.aws_aws_lambda[0].arn
      }] : [],
      local.aws_event_hot_local ? [{
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.aws_six_layer_domain_consumer[0].arn
      }] : [],
      local.aws_event_l1_local ? [{
        Effect = "Allow"
        Action = ["iot:StartCommandExecution"]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:command/*",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:thing/*",
        ]
      }] : [],
      local.aws_event_l1_local ? [{
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = aws_sns_topic.domain_control[0].arn
      }] : [],
    )
  })
}

resource "aws_lambda_function" "event_runtime" {
  for_each      = local.aws_event_runtime_roles
  function_name = "${local.aws_event_name}-event-${each.key}"
  role          = aws_iam_role.event_runtime[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = local.python_runtime_aws
  timeout       = 60
  memory_size   = var.aws_event_runtime_memory_mib

  filename         = local.aws_event_package
  source_code_hash = filebase64sha256(local.aws_event_package)

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.eventing[0].name
  }

  environment {
    variables = {
      ARCHITECTURE_PROFILE      = "six-layer-eventing@1"
      AWS_ACCOUNT_ID            = data.aws_caller_identity.current[0].account_id
      CONSUMER_ROLE             = each.key
      CONTROL_FAILURE_QUEUE_URL = aws_sqs_queue.event_control_dlq[0].url
      CONTROL_TOPIC_ARN         = aws_sns_topic.domain_control[0].arn
      DEVICE_COMMAND_ARN        = try(awscc_iot_command.aws_aws_iot_commands[0].command_arn, "")
      IOT_COMMANDS_ENDPOINT     = try(data.aws_iot_endpoint.main[0].endpoint_address, "")
      MAX_RECEIVE_COUNT         = tostring(var.aws_event_max_receive_count)
      PROCESSING_FUNCTION_NAME  = local.aws_event_l2_local ? aws_lambda_function.aws_aws_lambda[0].function_name : ""
      HOT_FUNCTION_NAME         = local.aws_event_hot_local ? aws_lambda_function.aws_six_layer_domain_consumer[0].function_name : ""
    }
  }

  tags = local.aws_event_tags
  depends_on = [
    aws_cloudwatch_log_group.eventing,
    aws_iam_role_policy_attachment.event_runtime_logs,
    aws_iam_role_policy.event_runtime,
  ]
}

resource "aws_lambda_event_source_mapping" "event_runtime" {
  for_each = {
    for role, consumer in local.aws_event_runtime_roles : role => consumer
    if consumer.stream != null
  }
  event_source_arn                   = aws_kinesis_stream_consumer.domain_consumers[each.key].arn
  function_name                      = aws_lambda_function.event_runtime[each.key].arn
  starting_position                  = "TRIM_HORIZON"
  batch_size                         = var.aws_event_runtime_batch_max
  maximum_batching_window_in_seconds = 1
  parallelization_factor             = 1
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_retry_attempts             = var.aws_event_max_receive_count - 1
  maximum_record_age_in_seconds      = 86400
  bisect_batch_on_function_error     = true
  destination_config {
    on_failure {
      destination_arn = aws_s3_bucket.event_telemetry_dlq[0].arn
    }
  }
  enabled = true
}

resource "aws_lambda_event_source_mapping" "domain_control" {
  count                              = local.aws_event_l1_local || local.aws_event_l2_local || local.aws_event_hot_local ? 1 : 0
  event_source_arn                   = aws_sqs_queue.domain_control[0].arn
  function_name                      = aws_lambda_function.event_runtime["control-router"].arn
  batch_size                         = var.aws_event_runtime_batch_max
  maximum_batching_window_in_seconds = 0
  function_response_types            = ["ReportBatchItemFailures"]
  enabled                            = true
}

output "aws_event_kinesis_arn" {
  value = local.aws_event_enabled ? aws_kinesis_stream.domain_telemetry["received"].arn : null
}

output "aws_event_control_topic_arn" {
  value = local.aws_event_enabled ? aws_sns_topic.domain_control[0].arn : null
}

output "aws_event_control_queue_arn" {
  value = local.aws_event_enabled ? aws_sqs_queue.domain_control[0].arn : null
}

output "aws_event_runtime_arn" {
  value = try(aws_lambda_function.event_runtime["control-router"].arn, null)
}

output "aws_event_telemetry_dlq_arn" {
  value = local.aws_event_enabled ? aws_s3_bucket.event_telemetry_dlq[0].arn : null
}

output "aws_event_log_group" {
  value = local.aws_event_enabled ? aws_cloudwatch_log_group.eventing[0].name : null
}
