# AWS Setup Layer
#
# This file creates the foundation infrastructure for AWS deployments.
# The Setup Layer is deployed FIRST and provides resource organization.
#
# Resources Created:
# - Resource Group: Tag-based grouping for all twin resources
#
# Note: Unlike Azure Resource Groups, AWS Resource Groups are query-based
# and do not contain resources - they provide a logical grouping view.

# ==============================================================================
# Locals for AWS
# ==============================================================================

locals {
  aws_common_tags = {
    DigitalTwin = var.digital_twin_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
  
  # Determine if any layer uses AWS
  aws_enabled = (
    var.layer_1_provider == "aws" ||
    var.layer_2_provider == "aws" ||
    var.layer_3_hot_provider == "aws" ||
    var.layer_3_cold_provider == "aws" ||
    var.layer_3_archive_provider == "aws" ||
    var.layer_4_provider == "aws" ||
    var.layer_5_provider == "aws"
  )

  # ===========================================================================
  # AWS Resource Names - Single Source of Truth
  # ===========================================================================

  # Setup
  aws_resource_group_name = "${var.digital_twin_name}-rg"

  # L0 Glue
  aws_l0_role_name                    = "${var.digital_twin_name}-l0-lambda-role"
  aws_l0_dynamodb_policy_name         = "${var.digital_twin_name}-l0-dynamodb-policy"
  aws_l0_ingestion_function_name      = "${var.digital_twin_name}-l0-ingestion"
  aws_l0_hot_writer_function_name     = "${var.digital_twin_name}-l0-hot-writer"
  aws_l0_hot_reader_function_name     = "${var.digital_twin_name}-l0-hot-reader"
  aws_l0_cold_writer_function_name    = "${var.digital_twin_name}-l0-cold-writer"
  aws_l0_archive_writer_function_name = "${var.digital_twin_name}-l0-archive-writer"

  # L1 IoT
  aws_l1_dispatcher_role_name     = "${var.digital_twin_name}-l1-dispatcher-role"
  aws_l1_dispatcher_policy_name   = "${var.digital_twin_name}-l1-dispatcher-invoke-policy"
  aws_l1_dispatcher_function_name = "${var.digital_twin_name}-l1-dispatcher"
  aws_l1_connector_role_name      = "${var.digital_twin_name}-l1-connector-role"
  aws_l1_connector_function_name  = "${var.digital_twin_name}-connector"
  aws_l1_iot_rule_name            = replace("${var.digital_twin_name}_telemetry_rule", "-", "_")
  aws_l1_iot_rule_role_name       = "${var.digital_twin_name}-l1-iot-rule-role"
  aws_l1_iot_rule_policy_name     = "${var.digital_twin_name}-l1-iot-rule-lambda-policy"
  aws_l1_iot_topic_pattern        = "dt/${var.digital_twin_name}/+/telemetry"

  # L2 Compute
  aws_l2_role_name               = "${var.digital_twin_name}-l2-lambda-role"
  aws_l2_dynamodb_policy_name    = "${var.digital_twin_name}-l2-dynamodb-policy"
  aws_l2_s3_policy_name          = "${var.digital_twin_name}-l2-s3-policy"
  aws_l2_invoke_policy_name      = "${var.digital_twin_name}-l2-invoke-policy"
  aws_l2_persister_function_name = "${var.digital_twin_name}-l2-persister"
  aws_l2_event_checker_name      = "${var.digital_twin_name}-l2-event-checker"
  aws_l2_processor_function_name = "${var.digital_twin_name}-processor"
  aws_l2_processor_name_pattern  = "${var.digital_twin_name}-%s-processor"
  aws_l2_event_workflow_name     = "${var.digital_twin_name}-l2-event-workflow"
  aws_l2_sfn_role_name           = "${var.digital_twin_name}-l2-sfn-role"
  aws_l2_sfn_policy_name         = "${var.digital_twin_name}-l2-sfn-lambda-policy"
  aws_l2_feedback_wrapper_name   = "${var.digital_twin_name}-event-feedback-wrapper"
  aws_l2_event_feedback_name     = "${var.digital_twin_name}-event-feedback"
  aws_l2_iot_publish_policy_name = "${var.digital_twin_name}-l2-iot-publish-policy"

  # L3 Storage
  aws_l3_dynamodb_table_name      = "${var.digital_twin_name}-${local.storage_tier_hot}"
  aws_l3_s3_cold_bucket_name      = "${var.digital_twin_name}-${local.storage_tier_cold}"
  aws_l3_s3_archive_bucket_name   = "${var.digital_twin_name}-${local.storage_tier_archive}"
  aws_l3_role_name                = "${var.digital_twin_name}-l3-lambda-role"
  aws_l3_dynamodb_policy_name     = "${var.digital_twin_name}-l3-dynamodb-policy"
  aws_l3_s3_policy_name           = "${var.digital_twin_name}-l3-s3-policy"
  aws_l3_hot_reader_name          = "${var.digital_twin_name}-l3-hot-reader"
  aws_l3_hot_to_cold_mover_name   = "${var.digital_twin_name}-l3-hot-to-cold-mover"
  aws_l3_hot_to_cold_schedule     = "${var.digital_twin_name}-l3-hot-to-cold-schedule"
  aws_l3_cold_to_archive_name     = "${var.digital_twin_name}-l3-cold-to-archive-mover"
  aws_l3_cold_to_archive_schedule = "${var.digital_twin_name}-l3-cold-to-archive-schedule"

  # L4 TwinMaker
  aws_l4_twinmaker_workspace_id  = "${var.digital_twin_name}-${local.deployment_suffix}"
  aws_l4_twinmaker_role_name     = "${var.digital_twin_name}-l4-twinmaker-role"
  aws_l4_twinmaker_s3_policy     = "${var.digital_twin_name}-l4-twinmaker-s3-policy"
  aws_l4_twinmaker_lambda_policy = "${var.digital_twin_name}-l4-twinmaker-lambda-policy"
  aws_l4_twinmaker_bucket_name   = "${var.digital_twin_name}-twinmaker"
  aws_l4_connector_role_name     = "${var.digital_twin_name}-l4-connector-role"
  aws_l4_connector_policy_name   = "${var.digital_twin_name}-l4-connector-dynamodb-policy"
  aws_l4_connector_function_name = "${var.digital_twin_name}-l4-connector"
  aws_l4_scene_id                = "main-scene"

  # L5 Grafana
  aws_l5_grafana_role_name      = "${var.digital_twin_name}-l5-grafana-role"
  aws_l5_grafana_workspace_name = "${var.digital_twin_name}-grafana"
  aws_l5_grafana_api_key_name   = "${var.digital_twin_name}-admin-key"

  # E2E Testing
  aws_e2e_iot_publish_policy = "${var.digital_twin_name}-e2e-iot-publish"
}

# ==============================================================================
# AWS Resource Group (Tag-based Query)
# ==============================================================================

resource "aws_resourcegroups_group" "main" {
  count = local.aws_enabled ? 1 : 0
  name  = "${var.digital_twin_name}-rg"

  resource_query {
    query = jsonencode({
      ResourceTypeFilters = ["AWS::AllSupported"]
      TagFilters = [
        {
          Key    = "DigitalTwin"
          Values = [var.digital_twin_name]
        }
      ]
    })
  }

  tags = local.aws_common_tags
}

# ==============================================================================
# Data Sources
# ==============================================================================

# Get current AWS account ID and region
data "aws_caller_identity" "current" {
  count = local.aws_enabled ? 1 : 0
}

data "aws_region" "current" {
  count = local.aws_enabled ? 1 : 0
}
