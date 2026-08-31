mock_provider "archive" {}
mock_provider "azapi" {}
mock_provider "aws" {}
mock_provider "aws" {
  alias = "sso"
}
mock_provider "awscc" {}
mock_provider "azuread" {}
mock_provider "azurerm" {}
mock_provider "azurerm" {
  alias = "preparation"
}
mock_provider "google" {}
mock_provider "kubernetes" {}
mock_provider "local" {}
mock_provider "random" {}
mock_provider "time" {}
mock_provider "tls" {}

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
      length(google_logging_project_sink.eventing) == 1 &&
      length(random_password.inter_cloud_token) == 0 &&
      length(terraform_data.phase_8_fixed_region_guard) == 1
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
run "six_layer_single_cloud_gcp_large_uses_six_fixed_worker_pools" {
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
      "dimension.gcp.gcp.cloud-run-storage-job.task_count"                           = "3"
      "dimension.gcp.gcp.firestore-native-standard-raw-and-rollup.timestamp_shards"  = "16"
      "dimension.gcp.apache.bifromq-4.0.0-incubating-on-gke-standard.resource_count" = "12"
      "dimension.gcp.gcp.ordered-mqtt-pubsub-adapter.node_count"                     = "4"
      "dimension.gcp.gcp.pubsub-separated-event-layer-topics.publish_bytes"          = "1000000000000"
      "dimension.gcp.gcp.cloud-run-worker-pool-fixed-large.resource_count"           = "126"
    }
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
      toset(keys(google_cloud_run_v2_worker_pool.event_telemetry)) == toset([
        "telemetry-processor",
        "historical-persistence",
        "twin-state-update",
        "rule-evaluator",
        "audit",
        "realtime-visualization",
      ]) &&
      alltrue([
        for pool in values(google_cloud_run_v2_worker_pool.event_telemetry) :
        pool.scaling[0].manual_instance_count == 21
      ]) &&
      alltrue([
        for key, subscription in google_pubsub_subscription.domain_events :
        length(subscription.push_config) == (key == "control-router" ? 1 : 0)
      ]) &&
      google_pubsub_topic.domain_events["received"].message_retention_duration == "604800s"
    )
    error_message = "GCP Large must use six independent 21-instance StreamingPull pools, push-only control, and seven-day retention."
  }
}
