# Source-owned AWS cross-cloud bridge for five-layer-baseline@2.
#
# The bridge is created only for resolved AWS event routes. It consumes the
# directional AWS outbox brokers, validates the frozen canonical contract, and
# publishes through official destination SDKs with short-lived workload
# identity credentials. No static cross-cloud secret is provisioned.

locals {
  aws_v2_bridge_enabled = length(local.aws_v2_outbound_event_routes) > 0
  aws_v2_bridge_destinations_selected = toset([
    for route in values(local.aws_v2_outbound_event_routes) : route.destination_provider
  ])
  aws_v2_bridge_to_azure_enabled = contains(local.aws_v2_bridge_destinations_selected, "azure")
  aws_v2_bridge_to_gcp_enabled   = contains(local.aws_v2_bridge_destinations_selected, "gcp")

  aws_v2_bridge_to_azure_telemetry = anytrue([
    for route in values(local.aws_v2_outbound_event_routes) :
    route.destination_provider == "azure" && route.channel_class == "telemetry"
  ])
  aws_v2_bridge_to_azure_control = anytrue([
    for route in values(local.aws_v2_outbound_event_routes) :
    route.destination_provider == "azure" && route.channel_class == "control"
  ])
  aws_v2_bridge_to_gcp_telemetry = anytrue([
    for route in values(local.aws_v2_outbound_event_routes) :
    route.destination_provider == "gcp" && route.channel_class == "telemetry"
  ])
  aws_v2_bridge_to_gcp_control = anytrue([
    for route in values(local.aws_v2_outbound_event_routes) :
    route.destination_provider == "gcp" && route.channel_class == "control"
  ])
  aws_v2_bridge_azure_telemetry_scopes = merge(
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "azure" && route.channel_class == "telemetry" && !endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { remote = azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].id } : {},
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "azure" && route.channel_class == "telemetry" && endswith(route.logical_edge_id, "-to-eventing") && contains(route.event_types, "telemetry.received.v1")
    ]) ? { event_received = local.azure_event_dedicated ? azurerm_eventhub.domain_telemetry_dedicated["received"].id : azurerm_eventhub.domain_telemetry_standard["received"].id } : {},
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "azure" && route.channel_class == "telemetry" && endswith(route.logical_edge_id, "-to-eventing") && contains(route.event_types, "telemetry.processed.v1")
    ]) ? { event_processed = local.azure_event_dedicated ? azurerm_eventhub.domain_telemetry_dedicated["processed"].id : azurerm_eventhub.domain_telemetry_standard["processed"].id } : {},
  )
  aws_v2_bridge_azure_control_scopes = merge(
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "azure" && route.channel_class == "control" && !endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { remote = azurerm_servicebus_topic.azure_v2_remote_control["inbound"].id } : {},
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "azure" && route.channel_class == "control" && endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { event = azurerm_servicebus_topic.domain_control[0].id } : {},
  )
  aws_v2_bridge_gcp_topic_targets = merge(
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "telemetry" && !endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { remote_telemetry = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-telemetry-inbound"].name } : {},
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "control" && !endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { remote_control = google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-control-inbound"].name } : {},
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "telemetry" && endswith(route.logical_edge_id, "-to-eventing") && contains(route.event_types, "telemetry.received.v1")
    ]) ? { event_received = google_pubsub_topic.domain_events["received"].name } : {},
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "telemetry" && endswith(route.logical_edge_id, "-to-eventing") && contains(route.event_types, "telemetry.processed.v1")
    ]) ? { event_processed = google_pubsub_topic.domain_events["processed"].name } : {},
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      route.destination_provider == "gcp" && route.channel_class == "control" && endswith(route.logical_edge_id, "-to-eventing")
    ]) ? { event_control = google_pubsub_topic.domain_events["control"].name } : {},
  )
  aws_v2_bridge_telemetry_enabled = local.aws_v2_remote_telemetry_outbound || local.aws_v2_event_remote_telemetry_outbound
  aws_v2_bridge_control_enabled   = local.aws_v2_remote_control_outbound || local.aws_v2_event_remote_control_outbound
  aws_v2_event_bridge_streams = local.aws_event_enabled ? merge(
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      startswith(route.logical_edge_id, "edge.eventing-to-") && contains(route.event_types, "telemetry.received.v1")
    ]) ? { received = aws_kinesis_stream.domain_telemetry["received"].arn } : {},
    anytrue([
      for route in values(local.aws_v2_outbound_event_routes) :
      startswith(route.logical_edge_id, "edge.eventing-to-") && contains(route.event_types, "telemetry.processed.v1")
    ]) ? { processed = aws_kinesis_stream.domain_telemetry["processed"].arn } : {},
  ) : {}
  aws_v2_event_bridge_control_types = sort(distinct(flatten([
    for route in values(local.aws_v2_outbound_event_routes) : route.event_types
    if startswith(route.logical_edge_id, "edge.eventing-to-") && route.channel_class == "control"
  ])))
  aws_v2_bridge_control_source_arns = compact([
    local.aws_v2_remote_control_outbound ? aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["outbound"].arn : "",
    local.aws_v2_event_remote_control_outbound ? aws_sns_topic.domain_control[0].arn : "",
  ])

  aws_v2_bridge_destinations = merge(
    local.aws_v2_bridge_to_azure_enabled ? {
      azure = {
        route_targets = {
          for route_id, route in local.aws_v2_outbound_event_routes : route_id => merge(
            route.channel_class == "telemetry" ? {
              telemetry_namespace = endswith(route.logical_edge_id, "-to-eventing") ? "${local.azure_event_namespace_name}.servicebus.windows.net" : "${azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].name}.servicebus.windows.net"
              telemetry_entity = endswith(route.logical_edge_id, "-to-eventing") ? (
                contains(route.event_types, "telemetry.processed.v1") ? local.azure_event_hub_names.processed : local.azure_event_hub_names.received
              ) : azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].name
            } : {},
            route.channel_class == "control" ? {
              control_namespace = endswith(route.logical_edge_id, "-to-eventing") ? "${azurerm_servicebus_namespace.eventing[0].name}.servicebus.windows.net" : "${azurerm_servicebus_namespace.azure_azure_service_bus_standard[0].name}.servicebus.windows.net"
              control_entity    = endswith(route.logical_edge_id, "-to-eventing") ? azurerm_servicebus_topic.domain_control[0].name : azurerm_servicebus_topic.azure_v2_remote_control["inbound"].name
            } : {},
          ) if route.destination_provider == "azure"
        }
      }
    } : {},
    local.aws_v2_bridge_to_gcp_enabled ? {
      gcp = {
        route_targets = {
          for route_id, route in local.aws_v2_outbound_event_routes : route_id => merge(
            route.channel_class == "telemetry" ? {
              telemetry_topic = endswith(route.logical_edge_id, "-to-eventing") ? (
                contains(route.event_types, "telemetry.processed.v1") ? google_pubsub_topic.domain_events["processed"].id : google_pubsub_topic.domain_events["received"].id
              ) : google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-telemetry-inbound"].id
              api_endpoint = "europe-west1-pubsub.googleapis.com"
            } : {},
            route.channel_class == "control" ? {
              control_topic = endswith(route.logical_edge_id, "-to-eventing") ? google_pubsub_topic.domain_events["control"].id : google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics["remote-control-inbound"].id
              api_endpoint  = "europe-west1-pubsub.googleapis.com"
            } : {},
          ) if route.destination_provider == "gcp"
        }
      }
    } : {},
  )

  aws_v2_bridge_identities = merge(
    local.aws_v2_bridge_to_azure_enabled ? {
      azure = {
        tenant_id = nonsensitive(var.azure_tenant_id)
        client_id = azurerm_user_assigned_identity.azure_v2_bridge_target_from_aws[0].client_id
      }
    } : {},
    local.aws_v2_bridge_to_gcp_enabled ? {
      gcp = {
        provider_audience                 = "//iam.googleapis.com/${google_iam_workload_identity_pool_provider.gcp_v2_bridge_from_aws[0].name}"
        service_account_impersonation_url = "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${google_service_account.gcp_v2_bridge_target_from_aws[0].email}:generateAccessToken"
      }
    } : {},
  )
}

