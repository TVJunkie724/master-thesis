# Flex uses OneDeploy, not Kudu zipdeploy. Keep Python dependency installation
# on Azure's Linux builder; neither public blobs nor SCM basic auth are needed.
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm" }
  }
}

variable "app_id" { type = string }
variable "app_name" { type = string }
variable "resource_group_name" { type = string }
variable "package_path" { type = string }
variable "storage_account_name" { type = string }
variable "storage_container_name" { type = string }
variable "storage_connection_string" {
  type      = string
  sensitive = true
}

resource "terraform_data" "package_revision" {
  input            = timestamp()
  triggers_replace = [var.app_id, filesha256(var.package_path)]
  lifecycle { ignore_changes = [input] }
}

resource "azurerm_storage_blob" "package" {
  name                   = "${var.app_name}/${filesha256(var.package_path)}.zip"
  storage_account_name   = var.storage_account_name
  storage_container_name = var.storage_container_name
  type                   = "Block"
  source                 = var.package_path
  content_md5            = filemd5(var.package_path)
}

data "azurerm_storage_account_blob_container_sas" "package" {
  connection_string = var.storage_connection_string
  container_name    = var.storage_container_name
  https_only        = true
  start             = timeadd(terraform_data.package_revision.output, "-5m")
  expiry            = timeadd(terraform_data.package_revision.output, "2h")
  permissions {
    read   = true
    add    = false
    create = false
    write  = false
    delete = false
    list   = false
  }
}

resource "azurerm_resource_group_template_deployment" "publish" {
  name                = substr("${var.app_name}-package", 0, 64)
  resource_group_name = var.resource_group_name
  deployment_mode     = "Incremental"
  template_content = jsonencode({
    "$schema"      = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    contentVersion = "1.0.0.0"
    resources = [{
      type       = "Microsoft.Web/sites/extensions"
      apiVersion = "2022-09-01"
      name       = "${var.app_name}/onedeploy"
      properties = {
        packageUri  = "${azurerm_storage_blob.package.url}${data.azurerm_storage_account_blob_container_sas.package.sas}"
        remoteBuild = true
      }
    }]
  })
}
