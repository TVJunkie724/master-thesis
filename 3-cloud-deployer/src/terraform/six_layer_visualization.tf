# L5 consumes authenticated L3 HTTP only. It owns neither storage nor models.
# Core-only evaluation sets layer_5_provider to none and creates none of these.
locals {
  six_layer_visualization_device = try(var.iot_devices[0].id, "poc-device-001")
  six_layer_visualization_metric = try(var.iot_devices[0].properties[0].name, "temperature")
}

resource "aws_iam_role" "aws_six_layer_visualization" {
  count = local.aws_six_layer_l5_enabled ? 1 : 0
  name  = "${local.aws_six_layer_name}-six-visualization"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.aws_six_layer_tags
}

resource "aws_cloudwatch_log_group" "aws_six_layer_visualization" {
  count             = local.aws_six_layer_l5_enabled ? 1 : 0
  name              = "/aws/lambda/${local.aws_six_layer_name}-six-visualization"
  retention_in_days = 1
  tags              = local.aws_six_layer_tags
}

resource "aws_iam_role_policy" "aws_six_layer_visualization" {
  count = local.aws_six_layer_l5_enabled ? 1 : 0
  role  = aws_iam_role.aws_six_layer_visualization[0].id
  name  = "invoke-reader-and-write-logs"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["lambda:InvokeFunctionUrl", "lambda:InvokeFunction"], Resource = aws_lambda_function.aws_aws_lambda_raw_history_reader[0].arn },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.aws_six_layer_visualization[0].arn}:*" },
    ]
  })
}

resource "aws_lambda_function" "aws_six_layer_visualization" {
  count                          = local.aws_six_layer_l5_enabled ? 1 : 0
  function_name                  = "${local.aws_six_layer_name}-six-visualization"
  role                           = aws_iam_role.aws_six_layer_visualization[0].arn
  filename                       = local.aws_six_layer_runtime_package
  source_code_hash               = filebase64sha256(local.aws_six_layer_runtime_package)
  handler                        = "handler.visualization"
  runtime                        = local.python_runtime_aws
  timeout                        = 30
  memory_size                    = 512
  reserved_concurrent_executions = 2
  environment {
    variables = {
      L3_READER_URL  = aws_lambda_function_url.aws_aws_lambda_raw_history_reader[0].function_url
      L5_DEVICE_ID   = local.six_layer_visualization_device
      L5_METRIC      = local.six_layer_visualization_metric
      L5_ALLOW_EMPTY = "true"
    }
  }
  tags       = local.aws_six_layer_tags
  depends_on = [aws_iam_role_policy.aws_six_layer_visualization]
  lifecycle {
    precondition {
      condition     = var.layer_3_hot_provider == "aws"
      error_message = "L5 supports only provider-local L3 read access."
    }
  }
}

resource "aws_lambda_function_url" "aws_six_layer_visualization" {
  count              = local.aws_six_layer_l5_enabled ? 1 : 0
  function_name      = aws_lambda_function.aws_six_layer_visualization[0].function_name
  authorization_type = "AWS_IAM"
}

data "azurerm_function_app_host_keys" "azure_six_layer_visualization_reader" {
  count               = local.azure_six_layer_l5_enabled ? 1 : 0
  name                = azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader[0].name
  resource_group_name = azurerm_resource_group.main[0].name
  depends_on          = [module.azure_six_layer_reader_package]
}

resource "azurerm_function_app_flex_consumption" "azure_six_layer_visualization" {
  count                                          = local.azure_six_layer_l5_enabled ? 1 : 0
  name                                           = "${local.azure_six_layer_name}-six-visual-${local.deployment_suffix}"
  resource_group_name                            = azurerm_resource_group.main[0].name
  location                                       = azurerm_resource_group.main[0].location
  service_plan_id                                = azurerm_service_plan.azure_six_layer_flex["visualization"].id
  storage_container_type                         = "blobContainer"
  storage_container_endpoint                     = "${azurerm_storage_account.main[0].primary_blob_endpoint}${azurerm_storage_container.azure_six_layer_function_package["visualization"].name}"
  storage_authentication_type                    = "StorageAccountConnectionString"
  storage_access_key                             = azurerm_storage_account.main[0].primary_access_key
  runtime_name                                   = "python"
  runtime_version                                = "3.12"
  maximum_instance_count                         = 1
  instance_memory_in_mb                          = 2048
  https_only                                     = true
  webdeploy_publish_basic_authentication_enabled = false
  site_config {
    minimum_tls_version     = "1.2"
    scm_minimum_tls_version = "1.2"
  }
  # No always-ready worker and no Cosmos identity: L5 reads through L3 only.
  app_settings = {
    SIX_LAYER_VISUALIZATION_ENABLED = "true"
    L3_READER_URL                   = "https://${azurerm_function_app_flex_consumption.azure_azure_functions_flex_raw_history_reader[0].default_hostname}/api/raw-history/v1"
    L3_READER_KEY                   = data.azurerm_function_app_host_keys.azure_six_layer_visualization_reader[0].default_function_key
    L5_DEVICE_ID                    = local.six_layer_visualization_device
    L5_METRIC                       = local.six_layer_visualization_metric
    L5_ALLOW_EMPTY                  = "true"
  }
  tags = local.azure_six_layer_tags
  lifecycle {
    precondition {
      condition     = var.layer_3_hot_provider == "azure"
      error_message = "L5 supports only provider-local L3 read access."
    }
  }
}

module "azure_six_layer_visualization_package" {
  source                    = "./modules/azure_flex_package"
  count                     = local.azure_six_layer_l5_enabled ? 1 : 0
  app_id                    = azurerm_function_app_flex_consumption.azure_six_layer_visualization[0].id
  app_name                  = azurerm_function_app_flex_consumption.azure_six_layer_visualization[0].name
  resource_group_name       = azurerm_resource_group.main[0].name
  package_path              = local.azure_six_layer_runtime_package
  storage_account_name      = azurerm_storage_account.main[0].name
  storage_container_name    = azurerm_storage_container.azure_six_layer_function_package["visualization"].name
  storage_connection_string = azurerm_storage_account.main[0].primary_connection_string
}
