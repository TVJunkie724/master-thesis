# Output Values
#
# These outputs are used for:
# 1. Cross-cloud configuration (inter_cloud_connections.json)
# 2. E2E test verification
# 3. CLI/API response data

# ==============================================================================
# Azure Setup Outputs
# ==============================================================================

output "azure_resource_group_name" {
  description = "Name of the Azure Resource Group"
  value       = try(azurerm_resource_group.main[0].name, null)
}

output "azure_resource_group_id" {
  description = "ID of the Azure Resource Group"
  value       = try(azurerm_resource_group.main[0].id, null)
}

output "azure_managed_identity_id" {
  description = "ID of the User-Assigned Managed Identity"
  value       = try(azurerm_user_assigned_identity.main[0].id, null)
}

output "azure_managed_identity_client_id" {
  description = "Client ID of the Managed Identity"
  value       = try(azurerm_user_assigned_identity.main[0].client_id, null)
}

output "azure_storage_account_name" {
  description = "Name of the Storage Account"
  value       = try(azurerm_storage_account.main[0].name, null)
}

# ==============================================================================
# Azure L0 Glue Outputs
# ==============================================================================

output "azure_l0_function_app_name" {
  description = "Name of the L0 Glue Function App"
  value       = try(azurerm_linux_function_app.l0_glue[0].name, null)
}

output "azure_l0_function_app_url" {
  description = "Default hostname of the L0 Function App"
  value       = try("https://${azurerm_linux_function_app.l0_glue[0].default_hostname}", null)
}

# ==============================================================================
# Azure L1 IoT Outputs
# ==============================================================================

output "azure_iothub_name" {
  description = "Name of the Azure IoT Hub"
  value       = try(azurerm_iothub.main[0].name, null)
}

output "azure_iothub_hostname" {
  description = "Hostname of the Azure IoT Hub"
  value       = try(azurerm_iothub.main[0].hostname, null)
}

output "azure_l1_function_app_name" {
  description = "Name of the L1 Function App"
  value       = try(azurerm_linux_function_app.l1[0].name, null)
}

# ==============================================================================
# Azure L2 Compute Outputs
# ==============================================================================

output "azure_l2_function_app_name" {
  description = "Name of the L2 Function App"
  value       = try(azurerm_linux_function_app.l2[0].name, null)
}

output "azure_user_functions_app_name" {
  description = "Name of the User Functions App (event actions, processors)"
  value       = try(azurerm_linux_function_app.user[0].name, null)
}

# ==============================================================================
# Azure L3 Storage Outputs
# ==============================================================================

output "azure_cosmos_account_name" {
  description = "Name of the Cosmos DB Account"
  value       = try(azurerm_cosmosdb_account.main[0].name, null)
}

output "azure_cosmos_endpoint" {
  description = "Endpoint URL of the Cosmos DB Account"
  value       = try(azurerm_cosmosdb_account.main[0].endpoint, null)
}

output "azure_l3_function_app_name" {
  description = "Name of the L3 Function App"
  value       = try(azurerm_linux_function_app.l3[0].name, null)
}

output "azure_l3_hot_reader_url" {
  description = "URL of the L3 Hot Reader function"
  value       = try("https://${azurerm_linux_function_app.l3[0].default_hostname}/api/hot-reader", null)
}

# ==============================================================================
# Azure L4 Digital Twins Outputs
# ==============================================================================

output "azure_adt_instance_name" {
  description = "Name of the Azure Digital Twins instance"
  value       = try(azurerm_digital_twins_instance.main[0].name, null)
}

output "azure_adt_endpoint" {
  description = "Endpoint URL of the ADT instance"
  value       = try("https://${azurerm_digital_twins_instance.main[0].host_name}", null)
}

output "azure_3d_scenes_container_url" {
  description = "Azure Blob container URL for 3D Scenes Studio (if deployed)"
  value       = try(
    "https://${azurerm_storage_account.main[0].name}.blob.core.windows.net/${azurerm_storage_container.scenes[0].name}",
    null
  )
}

# ==============================================================================
# Azure L5 Visualization Outputs
# ==============================================================================

output "azure_grafana_name" {
  description = "Name of the Azure Managed Grafana workspace"
  value       = try(azurerm_dashboard_grafana.main[0].name, null)
}

output "azure_grafana_endpoint" {
  description = "Endpoint URL of the Grafana workspace"
  value       = try(azurerm_dashboard_grafana.main[0].endpoint, null)
}

# ==============================================================================
# Cross-Cloud Outputs
# ==============================================================================

