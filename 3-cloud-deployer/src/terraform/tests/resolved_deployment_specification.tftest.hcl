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

run "five_layer_v2_single_cloud_aws_binds_only_reviewed_bundle" {
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
    target = data.aws_ssoadmin_instances.aws_v2_layer_access
    values = {
      arns               = ["arn:aws:sso:::instance/ssoins-0123456789abcdef"]
      identity_store_ids = ["d-0123456789"]
    }
  }

  override_data {
    target = data.aws_identitystore_users.aws_v2_layer_access
    values = {
      users = []
    }
  }

  variables {
    digital_twin_name                     = "drift-test"
    architecture_profile_id               = "five-layer-baseline"
    architecture_profile_version          = "2"
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
    enable_aws_logging                    = false
    aws_v2_storage_mover_image            = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test-v2-images@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    resolved_component_dimensions = {
      "dimension.aws.aws.ecs-fargate-storage-mover.task_count" = "1"
    }
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "22222222-2222-4222-8222-222222222222"
      artifact_digest = "sha256:2222222222222222222222222222222222222222222222222222222222222222"
      package_path    = "${var.project_path}/.build/aws/five-layer-v2.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/aws/five-layer-v2.zip")}"
      adapter_id      = "adapter.aws.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition     = length(aws_lambda_function.l1_dispatcher) == 0
    error_message = "Five-layer v2 must not deploy the historical v1 AWS dispatcher."
  }

  assert {
    condition     = length(aws_lambda_function.aws_aws_lambda_event_adapter) == 1
    error_message = "Five-layer v2 must deploy the embedded AWS event adapter."
  }

  assert {
    condition = (
      length(aws_lambda_function.aws_v2_extension_action) == 1 &&
      length(aws_lambda_function.aws_v2_processor_extension) == 1 &&
      length(aws_sfn_state_machine.aws_aws_step_functions_standard) == 1 &&
      contains(keys(aws_lambda_function.aws_aws_lambda[0].environment[0].variables), "ACTION_FUNCTION_NAME") &&
      contains(keys(aws_lambda_function.aws_aws_lambda[0].environment[0].variables), "PROCESSOR_EXTENSION_FUNCTION_NAME")
    )
    error_message = "AWS L2 must bind the validated processor, fixed synthetic action, and four-state notification workflow."
  }

  assert {
    condition     = length(aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge) == 0
    error_message = "Single-cloud AWS must omit remote-only Kinesis streams."
  }

  assert {
    condition     = length(terraform_data.aws_v2_bridge_image_guard) == 0
    error_message = "Single-cloud AWS must not request a cross-cloud bridge image."
  }

  assert {
    condition     = length(aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw) == 1 && length(aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup) == 1
    error_message = "Five-layer v2 must bind raw and hourly-rollup storage."
  }

  assert {
    condition = (
      length(aws_ecs_task_definition.aws_aws_ecs_fargate_storage_mover) == 1 &&
      length(aws_codebuild_project.aws_aws_ecr_if_container_selected) == 1 &&
      toset(keys(aws_scheduler_schedule.aws_aws_eventbridge_scheduler)) == toset(["hot-to-cool-000"])
    )
    error_message = "DynamoDB-to-S3 tiering requires one digest-bound finite mover plus its automatic build foundation and task schedule."
  }

  assert {
    condition     = length(aws_s3_bucket_lifecycle_configuration.aws_aws_s3_standard_ia) == 1 && length(aws_s3_bucket_lifecycle_configuration.aws_aws_s3_glacier_deep_archive) == 0
    error_message = "Same-cloud S3 tiering must use one non-conflicting lifecycle configuration."
  }

  assert {
    condition     = length(awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard) == 1 && length(aws_grafana_workspace.aws_aws_amazon_managed_grafana_12) == 1
    error_message = "Five-layer v2 must expose both AWS L4 and L5 surfaces."
  }
}

