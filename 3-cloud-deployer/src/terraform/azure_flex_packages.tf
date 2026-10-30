# OneDeploy stays in Terraform's dependency graph so consumers receive keys
# only after their target package has been published.

module "azure_six_layer_ingress_package" {
  source                    = "./modules/azure_flex_package"
  count                     = local.azure_six_layer_event_enabled ? 1 : 0
  app_id                    = azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter[count.index].id
  app_name                  = azurerm_function_app_flex_consumption.azure_azure_functions_flex_event_adapter[count.index].name
  resource_group_name       = azurerm_resource_group.main[0].name
  package_path              = local.azure_six_layer_runtime_package
  storage_account_name      = azurerm_storage_account.main[0].name
  storage_container_name    = azurerm_storage_container.azure_six_layer_function_package["ingress"].name
  storage_connection_string = azurerm_storage_account.main[0].primary_connection_string
}

module "azure_six_layer_processing_package" {
  source                    = "./modules/azure_flex_package"
  count                     = local.azure_six_layer_l2_enabled ? 1 : 0
  app_id                    = azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[count.index].id
  app_name                  = azurerm_function_app_flex_consumption.azure_azure_functions_flex_consumption[count.index].name
  resource_group_name       = azurerm_resource_group.main[0].name
  package_path              = local.azure_six_layer_runtime_package
  storage_account_name      = azurerm_storage_account.main[0].name
  storage_container_name    = azurerm_storage_container.azure_six_layer_function_package["processing"].name
  storage_connection_string = azurerm_storage_account.main[0].primary_connection_string
}

module "azure_six_layer_action_package" {
  source                    = "./modules/azure_flex_package"
  count                     = local.azure_six_layer_l2_enabled ? 1 : 0
  app_id                    = azurerm_function_app_flex_consumption.azure_six_layer_extension_action[count.index].id
  app_name                  = azurerm_function_app_flex_consumption.azure_six_layer_extension_action[count.index].name
  resource_group_name       = azurerm_resource_group.main[0].name
  package_path              = local.azure_six_layer_runtime_package
  storage_account_name      = azurerm_storage_account.main[0].name
  storage_container_name    = azurerm_storage_container.azure_six_layer_function_package["action"].name
  storage_connection_string = azurerm_storage_account.main[0].primary_connection_string
}

module "azure_six_layer_reader_package" {
  source                    = "./modules/azure_flex_package"
  count                     = local.azure_six_layer_hot_enabled ? 1 : 0
  app_id                    = azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader[count.index].id
  app_name                  = azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader[count.index].name
  resource_group_name       = azurerm_resource_group.main[0].name
  package_path              = local.azure_six_layer_runtime_package
  storage_account_name      = azurerm_storage_account.main[0].name
  storage_container_name    = azurerm_storage_container.azure_six_layer_function_package["reader"].name
  storage_connection_string = azurerm_storage_account.main[0].primary_connection_string
}

module "azure_six_layer_eventing_package" {
  source                    = "./modules/azure_flex_package"
  count                     = local.azure_event_enabled ? 1 : 0
  app_id                    = azurerm_function_app_flex_consumption.event_runtime[count.index].id
  app_name                  = azurerm_function_app_flex_consumption.event_runtime[count.index].name
  resource_group_name       = azurerm_resource_group.main[0].name
  package_path              = local.azure_event_package
  storage_account_name      = azurerm_storage_account.main[0].name
  storage_container_name    = azurerm_storage_container.azure_event_function_package[0].name
  storage_connection_string = azurerm_storage_account.main[0].primary_connection_string
}

module "azure_six_layer_extension_package" {
  source                    = "./modules/azure_flex_package"
  for_each                  = local.azure_six_layer_processor_extensions
  app_id                    = azurerm_function_app_flex_consumption.azure_six_layer_processor_extension[each.key].id
  app_name                  = azurerm_function_app_flex_consumption.azure_six_layer_processor_extension[each.key].name
  resource_group_name       = azurerm_resource_group.main[0].name
  package_path              = each.value.package_path
  storage_account_name      = azurerm_storage_account.main[0].name
  storage_container_name    = azurerm_storage_container.azure_six_layer_function_package["extension"].name
  storage_connection_string = azurerm_storage_account.main[0].primary_connection_string
}
