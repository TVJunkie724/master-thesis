# Minimal Grafana test
# This is a standalone Terraform config to test Azure Managed Grafana deployment
# Run with: terraform init && terraform apply

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

variable "azure_subscription_id" {}
variable "azure_tenant_id" {}
variable "azure_client_id" {}
variable "azure_client_secret" {}

provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
  tenant_id       = var.azure_tenant_id
  client_id       = var.azure_client_id
  client_secret   = var.azure_client_secret
}

variable "location" {
  default = "westeurope"
}

variable "grafana_version" {
  description = "Grafana major version to test (9 or 10)"
  default     = "10"
}

# Resource group for testing
resource "azurerm_resource_group" "grafana_test" {
  name     = "rg-grafana-test"
  location = var.location
}

# Test Grafana deployment with Standard SKU
resource "azurerm_dashboard_grafana" "test" {
  name                = "grafana-e2e-test"
  resource_group_name = azurerm_resource_group.grafana_test.name
  location            = azurerm_resource_group.grafana_test.location
  
  # Standard SKU (production use)
  sku = "Standard"
  
  # Version to test - try "9", "10", or without this line
  grafana_major_version = var.grafana_version
  
  identity {
    type = "SystemAssigned"
  }
  
  public_network_access_enabled = true
  zone_redundancy_enabled       = false
  
  tags = {
    Environment = "test"
    Purpose     = "grafana-version-test"
  }
}

output "grafana_name" {
  value = azurerm_dashboard_grafana.test.name
}

output "grafana_endpoint" {
  value = azurerm_dashboard_grafana.test.endpoint
}

output "grafana_version" {
  value = var.grafana_version
}