run "five_layer_v2_single_cloud_azure_omits_remote_event_hubs" {
  command = plan

  variables {
    digital_twin_name                      = "drift-test"
    architecture_profile_id                = "five-layer-baseline"
    architecture_profile_version           = "2"
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
    azure_v2_storage_mover_image           = "drifttestv2mock.azurecr.io/storage-mover@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    resolved_component_dimensions = {
      "dimension.azure.azure.container-apps-scheduled-storage-job.task_count" = "1"
    }
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "33333333-3333-4333-8333-333333333333"
      artifact_digest = "sha256:3333333333333333333333333333333333333333333333333333333333333333"
      package_path    = "${var.project_path}/.build/azure/five-layer-v2.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/azure/five-layer-v2.zip")}"
      adapter_id      = "adapter.azure.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition     = length(azurerm_linux_function_app.l2) == 0
    error_message = "Five-layer v2 must not deploy the historical Azure L2 Function App."
  }

  assert {
    condition     = length(azurerm_servicebus_namespace.azure_azure_service_bus_standard) == 1 && length(azurerm_servicebus_subscription.azure_azure_service_bus_standard) == 1
    error_message = "Single-cloud Azure must retain the mandatory embedded Service Bus path."
  }

  assert {
    condition     = length(azurerm_eventhub_namespace.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge) == 0
    error_message = "Single-cloud Azure must omit remote-only Event Hubs."
  }

  assert {
    condition     = length(azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter) == 1
    error_message = "Five-layer v2 must deploy the Azure event adapter on Flex Consumption."
  }

  assert {
    condition     = azurerm_iothub.azure_azure_iot_hub[0].sku[0].name == "S1" && azurerm_iothub.azure_azure_iot_hub[0].sku[0].capacity == 1
    error_message = "The default Small Azure fixture must bind the reviewed S1 x1 IoT Hub allocation."
  }

  assert {
    condition     = length(azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption) == 1
    error_message = "Azure L2 must deploy its reviewed Flex Consumption processor boundary."
  }

  assert {
    condition = (
      length(azurerm_function_app_flex_consumption.azure_v2_processor_extension) == 1 &&
      length(azurerm_function_app_flex_consumption.azure_v2_extension_action) == 1 &&
      contains(keys(azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[0].app_settings), "V2_PROCESSOR_EXTENSION_KEY") &&
      contains(keys(azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[0].app_settings), "V2_ACTION_FUNCTION_KEY")
    )
    error_message = "Azure L2 must deploy and bind the validated processor plus fixed PoC action boundaries."
  }

  assert {
    condition = (
      length(azurerm_logic_app_workflow.azure_azure_logic_apps_consumption) == 1 &&
      length(azurerm_logic_app_trigger_http_request.azure_azure_logic_apps_consumption) == 1 &&
      length(azurerm_logic_app_action_custom.azure_v2_notification_normalize) == 1 &&
      length(azurerm_logic_app_action_custom.azure_v2_notification_prepare) == 1 &&
      length(azurerm_logic_app_action_custom.azure_v2_notification_deliver) == 1 &&
      length(azurerm_logic_app_action_custom.azure_v2_notification_complete) == 1
    )
    error_message = "Azure L2 must deploy the four-action Logic Apps workflow with one external PoC notification delivery."
  }

  assert {
    condition     = length(azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup) == 1 && length(azurerm_cosmosdb_sql_container.azure_azure_cosmos_db_nosql_raw_and_rollup) == 1
    error_message = "Azure L3 hot must deploy one Cosmos database boundary with a shared raw/rollup container."
  }

  assert {
    condition     = contains([for capability in azurerm_cosmosdb_account.azure_azure_cosmos_db_nosql_raw_and_rollup[0].capabilities : capability.name], "EnableServerless")
    error_message = "The default Small Azure fixture must select Cosmos Serverless."
  }

  assert {
    condition = (
      toset([for path in azurerm_cosmosdb_sql_container.azure_azure_cosmos_db_nosql_raw_and_rollup[0].indexing_policy[0].included_path : path.path]) == toset(["/device_id/?", "/stored_at/?", "/storage_window/?", "/storage_task/?", "/bucket_start/?", "/kind/?", "/metric/?"]) &&
      azurerm_cosmosdb_sql_container.azure_azure_cosmos_db_nosql_raw_and_rollup[0].indexing_policy[0].excluded_path[0].path == "/*"
    )
    error_message = "Azure L3 hot must opt in only the partition and bounded raw/rollup query paths."
  }

  assert {
    condition = (
      contains(keys(azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter[0].app_settings), "V2_ADT_ENDPOINT") &&
      azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[0].app_settings.V2_ADT_MODEL_ID == "dtmi:twin2multicloud:poc:TwinNode;1"
    )
    error_message = "Azure event and processing runtimes must bind the selected local ADT projection target."
  }

  assert {
    condition     = length(azurerm_storage_account.main) == 1 && length(azurerm_storage_container.azure_azure_blob_cool) == 1 && length(azurerm_storage_management_policy.azure_azure_blob_archive) == 1
    error_message = "Azure tiering must reuse one provider account and bind its private cool/archive lifecycle."
  }

  assert {
    condition = (
      length(azurerm_container_registry.azure_azure_acr_basic_if_container_selected) == 1 &&
      length(azurerm_container_app_environment.azure_azure_container_apps_scheduled_storage_job) == 1 &&
      toset(keys(azurerm_container_app_job.azure_azure_container_apps_scheduled_storage_job)) == toset(["hot-to-cool-000"]) &&
      azurerm_container_app_job.azure_azure_container_apps_scheduled_storage_job["hot-to-cool-000"].template[0].container[0].image == var.azure_v2_storage_mover_image
    )
    error_message = "Azure hot-to-cool tiering requires one digest-bound finite mover job for the Small fixture."
  }

  assert {
    condition     = length(azurerm_digital_twins_instance.azure_azure_digital_twins) == 1 && length(azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard) == 1
    error_message = "Five-layer v2 must expose independent Azure L4 and provider-local L5 browser surfaces."
  }

  assert {
    condition     = azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].grafana_major_version == "12" && azurerm_dashboard_grafana.azure_azure_managed_grafana_12_standard[0].sku == "Standard"
    error_message = "Azure L5 must use the frozen Managed Grafana 12 Standard selection."
  }

  assert {
    condition     = length(azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader) == 1
    error_message = "Azure L5 must expose L3 hot through its dedicated Flex raw-history reader."
  }

  assert {
    condition = (
      azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_human_reader"].role_definition_name == "Azure Digital Twins Data Reader" &&
      azurerm_role_assignment.azure_azure_entra_layer_access_bindings["grafana_human_viewer"].role_definition_name == "Grafana Viewer" &&
      azurerm_role_assignment.azure_azure_entra_layer_access_bindings["grafana_provisioner"].role_definition_name == "Grafana Admin"
    )
    error_message = "Azure browser access must remain read-only for the human principal while the deployer can provision Grafana."
  }

}

