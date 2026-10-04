# Offline dependency inspection only: mock providers, plan, never apply.
mock_provider "archive" {}
mock_provider "azapi" {}
mock_provider "aws" {}
mock_provider "aws" { alias = "sso" }
mock_provider "awscc" {}
mock_provider "azuread" {}
mock_provider "azurerm" {}
mock_provider "google" {}
mock_provider "kubernetes" {}
mock_provider "local" {}
mock_provider "random" {}
mock_provider "time" {}
mock_provider "tls" {}

variables {
  digital_twin_name        = "l4-offline"
  project_path             = "."
  layer_1_provider         = "aws"
  layer_2_provider         = "aws"
  layer_3_hot_provider     = "aws"
  layer_3_cold_provider    = "aws"
  layer_3_archive_provider = "aws"
  enable_aws_logging       = false
  enable_azure_logging     = false
  enable_gcp_logging       = false
}

run "aws_l4_infrastructure_only" {
  command = plan
  variables {
    layer_4_provider = "aws"
    layer_5_provider = "aws"
  }
  plan_options {
    target = [
      aws_s3_bucket.aws_six_layer_twinmaker,
      aws_s3_bucket_public_access_block.aws_six_layer_twinmaker,
      aws_iam_role.aws_six_layer_twinmaker,
      aws_iam_role_policy.aws_six_layer_twinmaker,
      awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard,
    ]
  }
  assert {
    condition     = length(awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard) == 1 && aws_s3_bucket_public_access_block.aws_six_layer_twinmaker[0].block_public_policy
    error_message = "The fixed AWS L4 cut requires one workspace and a private bucket."
  }
}

run "azure_l4_dependency_inspection" {
  command = plan
  variables {
    layer_1_provider                       = "azure"
    layer_2_provider                       = "azure"
    layer_3_hot_provider                   = "azure"
    layer_3_cold_provider                  = "azure"
    layer_3_archive_provider               = "azure"
    layer_4_provider                       = "azure"
    layer_5_provider                       = "azure"
    azure_layer_access_principal_object_id = "11111111-1111-1111-1111-111111111111"
  }
  override_data {
    target = data.azurerm_client_config.azure_six_layer_layer_access
    values = { object_id = "22222222-2222-2222-2222-222222222222" }
  }
  plan_options {
    target = [
      azurerm_resource_group.main,
      azurerm_digital_twins_instance.azure_azure_digital_twins,
      azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_seed_deployer"],
    ]
  }
  assert {
    condition     = length(azurerm_digital_twins_instance.azure_azure_digital_twins) == 1 && azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_seed_deployer"].role_definition_name == "Azure Digital Twins Data Owner"
    error_message = "The fixed Azure L4 cut requires one ADT and instance-scoped writer access."
  }
  assert {
    condition     = length(output.azure_component_twin_state_output.internal_evidence.access_binding_refs) == 0
    error_message = "An isolated writer check must not claim a human-reader binding."
  }
}

# The shared role-assignment map pulls unrelated infrastructure into its graph.
# Admit only the ADT/group roots instead; an instance-scoped SDK role binding
# must be separately planned, tracked and removed by the future live runner.
run "azure_l4_infrastructure_only" {
  command = plan
  variables {
    layer_4_provider = "azure"
    layer_5_provider = "azure"
  }
  plan_options {
    target = [
      azurerm_resource_group.main,
      azurerm_digital_twins_instance.azure_azure_digital_twins,
    ]
  }
  assert {
    condition     = length(azurerm_digital_twins_instance.azure_azure_digital_twins) == 1
    error_message = "The infrastructure-only plan requires exactly one ADT instance."
  }
}
