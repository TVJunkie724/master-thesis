variable "project_path" {
  type = string
}

mock_provider "archive" {}
mock_provider "azapi" {}
mock_provider "aws" {}
mock_provider "aws" {
  alias = "sso"
}
mock_provider "awscc" {}
mock_provider "azuread" {}
mock_provider "azurerm" {}
mock_provider "google" {}
mock_provider "kubernetes" {}
mock_provider "local" {}
mock_provider "random" {}
mock_provider "time" {}
mock_provider "tls" {}

run "six_layer_single_cloud_aws_adds_independent_event_bundle" {
  command = plan

  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "123456789012"
      arn        = "arn:aws:iam::123456789012:user/terraform-mock"
      user_id    = "AIDACKCEVSQ6C2EXAMPLE"
    }
  }

  override_data {
    target = data.aws_ssoadmin_instances.aws_six_layer_layer_access
    values = {
      arns               = ["arn:aws:sso:::instance/ssoins-0123456789abcdef"]
      identity_store_ids = ["d-0123456789"]
    }
  }

  override_data {
    target = data.aws_identitystore_users.aws_six_layer_layer_access
    values = {
      users = []
    }
  }

  variables {
    digital_twin_name                     = "drift-test"
    architecture_profile_id               = "six-layer-eventing"
    architecture_profile_version          = "1"
    event_layer_provider                  = "aws"
    layer_1_provider                      = "aws"
    layer_2_provider                      = "aws"
    layer_3_hot_provider                  = "aws"
    layer_3_cold_provider                 = "aws"
    layer_3_archive_provider              = "aws"
    layer_4_provider                      = "aws"
    layer_5_provider                      = "aws"
    layer_3_hot_to_cold_interval_days     = 30
    layer_3_cold_to_archive_interval_days = 90
    layer_3_archive_expiry_interval_days  = 365
    platform_user_email                   = "researcher@example.test"
    platform_user_first_name              = "Thesis"
    platform_user_last_name               = "Researcher"
    aws_layer_access_principal_intent     = "invite_builtin"
    enable_aws_logging                    = false
    aws_event_kinesis_shards              = 1
    aws_six_layer_storage_mover_image     = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test-six-images@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    resolved_component_dimensions = {
      "dimension.aws.aws.ecs-fargate-storage-mover.task_count"   = "1"
      "dimension.aws.aws.kinesis-data-streams.shards_per_stream" = "1"
    }
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "44444444-4444-4444-8444-444444444444"
      artifact_digest = "sha256:4444444444444444444444444444444444444444444444444444444444444444"
      package_path    = "${var.project_path}/.build/aws/six-layer-domain.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/aws/six-layer-domain.zip")}"
      adapter_id      = "adapter.aws.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      length(aws_kinesis_stream.domain_telemetry) == 2 &&
      length(aws_kinesis_stream_consumer.domain_consumers) == 4 &&
      length(aws_sns_topic.domain_control) == 1 &&
      length(aws_sqs_queue.domain_control) == 1 &&
      length(aws_sqs_queue.event_control_dlq) == 1 &&
      length(aws_lambda_function.event_runtime) == 5 &&
      length(aws_s3_bucket.event_telemetry_dlq) == 1 &&
      length(aws_cloudwatch_log_group.eventing) == 1
    )
    error_message = "Six-layer AWS must deploy the complete reviewed Event Layer bundle."
  }

  assert {
    condition = (
      aws_kinesis_stream.domain_telemetry["received"].shard_count == 1 &&
      aws_kinesis_stream.domain_telemetry["processed"].shard_count == 1 &&
      aws_kinesis_stream.domain_telemetry["received"].retention_period == 24 &&
      jsondecode(aws_sns_topic.domain_control[0].archive_policy).MessageRetentionPeriod == "7" &&
      var.aws_event_max_receive_count == 6 &&
      aws_lambda_function.event_runtime["control-router"].memory_size == 256
    )
    error_message = "Six-layer AWS must bind the reviewed Small capacity values."
  }

  assert {
    condition = (
      length(aws_lambda_event_source_mapping.event_runtime) == 4 &&
      length(aws_lambda_event_source_mapping.domain_control) == 1 &&
      length(aws_sqs_queue.aws_aws_sqs_fifo) == 0 &&
      length(aws_lambda_event_source_mapping.aws_six_layer_embedded_events) == 0 &&
      length(aws_lambda_function.aws_six_layer_cross_cloud_bridge) == 0
    )
    error_message = "Single-cloud AWS must use only the independent Event Layer transport and omit embedded transport and every cross-cloud bridge."
  }
}