run "five_layer_v2_remote_azure_large_binds_dedicated_capacity" {
  command = plan

  variables {
    digital_twin_name                      = "drift-test"
    architecture_profile_id                = "five-layer-baseline"
    architecture_profile_version           = "2"
    layer_1_provider                       = "aws"
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
    enable_aws_logging                     = false
    enable_azure_logging                   = false
    aws_v2_bridge_image                    = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test-v2-images@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    azure_v2_storage_mover_image           = "drifttestv2mock.azurecr.io/storage-mover@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    resolved_component_dimensions = {
      "dimension.azure.azure.event-hubs-only-for-reviewed-remote-telemetry-edge.throughput_unit_hours" = "0"
      "dimension.azure.azure.event-hubs-only-for-reviewed-remote-telemetry-edge.capacity_unit_hours"   = "4380"
      "dimension.azure.azure.container-apps-scheduled-storage-job.task_count"                          = "30"
    }
    resolved_cross_cloud_routes = [
      {
        route_id                = "graph.ingestion.processing.telemetry"
        logical_edge_id         = "edge.ingestion-to-processing"
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
        route_id                = "graph.ingestion.hot.control"
        logical_edge_id         = "edge.ingestion-to-hot-storage"
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
        route_id                = "graph.processing.ingestion.control"
        logical_edge_id         = "edge.processing-to-ingestion"
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
      artifact_id     = "44444444-4444-4444-8444-444444444444"
      artifact_digest = "sha256:4444444444444444444444444444444444444444444444444444444444444444"
      package_path    = "${var.project_path}/.build/azure/five-layer-v2.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/azure/five-layer-v2.zip")}"
      adapter_id      = "adapter.azure.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition     = length(azurerm_eventhub_cluster.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge) == 1 && length(azapi_update_resource.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge) == 1
    error_message = "Large Azure remote telemetry must bind one Dedicated cluster and its AzAPI capacity update."
  }

  assert {
    condition     = azapi_update_resource.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge[0].body.sku.capacity == 6
    error_message = "Large Azure remote telemetry must apply the reviewed six-CU allocation."
  }

  assert {
    condition     = azurerm_eventhub.azure_azure_event_hubs_only_for_reviewed_remote_telemetry_edge["inbound"].partition_count == 200
    error_message = "Large Azure remote telemetry must retain the reviewed 200-partition Event Hub."
  }

  assert {
    condition     = length(azurerm_function_app_flex_consumption.azure_v2_processor_extension) == 1
    error_message = "Cross-cloud Azure L2 must retain its validated processor extension boundary."
  }

  assert {
    condition     = length(azurerm_container_app_job.azure_azure_container_apps_scheduled_storage_job) == 30
    error_message = "The Large Azure fixture must materialize all 30 reviewed finite storage tasks."
  }

  assert {
    condition = (
      length(terraform_data.aws_v2_bridge_image_guard) == 1 &&
      length(aws_codebuild_project.aws_aws_ecr_if_container_selected) == 1
    )
    error_message = "AWS outbound event routes must request one digest-bound bridge image and its automatic build foundation."
  }
}

