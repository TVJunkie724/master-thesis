"""Version-aware effective-permission validation for active Phase 8 packs."""

from unittest.mock import Mock, patch

from src.api.azure_credentials_checker import (
    _azure_permission_contract_for_version,
    _compare_permissions as compare_azure_permissions,
)
from src.api.credentials_checker import (
    _aws_permission_contract_for_version,
    _compare_permissions as compare_aws_permissions,
    _get_all_required_permissions,
)
from src.api.gcp_credentials_checker import (
    GCP_V2_DIRECTLY_TESTED_PERMISSIONS,
    GCP_V2_PROJECT_TESTABLE_PERMISSIONS,
    _check_v2_identity_prerequisite_api,
    _filter_gcp_permission_contract,
    _gcp_permission_contract_for_version,
    _get_all_required_gcp_permissions,
)
from src.api.permission_sets import (
    ACTIVE_PERMISSION_SET_VERSION,
    active_deployment_permission_pack,
    deployment_permission_pack_for_version,
)


def test_active_pack_loader_is_explicit_and_returns_defensive_copies():
    first = active_deployment_permission_pack("aws")
    second = active_deployment_permission_pack("aws")

    assert first == second
    assert first is not second
    first["provider"] = "tampered"
    assert second["provider"] == "aws"
    assert deployment_permission_pack_for_version("aws", None) is None
    assert deployment_permission_pack_for_version("aws", "thesis-demo-v1") is None


def test_aws_v2_checker_uses_every_frozen_pack_action_once():
    pack = active_deployment_permission_pack("aws")
    contract = _aws_permission_contract_for_version(ACTIVE_PERMISSION_SET_VERSION)
    expected = {
        action
        for group in pack["policy_inputs"]
        for action in group["actions"]
    }
    required = _get_all_required_permissions(contract)
    actual = {
        action for service in required.values() for action in service["actions"]
    }

    assert actual == expected
    comparison = compare_aws_permissions(expected, required, contract)
    assert comparison["summary"] == {
        "total_required": len(expected),
        "valid": len(expected),
        "missing": 0,
    }


@patch("src.api.credentials_checker._get_attached_permissions")
@patch("src.api.credentials_checker._check_aws_account_status")
@patch("src.api.credentials_checker._validate_aws_region")
@patch("src.api.credentials_checker._get_caller_identity")
@patch("src.api.credentials_checker._create_session")
def test_aws_credential_checker_selects_v2_contract(
    mock_create_session,
    mock_caller_identity,
    mock_region,
    mock_account_status,
    mock_attached_permissions,
):
    from src.api.credentials_checker import check_aws_credentials

    pack = active_deployment_permission_pack("aws")
    expected = {
        action
        for group in pack["policy_inputs"]
        for action in group["actions"]
    }
    mock_create_session.return_value = Mock()
    mock_caller_identity.return_value = {
        "account": "123456789012",
        "arn": "arn:aws:iam::123456789012:user/twin2mc-e2e-test",
        "user_id": "AIDATEST",
        "principal_type": "user",
    }
    mock_region.return_value = {"valid": True, "region": "eu-central-1"}
    mock_account_status.return_value = {"status": "active", "state": "ACTIVE"}
    mock_attached_permissions.return_value = (expected, None)

    result = check_aws_credentials(
        {
            "aws_access_key_id": "AKIATEST",
            "aws_secret_access_key": "synthetic-secret",
            "aws_region": "eu-central-1",
            "permission_set_version": "thesis-demo-v2",
        }
    )

    assert result["status"] == "valid"
    assert result["summary"] == {
        "total_required": len(expected),
        "valid": len(expected),
        "missing": 0,
    }


def test_azure_v2_checker_uses_exact_management_and_data_actions():
    pack = active_deployment_permission_pack("azure")
    contract = _azure_permission_contract_for_version(ACTIVE_PERMISSION_SET_VERSION)
    role_info = {
        "assignments": [{"role_name": "thesis-demo-v2"}],
        "all_actions": set(pack["role_inputs"]["actions"]),
        "all_data_actions": set(pack["role_inputs"]["data_actions"]),
    }

    assert set(contract) == {"thesis_demo_v2"}
    assert contract["thesis_demo_v2"]["required_actions"] == pack["role_inputs"][
        "actions"
    ]
    assert contract["thesis_demo_v2"]["required_data_actions"] == pack[
        "role_inputs"
    ]["data_actions"]
    comparison = compare_azure_permissions(role_info, contract)
    assert comparison["summary"] == {
        "total_layers": 1,
        "valid_layers": 1,
        "partial_layers": 0,
        "invalid_layers": 0,
    }


