# AWS implementation of five-layer-baseline@2.
#
# The profile deliberately keeps embedded eventing inside the five scientific
# layers. Shared resources therefore use one concrete Terraform address even
# when more than one resolved graph node references them.

locals {
  aws_v2_l1_enabled      = local.five_layer_v2_enabled && var.layer_1_provider == "aws"
  aws_v2_l2_enabled      = local.five_layer_v2_enabled && var.layer_2_provider == "aws"
  aws_v2_hot_enabled     = local.five_layer_v2_enabled && var.layer_3_hot_provider == "aws"
  aws_v2_cool_enabled    = local.five_layer_v2_enabled && var.layer_3_cold_provider == "aws"
  aws_v2_archive_enabled = local.five_layer_v2_enabled && var.layer_3_archive_provider == "aws"
  aws_v2_l4_enabled      = local.five_layer_v2_enabled && var.layer_4_provider == "aws"
  aws_v2_l5_enabled      = local.five_layer_v2_enabled && var.layer_5_provider == "aws"

  aws_v2_event_enabled = (
    local.aws_v2_l1_enabled || local.aws_v2_l2_enabled ||
    local.aws_v2_hot_enabled || local.aws_v2_l4_enabled
  )
  # The owner of the source tier runs the finite mover. DynamoDB -> S3 always
  # needs one; S3 -> archive needs one only across provider boundaries.
  aws_v2_storage_mover_enabled = (
    local.aws_v2_hot_enabled ||
    (local.aws_v2_cool_enabled && var.layer_3_archive_provider != "aws")
  )
  aws_v2_storage_task_count = tonumber(lookup(
    var.resolved_component_dimensions,
    "dimension.aws.aws.ecs-fargate-storage-mover.task_count",
    "0",
  ))
  aws_v2_storage_jobs = merge(
    local.aws_v2_hot_enabled ? {
      hot-to-cool = {
        source_provider      = "aws"
        destination_provider = var.layer_3_cold_provider
        schedule             = "rate(5 minutes)"
      }
    } : {},
    local.aws_v2_cool_enabled && var.layer_3_archive_provider != "aws" ? {
      cool-to-archive = {
        source_provider      = "aws"
        destination_provider = var.layer_3_archive_provider
        schedule             = "rate(1 day)"
      }
    } : {},
  )
  aws_v2_storage_schedule_tasks = {
    for item in flatten([
      for transition, job in local.aws_v2_storage_jobs : [
        for task_index in range(local.aws_v2_storage_task_count) : {
          key         = "${transition}-${format("%03d", task_index)}"
          transition  = transition
          task_index  = task_index
          source      = job.source_provider
          destination = job.destination_provider
          schedule    = job.schedule
        }
      ]
    ]) : item.key => item
  }
  aws_v2_object_store_enabled = local.aws_v2_cool_enabled || local.aws_v2_archive_enabled

  aws_v2_outbound_event_routes = {
    for route in var.resolved_cross_cloud_routes : route.route_id => route
    if local.five_layer_v2_enabled && route.execution_kind == "source_event_forwarder" && route.source_provider == "aws"
  }
  aws_v2_image_foundation_enabled = (
    local.aws_v2_storage_mover_enabled || length(local.aws_v2_outbound_event_routes) > 0
  )
  aws_v2_inbound_event_routes = {
    for route in var.resolved_cross_cloud_routes : route.route_id => route
    if local.five_layer_v2_enabled && route.execution_kind == "source_event_forwarder" && route.destination_provider == "aws"
  }
  aws_v2_remote_telemetry_outbound = anytrue([
    for route in values(local.aws_v2_outbound_event_routes) : route.channel_class == "telemetry"
  ])
  aws_v2_remote_telemetry_inbound = anytrue([
    for route in values(local.aws_v2_inbound_event_routes) : route.channel_class == "telemetry"
  ])
  aws_v2_remote_telemetry_routes = {
    for direction, enabled in {
      inbound  = local.aws_v2_remote_telemetry_inbound
      outbound = local.aws_v2_remote_telemetry_outbound
    } : direction => direction if enabled
  }
  aws_v2_remote_telemetry_enabled = length(local.aws_v2_remote_telemetry_routes) > 0

  aws_v2_remote_control_outbound = anytrue([
    for route in values(local.aws_v2_outbound_event_routes) : route.channel_class == "control"
  ])
  aws_v2_remote_control_inbound = anytrue([
    for route in values(local.aws_v2_inbound_event_routes) : route.channel_class == "control"
  ])
  aws_v2_remote_control_routes = {
    for direction, enabled in {
      inbound  = local.aws_v2_remote_control_inbound
      outbound = local.aws_v2_remote_control_outbound
    } : direction => direction if enabled
  }
  aws_v2_remote_control_enabled  = length(local.aws_v2_remote_control_routes) > 0
  aws_v2_domain_consumer_enabled = local.aws_v2_remote_telemetry_inbound || local.aws_v2_remote_control_inbound

  aws_v2_runtime_package = "${var.project_path}/.build/aws/five-layer-v2.zip"
  aws_v2_name            = substr(replace(lower(var.digital_twin_name), "_", "-"), 0, 32)
  aws_v2_processor_extensions = local.aws_v2_l2_enabled ? {
    for package in var.validated_extension_packages : package.artifact_id => package
    if package.slot_id == "processor.telemetry" && package.slot_version == "1"
  } : {}
  aws_v2_tags = merge(local.aws_common_tags, {
    ArchitectureProfile = "five-layer-baseline@2"
  })
}

resource "terraform_data" "aws_v2_processor_extension_guard" {
  count = local.aws_v2_l2_enabled ? 1 : 0

  input = {
    package_count = length(local.aws_v2_processor_extensions)
  }

  lifecycle {
    precondition {
      condition     = length(local.aws_v2_processor_extensions) == 1
      error_message = "AWS Five-layer v2 requires exactly one validated processor.telemetry@1 package."
    }
  }
}

# -----------------------------------------------------------------------------
# Embedded eventing and L1 acquisition
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "aws_aws_cloudwatch" {
  count             = local.aws_v2_event_enabled || local.aws_v2_storage_mover_enabled || local.aws_v2_l5_enabled ? 1 : 0
  name              = "/twin2multicloud/${local.aws_v2_name}/five-layer-v2"
  retention_in_days = var.log_retention_days
  tags              = local.aws_v2_tags
}

resource "aws_sqs_queue" "aws_aws_sqs_fifo" {
  count                       = local.aws_v2_event_enabled ? 1 : 0
  name                        = "${local.aws_v2_name}-embedded-events.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  visibility_timeout_seconds  = 60
  message_retention_seconds   = 1209600
  receive_wait_time_seconds   = 20
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.aws_v2_embedded_failure[0].arn
    maxReceiveCount     = 5
  })
  tags = local.aws_v2_tags
}