run "five_layer_v2_single_cloud_gcp_activates_only_v2_foundation" {
  command = plan

  variables {
    digital_twin_name                     = "drift-test"
    architecture_profile_id               = "five-layer-baseline"
    architecture_profile_version          = "2"
    layer_1_provider                      = "google"
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
    gcp_v2_platform_image                 = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/platform@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    gcp_v2_processor_extension_image      = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/processor@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    gcp_v2_storage_mover_image            = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/storage-mover@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    gcp_v2_grafana_image                  = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/grafana@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    gcp_grafana_source_cidrs              = ["203.0.113.42/32"]
    enable_gcp_logging                    = false
    resolved_component_dimensions = {
      "dimension.gcp.gcp.cloud-run-storage-job.task_count" = "1"
    }
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "55555555-5555-4555-8555-555555555555"
      artifact_digest = "sha256:5555555555555555555555555555555555555555555555555555555555555555"
      package_path    = "${var.project_path}/.build/azure/five-layer-v2.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/azure/five-layer-v2.zip")}"
      adapter_id      = "adapter.gcp.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      length(google_cloudfunctions2_function.dispatcher) == 0 &&
      length(google_cloudfunctions2_function.persister) == 0 &&
      length(google_firestore_database.main) == 0 &&
      length(google_storage_bucket.function_source) == 0
    )
    error_message = "Five-layer v2 GCP must not deploy the historical Cloud Functions/Firestore bundle."
  }

  assert {
    condition = toset(keys(google_project_service.gcp_v2_required)) == toset([
      "artifactregistry.googleapis.com",
      "cloudbuild.googleapis.com",
      "cloudscheduler.googleapis.com",
      "compute.googleapis.com",
      "container.googleapis.com",
      "firestore.googleapis.com",
      "iap.googleapis.com",
      "logging.googleapis.com",
      "monitoring.googleapis.com",
      "storage.googleapis.com",
      "workflows.googleapis.com",
    ])
    error_message = "Single-cloud GCP v2 must enable exactly its reviewed platform API foundation."
  }


  assert {
    condition = (
      length(google_artifact_registry_repository.gcp_gcp_artifact_registry_if_container_selected) == 1 &&
      length(google_storage_bucket.gcp_v2_cloud_build_sources) == 1 &&
      contains(keys(google_service_account.gcp_v2_runtime), "build") &&
      length(google_artifact_registry_repository_iam_member.gcp_v2_build_writer) == 1 &&
      length(google_storage_bucket_iam_member.gcp_v2_build_source_reader) == 1 &&
      length(google_project_iam_member.gcp_v2_build_log_writer) == 1 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter) == 3 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_service) == 1 &&
      length(google_cloud_run_v2_service.gcp_v2_processor_extension) == 1 &&
      length(google_cloud_run_v2_service.gcp_v2_action_sink) == 1 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_twin_api_materializer) == 1 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_iap_twin_explorer) == 1 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_raw_history_reader) == 1 &&
      length(google_cloud_run_v2_service_iam_member.gcp_v2_action_sink_invoker) == 2 &&
      length(google_cloud_run_v2_service_iam_member.gcp_gcp_cloud_run_iap_twin_explorer) == 1 &&
      length(google_iap_web_cloud_run_service_iam_member.gcp_gcp_cloud_run_iap_twin_explorer) == 1 &&
      length(google_workflows_workflow.gcp_gcp_workflows) == 1
    )
    error_message = "Single-cloud GCP v2 must bind its event adapter, validated processor, action boundary, workflow, Twin API, and IAP Explorer."
  }

  assert {
    condition = (
      length(google_container_cluster.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard) == 1 &&
      length(google_container_cluster.gcp_grafana_oss_12_on_gke) == 0 &&
      google_container_cluster.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard[0].initial_node_count == 1 &&
      !google_container_cluster.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard[0].remove_default_node_pool &&
      google_container_node_pool.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard[0].node_count == 3 &&
      length(google_container_node_pool.gcp_gcp_ordered_mqtt_pubsub_adapter) == 0 &&
      length(kubernetes_namespace_v1.gcp_grafana_oss_12_on_gke) == 1 &&
      length(google_compute_disk.gcp_gcp_persistent_disk_rwo) == 1 &&
      length(kubernetes_persistent_volume_v1.gcp_gcp_persistent_disk_rwo) == 1 &&
      length(kubernetes_persistent_volume_claim_v1.gcp_gcp_persistent_disk_rwo) == 1 &&
      length(kubernetes_secret_v1.gcp_gcp_grafana_tls_load_balancer) == 1 &&
      length(kubernetes_deployment_v1.gcp_grafana_oss_12_on_gke) == 1 &&
      length(kubernetes_service_v1.gcp_gcp_grafana_tls_load_balancer) == 1 &&
      length(google_compute_address.gcp_gcp_grafana_tls_load_balancer) == 1
    )
    error_message = "Single-cloud GCP v2 must retain one general L5 node beside the three-node BifroMQ pool and bind exactly one Grafana pod, disk, TLS secret, and CIDR-scoped LoadBalancer."
  }

  assert {
    condition = (
      length(kubernetes_deployment_v1.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard) == 1 &&
      kubernetes_deployment_v1.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard[0].spec[0].replicas == "3" &&
      kubernetes_deployment_v1.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard[0].spec[0].template[0].spec[0].container[0].image == "docker.io/apache/bifromq@sha256:14856495892e3b84d25092a90de3c2fc149a3482afd283abb95fdff18effd924" &&
      length(kubernetes_deployment_v1.gcp_gcp_ordered_mqtt_pubsub_adapter) == 1 &&
      kubernetes_deployment_v1.gcp_gcp_ordered_mqtt_pubsub_adapter[0].spec[0].replicas == "1" &&
      length(kubernetes_service_v1.gcp_gcp_external_load_balancer) == 1 &&
      kubernetes_service_v1.gcp_gcp_external_load_balancer[0].spec[0].port[0].port == 8883 &&
      length(google_pubsub_subscription.gcp_v2_command_adapter) == 1 &&
      length(google_cloud_run_v2_service_iam_member.gcp_v2_ingress_invoker) == 1
    )
    error_message = "Single-cloud GCP v2 must materialize the pinned authenticated BifroMQ edge, one ordered MQTT adapter, its TLS LoadBalancer, and the command return path."
  }

  assert {
    condition = (
      strcontains(kubernetes_config_map_v1.gcp_v2_bifromq[0].data["standalone.yml"], "org.apache.bifromq.demo.plugin.DemoAuthProvider") &&
      strcontains(kubernetes_config_map_v1.gcp_v2_bifromq[0].data["standalone.yml"], "tlsListener:") &&
      !strcontains(kubernetes_config_map_v1.gcp_v2_bifromq[0].data["standalone.yml"], "wsListener:\n            enable: true")
    )
    error_message = "The GCP v2 device edge must delegate auth and expose TLS without enabling the unreviewed WebSocket listener."
  }

  assert {
    condition = (
      toset(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics)) == toset(["received", "processed", "domain", "command", "failure"]) &&
      length(google_pubsub_subscription.gcp_gcp_pubsub_separated_embedded_topics) == 4
    )
    error_message = "Single-cloud GCP v2 must retain separated ordered telemetry, domain, command, and failure channels."
  }

  assert {
    condition = (
      length(google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup) == 1 &&
      length(google_firestore_field.gcp_gcp_firestore_native_standard_raw_and_rollup) == 7 &&
      length(google_firestore_index.gcp_gcp_firestore_native_standard_raw_and_rollup) == 3 &&
      length(google_firestore_index.gcp_gcp_firestore_native_standard_bounded_twin) == 2 &&
      length(google_storage_bucket.gcp_gcp_cloud_storage_nearline) == 1 &&
      length(google_storage_bucket.gcp_gcp_cloud_storage_archive) == 0 &&
      length(google_cloud_run_v2_job.gcp_gcp_cloud_run_storage_job) == 1 &&
      length(google_cloud_scheduler_job.gcp_gcp_cloud_scheduler) == 1
    )
    error_message = "Single-cloud GCP v2 must bind one Firestore hot store, one Nearline bucket with native archive transition, and one finite source-owned mover."
  }
}