resource "terraform_data" "aws_v2_bridge_identity_guard" {
  count = local.aws_v2_bridge_to_azure_enabled ? 1 : 0
  input = {
    issuer       = var.aws_outbound_identity_issuer
    destinations = var.aws_outbound_identity_destinations
  }
  lifecycle {
    precondition {
      condition = (
        var.aws_outbound_identity_required &&
        contains(var.aws_outbound_identity_destinations, "azure") &&
        startswith(var.aws_outbound_identity_issuer, "https://")
      )
      error_message = "AWS-to-Azure event routes require the ready account-scoped AWS outbound identity issuer from preplan."
    }
  }
}

# -----------------------------------------------------------------------------
# AWS source runtime and bounded failure retention
# -----------------------------------------------------------------------------

resource "aws_iam_role" "aws_v2_bridge" {
  count = local.aws_v2_bridge_enabled ? 1 : 0
  name  = "${local.aws_v2_name}-v2-event-bridge-${local.deployment_suffix}"
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

resource "aws_iam_role_policy_attachment" "aws_v2_bridge_logs" {
  count      = local.aws_v2_bridge_enabled ? 1 : 0
  role       = aws_iam_role.aws_v2_bridge[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_s3_bucket" "aws_v2_bridge_telemetry_failure" {
  count         = local.aws_v2_bridge_telemetry_enabled ? 1 : 0
  bucket        = "${local.aws_v2_name}-bridge-fail-${local.deployment_suffix}"
  force_destroy = true
  tags          = local.aws_v2_tags
}

resource "aws_s3_bucket_server_side_encryption_configuration" "aws_v2_bridge_telemetry_failure" {
  count  = local.aws_v2_bridge_telemetry_enabled ? 1 : 0
  bucket = aws_s3_bucket.aws_v2_bridge_telemetry_failure[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "aws_v2_bridge_telemetry_failure" {
  count                   = local.aws_v2_bridge_telemetry_enabled ? 1 : 0
  bucket                  = aws_s3_bucket.aws_v2_bridge_telemetry_failure[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "aws_v2_bridge_telemetry_failure" {
  count  = local.aws_v2_bridge_telemetry_enabled ? 1 : 0
  bucket = aws_s3_bucket.aws_v2_bridge_telemetry_failure[0].id
  rule {
    id     = "expire-poc-bridge-failures"
    status = "Enabled"
    filter {}
    expiration { days = 14 }
  }
}

resource "aws_sqs_queue" "aws_v2_bridge_control_failure" {
  count                       = local.aws_v2_bridge_control_enabled ? 1 : 0
  name                        = "${local.aws_v2_name}-bridge-failure.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  message_retention_seconds   = 1209600
  receive_wait_time_seconds   = 20
  visibility_timeout_seconds  = 360
  tags                        = local.aws_v2_tags
}

resource "aws_sqs_queue" "aws_v2_bridge_control_source" {
  count                       = local.aws_v2_bridge_control_enabled ? 1 : 0
  name                        = "${local.aws_v2_name}-bridge-source.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  message_retention_seconds   = 1209600
  receive_wait_time_seconds   = 20
  visibility_timeout_seconds  = 360
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.aws_v2_bridge_control_failure[0].arn
    maxReceiveCount     = 6
  })
  tags = local.aws_v2_tags
}

resource "aws_sqs_queue_policy" "aws_v2_bridge_control_source" {
  count     = local.aws_v2_bridge_control_enabled ? 1 : 0
  queue_url = aws_sqs_queue.aws_v2_bridge_control_source[0].url
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowOnlyDirectionalOutboundTopic"
      Effect    = "Allow"
      Principal = { Service = "sns.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.aws_v2_bridge_control_source[0].arn
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = local.aws_v2_bridge_control_source_arns
        }
      }
    }]
  })
}

