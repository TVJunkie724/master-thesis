# Azure Logic App Isolated E2E Test
#
# This Terraform config replicates the PRODUCTION deployment pattern:
# 1. Creates empty Logic App workflow container
# 2. Applies full workflow definition via ARM template (includes trigger)
#
# This matches the fixed production code in azure_compute.tf
#
# Usage:
#   cd tests/e2e/azure_logicapp_isolated_test
#   terraform init
#   terraform plan -var-file=test.tfvars.json
#   terraform apply -var-file=test.tfvars.json
#   terraform destroy -var-file=test.tfvars.json

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "azure_subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "azure_tenant_id" {
  description = "Azure AD Tenant ID"
  type        = string
}

variable "azure_client_id" {
  description = "Service Principal Client ID"
  type        = string
}

variable "azure_client_secret" {
  description = "Service Principal Client Secret"
  type        = string
  sensitive   = true
}

variable "azure_region" {
  description = "Azure region for resources"
  type        = string
  default     = "westeurope"
}

variable "test_name" {
  description = "Name for the test resources (must be globally unique)"
  type        = string
  default     = "logicapp-iso-e2e"
}

variable "workflow_definition_file" {
  description = "Path to the azure_logic_app.json file from the template"
  type        = string
}

# =============================================================================
# Provider
# =============================================================================

provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
  tenant_id       = var.azure_tenant_id
  client_id       = var.azure_client_id
  client_secret   = var.azure_client_secret
}

# =============================================================================
# Resource Group
# =============================================================================

resource "azurerm_resource_group" "test" {
  name     = "rg-${var.test_name}"
  location = var.azure_region

  tags = {
    Purpose   = "logic-app-isolated-e2e-test"
    CreatedBy = "terraform"
  }
}

# =============================================================================
# Logic App Workflow (Empty Container)
# =============================================================================

resource "azurerm_logic_app_workflow" "test" {
  name                = var.test_name
  location            = azurerm_resource_group.test.location
  resource_group_name = azurerm_resource_group.test.name

  tags = {
    Purpose = "logic-app-isolated-e2e-test"
  }

  # Definition is set via ARM template below
  lifecycle {
    ignore_changes = [parameters]
  }
}

# =============================================================================
# ARM Template Deployment
# Applies the full workflow definition from azure_logic_app.json
# This is the same pattern used in production azure_compute.tf
# =============================================================================

resource "azurerm_resource_group_template_deployment" "logic_app_definition" {
  name                = "${var.test_name}-definition"
  resource_group_name = azurerm_resource_group.test.name
  deployment_mode     = "Incremental"

  template_content = jsonencode({
    "$schema"      = "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"
    contentVersion = "1.0.0.0"
    resources = [{
      type       = "Microsoft.Logic/workflows"
      apiVersion = "2019-05-01"
      name       = azurerm_logic_app_workflow.test.name
      location   = var.azure_region
      properties = {
        state      = "Enabled"
        # Extract .definition from the JSON wrapper (matches production pattern)
        definition = jsondecode(file(var.workflow_definition_file)).definition
      }
    }]
  })

  depends_on = [azurerm_logic_app_workflow.test]
}

# =============================================================================
# Outputs
# =============================================================================

output "resource_group_name" {
  description = "Name of the created resource group"
  value       = azurerm_resource_group.test.name
}

output "logic_app_name" {
  description = "Name of the created Logic App"
  value       = azurerm_logic_app_workflow.test.name
}

output "logic_app_id" {
  description = "ID of the created Logic App"
  value       = azurerm_logic_app_workflow.test.id
}

output "access_endpoint" {
  description = "Logic App access endpoint (trigger URL)"
  value       = azurerm_logic_app_workflow.test.access_endpoint
}

output "portal_designer_url" {
  description = "Direct Azure Portal URL to Logic App designer"
  value       = "https://portal.azure.com/#@${var.azure_tenant_id}/resource${azurerm_logic_app_workflow.test.id}/designer"
}

output "portal_overview_url" {
  description = "Direct Azure Portal URL to Logic App overview"
  value       = "https://portal.azure.com/#@${var.azure_tenant_id}/resource${azurerm_logic_app_workflow.test.id}/overview"
}

output "test_summary" {
  description = "Summary of the test"
  value = <<-EOT
    
    ============================================================
    AZURE LOGIC APP ISOLATED E2E TEST COMPLETE
    ============================================================
    
    Logic App:    ${azurerm_logic_app_workflow.test.name}
    Resource Grp: ${azurerm_resource_group.test.name}
    Region:       ${var.azure_region}
    
    VERIFICATION:
    1. Open the Portal URL below
    2. Click "Logic app designer" in the left menu
    3. Verify the workflow shows:
       - HTTP Request trigger
       - Call_Azure_Function_A action
       - Call_Azure_Function_B action
       - Response action
    
    Portal Designer URL:
    https://portal.azure.com/#@${var.azure_tenant_id}/resource${azurerm_logic_app_workflow.test.id}/designer
    
    ============================================================
  EOT
}