run "five_layer_v2_gcp_source_owns_both_remote_archive_transitions" {
  command = plan

  variables {
    digital_twin_name                      = "drift-test"
    architecture_profile_id                = "five-layer-baseline"
    architecture_profile_version           = "2"
    layer_1_provider                       = "google"
    layer_2_provider                       = "google"
    layer_3_hot_provider                   = "google"
    layer_3_cold_provider                  = "google"
    layer_3_archive_provider               = "azure"
    layer_4_provider                       = "google"
    layer_5_provider                       = "google"
    layer_3_hot_to_cold_interval_days      = 30
    layer_3_cold_to_archive_interval_days  = 90
    layer_3_archive_expiry_interval_days   = 365
    platform_user_email                    = "researcher@example.test"
    platform_user_first_name               = "Thesis"
    platform_user_last_name                = "Researcher"
    gcp_project_id                         = "phase8-poc-project"
    gcp_region                             = "europe-west1"
    gcp_v2_platform_image                  = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/platform@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    gcp_v2_processor_extension_image       = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/processor@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    gcp_v2_storage_mover_image             = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/storage-mover@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    gcp_v2_grafana_image                   = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/grafana@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    gcp_grafana_source_cidrs               = ["203.0.113.42/32"]
    azure_layer_access_principal_object_id = "11111111-1111-1111-1111-111111111111"
    azure_layer_access_principal_label     = "researcher@example.test"
    enable_gcp_logging                     = false
    enable_azure_logging                   = false
    resolved_component_dimensions = {
      "dimension.gcp.gcp.firestore-native-standard-raw-and-rollup.timestamp_shards" = "16"
      "dimension.gcp.gcp.cloud-run-storage-job.task_count"                          = "3"
    }
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "66666666-6666-4666-8666-666666666666"
      artifact_digest = "sha256:6666666666666666666666666666666666666666666666666666666666666666"
      package_path    = "${var.project_path}/.build/azure/five-layer-v2.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/azure/five-layer-v2.zip")}"
      adapter_id      = "adapter.gcp.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      toset(keys(google_cloud_run_v2_job.gcp_gcp_cloud_run_storage_job)) == toset(["hot-to-cool", "cool-to-archive"]) &&
      toset(keys(google_cloud_scheduler_job.gcp_gcp_cloud_scheduler)) == toset(["hot-to-cool", "cool-to-archive"]) &&
      google_cloud_run_v2_job.gcp_gcp_cloud_run_storage_job["hot-to-cool"].template[0].task_count == 3 &&
      google_cloud_run_v2_job.gcp_gcp_cloud_run_storage_job["hot-to-cool"].template[0].parallelism == 3 &&
      google_cloud_scheduler_job.gcp_gcp_cloud_scheduler["hot-to-cool"].schedule == "*/5 * * * *" &&
      length(google_storage_bucket.gcp_gcp_cloud_storage_nearline) == 1 &&
      length(google_storage_bucket.gcp_gcp_cloud_storage_archive) == 0
    )
    error_message = "GCP must bind the reviewed finite source-side transitions, Large task count, five-minute hot schedule, and remote archive placement."
  }

  assert {
    condition = (
      terraform_data.gcp_v2_hot_capacity_guard[0].input.timestamp_shards == 16 &&
      google_container_node_pool.gcp_apache_bifromq_4_0_0_incubating_on_gke_standard[0].node_count == 12 &&
      google_container_node_pool.gcp_gcp_ordered_mqtt_pubsub_adapter[0].node_count == 4 &&
      toset(keys(google_firestore_index.gcp_gcp_firestore_native_standard_raw_and_rollup)) == toset(["raw_history", "raw_mover", "rollup_history"]) &&
      contains([for field in google_firestore_index.gcp_gcp_firestore_native_standard_raw_and_rollup["raw_history"].fields : field.field_path], "timestamp_shard") &&
      contains([for field in google_firestore_index.gcp_gcp_firestore_native_standard_raw_and_rollup["raw_mover"].fields : field.field_path], "timestamp_shard") &&
      !contains([for field in google_firestore_index.gcp_gcp_firestore_native_standard_raw_and_rollup["rollup_history"].fields : field.field_path], "timestamp_shard")
    )
    error_message = "Large GCP hot storage must preserve its reviewed sixteen-way timestamp shard in the raw history and mover indexes only."
  }
}