output "inter_cloud_token" {
  description = "Token for cross-cloud authentication"
  value       = var.inter_cloud_token != "" ? var.inter_cloud_token : try(random_password.inter_cloud_token[0].result, null)
  sensitive   = true
}

# ==============================================================================
# AWS Setup Outputs
# ==============================================================================

output "aws_resource_group_name" {
  description = "Name of the AWS Resource Group"
  value       = try(aws_resourcegroups_group.main[0].name, null)
}

output "aws_account_id" {
  description = "AWS Account ID"
  value       = try(data.aws_caller_identity.current[0].account_id, null)
}

output "aws_region" {
  description = "AWS Region"
  value       = try(data.aws_region.current[0].name, null)
}

# ==============================================================================
# AWS L0 Glue Outputs
# ==============================================================================

output "aws_l0_ingestion_function_name" {
  description = "Name of the L0 Ingestion Lambda"
  value       = try(aws_lambda_function.l0_ingestion[0].function_name, null)
}

output "aws_l0_ingestion_url" {
  description = "Function URL for L0 Ingestion"
  value       = try(aws_lambda_function_url.l0_ingestion[0].function_url, null)
}

output "aws_l0_hot_writer_url" {
  description = "Function URL for L0 Hot Writer"
  value       = try(aws_lambda_function_url.l0_hot_writer[0].function_url, null)
}

output "aws_l0_hot_reader_url" {
  description = "Function URL for L0 Hot Reader"
  value       = try(aws_lambda_function_url.l0_hot_reader[0].function_url, null)
}

output "aws_l0_cold_writer_function_name" {
  description = "Name of the L0 Cold Writer Lambda"
  value       = try(aws_lambda_function.l0_cold_writer[0].function_name, null)
}

output "aws_l0_cold_writer_url" {
  description = "Function URL for L0 Cold Writer"
  value       = try(aws_lambda_function_url.l0_cold_writer[0].function_url, null)
}

output "aws_l0_archive_writer_function_name" {
  description = "Name of the L0 Archive Writer Lambda"
  value       = try(aws_lambda_function.l0_archive_writer[0].function_name, null)
}

output "aws_l0_archive_writer_url" {
  description = "Function URL for L0 Archive Writer"
  value       = try(aws_lambda_function_url.l0_archive_writer[0].function_url, null)
}

# ==============================================================================
# AWS L1 IoT Outputs
# ==============================================================================

output "aws_l1_dispatcher_function_name" {
  description = "Name of the L1 Dispatcher Lambda"
  value       = try(aws_lambda_function.l1_dispatcher[0].function_name, null)
}

output "aws_iot_topic_rule_name" {
  description = "Name of the IoT Topic Rule"
  value       = try(aws_iot_topic_rule.dispatcher[0].name, null)
}

# ==============================================================================
# AWS L2 Compute Outputs
# ==============================================================================

output "aws_l2_persister_function_name" {
  description = "Name of the L2 Persister Lambda"
  value       = try(aws_lambda_function.l2_persister[0].function_name, null)
}

output "aws_l2_event_checker_function_name" {
  description = "Name of the L2 Event Checker Lambda"
  value       = try(aws_lambda_function.l2_event_checker[0].function_name, null)
}

output "aws_l2_step_function_arn" {
  description = "ARN of the L2 Step Functions State Machine"
  value       = try(aws_sfn_state_machine.l2_event_workflow[0].arn, null)
}

# ==============================================================================
# AWS L3 Storage Outputs
# ==============================================================================

output "aws_dynamodb_table_name" {
  description = "Name of the DynamoDB hot storage table"
  value       = try(aws_dynamodb_table.l3_hot[0].name, null)
}

output "aws_dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = try(aws_dynamodb_table.l3_hot[0].arn, null)
}

output "aws_l3_hot_reader_function_name" {
  description = "Name of the L3 Hot Reader Lambda"
  value       = try(aws_lambda_function.l3_hot_reader[0].function_name, null)
}

output "aws_l3_hot_reader_url" {
  description = "Function URL for L3 Hot Reader"
  value       = try(aws_lambda_function_url.l3_hot_reader[0].function_url, null)
}

output "aws_s3_cold_bucket" {
  description = "Name of the cold storage S3 bucket"
  value       = try(aws_s3_bucket.l3_cold[0].bucket, null)
}

output "aws_s3_archive_bucket" {
  description = "Name of the archive storage S3 bucket"
  value       = try(aws_s3_bucket.l3_archive[0].bucket, null)
}

# ==============================================================================
# AWS L4 TwinMaker Outputs
# ==============================================================================

