mock_provider "archive" {}
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