@patch("src.api.azure_credentials_checker._get_role_assignments_with_permissions")
@patch("src.api.azure_credentials_checker._check_sp_credential_expiration")
@patch("src.api.azure_credentials_checker._get_caller_identity")
@patch("src.api.azure_credentials_checker._create_credential")
def test_azure_credential_checker_selects_v2_contract(
    mock_create_credential,
    mock_caller_identity,
    mock_expiration,
    mock_role_assignments,
):
    from src.api.azure_credentials_checker import check_azure_credentials

    pack = active_deployment_permission_pack("azure")
    mock_create_credential.return_value = Mock()
    mock_caller_identity.return_value = {
        "subscription_id": "sub-123",
        "subscription_name": "Test Subscription",
        "tenant_id": "tenant-123",
        "state": "Enabled",
        "principal_id": "sp-123",
    }
    mock_expiration.return_value = {"status": "valid"}
    mock_role_assignments.return_value = {
        "assignments": [{"role_name": "thesis-demo-v2"}],
        "all_actions": set(pack["role_inputs"]["actions"]),
        "all_data_actions": set(pack["role_inputs"]["data_actions"]),
    }

    result = check_azure_credentials(
        {
            "azure_subscription_id": "sub-123",
            "azure_tenant_id": "tenant-123",
            "azure_client_id": "client-123",
            "azure_client_secret": "synthetic-secret",
            "permission_set_version": "thesis-demo-v2",
        }
    )

    assert result["status"] == "valid"
    assert result["summary"] == {
        "total_layers": 1,
        "valid_layers": 1,
        "partial_layers": 0,
        "invalid_layers": 0,
    }
    assert result["recommended_roles"] == {
        "custom": "Versioned thesis-demo-v2 custom role",
        "builtin": [],
    }


def test_gcp_v2_checker_partitions_pack_without_losing_permissions():
    pack = active_deployment_permission_pack("gcp")
    contract = _gcp_permission_contract_for_version(ACTIVE_PERMISSION_SET_VERSION)
    expected = set(pack["custom_role_inputs"])
    actual = _get_all_required_gcp_permissions(contract)

    assert actual == expected
    assert GCP_V2_PROJECT_TESTABLE_PERMISSIONS < actual
    assert GCP_V2_DIRECTLY_TESTED_PERMISSIONS < actual
    assert GCP_V2_PROJECT_TESTABLE_PERMISSIONS.isdisjoint(
        GCP_V2_DIRECTLY_TESTED_PERMISSIONS
    )
    filtered = _filter_gcp_permission_contract(
        GCP_V2_PROJECT_TESTABLE_PERMISSIONS,
        contract,
    )
    assert _get_all_required_gcp_permissions(filtered) == (
        GCP_V2_PROJECT_TESTABLE_PERMISSIONS
    )
    assert (actual - GCP_V2_PROJECT_TESTABLE_PERMISSIONS) | (
        GCP_V2_PROJECT_TESTABLE_PERMISSIONS
    ) == expected


@patch("google.cloud.service_usage_v1.ServiceUsageClient")
def test_gcp_v2_checks_only_the_existing_iam_api(mock_service_usage_client):
    from google.cloud import service_usage_v1

    client = mock_service_usage_client.return_value
    client.get_service.return_value = Mock(state=service_usage_v1.State.ENABLED)

    result = _check_v2_identity_prerequisite_api(
        "test-project",
        credentials=Mock(),
    )

    assert result == {
        "status": "checked",
        "api": "iam.googleapis.com",
        "enabled": True,
        "required_permission": "serviceusage.services.get",
    }
    client.get_service.assert_called_once_with(
        name="projects/test-project/services/iam.googleapis.com"
    )
