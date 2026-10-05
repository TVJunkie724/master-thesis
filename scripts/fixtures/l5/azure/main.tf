# Fixed L3/L5 research cut; no IoT, Event, Twin service or container image.
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
    random  = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
variable "prefix" { type = string }
variable "region" { type = string }
variable "package_path" { type = string }
provider "azurerm" {
  features {}
  resource_provider_registrations = "none"
}
data "azurerm_client_config" "current" {}
resource "random_password" "cursor" {
  length  = 64
  special = false
}
resource "azurerm_resource_group" "run" {
  name     = var.prefix
  location = var.region
}
resource "azurerm_storage_account" "packages" {
  name                            = replace(var.prefix, "-", "")
  resource_group_name             = azurerm_resource_group.run.name
  location                        = var.region
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
}
resource "azurerm_storage_container" "packages" {
  for_each              = toset(["reader", "visualization"])
  name                  = each.key
  storage_account_id    = azurerm_storage_account.packages.id
  container_access_type = "private"
}
resource "azurerm_cosmosdb_account" "history" {
  name                          = "${var.prefix}-cosmos"
  resource_group_name           = azurerm_resource_group.run.name
  location                      = var.region
  offer_type                    = "Standard"
  kind                          = "GlobalDocumentDB"
  local_authentication_disabled = true
  capabilities { name = "EnableServerless" }
  consistency_policy { consistency_level = "Session" }
  geo_location {
    location          = var.region
    failover_priority = 0
  }
}
resource "azurerm_cosmosdb_sql_database" "history" {
  name                = "history"
  resource_group_name = azurerm_resource_group.run.name
  account_name        = azurerm_cosmosdb_account.history.name
}
resource "azurerm_cosmosdb_sql_container" "history" {
  name                = "telemetry-history"
  resource_group_name = azurerm_resource_group.run.name
  account_name        = azurerm_cosmosdb_account.history.name
  database_name       = azurerm_cosmosdb_sql_database.history.name
  partition_key_paths = ["/device_id"]
}
resource "azurerm_service_plan" "runtime" {
  for_each            = toset(["reader", "visualization"])
  name                = "${var.prefix}-${each.key}"
  resource_group_name = azurerm_resource_group.run.name
  location            = var.region
  os_type             = "Linux"
  sku_name            = "FC1"
}
resource "azurerm_function_app_flex_consumption" "reader" {
  name                                           = "${var.prefix}-reader"
  resource_group_name                            = azurerm_resource_group.run.name
  location                                       = var.region
  service_plan_id                                = azurerm_service_plan.runtime["reader"].id
  storage_container_type                         = "blobContainer"
  storage_container_endpoint                     = "${azurerm_storage_account.packages.primary_blob_endpoint}${azurerm_storage_container.packages["reader"].name}"
  storage_authentication_type                    = "StorageAccountConnectionString"
  storage_access_key                             = azurerm_storage_account.packages.primary_access_key
  runtime_name                                   = "python"
  runtime_version                                = "3.12"
  maximum_instance_count                         = 1
  instance_memory_in_mb                          = 2048
  https_only                                     = true
  webdeploy_publish_basic_authentication_enabled = false
  always_ready {
    name           = "http"
    instance_count = 1
  }
  identity { type = "SystemAssigned" }
  site_config { minimum_tls_version = "1.2" }
  app_settings = {
    ARCHITECTURE_PROFILE          = "six-layer-eventing@1"
    SIX_LAYER_RAW_HISTORY_ENABLED = "true"
    SIX_LAYER_COSMOS_ENDPOINT     = azurerm_cosmosdb_account.history.endpoint
    SIX_LAYER_COSMOS_DATABASE     = azurerm_cosmosdb_sql_database.history.name
    SIX_LAYER_COSMOS_CONTAINER    = azurerm_cosmosdb_sql_container.history.name
    SIX_LAYER_CURSOR_HMAC_KEY     = random_password.cursor.result
  }
}
resource "azurerm_cosmosdb_sql_role_assignment" "reader" {
  resource_group_name = azurerm_resource_group.run.name
  account_name        = azurerm_cosmosdb_account.history.name
  role_definition_id  = "${azurerm_cosmosdb_account.history.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000001"
  principal_id        = azurerm_function_app_flex_consumption.reader.identity[0].principal_id
  scope               = azurerm_cosmosdb_account.history.id
}
resource "azurerm_cosmosdb_sql_role_assignment" "fixture_writer" {
  resource_group_name = azurerm_resource_group.run.name
  account_name        = azurerm_cosmosdb_account.history.name
  role_definition_id  = "${azurerm_cosmosdb_account.history.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = data.azurerm_client_config.current.object_id
  scope               = azurerm_cosmosdb_account.history.id
}
module "reader_package" {
  source                    = "./package_module"
  app_id                    = azurerm_function_app_flex_consumption.reader.id
  app_name                  = azurerm_function_app_flex_consumption.reader.name
  resource_group_name       = azurerm_resource_group.run.name
  package_path              = var.package_path
  storage_account_name      = azurerm_storage_account.packages.name
  storage_container_name    = azurerm_storage_container.packages["reader"].name
  storage_connection_string = azurerm_storage_account.packages.primary_connection_string
}
data "azurerm_function_app_host_keys" "reader" {
  name                = azurerm_function_app_flex_consumption.reader.name
  resource_group_name = azurerm_resource_group.run.name
  depends_on          = [module.reader_package]
}
resource "azurerm_function_app_flex_consumption" "visualization" {
  name                                           = "${var.prefix}-visualization"
  resource_group_name                            = azurerm_resource_group.run.name
  location                                       = var.region
  service_plan_id                                = azurerm_service_plan.runtime["visualization"].id
  storage_container_type                         = "blobContainer"
  storage_container_endpoint                     = "${azurerm_storage_account.packages.primary_blob_endpoint}${azurerm_storage_container.packages["visualization"].name}"
  storage_authentication_type                    = "StorageAccountConnectionString"
  storage_access_key                             = azurerm_storage_account.packages.primary_access_key
  runtime_name                                   = "python"
  runtime_version                                = "3.12"
  maximum_instance_count                         = 1
  instance_memory_in_mb                          = 2048
  https_only                                     = true
  webdeploy_publish_basic_authentication_enabled = false
  always_ready {
    name           = "http"
    instance_count = 1
  }
  site_config { minimum_tls_version = "1.2" }
  app_settings = {
    SIX_LAYER_VISUALIZATION_ENABLED = "true"
    L3_READER_URL                   = "https://${azurerm_function_app_flex_consumption.reader.default_hostname}/api/raw-history/v1"
    L3_READER_KEY                   = data.azurerm_function_app_host_keys.reader.default_function_key
    L5_DEVICE_ID                    = "l5-device"
    L5_METRIC                       = "temperature"
  }
}
module "visualization_package" {
  source                    = "./package_module"
  app_id                    = azurerm_function_app_flex_consumption.visualization.id
  app_name                  = azurerm_function_app_flex_consumption.visualization.name
  resource_group_name       = azurerm_resource_group.run.name
  package_path              = var.package_path
  storage_account_name      = azurerm_storage_account.packages.name
  storage_container_name    = azurerm_storage_container.packages["visualization"].name
  storage_connection_string = azurerm_storage_account.packages.primary_connection_string
}
output "reader_url" { value = "https://${azurerm_function_app_flex_consumption.reader.default_hostname}/api/raw-history/v1" }
output "visualization_url" { value = "https://${azurerm_function_app_flex_consumption.visualization.default_hostname}/api/visualization/v1" }
output "cosmos_endpoint" { value = azurerm_cosmosdb_account.history.endpoint }