run "five_layer_v2_gcp_archive_only_accepts_remote_cool_objects" {
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
    target = data.aws_ssoadmin_instances.aws_v2_layer_access
    values = {
      arns               = ["arn:aws:sso:::instance/ssoins-0123456789abcdef"]
      identity_store_ids = ["d-0123456789"]
    }
  }

  override_data {
    target = data.aws_identitystore_users.aws_v2_layer_access
    values = {
      users = []
    }
  }

  variables {
    digital_twin_name                     = "drift-test"
    architecture_profile_id               = "five-layer-baseline"
    architecture_profile_version          = "2"
    layer_1_provider                      = "google"
    layer_2_provider                      = "google"
    layer_3_hot_provider                  = "aws"
    layer_3_cold_provider                 = "aws"
    layer_3_archive_provider              = "google"
    layer_4_provider                      = "google"
    layer_5_provider                      = "aws"
    layer_3_hot_to_cold_interval_days     = 30
    layer_3_cold_to_archive_interval_days = 90
    layer_3_archive_expiry_interval_days  = 365
    platform_user_email                   = "researcher@example.test"
    platform_user_first_name              = "Thesis"
    platform_user_last_name               = "Researcher"
    gcp_project_id                        = "phase8-poc-project"
    gcp_region                            = "europe-west1"
    gcp_v2_platform_image                 = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/platform@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    gcp_v2_processor_extension_image      = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/processor@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    enable_gcp_logging                    = false
    enable_aws_logging                    = false
    aws_v2_storage_mover_image            = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test-v2-images@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    aws_v2_bridge_image                   = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test-v2-images@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    resolved_component_dimensions = {
      "dimension.aws.aws.ecs-fargate-storage-mover.task_count" = "1"
    }
    resolved_cross_cloud_routes = [
      {
        route_id                = "graph.ingestion.hot.control"
        logical_edge_id         = "edge.ingestion-to-hot-storage"
        source_provider         = "gcp"
        destination_provider    = "aws"
        execution_kind          = "source_event_forwarder"
        channel_class           = "control"
        event_types             = ["device.command.outcome.v1"]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "google_service_account_oidc_to_assume_role_with_web_identity"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id                = "graph.processing.hot.telemetry"
        logical_edge_id         = "edge.processing-to-hot-storage"
        source_provider         = "gcp"
        destination_provider    = "aws"
        execution_kind          = "source_event_forwarder"
        channel_class           = "telemetry"
        event_types             = ["telemetry.processed.v1"]
        source_broker_kind      = "telemetry_stream"
        destination_broker_kind = "telemetry_stream"
        identity_exchange       = "google_service_account_oidc_to_assume_role_with_web_identity"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id             = "graph.processing.hot.control"
        logical_edge_id      = "edge.processing-to-hot-storage"
        source_provider      = "gcp"
        destination_provider = "aws"
        execution_kind       = "source_event_forwarder"
        channel_class        = "control"
        event_types = [
          "extension.action.outcome.v1",
          "notification.workflow.outcome.v1",
        ]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "google_service_account_oidc_to_assume_role_with_web_identity"
        payload_contract_id     = "canonical-domain-event.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
      {
        route_id             = "graph.hot.twin.control"
        logical_edge_id      = "edge.hot-storage-to-twin-state"
        source_provider      = "aws"
        destination_provider = "gcp"
        execution_kind       = "source_event_forwarder"
        channel_class        = "control"
        event_types = [
          "twin.state.upserted",
          "twin.model.upserted",
          "twin.relationship.upserted",
          "twin.relationship.deleted",
        ]
        source_broker_kind      = "control_topic"
        destination_broker_kind = "control_topic"
        identity_exchange       = "aws_subject_token_to_gcp_workload_identity_federation"
        payload_contract_id     = "twin_projection.v1"
        trust_contract_id       = "trust.workload-identity-federation"
      },
    ]
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "77777777-7777-4777-8777-777777777777"
      artifact_digest = "sha256:7777777777777777777777777777777777777777777777777777777777777777"
      package_path    = "${var.project_path}/.build/azure/five-layer-v2.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/azure/five-layer-v2.zip")}"
      adapter_id      = "adapter.gcp.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      length(google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup) == 1 &&
      length(google_storage_bucket.gcp_gcp_cloud_storage_nearline) == 0 &&
      length(google_storage_bucket.gcp_gcp_cloud_storage_archive) == 1 &&
      length(google_cloud_run_v2_job.gcp_gcp_cloud_run_storage_job) == 0
    )
    error_message = "GCP L4 plus archive-only storage must share one L4 database, create one direct-ingress Archive bucket, and omit source-side movers."
  }

  assert {
    condition = (
      toset(keys(aws_kinesis_stream.aws_aws_kinesis_only_for_reviewed_remote_telemetry_edge)) == toset(["inbound"]) &&
      length(aws_sns_topic.aws_aws_sns_fifo_only_for_reviewed_remote_control_edge) == 1 &&
      length(aws_sqs_queue.aws_v2_remote_control) == 1 &&
      contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-telemetry-outbound") &&
      contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-control-outbound") &&
      contains(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics), "remote-control-inbound")
    )
    error_message = "A provider used on both sides must materialize route-owned inbound and outbound telemetry/control brokers without inventing a fixed sender role."
  }
}

