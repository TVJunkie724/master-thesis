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
mock_provider "local" {}
mock_provider "random" {}
mock_provider "time" {}

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
    condition     = length(aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw) == 1 && length(aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup) == 1
    error_message = "Five-layer v2 must bind raw and hourly-rollup storage."
  }

  assert {
    condition     = length(aws_ecs_task_definition.aws_aws_ecs_fargate_storage_mover) == 1
    error_message = "DynamoDB-to-S3 tiering requires exactly one finite mover definition."
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
      toset([for path in azurerm_cosmosdb_sql_container.azure_azure_cosmos_db_nosql_raw_and_rollup[0].indexing_policy[0].included_path : path.path]) == toset(["/device_id/?", "/stored_at/?", "/bucket_start/?", "/kind/?", "/metric/?"]) &&
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
    resolved_component_dimensions = {
      "dimension.azure.azure.event-hubs-only-for-reviewed-remote-telemetry-edge.throughput_unit_hours" = "0"
      "dimension.azure.azure.event-hubs-only-for-reviewed-remote-telemetry-edge.capacity_unit_hours"   = "4380"
    }
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
    enable_gcp_logging                    = false
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
      "cloudscheduler.googleapis.com",
      "compute.googleapis.com",
      "container.googleapis.com",
      "firestore.googleapis.com",
      "iap.googleapis.com",
      "logging.googleapis.com",
      "monitoring.googleapis.com",
      "secretmanager.googleapis.com",
      "storage.googleapis.com",
      "workflows.googleapis.com",
    ])
    error_message = "Single-cloud GCP v2 must enable exactly its reviewed platform API foundation."
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
