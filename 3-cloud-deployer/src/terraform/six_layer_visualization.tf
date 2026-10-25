# Managed Grafana restores the original L5 service family. L3 owns its reader;
# L5 owns only the workspace, invocation permission and dashboard provisioning.
# Core-only evaluation creates none of these resources.

resource "aws_iam_role" "aws_six_layer_grafana" {
  count = local.aws_six_layer_l5_enabled ? 1 : 0
  name  = "${local.aws_six_layer_name}-six-grafana"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Principal = { Service = "grafana.amazonaws.com" }, Action = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current[0].account_id } }
    }]
  })
  tags = local.aws_six_layer_tags
}

resource "aws_iam_role_policy" "aws_six_layer_grafana" {
  count = local.aws_six_layer_l5_enabled ? 1 : 0
  role  = aws_iam_role.aws_six_layer_grafana[0].id
  name  = "invoke-l3-reader"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow", Action = ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"]
      Resource = aws_lambda_function.aws_aws_lambda_raw_history_reader[0].arn
    }]
  })
}

resource "aws_grafana_workspace" "aws_six_layer" {
  count                    = local.aws_six_layer_l5_enabled ? 1 : 0
  name                     = "${local.aws_six_layer_name}-six-grafana"
  account_access_type      = "CURRENT_ACCOUNT"
  authentication_providers = ["AWS_SSO"]
  permission_type          = "CUSTOMER_MANAGED"
  role_arn                 = aws_iam_role.aws_six_layer_grafana[0].arn
  grafana_version          = "12.4"
  configuration            = jsonencode({ plugins = { pluginAdminEnabled = true } })
  tags                     = local.aws_six_layer_tags
  depends_on               = [aws_iam_role_policy.aws_six_layer_grafana]
  lifecycle {
    precondition {
      condition     = var.layer_3_hot_provider == "aws" && local.aws_six_layer_layer_access_enabled
      error_message = "Grafana requires provider-local L3 and the selected Identity Center user."
    }
  }
}

resource "aws_grafana_role_association" "aws_six_layer_viewer" {
  count        = local.aws_six_layer_l5_enabled ? 1 : 0
  role         = "VIEWER"
  user_ids     = [local.aws_six_layer_layer_user_id]
  workspace_id = aws_grafana_workspace.aws_six_layer[0].id
}

resource "azurerm_dashboard_grafana" "azure_six_layer" {
  count                         = local.azure_six_layer_l5_enabled ? 1 : 0
  name                          = "${local.azure_six_layer_name}-grafana-${local.deployment_suffix}"
  resource_group_name           = azurerm_resource_group.main[0].name
  location                      = azurerm_resource_group.main[0].location
  sku                           = "Standard"
  grafana_major_version         = "12"
  public_network_access_enabled = true
  zone_redundancy_enabled       = false
  identity { type = "SystemAssigned" }
  tags = local.azure_six_layer_tags
  lifecycle {
    precondition {
      condition     = var.layer_3_hot_provider == "azure" && var.azure_layer_access_principal_object_id != ""
      error_message = "Grafana requires provider-local L3 and an existing Entra viewer."
    }
  }
}

resource "azurerm_role_assignment" "azure_six_layer_grafana_deployer" {
  count                            = local.azure_six_layer_l5_enabled ? 1 : 0
  scope                            = azurerm_dashboard_grafana.azure_six_layer[0].id
  role_definition_name             = "Grafana Admin"
  principal_id                     = data.azurerm_client_config.azure_six_layer_layer_access[0].object_id
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "azure_six_layer_grafana_viewer" {
  count                = local.azure_six_layer_l5_enabled ? 1 : 0
  scope                = azurerm_dashboard_grafana.azure_six_layer[0].id
  role_definition_name = "Grafana Viewer"
  principal_id         = var.azure_layer_access_principal_object_id
  principal_type       = "User"
}