output "aws_twinmaker_workspace_id" {
  description = "ID of the TwinMaker Workspace"
  value       = try(awscc_iottwinmaker_workspace.main[0].workspace_id, null)
}

output "aws_twinmaker_workspace_arn" {
  description = "ARN of the TwinMaker Workspace"
  value       = try(awscc_iottwinmaker_workspace.main[0].arn, null)
}

output "aws_twinmaker_scene_id" {
  description = "AWS TwinMaker 3D scene ID (if deployed)"
  value       = try(awscc_iottwinmaker_scene.main[0].scene_id, null)
}

# ==============================================================================
# AWS L5 Grafana Outputs
# ==============================================================================

output "aws_grafana_workspace_id" {
  description = "ID of the Grafana Workspace"
  value       = try(aws_grafana_workspace.main[0].id, null)
}

output "aws_grafana_endpoint" {
  description = "Endpoint URL of the Grafana Workspace"
  value       = try(aws_grafana_workspace.main[0].endpoint, null)
}

output "aws_grafana_api_key" {
  description = "API Key for Grafana configuration"
  value       = try(aws_grafana_workspace_api_key.admin[0].key, null)
  sensitive   = true
}

# ==============================================================================
# GCP Setup Outputs
# ==============================================================================

output "gcp_project_id" {
  description = "GCP Project ID (provided or auto-created)"
  value       = local.deploy_gcp ? local.gcp_project_id : null
}

output "gcp_service_account_email" {
  description = "Email of the GCP Service Account"
  value       = try(google_service_account.functions[0].email, null)
}

output "gcp_function_source_bucket" {
  description = "Name of the function source bucket"
  value       = try(google_storage_bucket.function_source[0].name, null)
}

# ==============================================================================
# GCP L1 IoT Outputs
# ==============================================================================

output "gcp_pubsub_telemetry_topic" {
  description = "Pub/Sub topic for telemetry"
  value       = try(google_pubsub_topic.telemetry[0].id, null)
}

output "gcp_pubsub_events_topic" {
  description = "Pub/Sub topic for events"
  value       = try(google_pubsub_topic.events[0].id, null)
}

output "gcp_dispatcher_url" {
  description = "URL of the dispatcher function"
  value       = try(google_cloudfunctions2_function.dispatcher[0].url, null)
}

# ==============================================================================
# GCP L2 Compute Outputs
# ==============================================================================

output "gcp_processor_url" {
  description = "URL of the processor function"
  value       = try(google_cloudfunctions2_function.processor[0].url, null)
}

output "gcp_persister_url" {
  description = "URL of the persister function"
  value       = try(google_cloudfunctions2_function.persister[0].url, null)
}

output "gcp_event_checker_url" {
  description = "URL of the event checker function (optional)"
  value       = try(google_cloudfunctions2_function.event_checker[0].url, null)
}

output "gcp_user_functions_url" {
  description = "URL of the user functions (event actions, processors)"
  value       = try(google_cloudfunctions2_function.processor[0].url, null)
}

output "gcp_event_workflow_id" {
  description = "ID of the event processing Cloud Workflow (optional)"
  value       = try(google_workflows_workflow.event_workflow[0].id, null)
}

# ==============================================================================
# GCP L3 Storage Outputs
# ==============================================================================

output "gcp_firestore_database" {
  description = "Firestore database name"
  value       = try(google_firestore_database.main[0].name, null)
}

output "gcp_cold_bucket" {
  description = "Name of the cold storage bucket"
  value       = try(google_storage_bucket.cold[0].name, null)
}

output "gcp_hot_reader_url" {
  description = "URL of the hot reader function"
  value       = try(google_cloudfunctions2_function.hot_reader[0].url, null)
}

# ==============================================================================
# GCP L0 Glue Outputs
# ==============================================================================

output "gcp_ingestion_url" {
  description = "URL of the ingestion function (multi-cloud)"
  value       = try(google_cloudfunctions2_function.ingestion[0].url, null)
}

output "gcp_hot_writer_url" {
  description = "URL of the hot writer function (multi-cloud)"
  value       = try(google_cloudfunctions2_function.hot_writer[0].url, null)
}

output "gcp_cold_writer_url" {
  description = "URL of the cold writer function (multi-cloud)"
  value       = try(google_cloudfunctions2_function.cold_writer[0].url, null)
}

output "gcp_archive_writer_url" {
  description = "URL of the archive writer function (multi-cloud)"
  value       = try(google_cloudfunctions2_function.archive_writer[0].url, null)
}