resource "aws_sqs_queue" "aws_v2_embedded_failure" {
  count                      = local.aws_v2_event_enabled ? 1 : 0
  name                       = "${local.aws_v2_name}-embedded-failure.fifo"
  fifo_queue                 = true
  message_retention_seconds  = 1209600
  receive_wait_time_seconds  = 20
  visibility_timeout_seconds = 60
  tags                       = local.aws_v2_tags
}

resource "aws_sqs_queue" "aws_v2_remote_failure" {
  count                      = local.aws_v2_remote_telemetry_inbound || local.aws_v2_remote_control_inbound ? 1 : 0
  name                       = "${local.aws_v2_name}-remote-failure"
  message_retention_seconds  = 1209600
  receive_wait_time_seconds  = 20
  visibility_timeout_seconds = 60
  tags                       = local.aws_v2_tags
}

resource "aws_sqs_queue" "aws_v2_remote_control" {
  count                       = local.aws_v2_remote_control_inbound ? 1 : 0
  name                        = "${local.aws_v2_name}-remote-control-landing.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  message_retention_seconds   = 1209600
  receive_wait_time_seconds   = 20
  visibility_timeout_seconds  = 60
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.aws_v2_embedded_failure[0].arn
    maxReceiveCount     = 5
  })
  tags = local.aws_v2_tags
}

resource "aws_sqs_queue_policy" "aws_v2_remote_control" {
  count     = local.aws_v2_remote_control_inbound ? 1 : 0
  queue_url = aws_sqs_queue.aws_v2_remote_control[0].url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowSelectedRemoteControlTopic"
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.aws_v2_remote_control[0].arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["inbound"].arn
        }
      }
    }]
  })
}

resource "aws_kinesis_stream" "aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge" {
  for_each         = local.aws_v2_remote_telemetry_routes
  name             = "${local.aws_v2_name}-remote-telemetry-${each.key}"
  shard_count      = 1
  retention_period = 24

  stream_mode_details {
    stream_mode = "PROVISIONED"
  }

  tags = local.aws_v2_tags
}

resource "aws_sns_topic" "aws_aws_sns_fifo_only_for_reviewed_remote_control_edge" {
  for_each                    = local.aws_v2_remote_control_routes
  name                        = "${local.aws_v2_name}-remote-control-${each.key}.fifo"
  fifo_topic                  = true
  content_based_deduplication = false
  tags                        = local.aws_v2_tags
}

