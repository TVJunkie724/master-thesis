# ==============================================================================
# Azure Observability - Log Analytics, App Insights, and Diagnostic Settings
#
# Toggle: var.enable_azure_logging (applied at resource level via count)
# All resources check enable_azure_logging && <layer_condition>
# ==============================================================================

resource "azurerm_log_analytics_workspace" "main" {
  count               = var.enable_azure_logging && local.deploy_azure ? 1 : 0
  name                = "${var.digital_twin_name}-logs"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name
  sku                 = "PerGB2018"
  # Azure requires 30-730 days retention (unlike AWS/GCP which allow shorter)
  retention_in_days   = max(30, var.log_retention_days)
  tags                = local.common_tags
}

resource "azurerm_application_insights" "functions" {
  count               = var.enable_azure_logging && local.deploy_azure ? 1 : 0
  name                = "${var.digital_twin_name}-insights"
  location            = azurerm_resource_group.main[0].location
  resource_group_name = azurerm_resource_group.main[0].name
  workspace_id        = azurerm_log_analytics_workspace.main[0].id
  application_type    = "web"
  tags                = local.common_tags
}

locals {
  app_insights_key      = var.enable_azure_logging && local.deploy_azure ? try(azurerm_application_insights.functions[0].instrumentation_key, "") : ""
  app_insights_conn_str = var.enable_azure_logging && local.deploy_azure ? try(azurerm_application_insights.functions[0].connection_string, "") : ""
}

resource "azurerm_monitor_diagnostic_setting" "iothub" {
  count                      = var.enable_azure_logging && var.layer_1_provider == "azure" ? 1 : 0
  name                       = "${var.digital_twin_name}-logs-${local.deployment_suffix}"
  target_resource_id         = azurerm_iothub.main[0].id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main[0].id
  enabled_log { category = "Connections" }
  enabled_log { category = "DeviceTelemetry" }
  enabled_log { category = "Routes" }
  enabled_metric { category = "AllMetrics" }
  depends_on = [azurerm_log_analytics_workspace.main]
}

resource "azurerm_monitor_diagnostic_setting" "eventgrid" {
  count                      = var.enable_azure_logging && var.layer_1_provider == "azure" ? 1 : 0
  name                       = "${var.digital_twin_name}-logs-${local.deployment_suffix}"
  target_resource_id         = azurerm_eventgrid_system_topic.iothub[0].id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main[0].id
  enabled_log { category = "DeliveryFailures" }
  enabled_metric { category = "AllMetrics" }
  depends_on = [azurerm_log_analytics_workspace.main]
}

resource "azurerm_monitor_diagnostic_setting" "cosmos" {
  count                      = var.enable_azure_logging && var.layer_3_hot_provider == "azure" ? 1 : 0
  name                       = "${var.digital_twin_name}-logs-${local.deployment_suffix}"
  target_resource_id         = azurerm_cosmosdb_account.main[0].id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main[0].id
  enabled_log { category = "DataPlaneRequests" }
  enabled_log { category = "QueryRuntimeStatistics" }
  enabled_metric { category = "AllMetrics" }
  depends_on = [azurerm_log_analytics_workspace.main]
}

resource "azurerm_monitor_diagnostic_setting" "adt" {
  count                      = var.enable_azure_logging && var.layer_4_provider == "azure" ? 1 : 0
  name                       = "${var.digital_twin_name}-logs-${local.deployment_suffix}"
  target_resource_id         = azurerm_digital_twins_instance.main[0].id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main[0].id
  enabled_log { category = "DigitalTwinsOperation" }
  enabled_log { category = "EventRoutesOperation" }
  enabled_metric { category = "AllMetrics" }
  depends_on = [azurerm_log_analytics_workspace.main]
}

resource "azurerm_monitor_diagnostic_setting" "logic_app" {
  count                      = var.enable_azure_logging && var.layer_2_provider == "azure" && var.trigger_notification_workflow && var.use_event_checking ? 1 : 0
  name                       = "${var.digital_twin_name}-logs-${local.deployment_suffix}"
  target_resource_id         = azurerm_logic_app_workflow.event_notification[0].id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main[0].id
  enabled_log { category = "WorkflowRuntime" }
  enabled_metric { category = "AllMetrics" }
  depends_on = [azurerm_log_analytics_workspace.main]
}

resource "azurerm_monitor_diagnostic_setting" "grafana" {
  count                      = var.enable_azure_logging && var.layer_5_provider == "azure" ? 1 : 0
  name                       = "${var.digital_twin_name}-logs-${local.deployment_suffix}"
  target_resource_id         = azurerm_dashboard_grafana.main[0].id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main[0].id
  enabled_log { category = "GrafanaLoginEvents" }
  enabled_metric { category = "AllMetrics" }
  depends_on = [azurerm_log_analytics_workspace.main]
}

resource "azurerm_monitor_diagnostic_setting" "storage" {
  count                      = var.enable_azure_logging && local.deploy_azure ? 1 : 0
  name                       = "${var.digital_twin_name}-logs-${local.deployment_suffix}"
  target_resource_id         = "${azurerm_storage_account.main[0].id}/blobServices/default"
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main[0].id
  enabled_log { category = "StorageRead" }
  enabled_log { category = "StorageWrite" }
  enabled_metric { category = "AllMetrics" }
  depends_on = [azurerm_log_analytics_workspace.main]
}
