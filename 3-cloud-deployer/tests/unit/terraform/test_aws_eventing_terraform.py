"""Source-level gates for the reviewed AWS Event Layer bundle."""

from pathlib import Path


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"


def _source(filename: str) -> str:
    return (TERRAFORM_ROOT / filename).read_text(encoding="utf-8")


def test_aws_event_layer_owns_exact_reviewed_resource_symbols():
    source = _source("aws_eventing.tf")
    required = {
        'resource "aws_cloudwatch_log_group" "eventing"',
        'resource "aws_kinesis_stream" "domain_telemetry"',
        'resource "aws_kinesis_stream_consumer" "domain_consumers"',
        'resource "aws_lambda_event_source_mapping" "domain_control"',
        'resource "aws_lambda_event_source_mapping" "event_runtime"',
        'resource "aws_lambda_function" "event_runtime"',
        'resource "aws_s3_bucket" "event_telemetry_dlq"',
        'resource "aws_s3_bucket_lifecycle_configuration" "event_telemetry_dlq"',
        'resource "aws_sns_topic" "domain_control"',
        'resource "aws_sns_topic_subscription" "domain_control"',
        'resource "aws_sqs_queue" "domain_control"',
        'resource "aws_sqs_queue" "event_control_dlq"',
        'resource "aws_sqs_queue_redrive_allow_policy" "event_control"',
    }
    assert all(symbol in source for symbol in required)
    assert 'resource "aws_lambda_function_url"' not in source


def test_aws_event_layer_is_profile_and_provider_gated():
    source = _source("aws_eventing.tf")
    assert "local.six_layer_eventing_enabled" in source
    assert 'var.event_layer_provider == "aws"' in source
    assert "aws_event_local_processed_roles" in source
    assert (
        "local.aws_event_l1_local || local.aws_event_l2_local || "
        "local.aws_event_hot_local"
    ) in source


def test_aws_event_layer_uses_graph_capacity_and_bounded_failure_storage():
    source = _source("aws_eventing.tf")
    assert "shard_count      = var.aws_event_kinesis_shards" in source
    assert "retention_period = local.aws_event_retention_hours" in source
    assert 'received  = "${local.aws_event_name}-domain-received"' in source
    assert 'processed = "${local.aws_event_name}-domain-processed"' in source
    assert '"historical-persistence"' in source
    assert '"twin-state-update"' in source
    assert '"rule-evaluator"' in source
    assert (
        "event_source_arn                   = "
        "aws_kinesis_stream_consumer.domain_consumers[each.key].arn"
    ) in source
    assert '"bridge-${channel}" => { stream = channel }' in source
    assert (
        'aws_kinesis_stream_consumer.domain_consumers["bridge-${each.key}"].arn'
        in _source("five_layer_v2_bridge_aws.tf")
    )
    assert (
        "count                = "
        "length(local.aws_event_local_control_event_types) > 0 ? 1 : 0"
    ) in source
    assert (
        "MessageRetentionPeriod = tostring(var.aws_event_control_archive_hours / 24)"
        in source
    )
    assert (
        "maximum_retry_attempts             = var.aws_event_max_receive_count - 1"
        in source
    )
    assert "maxReceiveCount     = var.aws_event_max_receive_count" in source
    assert "CONTROL_FAILURE_QUEUE_URL" in source
    assert "aws_event_local_control_event_types" in source
    assert "filter_policy" in source
    assert '"s3:ListBucket"' in source
    assert "IOT_COMMANDS_ENDPOINT" in source
    assert 'handler       = "lambda_function.lambda_handler"' in source
    assert "aws_s3_bucket.event_telemetry_dlq[0].arn" in source
    assert "ReportBatchItemFailures" in source


def test_inherited_aws_domain_runtime_routes_through_local_event_layer():
    source = _source("aws_five_layer_v2.tf")
    assert (
        "EVENTING_RECEIVED_STREAM_ARN = local.six_layer_eventing_enabled && "
        'var.event_layer_provider == "aws" ? '
        'aws_kinesis_stream.domain_telemetry["received"].arn'
    ) in source
    assert (
        "EVENTING_PROCESSED_STREAM_ARN     = local.six_layer_eventing_enabled && "
        'var.event_layer_provider == "aws" ? '
        'aws_kinesis_stream.domain_telemetry["processed"].arn'
    ) in source
    assert "EVENTING_CONTROL_TOPIC_ARN" in source
    assert "aws_v2_embedded_event_enabled" in source
    assert "local.aws_v2_l2_enabled && local.aws_v2_embedded_event_enabled" in source
    assert "L1_PROVIDER                       = var.layer_1_provider" in source
    assert "L2_PROVIDER                       = var.layer_2_provider" in source
    assert "raw_message_delivery = true" in source


def test_aws_event_layer_can_be_the_source_of_a_directed_bridge():
    source = _source("five_layer_v2_bridge_aws.tf")
    assert "aws_v2_event_bridge_streams" in source
    assert 'aws_kinesis_stream.domain_telemetry["received"].arn' in source
    assert 'aws_kinesis_stream.domain_telemetry["processed"].arn' in source
    assert (
        'resource "aws_sns_topic_subscription" "aws_v2_event_bridge_control_source"'
    ) in source
    assert "aws_v2_event_bridge_control_types" in source
    assert (
        'resource "aws_lambda_event_source_mapping" "aws_v2_event_bridge_telemetry"'
    ) in source
