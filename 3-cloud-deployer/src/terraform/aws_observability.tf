# ==============================================================================
# AWS Observability - CloudWatch Log Groups
#
# Toggle: var.enable_aws_logging (applied at resource level, not in locals)
# Locals define which log groups to create based on layer provider selection.
# The for_each/count guards apply the logging toggle.
# ==============================================================================

locals {
  aws_l0_log_groups = local.aws_enabled ? {
    "l0-ingestion"      = local.aws_l0_ingestion_function_name
    "l0-hot-writer"     = local.aws_l0_hot_writer_function_name
    "l0-hot-reader"     = local.aws_l0_hot_reader_function_name
    "l0-cold-writer"    = local.aws_l0_cold_writer_function_name
    "l0-archive-writer" = local.aws_l0_archive_writer_function_name
  } : {}

  aws_l1_log_groups = var.layer_1_provider == "aws" ? {
    "l1-dispatcher" = local.aws_l1_dispatcher_function_name
    "l1-connector"  = local.aws_l1_connector_function_name
  } : {}

  aws_l2_base_log_groups = var.layer_2_provider == "aws" ? {
    "l2-persister"      = local.aws_l2_persister_function_name
    "processor-wrapper" = local.aws_l2_processor_function_name
  } : {}

  aws_l2_event_checker_log_groups = var.layer_2_provider == "aws" && var.use_event_checking ? {
    "l2-event-checker" = local.aws_l2_event_checker_name
  } : {}

  aws_l2_feedback_log_groups = var.layer_2_provider == "aws" && var.return_feedback_to_device ? {
    "feedback-wrapper" = local.aws_l2_feedback_wrapper_name
  } : {}

  aws_l2_user_processor_log_groups = var.layer_2_provider == "aws" ? {
    for p in var.aws_processors : "processor-${p.name}" => format(local.aws_l2_processor_name_pattern, p.name)
  } : {}

  aws_l2_event_action_log_groups = var.layer_2_provider == "aws" && var.use_event_checking ? {
    for a in var.aws_event_actions : "event-action-${a.name}" => format(local.aws_l2_event_action_name_pattern, a.name)
  } : {}

  aws_l2_event_feedback_log_group = var.layer_2_provider == "aws" && var.aws_event_feedback_enabled ? {
    "event-feedback" = local.aws_l2_event_feedback_name
  } : {}

  aws_l3_log_groups = var.layer_3_hot_provider == "aws" ? {
    "l3-hot-reader"        = local.aws_l3_hot_reader_name
    "l3-hot-to-cold-mover" = local.aws_l3_hot_to_cold_mover_name
    "l3-cold-to-archive"   = local.aws_l3_cold_to_archive_name
  } : {}

  aws_l4_log_groups = var.layer_4_provider == "aws" ? {
    "l4-connector" = local.aws_l4_connector_function_name
  } : {}

  aws_lambda_log_groups = merge(
    local.aws_l0_log_groups, local.aws_l1_log_groups,
    local.aws_l2_base_log_groups, local.aws_l2_event_checker_log_groups,
    local.aws_l2_feedback_log_groups, local.aws_l2_user_processor_log_groups,
    local.aws_l2_event_action_log_groups, local.aws_l2_event_feedback_log_group,
    local.aws_l3_log_groups, local.aws_l4_log_groups
  )
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = var.enable_aws_logging ? local.aws_lambda_log_groups : {}
  name              = "/aws/lambda/${each.value}"
  retention_in_days = var.log_retention_days
  tags              = local.aws_common_tags
}

resource "aws_cloudwatch_log_group" "sfn" {
  count             = var.enable_aws_logging && var.layer_2_provider == "aws" && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
  name              = "/aws/states/${local.aws_l2_event_workflow_name}"
  retention_in_days = var.log_retention_days
  tags              = local.aws_common_tags
}

resource "aws_cloudwatch_log_group" "iot" {
  count             = var.enable_aws_logging && var.layer_1_provider == "aws" ? 1 : 0
  name              = "/aws/iot/${var.digital_twin_name}"
  retention_in_days = var.log_retention_days
  tags              = local.aws_common_tags
}
