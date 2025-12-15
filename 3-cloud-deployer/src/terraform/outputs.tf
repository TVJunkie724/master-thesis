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
