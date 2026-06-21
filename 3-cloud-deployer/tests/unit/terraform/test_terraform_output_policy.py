"""Tests for Terraform output visibility classification."""

from src.terraform_output_policy import (
    TerraformOutputVisibility,
    classify_terraform_output,
    classify_terraform_outputs,
)


def test_secret_bearing_outputs_are_redacted():
    secret_outputs = [
        "azure_platform_user_password",
        "inter_cloud_token",
        "aws_grafana_api_key",
        "azure_iothub_connection_string",
    ]

    for name in secret_outputs:
        policy = classify_terraform_output(name)
        assert policy.visibility == TerraformOutputVisibility.REDACTED


def test_ui_facing_outputs_are_safe():
    safe_outputs = [
        "azure_adt_endpoint",
        "azure_3d_scenes_studio_url",
        "aws_grafana_endpoint",
        "gcp_dispatcher_url",
        "digital_twin_name",
    ]

    for name in safe_outputs:
        policy = classify_terraform_output(name)
        assert policy.visibility == TerraformOutputVisibility.SAFE


def test_infrastructure_identifiers_are_internal_only():
    internal_outputs = [
        "aws_iot_role_arn",
        "azure_resource_group_id",
        "aws_account_id",
        "gcp_service_account_email",
    ]

    for name in internal_outputs:
        policy = classify_terraform_output(name)
        assert policy.visibility == TerraformOutputVisibility.INTERNAL_ONLY


def test_unknown_outputs_default_to_internal_only():
    policy = classify_terraform_output("new_provider_experimental_value")

    assert policy.visibility == TerraformOutputVisibility.INTERNAL_ONLY
    assert "not explicitly classified" in policy.reason


def test_classify_terraform_outputs_preserves_output_names():
    policies = classify_terraform_outputs(
        {
            "aws_grafana_endpoint": "https://grafana.example.test",
            "aws_grafana_api_key": "secret",
        }
    )

    assert set(policies) == {"aws_grafana_endpoint", "aws_grafana_api_key"}
    assert policies["aws_grafana_endpoint"].visibility == TerraformOutputVisibility.SAFE
    assert policies["aws_grafana_api_key"].visibility == TerraformOutputVisibility.REDACTED
