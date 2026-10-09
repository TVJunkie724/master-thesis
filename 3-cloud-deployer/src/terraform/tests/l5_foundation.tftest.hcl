# Provider-mocked Apply only: L5 does not exist during the image foundation stage.
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

run "aws_image_foundation_has_no_premature_l5_output" {
  command = apply
  override_data {
    target = data.aws_caller_identity.current
    values = {
      account_id = "123456789012"
      arn        = "arn:aws:iam::123456789012:user/terraform-mock"
      user_id    = "AIDACKCEVSQ6C2EXAMPLE"
    }
  }
  override_data {
    target = data.aws_iot_endpoint.main
    values = { endpoint_address = "test-ats.iot.eu-central-1.amazonaws.com" }
  }
  override_data {
    target = data.aws_ssoadmin_instances.aws_six_layer_layer_access
    values = {
      arns               = ["arn:aws:sso:::instance/ssoins-0123456789abcdef"]
      identity_store_ids = ["d-0123456789"]
    }
  }
  override_data {
    target = data.aws_identitystore_users.aws_six_layer_layer_access
    values = { users = [] }
  }
  override_resource {
    target = aws_ecr_repository.aws_aws_ecr_if_container_selected
    values = { repository_url = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test" }
  }
  plan_options {
    target = [aws_ecr_repository.aws_aws_ecr_if_container_selected]
  }
  variables {
    digital_twin_name                 = "drift-test"
    architecture_profile_id           = "six-layer-eventing"
    architecture_profile_version      = "1"
    event_layer_provider              = "aws"
    layer_1_provider                  = "aws"
    layer_2_provider                  = "aws"
    layer_3_hot_provider              = "aws"
    layer_3_cold_provider             = "aws"
    layer_3_archive_provider          = "aws"
    layer_4_provider                  = "aws"
    layer_5_provider                  = "aws"
    aws_event_kinesis_shards          = 1
    platform_user_email               = "researcher@example.test"
    platform_user_first_name          = "Thesis"
    platform_user_last_name           = "Researcher"
    aws_layer_access_principal_intent = "invite_builtin"
    aws_six_layer_storage_mover_image = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/drift-test@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    resolved_component_dimensions = {
      "dimension.aws.aws.ecs-fargate-storage-mover.task_count"   = "1"
      "dimension.aws.aws.kinesis-data-streams.shards_per_stream" = "1"
    }
    validated_extension_packages = [{
      slot_id         = "processor.telemetry"
      slot_version    = "1"
      artifact_id     = "44444444-4444-4444-8444-444444444444"
      artifact_digest = "sha256:4444444444444444444444444444444444444444444444444444444444444444"
      package_path    = "${var.project_path}/.build/aws/six-layer-domain.zip"
      package_digest  = "sha256:${filesha256("${var.project_path}/.build/aws/six-layer-domain.zip")}"
      adapter_id      = "adapter.aws.python311"
      adapter_version = "1"
    }]
  }
  assert {
    condition     = output.aws_component_visualization_output == null
    error_message = "Image foundation must not advertise a nonexistent L5 consumer."
  }
}
