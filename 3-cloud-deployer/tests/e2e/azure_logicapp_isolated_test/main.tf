# Azure Logic App Isolated E2E Test
#
# This is a focused Terraform config that replicates the PRODUCTION deployment pattern:
# 1. Creates empty Logic App workflow container
# 2. Applies full workflow definition via ARM template
# 3. Optionally creates a separate HTTP trigger (controlled by use_separate_trigger)
#
# PURPOSE: Diagnose why Logic App workflows appear empty in Azure Portal
#
# The test uses the actual template's azure_logic_app.json to match production.
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

variable "use_separate_trigger" {
  description = "If true, creates separate azurerm_logic_app_trigger (production pattern). If false, uses trigger from JSON only."
  type        = bool
  default     = true  # Default matches production to reproduce the bug
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
    Purpose     = "logic-app-isolated-e2e-test"
    CreatedBy   = "terraform"
    TestPattern = var.use_separate_trigger ? "production-3-resources" : "arm-only-2-resources"
  }
}

# =============================================================================
# Logic App Workflow (Empty Container) - Step 1 of 3-resource pattern
# =============================================================================

resource "azurerm_logic_app_workflow" "test" {
  name                = var.test_name
  location            = azurerm_resource_group.test.location
  resource_group_name = azurerm_resource_group.test.name

  tags = {
    Purpose     = "logic-app-isolated-e2e-test"
    TestPattern = var.use_separate_trigger ? "production-3-resources" : "arm-only-2-resources"
  }

  # Definition is set via ARM template below
  lifecycle {
    ignore_changes = [parameters]
  }
}

# =============================================================================
# ARM Template Deployment - Step 2 of 3-resource pattern
# Applies the full workflow definition from azure_logic_app.json
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
        # CRITICAL: Extract .definition from the JSON wrapper (matches production pattern)
        definition = jsondecode(file(var.workflow_definition_file)).definition
      }
    }]
  })

  depends_on = [azurerm_logic_app_workflow.test]
}

# =============================================================================
# Separate HTTP Trigger - Step 3 of 3-resource pattern (OPTIONAL)
# This is the suspected cause of the visualization bug!
# When use_separate_trigger = true, this creates a SECOND trigger that may
# conflict with the "manual" trigger already defined in azure_logic_app.json
# =============================================================================

resource "azurerm_logic_app_trigger_http_request" "event_trigger" {
  count        = var.use_separate_trigger ? 1 : 0
  name         = "event-trigger"
  logic_app_id = azurerm_logic_app_workflow.test.id

  schema = jsonencode({
    type = "object"
    properties = {
      eventType = { type = "string" }
      deviceId  = { type = "string" }
      payload   = { type = "object" }
      action    = { type = "string" }
    }
  })

  depends_on = [azurerm_resource_group_template_deployment.logic_app_definition]
}

# =============================================================================
# Outputs - For Manual Inspection
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

output "test_pattern" {
  description = "Which test pattern was used"
  value       = var.use_separate_trigger ? "PRODUCTION (3-resources: workflow + ARM + separate trigger)" : "ARM-ONLY (2-resources: workflow + ARM)"
}

output "portal_designer_url" {
  description = "Direct Azure Portal URL to Logic App designer"
  value       = "https://portal.azure.com/#@${var.azure_tenant_id}/resource${azurerm_logic_app_workflow.test.id}/designer"
}

output "portal_overview_url" {
  description = "Direct Azure Portal URL to Logic App overview"
  value       = "https://portal.azure.com/#@${var.azure_tenant_id}/resource${azurerm_logic_app_workflow.test.id}/overview"
}

output "callback_url" {
  description = "HTTP trigger callback URL (from the trigger defined in JSON)"
  value       = try(azurerm_logic_app_workflow.test.access_endpoint, "Check portal for trigger URL")
}

output "separate_trigger_created" {
  description = "Whether the separate trigger resource was created"
  value       = var.use_separate_trigger ? "YES - azurerm_logic_app_trigger_http_request created" : "NO - only using trigger from JSON definition"
}

output "test_summary" {
  description = "Summary of the test for investigation"
  value = <<-EOT
    
    ============================================================
    AZURE LOGIC APP ISOLATED E2E TEST COMPLETE
    ============================================================
    
    Test Pattern: ${var.use_separate_trigger ? "PRODUCTION (3 resources)" : "ARM-ONLY (2 resources)"}
    
    Logic App:    ${azurerm_logic_app_workflow.test.name}
    Resource Grp: ${azurerm_resource_group.test.name}
    Region:       ${var.azure_region}
    
    ${var.use_separate_trigger ? "⚠️  SEPARATE TRIGGER CREATED - This may cause visualization issues!" : "✅ NO SEPARATE TRIGGER - Using trigger from JSON definition only"}
    
    MANUAL VERIFICATION:
    1. Open the Portal URL below
    2. Click "Logic app designer" in the left menu
    3. Check if the workflow shows:
       - "manual" HTTP Request trigger
       - "Call_Azure_Function_A" action
       - "Call_Azure_Function_B" action
       - "Response" action
    
    Portal Designer URL:
    https://portal.azure.com/#@${var.azure_tenant_id}/resource${azurerm_logic_app_workflow.test.id}/designer
    
    ============================================================
  EOT
}