run "six_layer_single_cloud_azure_adds_independent_event_bundle" {
  command = plan

  variables {
    digital_twin_name                      = "drift-test"
    architecture_profile_id                = "six-layer-eventing"
    architecture_profile_version           = "1"
    event_layer_provider                   = "azure"
    layer_1_provider                       = "azure"
    layer_2_provider                       = "azure"
    layer_3_hot_provider                   = "azure"
    layer_3_cold_provider                  = "azure"
    layer_3_archive_provider               = "azure"
    layer_4_provider                       = "azure"
    layer_5_provider                       = "azure"
    layer_3_hot_to_cold_interval_days      = 30
    layer_3_cold_to_archive_interval_days  = 90
    layer_3_archive_expiry_interval_days   = 365
    platform_user_email                    = "researcher@example.test"
    platform_user_first_name               = "Thesis"
    platform_user_last_name                = "Researcher"
    azure_layer_access_principal_object_id = "11111111-1111-1111-1111-111111111111"
    azure_layer_access_principal_label     = "researcher@example.test"
    enable_azure_logging                   = false
    azure_event_hubs_throughput_units      = 1
    azure_event_partitions                 = 4
    azure_event_retention_hours            = 24
    azure_six_layer_storage_mover_image    = "drifttestv2mock.azurecr.io/storage-mover@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    resolved_component_dimensions = {
      "dimension.azure.azure.container-apps-scheduled-storage-job.task_count"        = "1"
      "dimension.azure.azure.event-hubs-standard-small-medium.throughput_unit_hours" = "730"
      "dimension.azure.azure.event-hubs-standard-small-medium.capacity_unit_hours"   = "0"
    }
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "55555555-5555-4555-8555-555555555555"
      artifact_digest = "sha256:5555555555555555555555555555555555555555555555555555555555555555"
      package_path    = "${var.project_path}/.build/azure/six-layer-domain.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/azure/six-layer-domain.zip")}"
      adapter_id      = "adapter.azure.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      length(azurerm_eventhub_namespace.eventing_standard) == 1 &&
      length(azurerm_eventhub_namespace.eventing_dedicated) == 0 &&
      length(azurerm_eventhub.domain_telemetry_standard) == 3 &&
      length(azurerm_eventhub_consumer_group.domain_standard) == 4 &&
      length(azurerm_servicebus_namespace.eventing) == 1 &&
      length(azurerm_servicebus_topic.domain_control) == 1 &&
      length(azurerm_servicebus_subscription.domain_control) == 1 &&
      length(azurerm_function_app_flex_consumption.event_runtime) == 1 &&
      length(azurerm_log_analytics_workspace.eventing) == 1
    )
    error_message = "Six-layer Azure must deploy the complete reviewed Small Event Layer bundle."
  }

  assert {
    condition = (
      azurerm_eventhub_namespace.eventing_standard[0].capacity == 1 &&
      azurerm_eventhub.domain_telemetry_standard["received"].partition_count == 4 &&
      azurerm_eventhub.domain_telemetry_standard["received"].retention_description[0].retention_time_in_hours == 24 &&
      azurerm_servicebus_subscription.domain_control[0].max_delivery_count == 6 &&
      azurerm_function_app_flex_consumption.event_runtime[0].instance_memory_in_mb == 2048
    )
    error_message = "Six-layer Azure must bind the reviewed Small capacity values."
  }

  assert {
    condition = (
      length(azurerm_servicebus_namespace.azure_azure_service_bus_standard) == 0 &&
      length(azurerm_servicebus_queue.azure_azure_service_bus_standard) == 0 &&
      length(azurerm_servicebus_subscription.azure_azure_service_bus_standard) == 0 &&
      azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter[0].app_settings.ARCHITECTURE_PROFILE == "six-layer-eventing@1" &&
      azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[0].app_settings.SIX_LAYER_DOMAIN_CONSUMER_ENABLED == "false" &&
      azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[0].app_settings.SIX_LAYER_EVENTING_DELIVERY_ENDPOINT_ENABLED == "true"
    )
    error_message = "Single-cloud Azure must replace embedded transport with the independent Event Layer."
  }
}