run "five_layer_v2_gcp_l4_stays_independent_from_aws_l3_l5" {
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
    target = data.aws_ssoadmin_instances.aws_v2_layer_access
    values = {
      arns               = ["arn:aws:sso:::instance/ssoins-0123456789abcdef"]
      identity_store_ids = ["d-0123456789"]
    }
  }

  override_data {
    target = data.aws_identitystore_users.aws_v2_layer_access
    values = {
      users = []
    }
  }

  variables {
    digital_twin_name                     = "drift-test"
    architecture_profile_id               = "five-layer-baseline"
    architecture_profile_version          = "2"
    layer_1_provider                      = "aws"
    layer_2_provider                      = "aws"
    layer_3_hot_provider                  = "aws"
    layer_3_cold_provider                 = "aws"
    layer_3_archive_provider              = "aws"
    layer_4_provider                      = "google"
    layer_5_provider                      = "aws"
    layer_3_hot_to_cold_interval_days     = 30
    layer_3_cold_to_archive_interval_days = 90
    layer_3_archive_expiry_interval_days  = 365
    platform_user_email                   = "researcher@example.test"
    platform_user_first_name              = "Thesis"
    platform_user_last_name               = "Researcher"
    gcp_project_id                        = "phase8-poc-project"
    gcp_region                            = "europe-west1"
    gcp_v2_platform_image                 = "europe-west1-docker.pkg.dev/phase8-poc-project/drift-test-v2/platform@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    enable_aws_logging                    = false
    enable_gcp_logging                    = false
    aws_v2_storage_mover_image            = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test-v2-images@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
    aws_v2_bridge_image                   = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test-v2-images@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
    resolved_component_dimensions = {
      "dimension.aws.aws.ecs-fargate-storage-mover.task_count" = "1"
    }
    resolved_cross_cloud_routes = [{
      route_id             = "graph.hot.twin.control"
      logical_edge_id      = "edge.hot-storage-to-twin-state"
      source_provider      = "aws"
      destination_provider = "gcp"
      execution_kind       = "source_event_forwarder"
      channel_class        = "control"
      event_types = [
        "twin.state.upserted",
        "twin.model.upserted",
        "twin.relationship.upserted",
        "twin.relationship.deleted",
      ]
      source_broker_kind      = "control_topic"
      destination_broker_kind = "control_topic"
      identity_exchange       = "aws_subject_token_to_gcp_workload_identity_federation"
      payload_contract_id     = "twin_projection.v1"
      trust_contract_id       = "trust.workload-identity-federation"
    }]
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "88888888-8888-4888-8888-888888888888"
      artifact_digest = "sha256:8888888888888888888888888888888888888888888888888888888888888888"
      package_path    = "${var.project_path}/.build/aws/five-layer-v2.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/aws/five-layer-v2.zip")}"
      adapter_id      = "adapter.aws.python311"
      adapter_version = "1"
    }]
  }

  assert {
    condition = (
      length(google_firestore_database.gcp_gcp_firestore_native_standard_raw_and_rollup) == 1 &&
      length(google_firestore_index.gcp_gcp_firestore_native_standard_raw_and_rollup) == 0 &&
      length(google_firestore_index.gcp_gcp_firestore_native_standard_bounded_twin) == 2 &&
      toset(keys(google_cloud_run_v2_service.gcp_gcp_cloud_run_event_adapter)) == toset(["domain"]) &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_twin_api_materializer) == 1 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_iap_twin_explorer) == 1 &&
      length(google_cloud_run_v2_service.gcp_gcp_cloud_run_raw_history_reader) == 0 &&
      length(google_cloud_run_v2_service_iam_member.gcp_gcp_cloud_run_iap_twin_explorer) == 1 &&
      length(google_iap_web_cloud_run_service_iam_member.gcp_gcp_cloud_run_iap_twin_explorer) == 1 &&
      toset(keys(google_pubsub_topic.gcp_gcp_pubsub_separated_embedded_topics)) == toset(["domain", "failure", "remote-control-inbound"]) &&
      toset(keys(google_pubsub_subscription.gcp_gcp_pubsub_separated_embedded_topics)) == toset(["domain", "twin"])
    )
    error_message = "Independent GCP L4 must create only its shared data database, bounded relationship indexes, Twin materializer, read-only IAP Explorer, and domain path while AWS retains L3/L5."
  }
}

run "all_aws_selections_bind_to_resources" {
  command = plan

  variables {
    digital_twin_name                       = "drift-test"
    layer_1_provider                        = "aws"
    layer_2_provider                        = "aws"
    layer_3_hot_provider                    = "aws"
    layer_3_cold_provider                   = "aws"
    layer_3_archive_provider                = "aws"
    layer_4_provider                        = "aws"
    layer_5_provider                        = "aws"
    aws_l1_lambda_memory_mb                 = 256
    aws_l2_lambda_memory_mb                 = 256
    aws_dynamodb_billing_mode               = "PAY_PER_REQUEST"
    aws_l3_reader_lambda_memory_mb          = 256
    aws_l3_cool_storage_class               = "STANDARD_IA"
    aws_hot_to_cool_mover_memory_mb         = 512
    aws_hot_to_cool_schedule_expression     = "rate(1 day)"
    aws_l3_archive_storage_class            = "DEEP_ARCHIVE"
    aws_cool_to_archive_mover_memory_mb     = 512
    aws_cool_to_archive_schedule_expression = "rate(7 days)"
    aws_l4_lambda_memory_mb                 = 256
    use_event_checking                      = false
    enable_aws_logging                      = false
  }

  assert {
    condition     = aws_lambda_function.l1_dispatcher[0].memory_size == 256
    error_message = "AWS L1 memory drifted from the resolved specification."
  }

  assert {
    condition     = aws_dynamodb_table.l3_hot[0].billing_mode == "PAY_PER_REQUEST"
    error_message = "AWS DynamoDB billing mode drifted from the resolved specification."
  }

  assert {
    condition     = aws_cloudwatch_event_rule.l3_hot_to_cold[0].schedule_expression == "rate(1 day)"
    error_message = "AWS hot-to-cool schedule drifted from the resolved specification."
  }

  assert {
    condition     = aws_cloudwatch_event_rule.l3_cold_to_archive[0].schedule_expression == "rate(7 days)"
    error_message = "AWS cool-to-archive schedule drifted from the resolved specification."
  }
}