resource "aws_iam_role" "aws_v2_lambda" {
  count = local.aws_v2_event_enabled || local.aws_v2_l5_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-lambda-${local.deployment_suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy_attachment" "aws_v2_lambda_logs" {
  count      = local.aws_v2_event_enabled || local.aws_v2_l5_enabled ? 1 : 0
  role       = aws_iam_role.aws_v2_lambda[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "aws_v2_lambda_data" {
  count = local.aws_v2_event_enabled || local.aws_v2_l5_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-runtime-data"
  role  = aws_iam_role.aws_v2_lambda[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      local.aws_v2_event_enabled ? [{
        Effect = "Allow"
        Action = ["sqs:GetQueueAttributes", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:SendMessage"]
        Resource = concat(
          [
            aws_sqs_queue.aws_aws_sqs_fifo[0].arn,
            aws_sqs_queue.aws_v2_embedded_failure[0].arn,
          ],
          aws_sqs_queue.aws_v2_remote_failure[*].arn,
          aws_sqs_queue.aws_v2_remote_control[*].arn,
        )
      }] : [],
      local.aws_v2_remote_telemetry_enabled ? [{
        Effect   = "Allow"
        Action   = ["kinesis:DescribeStream", "kinesis:GetRecords", "kinesis:GetShardIterator", "kinesis:ListShards", "kinesis:PutRecord"]
        Resource = [for stream in aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge : stream.arn]
      }] : [],
      local.aws_v2_remote_control_enabled ? [{
        Effect   = "Allow"
        Action   = ["sns:Publish"]
        Resource = [for topic in aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge : topic.arn]
      }] : [],
      local.aws_v2_hot_enabled ? [{
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:TransactWriteItems"]
        Resource = [
          aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].arn,
          "${aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].arn}/index/*",
          aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup[0].arn,
        ]
      }] : [],
      local.aws_v2_l1_enabled ? [{
        Effect = "Allow"
        Action = ["iot:StartCommandExecution"]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:command/*",
          "arn:aws:iot:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:thing/*",
        ]
      }] : [],
      local.aws_v2_l2_enabled ? [{
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          aws_lambda_function.aws_v2_extension_action[0].arn,
          one(values(aws_lambda_function.aws_v2_processor_extension)).arn,
        ]
      }] : [],
      local.aws_v2_l2_enabled ? [{
        Effect   = "Allow"
        Action   = ["states:StartExecution"]
        Resource = [aws_sfn_state_machine.aws_aws_step_functions_standard[0].arn]
      }] : [],
      local.aws_v2_l4_enabled ? [{
        Effect = "Allow"
        Action = [
          "iottwinmaker:CreateEntity", "iottwinmaker:GetEntity",
          "iottwinmaker:UpdateEntity", "iottwinmaker:DeleteEntity",
          "iottwinmaker:BatchPutPropertyValues"
        ]
        Resource = ["*"]
      }] : []
    )
  })
}

resource "aws_lambda_function" "aws_aws_lambda_event_adapter" {
  count         = local.aws_v2_event_enabled ? 1 : 0
  function_name = "${local.aws_v2_name}-v2-event-adapter"
  role          = aws_iam_role.aws_v2_lambda[0].arn
  handler       = "handler.event_adapter"
  runtime       = local.python_runtime_aws
  timeout       = 30
  memory_size   = 512

  filename         = local.aws_v2_runtime_package
  source_code_hash = filebase64sha256(local.aws_v2_runtime_package)

  environment {
    variables = {
      ARCHITECTURE_PROFILE      = "five-layer-baseline@2"
      DEPLOYMENT_ID             = local.deployment_suffix
      EVENT_QUEUE_URL           = aws_sqs_queue.aws_aws_sqs_fifo[0].url
      TELEMETRY_STREAM_ARN      = try(aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["outbound"].arn, "")
      CONTROL_TOPIC_ARN         = try(aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["outbound"].arn, "")
      LOCAL_PROCESSING          = tostring(local.aws_v2_l2_enabled)
      HOT_PROVIDER              = var.layer_3_hot_provider
      TWIN_PROVIDER             = var.layer_4_provider
      RAW_TABLE_NAME            = try(aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].name, "")
      ROLLUP_TABLE_NAME         = try(aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup[0].name, "")
      HOT_BOUNDARY_DAYS         = tostring(var.layer_3_hot_to_cold_interval_days)
      SOURCE_EXPIRY_GRACE_HOURS = "48"
      STORAGE_TASK_COUNT        = tostring(local.aws_v2_storage_task_count)
      TWINMAKER_WORKSPACE       = try(awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0].workspace_id, "")
    }
  }
  tags = local.aws_v2_tags
}

resource "aws_iot_thing" "aws_aws_iot_core" {
  count = local.aws_v2_l1_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-poc-gateway"
  attributes = {
    architecture_profile = "five-layer-baseline-v2"
  }
}

resource "aws_iot_topic_rule" "aws_aws_iot_core" {
  count       = local.aws_v2_l1_enabled ? 1 : 0
  name        = replace("${local.aws_v2_name}_v2_telemetry", "-", "_")
  description = "Five-layer v2 telemetry ingress"
  enabled     = true
  sql         = "SELECT * FROM 'dt/${var.digital_twin_name}/+/telemetry'"
  sql_version = "2016-03-23"

  lambda {
    function_arn = aws_lambda_function.aws_aws_lambda_event_adapter[0].arn
  }

  tags = local.aws_v2_tags
}

resource "aws_lambda_permission" "aws_v2_iot_event_adapter" {
  count         = local.aws_v2_l1_enabled ? 1 : 0
  statement_id  = "AllowFiveLayerV2IoT"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.aws_aws_lambda_event_adapter[0].function_name
  principal     = "iot.amazonaws.com"
  source_arn    = aws_iot_topic_rule.aws_aws_iot_core[0].arn
}

resource "awscc_iot_command" "aws_aws_iot_commands" {
  count        = local.aws_v2_l1_enabled ? 1 : 0
  command_id   = "${local.aws_v2_name}-device-command"
  display_name = "${var.digital_twin_name} PoC device command"
  namespace    = "AWS-IoT"
  payload_template = jsonencode({
    message = "$${aws:iot:commandexecution::parameter:message}"
  })
  mandatory_parameters = [{
    name = "message"
    type = "STRING"
  }]
}

# -----------------------------------------------------------------------------
# L2 processing and mandatory embedded workflow
# -----------------------------------------------------------------------------

resource "aws_lambda_function" "aws_aws_lambda" {
  count         = local.aws_v2_l2_enabled ? 1 : 0
  function_name = "${local.aws_v2_name}-v2-processor"
  role          = aws_iam_role.aws_v2_lambda[0].arn
  handler       = "handler.domain_consumer"
  runtime       = local.python_runtime_aws
  timeout       = 30
  memory_size   = 512

  filename         = local.aws_v2_runtime_package
  source_code_hash = filebase64sha256(local.aws_v2_runtime_package)

  environment {
    variables = {
      ARCHITECTURE_PROFILE              = "five-layer-baseline@2"
      DEPLOYMENT_ID                     = local.deployment_suffix
      EVENT_QUEUE_URL                   = aws_sqs_queue.aws_aws_sqs_fifo[0].url
      CONTROL_TOPIC_ARN                 = try(aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["outbound"].arn, "")
      L1_PROVIDER                       = var.layer_1_provider
      RAW_TABLE_NAME                    = try(aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].name, "")
      ROLLUP_TABLE_NAME                 = try(aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup[0].name, "")
      HOT_PROVIDER                      = var.layer_3_hot_provider
      TWIN_PROVIDER                     = var.layer_4_provider
      TELEMETRY_STREAM_ARN              = try(aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["outbound"].arn, "")
      HOT_BOUNDARY_DAYS                 = tostring(var.layer_3_hot_to_cold_interval_days)
      SOURCE_EXPIRY_GRACE_HOURS         = "48"
      STORAGE_TASK_COUNT                = tostring(local.aws_v2_storage_task_count)
      TWINMAKER_WORKSPACE               = try(awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0].workspace_id, "")
      RULES_JSON                        = jsonencode(var.events)
      PROCESSOR_EXTENSION_FUNCTION_NAME = try(one(values(aws_lambda_function.aws_v2_processor_extension)).function_name, "")
      ACTION_FUNCTION_NAME              = try(aws_lambda_function.aws_v2_extension_action[0].function_name, "")
      NOTIFICATION_STATE_MACHINE_ARN    = "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:stateMachine:${local.aws_v2_name}-v2-event-workflow"
      DEVICE_COMMAND_ARN                = try(awscc_iot_command.aws_aws_iot_commands[0].command_arn, "")
      AWS_ACCOUNT_ID                    = data.aws_caller_identity.current[0].account_id
    }
  }
  tags = local.aws_v2_tags
}

resource "aws_iam_role" "aws_v2_extension_action" {
  count = local.aws_v2_l2_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-poc-action-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role" "aws_v2_processor_extension" {
  count = local.aws_v2_l2_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-processor-extension-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy_attachment" "aws_v2_processor_extension_logs" {
  count      = local.aws_v2_l2_enabled ? 1 : 0
  role       = aws_iam_role.aws_v2_processor_extension[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "aws_v2_processor_extension" {
  for_each      = local.aws_v2_processor_extensions
  function_name = "${local.aws_v2_name}-v2-processor-extension"
  role          = aws_iam_role.aws_v2_processor_extension[0].arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.11"
  timeout       = 30
  memory_size   = 256

  filename         = each.value.package_path
  source_code_hash = filebase64sha256(each.value.package_path)

  environment {
    variables = {
      ARCHITECTURE_PROFILE = "five-layer-baseline@2"
    }
  }
  tags = local.aws_v2_tags

  lifecycle {
    precondition {
      condition     = each.value.adapter_id == "adapter.aws.python311" && each.value.adapter_version == "1"
      error_message = "AWS Five-layer v2 requires the reviewed processor.telemetry@1 AWS adapter."
    }
  }

  depends_on = [
    terraform_data.aws_v2_processor_extension_guard,
    terraform_data.validated_extension_package,
    aws_iam_role_policy_attachment.aws_v2_processor_extension_logs,
  ]
}

resource "aws_iam_role_policy_attachment" "aws_v2_extension_action_logs" {
  count      = local.aws_v2_l2_enabled ? 1 : 0
  role       = aws_iam_role.aws_v2_extension_action[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "aws_v2_extension_action" {
  count         = local.aws_v2_l2_enabled ? 1 : 0
  function_name = "${local.aws_v2_name}-v2-poc-action"
  role          = aws_iam_role.aws_v2_extension_action[0].arn
  handler       = "handler.poc_boundary"
  runtime       = local.python_runtime_aws
  timeout       = 30
  memory_size   = 256

  filename         = local.aws_v2_runtime_package
  source_code_hash = filebase64sha256(local.aws_v2_runtime_package)

  environment {
    variables = {
      ARCHITECTURE_PROFILE = "five-layer-baseline@2"
    }
  }
  tags = local.aws_v2_tags

  depends_on = [aws_iam_role_policy_attachment.aws_v2_extension_action_logs]
}

resource "aws_lambda_event_source_mapping" "aws_v2_embedded_events" {
  count                              = local.aws_v2_l2_enabled ? 1 : 0
  event_source_arn                   = aws_sqs_queue.aws_aws_sqs_fifo[0].arn
  function_name                      = aws_lambda_function.aws_aws_lambda[0].arn
  batch_size                         = 1
  maximum_batching_window_in_seconds = 0
  function_response_types            = ["ReportBatchItemFailures"]
  enabled                            = true
}

resource "aws_lambda_function" "aws_v2_domain_consumer" {
  count         = local.aws_v2_domain_consumer_enabled ? 1 : 0
  function_name = "${local.aws_v2_name}-v2-domain-consumer"
  role          = aws_iam_role.aws_v2_lambda[0].arn
  handler       = "handler.domain_consumer"
  runtime       = local.python_runtime_aws
  timeout       = 30
  memory_size   = 512

  filename         = local.aws_v2_runtime_package
  source_code_hash = filebase64sha256(local.aws_v2_runtime_package)

  environment {
    variables = {
      ARCHITECTURE_PROFILE              = "five-layer-baseline@2"
      DEPLOYMENT_ID                     = local.deployment_suffix
      EVENT_QUEUE_URL                   = try(aws_sqs_queue.aws_aws_sqs_fifo[0].url, "")
      TELEMETRY_STREAM_ARN              = try(aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["outbound"].arn, "")
      CONTROL_TOPIC_ARN                 = try(aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["outbound"].arn, "")
      L1_PROVIDER                       = var.layer_1_provider
      HOT_PROVIDER                      = var.layer_3_hot_provider
      TWIN_PROVIDER                     = var.layer_4_provider
      RAW_TABLE_NAME                    = try(aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].name, "")
      ROLLUP_TABLE_NAME                 = try(aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup[0].name, "")
      HOT_BOUNDARY_DAYS                 = tostring(var.layer_3_hot_to_cold_interval_days)
      SOURCE_EXPIRY_GRACE_HOURS         = "48"
      STORAGE_TASK_COUNT                = tostring(local.aws_v2_storage_task_count)
      TWINMAKER_WORKSPACE               = try(awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0].workspace_id, "")
      RULES_JSON                        = jsonencode(var.events)
      PROCESSOR_EXTENSION_FUNCTION_NAME = try(one(values(aws_lambda_function.aws_v2_processor_extension)).function_name, "")
      ACTION_FUNCTION_NAME              = try(aws_lambda_function.aws_v2_extension_action[0].function_name, "")
      NOTIFICATION_STATE_MACHINE_ARN    = "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:stateMachine:${local.aws_v2_name}-v2-event-workflow"
      DEVICE_COMMAND_ARN                = try(awscc_iot_command.aws_aws_iot_commands[0].command_arn, "")
      AWS_ACCOUNT_ID                    = data.aws_caller_identity.current[0].account_id
    }
  }
  tags = local.aws_v2_tags
}

resource "aws_lambda_event_source_mapping" "aws_v2_remote_telemetry" {
  count                              = local.aws_v2_remote_telemetry_inbound ? 1 : 0
  event_source_arn                   = aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["inbound"].arn
  function_name                      = aws_lambda_function.aws_v2_domain_consumer[0].arn
  starting_position                  = "LATEST"
  batch_size                         = 1
  maximum_batching_window_in_seconds = 1
  parallelization_factor             = 1
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_retry_attempts             = 5
  maximum_record_age_in_seconds      = 86400
  bisect_batch_on_function_error     = true
  destination_config {
    on_failure {
      destination_arn = aws_sqs_queue.aws_v2_remote_failure[0].arn
    }
  }
  enabled = true
}

resource "aws_sns_topic_subscription" "aws_aws_sns_fifo_only_for_reviewed_remote_control_edge" {
  count     = local.aws_v2_remote_control_inbound ? 1 : 0
  topic_arn = aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["inbound"].arn
  protocol  = "sqs"
  endpoint  = aws_sqs_queue.aws_v2_remote_control[0].arn
}

resource "aws_lambda_event_source_mapping" "aws_v2_remote_control" {
  count                              = local.aws_v2_remote_control_inbound ? 1 : 0
  event_source_arn                   = aws_sqs_queue.aws_v2_remote_control[0].arn
  function_name                      = aws_lambda_function.aws_v2_domain_consumer[0].arn
  batch_size                         = 1
  maximum_batching_window_in_seconds = 0
  function_response_types            = ["ReportBatchItemFailures"]
  enabled                            = true
}

resource "aws_iam_role" "aws_v2_step_functions" {
  count = local.aws_v2_l2_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-workflow-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "states.amazonaws.com" }
    }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy" "aws_v2_step_functions" {
  count = local.aws_v2_l2_enabled ? 1 : 0
  name  = "invoke-v2-processor"
  role  = aws_iam_role.aws_v2_step_functions[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "lambda:InvokeFunction"
      Resource = [
        aws_lambda_function.aws_aws_lambda[0].arn,
        aws_lambda_function.aws_v2_extension_action[0].arn,
      ]
    }]
  })
}

resource "aws_sfn_state_machine" "aws_aws_step_functions_standard" {
  count    = local.aws_v2_l2_enabled ? 1 : 0
  name     = "${local.aws_v2_name}-v2-event-workflow"
  role_arn = aws_iam_role.aws_v2_step_functions[0].arn
  type     = "STANDARD"
  definition = jsonencode({
    Comment = "Fixed four-action five-layer v2 notification workflow"
    StartAt = "ValidateNotification"
    States = {
      ValidateNotification = {
        Type       = "Pass"
        ResultPath = null
        Next       = "PrepareDelivery"
      }
      PrepareDelivery = {
        Type       = "Pass"
        ResultPath = null
        Next       = "DeliverNotification"
      }
      DeliverNotification = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.aws_v2_extension_action[0].arn
          Payload = {
            schema_version    = "notification-delivery.v1"
            "invocation_id.$" = "$.event_id"
            "event.$"         = "$"
          }
        }
        ResultPath = "$.delivery_result"
        Next       = "RecordSuccess"
        Catch = [{
          ErrorEquals = ["States.ALL"]
          ResultPath  = "$.workflow_error"
          Next        = "RecordFailure"
        }]
      }
      RecordSuccess = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.aws_aws_lambda[0].arn
          Payload = {
            "workflow_request.$" = "$"
            status               = "SUCCEEDED"
          }
        }
        End = true
      }
      RecordFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::lambda:invoke"
        Parameters = {
          FunctionName = aws_lambda_function.aws_aws_lambda[0].arn
          Payload = {
            "workflow_request.$" = "$"
            status               = "FAILED"
          }
        }
        End = true
      }
    }
  })
  tags = local.aws_v2_tags
}

# -----------------------------------------------------------------------------
# L3 raw, hourly rollup, cool/archive object storage, and finite mover
# -----------------------------------------------------------------------------

resource "aws_dynamodb_table" "aws_aws_dynamodb_on_demand_raw" {
  count        = local.aws_v2_hot_enabled ? 1 : 0
  name         = "${local.aws_v2_name}-v2-raw"
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
  attribute {
    name = "storage_window"
    type = "S"
  }

  global_secondary_index {
    name            = "device-stored-at-index"
    hash_key        = "device_id"
    range_key       = "stored_at_event_id"
    projection_type = "ALL"
  }

  global_secondary_index {
    name            = "storage-window-index"
    hash_key        = "storage_window"
    range_key       = "stored_at_event_id"
    projection_type = "ALL"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  point_in_time_recovery { enabled = true }
  tags = local.aws_v2_tags
}

resource "aws_dynamodb_table" "aws_aws_dynamodb_on_demand_hourly_rollup" {
  count        = local.aws_v2_hot_enabled ? 1 : 0
  name         = "${local.aws_v2_name}-v2-hourly-rollup"
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
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }
  point_in_time_recovery { enabled = true }
  tags = local.aws_v2_tags
}

resource "aws_s3_bucket" "aws_aws_s3_standard_ia" {
  count         = local.aws_v2_object_store_enabled ? 1 : 0
  bucket        = "${local.aws_v2_name}-v2-history-${local.deployment_suffix}"
  force_destroy = true
  tags          = local.aws_v2_tags
}

resource "aws_s3_bucket_public_access_block" "aws_v2_history" {
  count                   = local.aws_v2_object_store_enabled ? 1 : 0
  bucket                  = aws_s3_bucket.aws_aws_s3_standard_ia[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "aws_v2_history" {
  count  = local.aws_v2_object_store_enabled ? 1 : 0
  bucket = aws_s3_bucket.aws_aws_s3_standard_ia[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 permits one lifecycle configuration per bucket. This resource owns the
# cool object lifecycle; in the same-provider case it also performs the native
# Deep Archive transition and final expiry.
resource "aws_s3_bucket_lifecycle_configuration" "aws_aws_s3_standard_ia" {
  count  = local.aws_v2_cool_enabled ? 1 : 0
  bucket = aws_s3_bucket.aws_aws_s3_standard_ia[0].id

  rule {
    id     = "five-layer-v2-cool-history"
    status = "Enabled"
    filter { prefix = "history/" }

    dynamic "transition" {
      for_each = local.aws_v2_archive_enabled ? [1] : []
      content {
        days          = var.layer_3_cold_to_archive_interval_days - var.layer_3_hot_to_cold_interval_days
        storage_class = "DEEP_ARCHIVE"
      }
    }

    expiration {
      days = local.aws_v2_archive_enabled ? (
        var.layer_3_archive_expiry_interval_days - var.layer_3_hot_to_cold_interval_days
        ) : (
        var.layer_3_cold_to_archive_interval_days - var.layer_3_hot_to_cold_interval_days + 2
      )
    }
  }
}

# When AWS owns only the archive tier, remote movers land directly in the
# same private bucket using DEEP_ARCHIVE and this non-conflicting lifecycle
# expires the objects at the cumulative A boundary.
resource "aws_s3_bucket_lifecycle_configuration" "aws_aws_s3_glacier_deep_archive" {
  count  = local.aws_v2_archive_enabled && !local.aws_v2_cool_enabled ? 1 : 0
  bucket = aws_s3_bucket.aws_aws_s3_standard_ia[0].id

  rule {
    id     = "five-layer-v2-remote-archive"
    status = "Enabled"
    filter { prefix = "history/" }
    expiration {
      days = var.layer_3_archive_expiry_interval_days - var.layer_3_cold_to_archive_interval_days
    }
  }
}

resource "aws_ecr_repository" "aws_aws_ecr_if_container_selected" {
  count                = local.aws_v2_image_foundation_enabled ? 1 : 0
  name                 = "${local.aws_v2_name}-v2-images"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
  tags = local.aws_v2_tags
}

resource "aws_s3_bucket" "aws_aws_ecr_if_container_selected" {
  count         = local.aws_v2_image_foundation_enabled ? 1 : 0
  bucket        = "${local.aws_v2_name}-v2-build-${local.deployment_suffix}"
  force_destroy = true
  tags          = local.aws_v2_tags
}

resource "aws_s3_bucket_public_access_block" "aws_aws_ecr_if_container_selected" {
  count                   = local.aws_v2_image_foundation_enabled ? 1 : 0
  bucket                  = aws_s3_bucket.aws_aws_ecr_if_container_selected[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "aws_aws_ecr_if_container_selected" {
  count  = local.aws_v2_image_foundation_enabled ? 1 : 0
  bucket = aws_s3_bucket.aws_aws_ecr_if_container_selected[0].id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "aws_aws_ecr_if_container_selected" {
  count  = local.aws_v2_image_foundation_enabled ? 1 : 0
  bucket = aws_s3_bucket.aws_aws_ecr_if_container_selected[0].id
  rule {
    id     = "expire-build-contexts"
    status = "Enabled"
    filter { prefix = "contexts/" }
    expiration { days = 1 }
  }
}

resource "aws_iam_role" "aws_aws_ecr_if_container_selected" {
  count = local.aws_v2_image_foundation_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-build-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "codebuild.amazonaws.com" } }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy" "aws_aws_ecr_if_container_selected" {
  count = local.aws_v2_image_foundation_enabled ? 1 : 0
  name  = "publish-content-addressed-image"
  role  = aws_iam_role.aws_aws_ecr_if_container_selected[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.aws_aws_ecr_if_container_selected[0].arn}/contexts/*"
      },
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart",
        ]
        Resource = aws_ecr_repository.aws_aws_ecr_if_container_selected[0].arn
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = [
          "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current[0].account_id}:log-group:/aws/codebuild/${local.aws_v2_name}-v2-images*",
        ]
      },
    ]
  })
}

resource "aws_codebuild_project" "aws_aws_ecr_if_container_selected" {
  count         = local.aws_v2_image_foundation_enabled ? 1 : 0
  name          = "${local.aws_v2_name}-v2-images"
  description   = "Bounded Five-layer v2 container publication"
  service_role  = aws_iam_role.aws_aws_ecr_if_container_selected[0].arn
  build_timeout = 20

  artifacts { type = "NO_ARTIFACTS" }
  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"
    privileged_mode             = true
  }
  source {
    type     = "S3"
    location = "${aws_s3_bucket.aws_aws_ecr_if_container_selected[0].bucket}/contexts/placeholder.zip"
    buildspec = yamlencode({
      version = "0.2"
      phases = {
        pre_build = { commands = [
          "aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $IMAGE_URI",
        ] }
        build = { commands = [
          "docker build --platform linux/amd64 --tag $IMAGE_URI:$IMAGE_TAG .",
        ] }
        post_build = { commands = [
          "docker push $IMAGE_URI:$IMAGE_TAG",
        ] }
      }
    })
  }
  tags       = local.aws_v2_tags
  depends_on = [aws_iam_role_policy.aws_aws_ecr_if_container_selected]
}

resource "terraform_data" "aws_v2_storage_mover_guard" {
  count = local.aws_v2_storage_mover_enabled ? 1 : 0
  input = {
    image      = var.aws_v2_storage_mover_image
    task_count = local.aws_v2_storage_task_count
  }
  lifecycle {
    precondition {
      condition     = contains([1, 3], local.aws_v2_storage_task_count)
      error_message = "AWS Five-layer v2 storage movement requires the exact reviewed 1/1/3 task_count capacity dimension."
    }
    precondition {
      condition = (
        var.aws_v2_storage_mover_image != "" &&
        startswith(var.aws_v2_storage_mover_image, "${aws_ecr_repository.aws_aws_ecr_if_container_selected[0].repository_url}@sha256:")
      )
      error_message = "AWS Five-layer v2 storage movement requires a digest-pinned image from the deployment ECR repository."
    }
  }
}

resource "terraform_data" "aws_v2_bridge_image_guard" {
  count = length(local.aws_v2_outbound_event_routes) > 0 ? 1 : 0
  input = {
    image = var.aws_v2_bridge_image
  }
  lifecycle {
    precondition {
      condition = (
        var.aws_v2_bridge_image != "" &&
        startswith(var.aws_v2_bridge_image, "${aws_ecr_repository.aws_aws_ecr_if_container_selected[0].repository_url}@sha256:")
      )
      error_message = "AWS Five-layer v2 outbound event routes require a digest-pinned bridge image from the deployment ECR repository."
    }
  }
}

resource "aws_ecs_cluster" "aws_aws_ecs_fargate_storage_mover" {
  count = local.aws_v2_storage_mover_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-storage-mover"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  tags = local.aws_v2_tags
}

resource "aws_iam_role" "aws_v2_ecs_execution" {
  count = local.aws_v2_storage_mover_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-ecs-exec-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy_attachment" "aws_v2_ecs_execution" {
  count      = local.aws_v2_storage_mover_enabled ? 1 : 0
  role       = aws_iam_role.aws_v2_ecs_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "aws_v2_storage_mover" {
  count = local.aws_v2_storage_mover_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-mover-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" } }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy" "aws_v2_storage_mover" {
  count = local.aws_v2_storage_mover_enabled ? 1 : 0
  name  = "bounded-storage-window"
  role  = aws_iam_role.aws_v2_storage_mover[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      local.aws_v2_hot_enabled ? [{
        Effect = "Allow"
        Action = ["dynamodb:Query"]
        Resource = [
          aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].arn,
          "${aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].arn}/index/storage-window-index",
        ]
      }] : [],
      local.aws_v2_object_store_enabled ? [{
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject"]
        Resource = [
          aws_s3_bucket.aws_aws_s3_standard_ia[0].arn,
          "${aws_s3_bucket.aws_aws_s3_standard_ia[0].arn}/history/*",
        ]
      }] : []
    )
  })
}

resource "aws_vpc" "aws_v2_storage_mover" {
  count                = local.aws_v2_storage_mover_enabled ? 1 : 0
  cidr_block           = "10.42.0.0/24"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.aws_v2_tags, { Name = "${local.aws_v2_name}-v2-mover" })
}

resource "aws_internet_gateway" "aws_v2_storage_mover" {
  count  = local.aws_v2_storage_mover_enabled ? 1 : 0
  vpc_id = aws_vpc.aws_v2_storage_mover[0].id
  tags   = local.aws_v2_tags
}

resource "aws_subnet" "aws_v2_storage_mover" {
  count                   = local.aws_v2_storage_mover_enabled ? 1 : 0
  vpc_id                  = aws_vpc.aws_v2_storage_mover[0].id
  cidr_block              = "10.42.0.0/25"
  map_public_ip_on_launch = true
  tags                    = local.aws_v2_tags
}

resource "aws_route_table" "aws_v2_storage_mover" {
  count  = local.aws_v2_storage_mover_enabled ? 1 : 0
  vpc_id = aws_vpc.aws_v2_storage_mover[0].id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.aws_v2_storage_mover[0].id
  }
  tags = local.aws_v2_tags
}

resource "aws_route_table_association" "aws_v2_storage_mover" {
  count          = local.aws_v2_storage_mover_enabled ? 1 : 0
  subnet_id      = aws_subnet.aws_v2_storage_mover[0].id
  route_table_id = aws_route_table.aws_v2_storage_mover[0].id
}

resource "aws_security_group" "aws_v2_storage_mover" {
  count       = local.aws_v2_storage_mover_enabled ? 1 : 0
  name_prefix = "${local.aws_v2_name}-v2-mover-"
  description = "Outbound-only finite storage mover"
  vpc_id      = aws_vpc.aws_v2_storage_mover[0].id
  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.aws_v2_tags
}

resource "aws_ecs_task_definition" "aws_aws_ecs_fargate_storage_mover" {
  count                    = local.aws_v2_storage_mover_enabled ? 1 : 0
  family                   = "${local.aws_v2_name}-v2-storage-mover"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.aws_v2_ecs_execution[0].arn
  task_role_arn            = aws_iam_role.aws_v2_storage_mover[0].arn

  container_definitions = jsonencode([{
    name      = "storage-mover"
    image     = var.aws_v2_storage_mover_image
    essential = true
    environment = [
      { name = "ARCHITECTURE_PROFILE", value = "five-layer-baseline@2" },
      { name = "DEPLOYMENT_ID", value = local.deployment_suffix },
      { name = "HOT_PROVIDER", value = var.layer_3_hot_provider },
      { name = "COOL_PROVIDER", value = var.layer_3_cold_provider },
      { name = "ARCHIVE_PROVIDER", value = var.layer_3_archive_provider },
      { name = "HOT_BOUNDARY_DAYS", value = tostring(var.layer_3_hot_to_cold_interval_days) },
      { name = "COOL_BOUNDARY_DAYS", value = tostring(var.layer_3_cold_to_archive_interval_days) },
      { name = "ARCHIVE_BOUNDARY_DAYS", value = tostring(var.layer_3_archive_expiry_interval_days) },
      { name = "STORAGE_TASK_COUNT", value = tostring(local.aws_v2_storage_task_count) },
      { name = "RAW_TABLE_NAME", value = try(aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].name, "") },
      { name = "HISTORY_BUCKET", value = try(aws_s3_bucket.aws_aws_s3_standard_ia[0].bucket, "") },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.aws_aws_cloudwatch[0].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "storage-mover"
      }
    }
  }])
  tags = local.aws_v2_tags
}

resource "aws_iam_role" "aws_v2_scheduler" {
  count = local.aws_v2_storage_mover_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-scheduler-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "scheduler.amazonaws.com" } }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy" "aws_v2_scheduler" {
  count = local.aws_v2_storage_mover_enabled ? 1 : 0
  name  = "run-finite-storage-mover"
  role  = aws_iam_role.aws_v2_scheduler[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = "ecs:RunTask", Resource = aws_ecs_task_definition.aws_aws_ecs_fargate_storage_mover[0].arn },
      { Effect = "Allow", Action = "iam:PassRole", Resource = [aws_iam_role.aws_v2_ecs_execution[0].arn, aws_iam_role.aws_v2_storage_mover[0].arn] },
    ]
  })
}

resource "aws_scheduler_schedule" "aws_aws_eventbridge_scheduler" {
  for_each            = local.aws_v2_storage_schedule_tasks
  name                = "${local.aws_v2_name}-v2-${each.key}"
  schedule_expression = each.value.schedule
  state               = "ENABLED"

  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_ecs_cluster.aws_aws_ecs_fargate_storage_mover[0].arn
    role_arn = aws_iam_role.aws_v2_scheduler[0].arn
    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.aws_aws_ecs_fargate_storage_mover[0].arn
      launch_type         = "FARGATE"
      task_count          = 1
      network_configuration {
        assign_public_ip = true
        subnets          = [aws_subnet.aws_v2_storage_mover[0].id]
        security_groups  = [aws_security_group.aws_v2_storage_mover[0].id]
      }
    }
    input = jsonencode({
      containerOverrides = [{
        name = "storage-mover"
        environment = [
          { name = "TRANSITION", value = each.value.transition },
          { name = "SOURCE_PROVIDER", value = each.value.source },
          { name = "DESTINATION_PROVIDER", value = each.value.destination },
          { name = "STORAGE_TASK_INDEX", value = tostring(each.value.task_index) },
          { name = "STORAGE_TASK_COUNT", value = tostring(local.aws_v2_storage_task_count) },
        ]
      }]
    })
    retry_policy {
      maximum_event_age_in_seconds = 86400
      maximum_retry_attempts       = 6
    }
  }
}

# -----------------------------------------------------------------------------
# L4 TwinMaker and interactive read access
# -----------------------------------------------------------------------------

resource "aws_s3_bucket" "aws_v2_twinmaker" {
  count         = local.aws_v2_l4_enabled ? 1 : 0
  bucket        = "${local.aws_v2_name}-v2-twinmaker-${local.deployment_suffix}"
  force_destroy = true
  tags          = local.aws_v2_tags
}

resource "aws_s3_bucket_public_access_block" "aws_v2_twinmaker" {
  count                   = local.aws_v2_l4_enabled ? 1 : 0
  bucket                  = aws_s3_bucket.aws_v2_twinmaker[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_iam_role" "aws_v2_twinmaker" {
  count = local.aws_v2_l4_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-twinmaker-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "iottwinmaker.amazonaws.com" } }]
  })
  tags = local.aws_v2_tags
}

resource "aws_iam_role_policy" "aws_v2_twinmaker" {
  count = local.aws_v2_l4_enabled ? 1 : 0
  name  = "workspace-bucket"
  role  = aws_iam_role.aws_v2_twinmaker[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetBucketLocation", "s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      Resource = [aws_s3_bucket.aws_v2_twinmaker[0].arn, "${aws_s3_bucket.aws_v2_twinmaker[0].arn}/*"]
    }]
  })
}

resource "awscc_iottwinmaker_workspace" "aws_aws_iot_twinmaker_standard" {
  count        = local.aws_v2_l4_enabled ? 1 : 0
  workspace_id = "${local.aws_v2_name}-${local.deployment_suffix}"
  description  = "Five-layer v2 PoC twin workspace"
  role         = aws_iam_role.aws_v2_twinmaker[0].arn
  s3_location  = aws_s3_bucket.aws_v2_twinmaker[0].arn
  tags         = local.aws_v2_tags
  depends_on   = [aws_iam_role_policy.aws_v2_twinmaker]
}

# -----------------------------------------------------------------------------
# L5 bounded raw-history reader and Managed Grafana
# -----------------------------------------------------------------------------

resource "aws_lambda_function" "aws_aws_lambda_raw_history_reader" {
  count                          = local.aws_v2_l5_enabled ? 1 : 0
  function_name                  = "${local.aws_v2_name}-v2-raw-history-reader"
  role                           = aws_iam_role.aws_v2_lambda[0].arn
  handler                        = "handler.raw_history_reader"
  runtime                        = local.python_runtime_aws
  timeout                        = 10
  memory_size                    = 512
  reserved_concurrent_executions = 2

  filename         = local.aws_v2_runtime_package
  source_code_hash = filebase64sha256(local.aws_v2_runtime_package)

  environment {
    variables = {
      ARCHITECTURE_PROFILE = "five-layer-baseline@2"
      RAW_TABLE_NAME       = aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].name
      ROLLUP_TABLE_NAME    = aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup[0].name
      MAXIMUM_POINTS       = "1000"
      READER_KEY_SHA256    = ""
    }
  }
  tags = local.aws_v2_tags
}

# The URL is transport-public but never application-anonymous. Stage 3 creates
# a 256-bit key, writes only its SHA-256 verifier to Lambda, and stores the key
# only in Grafana secureJsonData. An empty verifier fails closed.
resource "aws_lambda_function_url" "aws_aws_lambda_raw_history_reader" {
  count              = local.aws_v2_l5_enabled ? 1 : 0
  function_name      = aws_lambda_function.aws_aws_lambda_raw_history_reader[0].function_name
  authorization_type = "NONE"
}

resource "aws_iam_role" "aws_v2_grafana" {
  count = local.aws_v2_l5_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-grafana-${local.deployment_suffix}"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "grafana.amazonaws.com" } }]
  })
  tags = local.aws_v2_tags
}

resource "aws_grafana_workspace" "aws_aws_amazon_managed_grafana_12" {
  count                    = local.aws_v2_l5_enabled ? 1 : 0
  name                     = "${local.aws_v2_name}-v2-grafana"
  description              = "Five-layer v2 raw-history visualization"
  account_access_type      = "CURRENT_ACCOUNT"
  authentication_providers = ["AWS_SSO"]
  permission_type          = "SERVICE_MANAGED"
  role_arn                 = aws_iam_role.aws_v2_grafana[0].arn
  grafana_version          = "12.0"
  tags                     = local.aws_v2_tags
}

locals {
  aws_v2_layer_access_enabled = (
    (local.aws_v2_l4_enabled || local.aws_v2_l5_enabled) &&
    var.platform_user_email != ""
  )
}

data "aws_ssoadmin_instances" "aws_v2_layer_access" {
  provider = aws.sso
  count    = local.aws_v2_layer_access_enabled ? 1 : 0
}

locals {
  aws_v2_sso_instance_arn  = try(tolist(data.aws_ssoadmin_instances.aws_v2_layer_access[0].arns)[0], "")
  aws_v2_identity_store_id = try(tolist(data.aws_ssoadmin_instances.aws_v2_layer_access[0].identity_store_ids)[0], "")
}

data "aws_identitystore_users" "aws_v2_layer_access" {
  provider          = aws.sso
  count             = local.aws_v2_layer_access_enabled ? 1 : 0
  identity_store_id = local.aws_v2_identity_store_id
}

locals {
  aws_v2_matching_users = local.aws_v2_layer_access_enabled ? [
    for user in coalesce(try(data.aws_identitystore_users.aws_v2_layer_access[0].users, []), []) :
    user if user.user_name == var.platform_user_email
  ] : []
  aws_v2_create_layer_user = local.aws_v2_layer_access_enabled && length(local.aws_v2_matching_users) == 0
}

resource "aws_identitystore_user" "aws_v2_layer_access" {
  provider          = aws.sso
  count             = local.aws_v2_create_layer_user ? 1 : 0
  identity_store_id = local.aws_v2_identity_store_id
  display_name      = "${var.platform_user_first_name} ${var.platform_user_last_name}"
  user_name         = var.platform_user_email
  name {
    given_name  = var.platform_user_first_name
    family_name = var.platform_user_last_name
  }
  emails {
    value   = var.platform_user_email
    primary = true
  }
}

locals {
  aws_v2_layer_user_id = local.aws_v2_layer_access_enabled ? (
    length(local.aws_v2_matching_users) > 0 ?
    local.aws_v2_matching_users[0].user_id :
    try(aws_identitystore_user.aws_v2_layer_access[0].user_id, "")
  ) : ""
}

resource "aws_ssoadmin_permission_set" "aws_aws_iam_identity_center_layer_access" {
  provider         = aws.sso
  count            = local.aws_v2_layer_access_enabled ? 1 : 0
  instance_arn     = local.aws_v2_sso_instance_arn
  name             = substr("${local.aws_v2_name}-TwinViewer", 0, 32)
  description      = "Read-only TwinMaker and Grafana access for the thesis PoC"
  session_duration = "PT4H"
  tags             = local.aws_v2_tags
}

resource "aws_ssoadmin_permission_set_inline_policy" "aws_v2_layer_access" {
  provider           = aws.sso
  count              = local.aws_v2_layer_access_enabled ? 1 : 0
  instance_arn       = local.aws_v2_sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.aws_aws_iam_identity_center_layer_access[0].arn
  inline_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "iottwinmaker:GetWorkspace", "iottwinmaker:ListEntities",
        "iottwinmaker:GetEntity", "iottwinmaker:ListComponentTypes",
        "iottwinmaker:GetComponentType", "grafana:DescribeWorkspace"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_ssoadmin_account_assignment" "aws_aws_iam_identity_center_layer_access" {
  provider           = aws.sso
  count              = local.aws_v2_layer_access_enabled ? 1 : 0
  instance_arn       = local.aws_v2_sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.aws_aws_iam_identity_center_layer_access[0].arn
  principal_id       = local.aws_v2_layer_user_id
  principal_type     = "USER"
  target_id          = data.aws_caller_identity.current[0].account_id
  target_type        = "AWS_ACCOUNT"
  depends_on         = [aws_ssoadmin_permission_set_inline_policy.aws_v2_layer_access]
}

resource "aws_grafana_role_association" "aws_v2_layer_access" {
  count        = local.aws_v2_l5_enabled && local.aws_v2_layer_access_enabled ? 1 : 0
  role         = "ADMIN"
  user_ids     = [local.aws_v2_layer_user_id]
  workspace_id = aws_grafana_workspace.aws_aws_amazon_managed_grafana_12[0].id
}

# -----------------------------------------------------------------------------
# Catalog-owned component outputs and safe human-access surfaces
# -----------------------------------------------------------------------------

output "aws_component_ingestion_output" {
  value = local.aws_v2_l1_enabled ? {
    iot_thing_name = aws_iot_thing.aws_aws_iot_core[0].name
    queue_arn      = aws_sqs_queue.aws_aws_sqs_fifo[0].arn
  } : null
}

output "aws_component_processing_output" {
  value = local.aws_v2_l2_enabled ? {
    function_arn      = aws_lambda_function.aws_aws_lambda[0].arn
    state_machine_arn = aws_sfn_state_machine.aws_aws_step_functions_standard[0].arn
  } : null
}

output "aws_component_hot_storage_output" {
  value = local.aws_v2_hot_enabled ? {
    raw_table_arn    = aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0].arn
    rollup_table_arn = aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup[0].arn
  } : null
}

output "aws_component_cool_storage_output" {
  value = local.aws_v2_cool_enabled ? { bucket = aws_s3_bucket.aws_aws_s3_standard_ia[0].bucket } : null
}

output "aws_component_archive_storage_output" {
  value = local.aws_v2_archive_enabled ? { bucket = aws_s3_bucket.aws_aws_s3_standard_ia[0].bucket } : null
}

output "aws_component_twin_state_output" {
  value = local.aws_v2_l4_enabled ? {
    workspace_id = awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0].workspace_id
    access_url   = "https://${var.aws_region}.console.aws.amazon.com/iottwinmaker/home?region=${var.aws_region}#/workspaces/${awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0].workspace_id}"
  } : null
}

output "aws_component_visualization_output" {
  value = local.aws_v2_l5_enabled ? {
    workspace_id = aws_grafana_workspace.aws_aws_amazon_managed_grafana_12[0].id
    access_url   = "https://${aws_grafana_workspace.aws_aws_amazon_managed_grafana_12[0].endpoint}"
    reader_url   = aws_lambda_function_url.aws_aws_lambda_raw_history_reader[0].function_url
  } : null
}