run "six_layer_single_cloud_gcp_adds_independent_event_bundle" {
  command = plan

  variables {
    digital_twin_name                       = "drift-test"
    architecture_profile_id                 = "six-layer-eventing"
    architecture_profile_version            = "1"
    event_layer_provider                    = "google"
    layer_1_provider                        = "google"
    layer_2_provider                        = "google"
    layer_3_hot_provider                    = "google"
    layer_3_cold_provider                   = "google"
    layer_3_archive_provider                = "google"
    layer_4_provider                        = "google"
    layer_5_provider                        = "google"
    layer_3_hot_to_cold_interval_days       = 30
    layer_3_cold_to_archive_interval_days   = 90
    layer_3_archive_expiry_interval_days    = 365
    platform_user_email                     = "researcher@example.test"
    platform_user_first_name                = "Thesis"
    platform_user_last_name                 = "Researcher"
    gcp_project_id                          = "phase8-poc-project"
    gcp_region                              = "europe-west1"
    gcp_six_layer_platform_image            = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/platform@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    gcp_six_layer_processor_extension_image = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/processor@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    gcp_six_layer_storage_mover_image       = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/storage-mover@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    gcp_six_layer_grafana_image             = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/grafana@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    gcp_event_runtime_image                 = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/event-runtime@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    gcp_grafana_source_cidrs                = ["203.0.113.42/32"]
    enable_gcp_logging                      = false
    resolved_component_dimensions = {
      "dimension.gcp.gcp.cloud-run-storage-job.task_count"                  = "1"
      "dimension.gcp.gcp.pubsub-separated-event-layer-topics.publish_bytes" = "1029376000"
      "dimension.gcp.gcp.cloud-run-worker-pool-fixed-large.resource_count"  = "0"
    }
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "66666666-6666-4666-8666-666666666666"
      artifact_digest = "sha256:6666666666666666666666666666666666666666666666666666666666666666"
      package_path    = "${var.project_path}/.build/azure/six-layer-domain.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/azure/six-layer-domain.zip")}"
      adapter_id      = "adapter.gcp.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      toset(keys(google_pubsub_topic.domain_events)) == toset(["received", "processed", "control", "failure"]) &&
      toset(keys(google_pubsub_subscription.domain_events)) == toset(["telemetry-processor", "historical-persistence", "twin-state-update", "rule-evaluator", "control-router"]) &&
      length(google_cloud_run_v2_service.event_runtime) == 1 &&
      length(google_cloud_run_v2_worker_pool.event_telemetry) == 0 &&
      length(google_logging_project_bucket_config.eventing) == 1 &&
      length(google_logging_project_sink.eventing) == 1
    )
    error_message = "Six-layer GCP must deploy the complete reviewed Small push Event Layer bundle."
  }

  assert {
    condition = (
      google_pubsub_topic.domain_events["received"].message_retention_duration == "86400s" &&
      google_pubsub_subscription.domain_events["control-router"].dead_letter_policy[0].max_delivery_attempts == 6 &&
      google_cloud_run_v2_service.event_runtime[0].template[0].containers[0].resources[0].limits.memory == "512Mi"
    )
    error_message = "Six-layer GCP must bind the reviewed Small capacity values."
  }

  assert {
    condition = (
      toset(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics)) == toset(["command"]) &&
      length(google_pubsub_subscription.gcp_gcp_pubsub_separated_embedded_topics) == 0 &&
      length(google_cloud_run_v2_service.gcp_six_layer_cross_cloud_bridge) == 0 &&
      one([
        for environment in google_cloud_run_v2_service.gcp_gcp_cloud_run_service[0].template[0].containers[0].env : environment.value
        if environment.name == "ARCHITECTURE_PROFILE"
      ]) == "six-layer-eventing@1"
    )
    error_message = "Single-cloud GCP must replace embedded domain transport with the independent Event Layer while retaining the L1 command boundary."
  }
}