run "all_azure_selections_bind_to_resources" {
  command = plan

  variables {
    digital_twin_name                    = "drift-test"
    layer_1_provider                     = "azure"
    layer_2_provider                     = "azure"
    layer_3_hot_provider                 = "azure"
    layer_3_cold_provider                = "azure"
    layer_3_archive_provider             = "azure"
    layer_4_provider                     = "azure"
    layer_5_provider                     = "azure"
    azure_iot_hub_sku                    = "S3"
    azure_iot_hub_capacity               = 5
    azure_l1_function_plan_sku           = "Y1"
    azure_l2_function_plan_sku           = "Y1"
    azure_cosmos_capacity_mode           = "serverless"
    azure_l3_function_plan_sku           = "Y1"
    azure_storage_account_tier           = "Standard"
    azure_storage_replication_type       = "LRS"
    azure_l3_cool_blob_tier              = "Cool"
    azure_hot_to_cool_timer_schedule     = "0 0 0 * * *"
    azure_l3_archive_blob_tier           = "Archive"
    azure_cool_to_archive_timer_schedule = "0 0 0 * * 0"
    azure_l4_function_plan_sku           = "Y1"
    azure_grafana_sku                    = "Standard"
    use_event_checking                   = false
    enable_azure_logging                 = false
  }

  assert {
    condition     = azurerm_iothub.main[0].sku[0].name == "S3"
    error_message = "Azure IoT Hub SKU drifted from the resolved specification."
  }

  assert {
    condition     = azurerm_iothub.main[0].sku[0].capacity == 5
    error_message = "Azure IoT Hub capacity drifted from the resolved specification."
  }

  assert {
    condition     = azurerm_service_plan.l3[0].sku_name == "Y1"
    error_message = "Azure L3 Function plan drifted from the resolved specification."
  }

  assert {
    condition     = azurerm_dashboard_grafana.main[0].sku == "Standard"
    error_message = "Azure Grafana SKU drifted from the resolved specification."
  }
}

run "gcp_storage_selections_bind_to_resources" {
  command = plan

  variables {
    digital_twin_name                       = "drift-test"
    layer_1_provider                        = "aws"
    layer_2_provider                        = "aws"
    layer_3_hot_provider                    = "google"
    layer_3_cold_provider                   = "google"
    layer_3_archive_provider                = "google"
    layer_4_provider                        = "aws"
    layer_5_provider                        = "aws"
    aws_l1_lambda_memory_mb                 = 256
    aws_l2_lambda_memory_mb                 = 256
    aws_l4_lambda_memory_mb                 = 256
    gcp_project_id                          = "drift-test-project"
    gcp_firestore_mode                      = "FIRESTORE_NATIVE"
    gcp_l3_reader_function_memory_mb        = 256
    gcp_l3_reader_function_min_instances    = 0
    gcp_l3_reader_function_max_instances    = 10
    gcp_l3_cool_storage_class               = "NEARLINE"
    gcp_hot_to_cool_mover_memory_mb         = 512
    gcp_hot_to_cool_mover_min_instances     = 0
    gcp_hot_to_cool_mover_max_instances     = 1
    gcp_hot_to_cool_scheduler_cron          = "0 2 * * *"
    gcp_l3_archive_storage_class            = "ARCHIVE"
    gcp_cool_to_archive_mover_memory_mb     = 512
    gcp_cool_to_archive_mover_min_instances = 0
    gcp_cool_to_archive_mover_max_instances = 1
    gcp_cool_to_archive_scheduler_cron      = "0 3 * * 0"
    gcp_glue_function_memory_mb             = 256
    gcp_glue_function_min_instances         = 0
    gcp_glue_function_max_instances         = 10
    use_event_checking                      = false
    enable_aws_logging                      = false
    enable_gcp_logging                      = false
  }

  assert {
    condition     = google_firestore_database.main[0].type == "FIRESTORE_NATIVE"
    error_message = "GCP Firestore mode drifted from the resolved specification."
  }

  assert {
    condition     = google_storage_bucket.cold[0].storage_class == "NEARLINE"
    error_message = "GCP cool storage class drifted from the resolved specification."
  }

  assert {
    condition     = google_storage_bucket.archive[0].storage_class == "ARCHIVE"
    error_message = "GCP archive storage class drifted from the resolved specification."
  }

  assert {
    condition     = google_cloud_scheduler_job.hot_to_cold[0].schedule == "0 2 * * *"
    error_message = "GCP hot-to-cool schedule drifted from the resolved specification."
  }
}
