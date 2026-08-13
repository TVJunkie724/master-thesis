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

run "six_layer_aws_azure_gcp_routes_event_targets_without_hidden_landing" {
  command = plan

  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "123456789012"
      arn        = "arn:aws:iam::123456789012:user/terraform-mock"
      user_id    = "AIDACKCEVSQ6C2EXAMPLE"
    }
  }

  variables {
    digital_twin_name                     = "route-test-a"
    architecture_profile_id               = "six-layer-eventing"
    architecture_profile_version          = "1"
    layer_1_provider                      = "aws"
    event_layer_provider                  = "azure"
    layer_2_provider                      = "google"
    layer_3_hot_provider                  = "google"
    layer_3_cold_provider                 = "google"
    layer_3_archive_provider              = "google"
    layer_4_provider                      = "google"
    layer_5_provider                      = "google"
    layer_3_hot_to_cold_interval_days     = 30
    layer_3_cold_to_archive_interval_days = 90
    layer_3_archive_expiry_interval_days  = 365
    platform_user_email                   = "researcher@example.test"
    platform_user_first_name              = "Thesis"
    platform_user_last_name               = "Researcher"
    gcp_project_id                        = "phase8-poc-project"
    gcp_region                            = "europe-west1"
    gcp_v2_platform_image                 = "europe-west1-docker.pkg.dev/phase8-poc-project/route-test-a-v2/platform@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    gcp_v2_processor_extension_image      = "europe-west1-docker.pkg.dev/phase8-poc-project/route-test-a-v2/processor@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    gcp_v2_storage_mover_image            = "europe-west1-docker.pkg.dev/phase8-poc-project/route-test-a-v2/storage@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    gcp_v2_grafana_image                  = "europe-west1-docker.pkg.dev/phase8-poc-project/route-test-a-v2/grafana@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    gcp_grafana_source_cidrs              = ["203.0.113.42/32"]
    aws_v2_bridge_image                   = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/route-test@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    aws_outbound_identity_required        = true
    aws_outbound_identity_destinations    = ["azure"]
    aws_outbound_identity_issuer          = "https://token.actions.githubusercontent.com"
    azure_event_hubs_throughput_units     = 1
    enable_aws_logging                    = false
    enable_azure_logging                  = false
    enable_gcp_logging                    = false
    resolved_component_dimensions = {
      "dimension.azure.azure.event-hubs-standard-small-medium.throughput_unit_hours" = "0"
      "dimension.azure.azure.event-hubs-standard-small-medium.capacity_unit_hours"   = "0"
      "dimension.azure.azure.event-hubs-dedicated-large.capacity_unit_hours"         = "4380"
      "dimension.gcp.gcp.cloud-run-storage-job.task_count"                           = "1"
    }
    resolved_cross_cloud_routes = [
      {
        route_id                = "six.ingestion.event.telemetry"
        logical_edge_id         = "edge.ingestion-to-eventing"
        source_provider         = "aws"
        destination_provider    = "azure"
        execution_kind          = "source_event_forwarder"
        channel_class           = "telemetry"
        event_types             = ["telemetry.received.v1"]
        source_broker_kind      = "telemetry_stream"
        destination_broker_kind = "telemetry_stream"
        identity_exchange       = "aws_oidc_to_entra_federated_credential"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.ingestion.event.control"
        logical_edge_id         = "edge.ingestion-to-eventing"
        source_provider         = "aws"
        destination_provider    = "azure"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["device.command.outcome.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "aws_oidc_to_entra_federated_credential"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.event.processing.telemetry"
        logical_edge_id         = "edge.eventing-to-processing"
        source_provider         = "azure"
        destination_provider    = "gcp"
        execution_kind          = "source_event_forwarder"
        channel_class           = "telemetry"
        event_types             = ["telemetry.received.v1", "telemetry.processed.v1"]
        source_broker_kind      = "telemetry_stream"
        destination_broker_kind = "telemetry_stream"
        identity_exchange       = "entra_managed_identity_oidc_to_gcp_workload_identity_federation"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.event.processing.control"
        logical_edge_id         = "edge.eventing-to-processing"
        source_provider         = "azure"
        destination_provider    = "gcp"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["event.matched.v1", "notification.requested.v1", "extension.action.outcome.v1", "notification.workflow.outcome.v1", "device.command.outcome.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "entra_managed_identity_oidc_to_gcp_workload_identity_federation"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.processing.event.telemetry"
        logical_edge_id         = "edge.processing-to-eventing"
        source_provider         = "gcp"
        destination_provider    = "azure"
        execution_kind          = "source_event_forwarder"
        channel_class           = "telemetry"
        event_types             = ["telemetry.processed.v1"]
        source_broker_kind      = "telemetry_stream"
        destination_broker_kind = "telemetry_stream"
        identity_exchange       = "google_service_account_oidc_to_entra_federated_credential"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.processing.event.control"
        logical_edge_id         = "edge.processing-to-eventing"
        source_provider         = "gcp"
        destination_provider    = "azure"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["event.matched.v1", "notification.requested.v1", "device.command.requested.v1", "extension.action.outcome.v1", "notification.workflow.outcome.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "google_service_account_oidc_to_entra_federated_credential"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.event.ingestion.control"
        logical_edge_id         = "edge.eventing-to-ingestion"
        source_provider         = "azure"
        destination_provider    = "aws"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["device.command.requested.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "entra_managed_identity_oidc_to_assume_role_with_web_identity"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
    ]
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "77777777-7777-4777-8777-777777777777"
      artifact_digest = "sha256:7777777777777777777777777777777777777777777777777777777777777777"
      package_path    = "${var.project_path}/.build/azure/six-layer-domain.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/azure/six-layer-domain.zip")}"
      adapter_id      = "adapter.gcp.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      length(azapi_resource.event_hubs_dedicated_cluster) == 1 &&
      azapi_resource.event_hubs_dedicated_cluster[0].body.sku.capacity == 6 &&
      length(azurerm_eventhub_namespace.eventing_standard) == 0 &&
      length(azurerm_eventhub_namespace.eventing_dedicated) == 1 &&
      length(azurerm_eventhub.domain_telemetry_dedicated) == 3 &&
      azurerm_eventhub.domain_telemetry_dedicated["received"].partition_count == 200 &&
      length(azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge) == 0 &&
      length(azurerm_servicebus_topic.azure_v2_remote_control) == 0 &&
      toset(keys(azurerm_role_assignment.azure_v2_bridge_from_aws_telemetry)) == toset(["event_received"]) &&
      toset(keys(azurerm_role_assignment.azure_v2_bridge_from_aws_control)) == toset(["event"]) &&
      toset(keys(azurerm_role_assignment.azure_v2_bridge_from_gcp_telemetry)) == toset(["event_processed"]) &&
      toset(keys(azurerm_role_assignment.azure_v2_bridge_from_gcp_control)) == toset(["event"])
    )
    error_message = "AWS and GCP inputs must publish directly to the Azure Event Layer without hidden Azure domain landing brokers."
  }

  assert {
    condition = (
      toset(keys(google_pubsub_topic_iam_member.gcp_v2_bridge_from_azure)) == toset(["remote_telemetry", "remote_control"]) &&
      length(aws_iam_role_policy.aws_v2_bridge_target_from_azure) == 1 &&
      contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-telemetry-inbound") &&
      contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-control-inbound")
    )
    error_message = "Azure Event Layer outputs must retain the explicit AWS/GCP domain landing boundary."
  }
}
run "six_layer_azure_gcp_aws_routes_cover_remaining_directed_pairs" {
  command = plan

  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "123456789012"
      arn        = "arn:aws:iam::123456789012:user/terraform-mock"
      user_id    = "AIDACKCEVSQ6C2EXAMPLE"
    }
  }

  variables {
    digital_twin_name                     = "route-test-b"
    architecture_profile_id               = "six-layer-eventing"
    architecture_profile_version          = "1"
    layer_1_provider                      = "azure"
    event_layer_provider                  = "google"
    layer_2_provider                      = "aws"
    layer_3_hot_provider                  = "google"
    layer_3_cold_provider                 = "google"
    layer_3_archive_provider              = "google"
    layer_4_provider                      = "google"
    layer_5_provider                      = "google"
    layer_3_hot_to_cold_interval_days     = 30
    layer_3_cold_to_archive_interval_days = 90
    layer_3_archive_expiry_interval_days  = 365
    platform_user_email                   = "researcher@example.test"
    platform_user_first_name              = "Thesis"
    platform_user_last_name               = "Researcher"
    gcp_project_id                        = "phase8-poc-project"
    gcp_region                            = "europe-west1"
    gcp_v2_platform_image                 = "europe-west1-docker.pkg.dev/phase8-poc-project/route-test-b-v2/platform@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    gcp_v2_storage_mover_image            = "europe-west1-docker.pkg.dev/phase8-poc-project/route-test-b-v2/storage@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    gcp_v2_grafana_image                  = "europe-west1-docker.pkg.dev/phase8-poc-project/route-test-b-v2/grafana@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    gcp_event_runtime_image               = "europe-west1-docker.pkg.dev/phase8-poc-project/route-test-b-v2/event@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    gcp_grafana_source_cidrs              = ["203.0.113.42/32"]
    aws_v2_bridge_image                   = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/route-test@sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    aws_v2_storage_mover_image            = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/route-test-storage@sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    enable_aws_logging                    = false
    enable_azure_logging                  = false
    enable_gcp_logging                    = false
    resolved_component_dimensions = {
      "dimension.aws.aws.ecs-fargate-storage-mover.task_count"              = "1"
      "dimension.gcp.gcp.cloud-run-storage-job.task_count"                  = "1"
      "dimension.gcp.gcp.pubsub-separated-event-layer-topics.publish_bytes" = "1029376000"
      "dimension.gcp.gcp.cloud-run-worker-pool-fixed-large.resource_count"  = "0"
    }
    resolved_cross_cloud_routes = [
      {
        route_id                = "six.ingestion.event.telemetry"
        logical_edge_id         = "edge.ingestion-to-eventing"
        source_provider         = "azure"
        destination_provider    = "gcp"
        execution_kind          = "source_event_forwarder"
        channel_class           = "telemetry"
        event_types             = ["telemetry.received.v1"]
        source_broker_kind      = "telemetry_stream"
        destination_broker_kind = "telemetry_stream"
        identity_exchange       = "entra_managed_identity_oidc_to_gcp_workload_identity_federation"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.ingestion.event.control"
        logical_edge_id         = "edge.ingestion-to-eventing"
        source_provider         = "azure"
        destination_provider    = "gcp"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["device.command.outcome.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "entra_managed_identity_oidc_to_gcp_workload_identity_federation"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.event.processing.telemetry"
        logical_edge_id         = "edge.eventing-to-processing"
        source_provider         = "gcp"
        destination_provider    = "aws"
        execution_kind          = "source_event_forwarder"
        channel_class           = "telemetry"
        event_types             = ["telemetry.received.v1", "telemetry.processed.v1"]
        source_broker_kind      = "telemetry_stream"
        destination_broker_kind = "telemetry_stream"
        identity_exchange       = "google_service_account_oidc_to_assume_role_with_web_identity"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.event.processing.control"
        logical_edge_id         = "edge.eventing-to-processing"
        source_provider         = "gcp"
        destination_provider    = "aws"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["event.matched.v1", "notification.requested.v1", "extension.action.outcome.v1", "notification.workflow.outcome.v1", "device.command.outcome.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "google_service_account_oidc_to_assume_role_with_web_identity"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.processing.event.telemetry"
        logical_edge_id         = "edge.processing-to-eventing"
        source_provider         = "aws"
        destination_provider    = "gcp"
        execution_kind          = "source_event_forwarder"
        channel_class           = "telemetry"
        event_types             = ["telemetry.processed.v1"]
        source_broker_kind      = "telemetry_stream"
        destination_broker_kind = "telemetry_stream"
        identity_exchange       = "aws_subject_token_to_gcp_workload_identity_federation"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.processing.event.control"
        logical_edge_id         = "edge.processing-to-eventing"
        source_provider         = "aws"
        destination_provider    = "gcp"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["event.matched.v1", "notification.requested.v1", "device.command.requested.v1", "extension.action.outcome.v1", "notification.workflow.outcome.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "aws_subject_token_to_gcp_workload_identity_federation"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "six.event.ingestion.control"
        logical_edge_id         = "edge.eventing-to-ingestion"
        source_provider         = "gcp"
        destination_provider    = "azure"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["device.command.requested.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "google_service_account_oidc_to_entra_federated_credential"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
    ]
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "88888888-8888-4888-8888-888888888888"
      artifact_digest = "sha256:8888888888888888888888888888888888888888888888888888888888888888"
      package_path    = "${var.project_path}/.build/aws/six-layer-domain.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/aws/six-layer-domain.zip")}"
      adapter_id      = "adapter.aws.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      toset(keys(google_pubsub_topic.domain_events)) == toset(["received", "processed", "control", "failure"]) &&
      !contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-telemetry-inbound") &&
      !contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-control-inbound") &&
      !contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-telemetry-outbound") &&
      !contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-control-outbound") &&
      toset(keys(google_pubsub_topic_iam_member.gcp_v2_bridge_from_azure)) == toset(["event_received", "event_control"]) &&
      toset(keys(google_pubsub_topic_iam_member.gcp_v2_bridge_from_aws)) == toset(["event_processed", "event_control"])
    )
    error_message = "Azure and AWS inputs must publish directly to the GCP Event Layer without hidden GCP domain landing topics."
  }

  assert {
    condition = (
      toset(keys(aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge)) == toset(["inbound", "outbound"]) &&
      toset(keys(aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge)) == toset(["inbound", "outbound"]) &&
      toset(keys(azurerm_servicebus_topic.azure_v2_remote_control)) == toset(["inbound", "outbound"]) &&
      length(aws_iam_role_policy.aws_v2_bridge_target_from_gcp) == 1 &&
      toset(keys(azurerm_role_assignment.azure_v2_bridge_from_gcp_control)) == toset(["remote"])
    )
    error_message = "GCP Event Layer outputs must retain the explicit AWS/Azure domain landing boundary."
  }
}