resource "aws_sns_topic_subscription" "aws_v2_bridge_control_source" {
  count                = local.aws_v2_remote_control_outbound ? 1 : 0
  topic_arn            = aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge["outbound"].arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.aws_v2_bridge_control_source[0].arn
  raw_message_delivery = true
}

resource "aws_sns_topic_subscription" "aws_v2_event_bridge_control_source" {
  count                = local.aws_v2_event_remote_control_outbound ? 1 : 0
  topic_arn            = aws_sns_topic.domain_control[0].arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.aws_v2_bridge_control_source[0].arn
  raw_message_delivery = true
  filter_policy = jsonencode({
    event_type = local.aws_v2_event_bridge_control_types
  })
}

resource "aws_iam_role_policy" "aws_v2_bridge" {
  count = local.aws_v2_bridge_enabled ? 1 : 0
  name  = "bounded-source-and-failure-access"
  role  = aws_iam_role.aws_v2_bridge[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      local.aws_v2_bridge_telemetry_enabled ? [{
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
          local.aws_v2_remote_telemetry_outbound ? [aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["outbound"].arn] : [],
          values(local.aws_v2_event_bridge_streams),
        )
      }] : [],
      local.aws_v2_bridge_telemetry_enabled ? [{
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.aws_v2_bridge_telemetry_failure[0].arn
      }] : [],
      local.aws_v2_bridge_telemetry_enabled ? [{
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.aws_v2_bridge_telemetry_failure[0].arn}/*"
        Condition = {
          StringEquals = {
            "s3:ResourceAccount" = data.aws_caller_identity.current[0].account_id
          }
        }
      }] : [],
      local.aws_v2_bridge_control_enabled ? [{
        Effect = "Allow"
        Action = [
          "sqs:ChangeMessageVisibility",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ReceiveMessage",
        ]
        Resource = aws_sqs_queue.aws_v2_bridge_control_source[0].arn
      }] : [],
      local.aws_v2_bridge_control_enabled ? [{
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.aws_v2_bridge_control_failure[0].arn
      }] : [],
      local.aws_v2_bridge_to_azure_enabled ? [{
        Effect   = "Allow"
        Action   = ["sts:GetWebIdentityToken"]
        Resource = "*"
        Condition = {
          "ForAllValues:StringEquals" = {
            "sts:IdentityTokenAudience" = "api://AzureADTokenExchange"
          }
          StringEquals = {
            "sts:SigningAlgorithm" = "RS256"
          }
          NumericLessThanEquals = {
            "sts:DurationSeconds" = 300
          }
        }
      }] : [],
    )
  })
}

resource "aws_cloudwatch_log_group" "aws_v2_bridge" {
  count             = local.aws_v2_bridge_enabled ? 1 : 0
  name              = "/aws/lambda/${local.aws_v2_name}-v2-event-bridge"
  retention_in_days = var.log_retention_days
  tags              = local.aws_v2_tags
}

resource "aws_lambda_function" "aws_v2_cross_cloud_bridge" {
  count         = local.aws_v2_bridge_enabled ? 1 : 0
  function_name = "${local.aws_v2_name}-v2-event-bridge"
  role          = aws_iam_role.aws_v2_bridge[0].arn
  package_type  = "Image"
  image_uri     = var.aws_v2_bridge_image
  architectures = ["x86_64"]
  timeout       = 60
  memory_size   = 1024

  environment {
    variables = {
      BRIDGE_ROUTES_JSON               = jsonencode(values(local.aws_v2_outbound_event_routes))
      BRIDGE_DESTINATIONS_JSON         = jsonencode(local.aws_v2_bridge_destinations)
      BRIDGE_IDENTITIES_JSON           = jsonencode(local.aws_v2_bridge_identities)
      BRIDGE_TELEMETRY_FAILURE_BUCKET  = try(aws_s3_bucket.aws_v2_bridge_telemetry_failure[0].bucket, "")
      BRIDGE_CONTROL_FAILURE_QUEUE_URL = try(aws_sqs_queue.aws_v2_bridge_control_failure[0].url, "")
      AWS_STS_REGIONAL_ENDPOINTS       = "regional"
    }
  }

  tags = local.aws_v2_tags

  depends_on = [
    aws_cloudwatch_log_group.aws_v2_bridge,
    aws_iam_role_policy_attachment.aws_v2_bridge_logs,
    aws_iam_role_policy.aws_v2_bridge,
    azurerm_federated_identity_credential.azure_v2_bridge_from_aws,
    azurerm_role_assignment.azure_v2_bridge_from_aws_telemetry,
    azurerm_role_assignment.azure_v2_bridge_from_aws_control,
    google_service_account_iam_member.gcp_v2_bridge_from_aws,
    google_pubsub_topic_iam_member.gcp_v2_bridge_from_aws,
    terraform_data.aws_v2_bridge_image_guard,
  ]
}

resource "aws_lambda_event_source_mapping" "aws_v2_bridge_telemetry" {
  count                              = local.aws_v2_remote_telemetry_outbound ? 1 : 0
  event_source_arn                   = aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge["outbound"].arn
  function_name                      = aws_lambda_function.aws_v2_cross_cloud_bridge[0].arn
  starting_position                  = "TRIM_HORIZON"
  batch_size                         = 10
  maximum_batching_window_in_seconds = 1
  parallelization_factor             = 1
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_retry_attempts             = 5
  maximum_record_age_in_seconds      = 86400
  bisect_batch_on_function_error     = true
  destination_config {
    on_failure {
      destination_arn = aws_s3_bucket.aws_v2_bridge_telemetry_failure[0].arn
    }
  }
  enabled = true
}

resource "aws_lambda_event_source_mapping" "aws_v2_event_bridge_telemetry" {
  for_each                           = local.aws_v2_event_bridge_streams
  event_source_arn                   = aws_kinesis_stream_consumer.domain_consumers["bridge-${each.key}"].arn
  function_name                      = aws_lambda_function.aws_v2_cross_cloud_bridge[0].arn
  starting_position                  = "TRIM_HORIZON"
  batch_size                         = 10
  maximum_batching_window_in_seconds = 1
  parallelization_factor             = 1
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_retry_attempts             = 5
  maximum_record_age_in_seconds      = 86400
  bisect_batch_on_function_error     = true
  destination_config {
    on_failure {
      destination_arn = aws_s3_bucket.aws_v2_bridge_telemetry_failure[0].arn
    }
  }
  enabled = true
}

resource "aws_lambda_event_source_mapping" "aws_v2_bridge_control" {
  count                              = local.aws_v2_bridge_control_enabled ? 1 : 0
  event_source_arn                   = aws_sqs_queue.aws_v2_bridge_control_source[0].arn
  function_name                      = aws_lambda_function.aws_v2_cross_cloud_bridge[0].arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 0
  function_response_types            = ["ReportBatchItemFailures"]
  enabled                            = true
}

# -----------------------------------------------------------------------------
# Azure destination identity and least-privilege inbound publishing rights
# -----------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "azure_v2_bridge_target_from_aws" {
  count               = local.aws_v2_bridge_to_azure_enabled ? 1 : 0
  name                = "${local.azure_v2_name}-v2-from-aws-${local.deployment_suffix}"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  tags                = local.azure_v2_tags
}

resource "azurerm_federated_identity_credential" "azure_v2_bridge_from_aws" {
  count                     = local.aws_v2_bridge_to_azure_enabled ? 1 : 0
  name                      = "aws-event-bridge"
  user_assigned_identity_id = azurerm_user_assigned_identity.azure_v2_bridge_target_from_aws[0].id
  audience                  = ["api://AzureADTokenExchange"]
  issuer                    = var.aws_outbound_identity_issuer
  subject                   = aws_iam_role.aws_v2_bridge[0].arn

  depends_on = [
    terraform_data.aws_outbound_identity_preplan,
    terraform_data.aws_v2_bridge_identity_guard,
  ]
}

resource "azurerm_role_assignment" "azure_v2_bridge_from_aws_telemetry" {
  for_each             = local.aws_v2_bridge_azure_telemetry_scopes
  scope                = each.value
  role_definition_name = "Azure Event Hubs Data Sender"
  principal_id         = azurerm_user_assigned_identity.azure_v2_bridge_target_from_aws[0].principal_id
  principal_type       = "ServicePrincipal"
}

resource "azurerm_role_assignment" "azure_v2_bridge_from_aws_control" {
  for_each             = local.aws_v2_bridge_azure_control_scopes
  scope                = each.value
  role_definition_name = "Azure Service Bus Data Sender"
  principal_id         = azurerm_user_assigned_identity.azure_v2_bridge_target_from_aws[0].principal_id
  principal_type       = "ServicePrincipal"
}

# -----------------------------------------------------------------------------
# GCP destination identity and least-privilege inbound publishing rights
# -----------------------------------------------------------------------------

resource "google_service_account" "gcp_v2_bridge_target_from_aws" {
  count        = local.aws_v2_bridge_to_gcp_enabled ? 1 : 0
  project      = local.gcp_project_id
  account_id   = substr("${local.gcp_v2_name}-v2-from-aws", 0, 30)
  display_name = "${var.digital_twin_name} v2 bridge target from AWS"

  depends_on = [google_project_service.iam]
}

resource "google_iam_workload_identity_pool" "gcp_v2_bridge_from_aws" {
  count                     = local.aws_v2_bridge_to_gcp_enabled ? 1 : 0
  project                   = local.gcp_project_id
  workload_identity_pool_id = "${substr(local.gcp_v2_name, 0, 16)}-aws-bridge"
  display_name              = "AWS event bridge"
  description               = "Five-layer v2 source-owned AWS event bridge"

  depends_on = [google_project_service.gcp_v2_required]
}

resource "google_iam_workload_identity_pool_provider" "gcp_v2_bridge_from_aws" {
  count                              = local.aws_v2_bridge_to_gcp_enabled ? 1 : 0
  project                            = local.gcp_project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.gcp_v2_bridge_from_aws[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "aws-event-bridge"
  display_name                       = "AWS event bridge"
  description                        = "Trust only the deployment AWS bridge role"
  attribute_mapping = {
    "google.subject"     = "assertion.arn"
    "attribute.aws_role" = "assertion.arn.extract('assumed-role/{role_name}/')"
  }
  attribute_condition = "assertion.arn.startsWith('arn:aws:sts::${data.aws_caller_identity.current[0].account_id}:assumed-role/${aws_iam_role.aws_v2_bridge[0].name}/')"
  aws {
    account_id = data.aws_caller_identity.current[0].account_id
  }

  depends_on = [google_project_service.gcp_v2_required]
}

resource "google_service_account_iam_member" "gcp_v2_bridge_from_aws" {
  count              = local.aws_v2_bridge_to_gcp_enabled ? 1 : 0
  service_account_id = google_service_account.gcp_v2_bridge_target_from_aws[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.gcp_v2_bridge_from_aws[0].name}/attribute.aws_role/${aws_iam_role.aws_v2_bridge[0].name}"
}

resource "google_pubsub_topic_iam_member" "gcp_v2_bridge_from_aws" {
  for_each = local.aws_v2_bridge_gcp_topic_targets
  project  = local.gcp_project_id
  topic    = each.value
  role     = "roles/pubsub.publisher"
  member   = "serviceAccount:${google_service_account.gcp_v2_bridge_target_from_aws[0].email}"
}
