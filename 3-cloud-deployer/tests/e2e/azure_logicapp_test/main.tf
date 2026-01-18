# Azure Logic App E2E Test
# 
# This is a focused Terraform config to test ONLY:
# - Azure Logic App workflow creation WITH definition
# - HTTP trigger setup
# - Workflow definition file upload
#
# BUG FOUND: The main deployment creates empty Logic Apps because
# the workflow_definition attribute isn't being set.
#
# Usage:
#   cd tests/e2e/azure_logicapp_test
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

variable "test_name_suffix" {
  description = "Suffix for resource names (for unique naming)"
  type        = string
  default     = "e2e"
}

variable "workflow_definition_file" {
  description = "Path to workflow definition JSON file (optional, uses default if not provided)"
  type        = string
  default     = ""
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
# Locals
# =============================================================================

locals {
  name_prefix = "logicapp-${var.test_name_suffix}"
  
  # Default workflow definition if not provided via file
  # This is a simple workflow with an HTTP trigger and a Response action
  default_definition = {
    "$schema"        = "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#"
    contentVersion   = "1.0.0.0"
    parameters       = {}
    triggers = {
      manual = {
        type = "Request"
        kind = "Http"
        inputs = {
          schema = {
            type = "object"
            properties = {
              message = { type = "string" }
              value   = { type = "number" }
            }
          }
        }
      }
    }
    actions = {
      Response = {
        type = "Response"
        kind = "Http"
        inputs = {
          statusCode = 200
          body = {
            status    = "success"
            message   = "@triggerBody()['message']"
            processed = "@utcNow()"
          }
        }
        runAfter = {}
      }
    }
    outputs = {}
  }
  
  # Load from file if provided, otherwise use default
  # NOTE: The file should contain just the "definition" part, not wrapped in another object
  workflow_definition = var.workflow_definition_file != "" ? jsondecode(file(var.workflow_definition_file)) : local.default_definition
}

# =============================================================================
# Resource Group
# =============================================================================

resource "azurerm_resource_group" "test" {
  name     = "rg-${local.name_prefix}"
  location = var.azure_region

  tags = {
    Purpose = "logic-app-e2e-test"
  }
}

# =============================================================================
# Azure Logic App Workflow
# =============================================================================

# CRITICAL: The workflow_definition attribute MUST be set for the workflow
# to appear correctly in the Azure Portal designer!
resource "azurerm_logic_app_workflow" "test" {
  name                = local.name_prefix
  location            = azurerm_resource_group.test.location
  resource_group_name = azurerm_resource_group.test.name

  # THIS IS THE KEY - set the workflow definition JSON
  # Without this, the Logic App is created but empty (no actions, no triggers)
  workflow_parameters = {}
  
  # Note: For Logic Apps Standard (App Service-based), you would use
  # azurerm_logic_app_standard with its own deployment mechanism.
  # For Consumption Logic Apps, the definition is set here.

  tags = {
    Purpose = "logic-app-e2e-test"
  }

  # The workflow definition is set after creation using the azapi_update_resource
  # because azurerm_logic_app_workflow doesn't have a direct workflow_definition attribute
  # for complex definitions. We use lifecycle ignore to avoid conflicts.
  lifecycle {
    ignore_changes = [parameters]
  }
}

# =============================================================================
# Update Logic App with Workflow Definition (using AzAPI)
# =============================================================================

# Unfortunately, azurerm_logic_app_workflow doesn't directly support setting
# the full workflow definition with actions. We need to use either:
# 1. ARM template deployment
# 2. azapi provider for direct REST API calls
# 3. azurerm_logic_app_action_custom for each action

# Using ARM template for reliable definition upload
resource "azurerm_resource_group_template_deployment" "logic_app_definition" {
  name                = "${local.name_prefix}-definition"
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
        definition = local.workflow_definition
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

output "callback_url" {
  description = "HTTP trigger callback URL (available after definition is applied)"
  value       = try(azurerm_logic_app_workflow.test.access_endpoint, "Check portal for trigger URL")
}

output "workflow_definition_applied" {
  description = "Whether workflow definition was applied via ARM template"
  value       = azurerm_resource_group_template_deployment.logic_app_definition.id != "" ? true : false
}

output "test_summary" {
  description = "Summary of the test"
  value = <<-EOT
    ✅ Azure Logic App E2E Test Complete
    
    Logic App Name: ${azurerm_logic_app_workflow.test.name}
    Resource Group: ${azurerm_resource_group.test.name}
    Region: ${var.azure_region}
    
    The Logic App has been created WITH its workflow definition.
    Check the Azure Portal to verify the workflow designer shows actions.
    
    Portal URL: https://portal.azure.com/#@${var.azure_tenant_id}/resource${azurerm_logic_app_workflow.test.id}/designer
  EOT
}
