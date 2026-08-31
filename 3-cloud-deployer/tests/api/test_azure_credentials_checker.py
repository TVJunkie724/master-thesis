"""
Unit tests for Azure Credentials Checker.

Tests cover:
- Credential validation
- Action matching logic
- Layer status calculation
- CLI integration
"""

import base64
import pytest
import json
from unittest.mock import patch, MagicMock, Mock


def _azure_credentials():
    return {
        "azure_subscription_id": "sub-123",
        "azure_tenant_id": "tenant-123",
        "azure_client_id": "deployment-client-123",
        "azure_client_secret": "deployment-secret-123",
        "azure_preparation_client_id": "preparation-client-123",
        "azure_preparation_client_secret": "preparation-secret-123",
        "azure_region": "westeurope",
        "azure_region_iothub": "westeurope",
        "azure_region_digital_twin": "westeurope",
    }


def _identity(principal_id):
    return {
        "subscription_id": "sub-123",
        "subscription_name": "Test Sub",
        "tenant_id": "tenant-123",
        "state": "Enabled",
        "principal_id": principal_id,
    }


def _deployment_role_info():
    from src.api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS

    return {
        "assignments": [
            {"role_name": "Digital Twin Deployer", "principal_id": "deployment-sp"}
        ],
        "all_actions": {"*"},
        "all_data_actions": _all_required_azure_data_actions(
            REQUIRED_AZURE_PERMISSIONS
        ),
        "permission_blocks": [
            {
                "role_name": "Digital Twin Deployer",
                "actions": {"*"},
                "not_actions": {
                    "Microsoft.Authorization/roleAssignments/write",
                    "Microsoft.Authorization/roleAssignments/delete",
                },
                "data_actions": {"*"},
                "not_data_actions": set(),
            }
        ],
    }


def _preparation_condition(
    extra_role_ids=(), principal_types=("User", "ServicePrincipal")
):
    from src.api.azure_credentials_checker import AZURE_PREPARATION_ROLE_IDS

    role_ids = sorted({*AZURE_PREPARATION_ROLE_IDS, *extra_role_ids})
    return (
        "ActionMatches{'Microsoft.Authorization/roleAssignments/write'} "
        "ActionMatches{'Microsoft.Authorization/roleAssignments/delete'} "
        "@Request[Microsoft.Authorization/roleAssignments:RoleDefinitionId] "
        f"ForAnyOfAnyValues:GuidEquals {{{' '.join(role_ids)}}} "
        "@Request[Microsoft.Authorization/roleAssignments:PrincipalType] "
        f"ForAnyOfAnyValues:StringEqualsIgnoreCase {{{' '.join(principal_types)}}}"
    )


def _preparation_role_info(**assignment_updates):
    from src.api.azure_credentials_checker import AZURE_BUILTIN_ROLES

    assignment = {
        "role_name": "Role Based Access Control Administrator",
        "role_definition_id": AZURE_BUILTIN_ROLES[
            "Role Based Access Control Administrator"
        ],
        "principal_id": "preparation-sp",
        "scope": "/subscriptions/sub-123",
        "condition": _preparation_condition(),
        "condition_version": "2.0",
    }
    assignment.update(assignment_updates)
    return {
        "assignments": [assignment],
        "all_actions": set(),
        "all_data_actions": set(),
        "permission_blocks": [
            {
                "role_name": "Role Based Access Control Administrator",
                "actions": {
                    "Microsoft.Authorization/roleAssignments/write",
                    "Microsoft.Authorization/roleAssignments/delete",
                },
                "not_actions": set(),
                "data_actions": set(),
                "not_data_actions": set(),
            }
        ],
    }


class TestAzureCredentialValidation:
    """Tests for Azure credential validation logic."""

    def test_check_azure_credentials_missing_fields(self):
        """Test validation fails with missing required fields."""
        from src.api.azure_credentials_checker import (
            check_azure_credentials,
        )

        # Missing all fields
        result = check_azure_credentials({})
        assert result["status"] == "invalid"
        assert "Missing required credentials" in result["message"]

        # Missing some fields
        result = check_azure_credentials(
            {
                "azure_subscription_id": "sub-123",
                "azure_tenant_id": "tenant-123",
                # Missing client_id and client_secret
            }
        )
        assert result["status"] == "invalid"
        assert "azure_client_id" in result["message"]

    @patch("src.api.azure_credentials_checker._check_sp_credential_expiration")
    @patch("src.api.azure_credentials_checker._check_microsoft_graph_authority")
    @patch("src.api.azure_credentials_checker._validate_azure_regions")
    @patch("src.api.azure_credentials_checker._get_role_assignments_with_permissions")
    @patch("src.api.azure_credentials_checker._get_caller_identity")
    @patch("src.api.azure_credentials_checker._create_credential")
    def test_check_azure_credentials_valid(
        self,
        mock_credential,
        mock_identity,
        mock_roles,
        mock_regions,
        mock_graph,
        mock_expiration,
    ):
        """Test successful credential validation with all permissions present."""
        from src.api.azure_credentials_checker import check_azure_credentials

        mock_credential.side_effect = [Mock(), Mock()]
        mock_identity.side_effect = [
            _identity("deployment-sp"),
            _identity("preparation-sp"),
        ]
        mock_roles.side_effect = [_deployment_role_info(), _preparation_role_info()]
        mock_regions.return_value = {}
        mock_graph.return_value = {
            "status": "ready",
            "message": "ready",
            "missing_permissions": [],
            "unexpected_permissions": [],
        }
        mock_expiration.return_value = {"status": "valid"}

        result = check_azure_credentials(_azure_credentials())

        assert result["status"] == "valid"
        assert result["deployment_authority"]["status"] == "ready"
        assert result["preparation_authority"]["status"] == "ready"
        assert result["microsoft_graph_authority"]["status"] == "ready"
        assert result["can_list_roles"]

    @patch("src.api.azure_credentials_checker._check_sp_credential_expiration")
    @patch("src.api.azure_credentials_checker._check_microsoft_graph_authority")
    @patch("src.api.azure_credentials_checker._validate_azure_regions")
    @patch("src.api.azure_credentials_checker._get_role_assignments_with_permissions")
    @patch("src.api.azure_credentials_checker._get_caller_identity")
    @patch("src.api.azure_credentials_checker._create_credential")
    def test_check_azure_credentials_partial(
        self,
        mock_credential,
        mock_identity,
        mock_roles,
        mock_regions,
        mock_graph,
        mock_expiration,
    ):
        """Test partial credential validation when some actions are missing."""
        from src.api.azure_credentials_checker import check_azure_credentials

        mock_credential.side_effect = [Mock(), Mock()]
        mock_identity.side_effect = [
            _identity("deployment-sp"),
            _identity("preparation-sp"),
        ]

        # Missing some required actions
        deployment_roles = {
            "assignments": [{"role_name": "Reader", "principal_id": "sp-123"}],
            "all_actions": {"*/read"},  # Only read
            "all_data_actions": set(),
        }
        mock_roles.side_effect = [deployment_roles, _preparation_role_info()]
        mock_regions.return_value = {}
        mock_graph.return_value = {
            "status": "ready",
            "message": "ready",
            "missing_permissions": [],
            "unexpected_permissions": [],
        }
        mock_expiration.return_value = {"status": "valid"}

        result = check_azure_credentials(_azure_credentials())

        assert result["status"] in ["partial", "invalid"]

    @patch("src.api.azure_credentials_checker._create_credential")
    @patch("src.api.azure_credentials_checker._get_caller_identity")
    def test_check_azure_credentials_disabled_subscription(
        self, mock_identity, mock_cred
    ):
        """Test validation fails early for disabled subscriptions."""
        from src.api.azure_credentials_checker import check_azure_credentials

        # Simulate disabled subscription (billing issue, quota exceeded, etc.)
        mock_identity.return_value = {
            "subscription_id": "sub-123",
            "subscription_name": "Test Sub",
            "tenant_id": "tenant-123",
            "state": "Disabled",  # Key: subscription is disabled
            "principal_id": "sp-123",
        }

        result = check_azure_credentials(_azure_credentials())

        # Should fail with clear message about subscription state
        assert result["status"] == "invalid"
        assert "not enabled" in result["message"]
        assert "subscription" in result["message"].lower()

    @patch("src.api.azure_credentials_checker._create_credential")
    @patch("src.api.azure_credentials_checker._get_caller_identity")
    def test_check_azure_credentials_fails_when_principal_id_is_unknown(
        self, mock_identity, mock_cred
    ):
        """Permission validation must not aggregate unfiltered subscription roles."""
        from src.api.azure_credentials_checker import check_azure_credentials

        mock_identity.return_value = {
            "subscription_id": "sub-123",
            "subscription_name": "Test Sub",
            "tenant_id": "tenant-123",
            "state": "Enabled",
            "principal_type": "service_principal",
        }

        result = check_azure_credentials(_azure_credentials())

        assert result["status"] == "check_failed"
        assert result["can_list_roles"] is False
        assert "object ID" in result["message"]


class TestAzureRoleAssignmentFiltering:
    """Tests for filtering Azure RBAC assignments to the authenticated principal."""

    def test_decode_jwt_claims_extracts_principal_identifiers(self):
        from src.api.azure_credentials_checker import _decode_jwt_claims
        import base64

        payload = {
            "oid": "principal-123",
            "appid": "client-123",
        }
        encoded_payload = (
            base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        )
        token = f"header.{encoded_payload}.signature"

        assert _decode_jwt_claims(token) == payload

    def test_role_assignment_collection_filters_to_current_principal(self):
        from src.api.azure_credentials_checker import (
            _get_role_assignments_with_permissions,
        )
        from types import SimpleNamespace

        current_assignment = Mock(
            principal_id="current-principal",
            principal_type="ServicePrincipal",
            role_definition_id="/subscriptions/sub-123/providers/Microsoft.Authorization/roleDefinitions/current-role",
            scope="/subscriptions/sub-123",
            condition=None,
            condition_version=None,
        )
        other_assignment = Mock(
            principal_id="other-principal",
            principal_type="ServicePrincipal",
            role_definition_id="/subscriptions/sub-123/providers/Microsoft.Authorization/roleDefinitions/other-role",
            scope="/subscriptions/sub-123",
            condition=None,
            condition_version=None,
        )
        role_definitions = {
            "current-role": SimpleNamespace(
                role_name="Current Role",
                permissions=[
                    SimpleNamespace(
                        actions=["Microsoft.Web/sites/write"],
                        not_actions=[],
                        data_actions=[],
                        not_data_actions=[],
                    )
                ],
            ),
            "other-role": SimpleNamespace(
                role_name="Other Owner",
                permissions=[
                    SimpleNamespace(
                        actions=["*"],
                        not_actions=[],
                        data_actions=["*"],
                        not_data_actions=[],
                    )
                ],
            ),
        }

        auth_client = MagicMock()
        auth_client.role_assignments.list_for_scope.return_value = [
            current_assignment,
            other_assignment,
        ]
        auth_client.role_definitions.get_by_id.side_effect = lambda role_id: (
            role_definitions[role_id.split("/")[-1]]
        )

        auth_module = MagicMock()
        auth_module.AuthorizationManagementClient.return_value = auth_client

        with patch.dict(
            "sys.modules",
            {
                "azure.mgmt.authorization": auth_module,
                "azure.core.exceptions": MagicMock(HttpResponseError=Exception),
            },
        ):
            result = _get_role_assignments_with_permissions(
                credential=Mock(),
                subscription_id="sub-123",
                principal_id="current-principal",
            )

        assert result["assignments"] == [
            {
                "principal_id": "current-principal",
                "principal_type": "ServicePrincipal",
                "role_name": "Current Role",
                "role_definition_id": "current-role",
                "scope": "/subscriptions/sub-123",
                "condition": None,
                "condition_version": None,
            }
        ]
        assert result["all_actions"] == {"Microsoft.Web/sites/write"}
        assert result["all_data_actions"] == set()


class TestAzureSplitAuthority:
    def test_preparation_authority_accepts_exact_condition(self):
        from src.api.azure_credentials_checker import _validate_preparation_authority

        result = _validate_preparation_authority(_preparation_role_info())

        assert result["status"] == "ready"
        assert result["principal_types"] == ["ServicePrincipal", "User"]

    def test_preparation_authority_rejects_group_target(self):
        from src.api.azure_credentials_checker import _validate_preparation_authority

        role_info = _preparation_role_info(
            condition=_preparation_condition(
                principal_types=("User", "ServicePrincipal", "Group")
            )
        )

        result = _validate_preparation_authority(role_info)

        assert result["status"] == "invalid"
        assert "principal-type" in result["message"]

    def test_preparation_authority_rejects_owner_role_id(self):
        from src.api.azure_credentials_checker import (
            AZURE_BUILTIN_ROLES,
            _validate_preparation_authority,
        )

        role_info = _preparation_role_info(
            condition=_preparation_condition(
                extra_role_ids=(AZURE_BUILTIN_ROLES["Owner"],)
            )
        )

        result = _validate_preparation_authority(role_info)

        assert result["status"] == "invalid"
        assert result["unexpected_role_ids"] == [AZURE_BUILTIN_ROLES["Owner"]]

    def test_graph_authority_requires_exact_application_permissions(self):
        from src.api.azure_credentials_checker import (
            AZURE_GRAPH_APPLICATION_PERMISSIONS,
            _check_microsoft_graph_authority,
        )

        payload = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {"roles": sorted(AZURE_GRAPH_APPLICATION_PERMISSIONS)}
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
        credential = Mock()
        credential.get_token.return_value = Mock(token=f"header.{payload}.signature")

        result = _check_microsoft_graph_authority(credential)

        assert result["status"] == "ready"

    def test_graph_authority_rejects_additional_application_permission(self):
        from src.api.azure_credentials_checker import (
            AZURE_GRAPH_APPLICATION_PERMISSIONS,
            _check_microsoft_graph_authority,
        )

        payload = (
            base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "roles": sorted(
                            {*AZURE_GRAPH_APPLICATION_PERMISSIONS, "Directory.Read.All"}
                        )
                    }
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
        credential = Mock()
        credential.get_token.return_value = Mock(token=f"header.{payload}.signature")

        result = _check_microsoft_graph_authority(credential)

        assert result["status"] == "overprivileged"
        assert result["unexpected_permissions"] == ["Directory.Read.All"]


class TestAzureSPExpiration:
    """Tests for Azure Service Principal credential expiration checking."""

    @patch("requests.get")
    @patch("azure.identity.ClientSecretCredential")
    def test_historical_expired_secret_does_not_invalidate_active_secret(
        self,
        mock_credential_type,
        mock_get,
    ):
        from datetime import datetime, timedelta, timezone

        from src.api.azure_credentials_checker import _check_sp_credential_expiration

        now = datetime.now(timezone.utc)
        mock_credential_type.return_value.get_token.return_value = Mock(token="token")
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "value": [
                {
                    "passwordCredentials": [
                        {"endDateTime": (now - timedelta(days=60)).isoformat()},
                        {"endDateTime": (now + timedelta(days=365)).isoformat()},
                    ],
                    "keyCredentials": [],
                }
            ]
        }

        result = _check_sp_credential_expiration(
            tenant_id="tenant-123",
            client_id="client-123",
            client_secret="secret-123",
        )

        assert result["status"] == "valid"
        assert result["graph_authority"]["status"] == "ready"
        assert result["days_until_expiration"] >= 363
        assert "secret-123" not in str(result)

    @patch("requests.get")
    @patch("azure.identity.ClientSecretCredential")
    def test_graph_consent_denial_is_separate_from_credential_expiration(
        self,
        mock_credential_type,
        mock_get,
    ):
        from src.api.azure_credentials_checker import _check_sp_credential_expiration

        mock_credential_type.return_value.get_token.return_value = Mock(token="token")
        mock_get.return_value.status_code = 403

        result = _check_sp_credential_expiration(
            tenant_id="tenant-123",
            client_id="client-123",
            client_secret="secret-123",
        )

        assert result["status"] == "skipped"
        assert result["graph_authority"]["status"] == "consent_required"
        assert "secret-123" not in str(result)

    @patch("src.api.azure_credentials_checker._check_sp_credential_expiration")
    @patch("src.api.azure_credentials_checker._get_caller_identity")
    @patch("src.api.azure_credentials_checker._create_credential")
    def test_expired_sp_credentials_detected(
        self, mock_create_cred, mock_get_identity, mock_expiration
    ):
        """Test that expired SP credentials are detected and fail early."""
        from src.api.azure_credentials_checker import check_azure_credentials

        mock_create_cred.return_value = Mock()
        mock_get_identity.return_value = {
            "subscription_id": "sub-123",
            "subscription_name": "Test Subscription",
            "tenant_id": "tenant-123",
            "state": "Enabled",
            "principal_type": "service_principal",
            "principal_id": "sp-123",
        }
        mock_expiration.return_value = {
            "status": "expired",
            "message": "Azure Service Principal credentials expired 10 days ago.",
        }

        result = check_azure_credentials(_azure_credentials())

        assert result["status"] == "invalid"
        assert "expired" in result["message"].lower()

    @patch("src.api.azure_credentials_checker._check_sp_credential_expiration")
    @patch("src.api.azure_credentials_checker._check_microsoft_graph_authority")
    @patch("src.api.azure_credentials_checker._validate_azure_regions")
    @patch("src.api.azure_credentials_checker._get_role_assignments_with_permissions")
    @patch("src.api.azure_credentials_checker._get_caller_identity")
    @patch("src.api.azure_credentials_checker._create_credential")
    def test_expiring_soon_is_warning_not_failure(
        self,
        mock_create_cred,
        mock_get_identity,
        mock_roles,
        mock_regions,
        mock_graph,
        mock_expiration,
    ):
        """Test that credentials expiring soon produce warning but don't fail."""
        from src.api.azure_credentials_checker import check_azure_credentials

        mock_create_cred.side_effect = [Mock(), Mock()]
        mock_get_identity.side_effect = [
            _identity("deployment-sp"),
            _identity("preparation-sp"),
        ]
        mock_expiration.return_value = {
            "status": "expiring_soon",
            "days_until_expiration": 15,
            "message": "Azure Service Principal credentials expire in 15 days.",
        }
        mock_regions.return_value = {}
        mock_graph.return_value = {
            "status": "ready",
            "message": "ready",
            "missing_permissions": [],
            "unexpected_permissions": [],
        }
        mock_roles.side_effect = [_deployment_role_info(), _preparation_role_info()]

        result = check_azure_credentials(_azure_credentials())

        # Should proceed despite expiring soon (warning only)
        assert result["status"] == "valid"
        assert result["sp_credential_expiration"]["status"] == "expiring_soon"


class TestActionMatching:
    """Tests for action matching logic."""

    def test_action_matches_direct(self):
        """Test direct action match returns 'exact'."""
        from src.api.azure_credentials_checker import _action_matches

        user_actions = {"Microsoft.Web/sites/write", "Microsoft.Web/sites/read"}

        # Direct match returns "exact"
        assert _action_matches(user_actions, "Microsoft.Web/sites/write") == "exact"
        # No match returns "none"
        assert _action_matches(user_actions, "Microsoft.Web/sites/delete") == "none"

    def test_action_matches_wildcard_all(self):
        """Test wildcard * matches everything and returns 'wildcard'."""
        from src.api.azure_credentials_checker import _action_matches

        user_actions = {"*"}

        # Wildcard matches return "wildcard"
        assert _action_matches(user_actions, "Microsoft.Web/sites/write") == "wildcard"
        assert (
            _action_matches(user_actions, "Microsoft.Storage/storageAccounts/delete")
            == "wildcard"
        )

    def test_action_matches_suffix_wildcard(self):
        """Test suffix wildcard like Microsoft.Web/* returns 'wildcard'."""
        from src.api.azure_credentials_checker import _action_matches

        user_actions = {"Microsoft.Web/*"}

        # Prefix wildcard matches return "wildcard"
        assert _action_matches(user_actions, "Microsoft.Web/sites/write") == "wildcard"
        assert (
            _action_matches(user_actions, "Microsoft.Web/serverfarms/delete")
            == "wildcard"
        )
        # Non-matching prefix returns "none"
        assert (
            _action_matches(user_actions, "Microsoft.Storage/storageAccounts/write")
            == "none"
        )

    def test_action_matches_read_wildcard(self):
        """Test */read wildcard returns 'wildcard' for read actions."""
        from src.api.azure_credentials_checker import _action_matches

        user_actions = {"*/read"}

        # Suffix wildcard matches return "wildcard"
        assert _action_matches(user_actions, "Microsoft.Web/sites/read") == "wildcard"
        assert (
            _action_matches(user_actions, "Microsoft.Storage/storageAccounts/read")
            == "wildcard"
        )
        # Non-matching suffix returns "none"
        assert _action_matches(user_actions, "Microsoft.Web/sites/write") == "none"


class TestComparePermissions:
    """Tests for permission comparison by layer."""

    def test_compare_permissions_all_valid(self):
        """Test all layers valid when all actions present."""
        from src.api.azure_credentials_checker import (
            REQUIRED_AZURE_PERMISSIONS,
            _compare_permissions,
        )

        role_info = {
            "assignments": [{"role_name": "Owner"}],
            "all_actions": {"*"},  # Owner has all actions
            "all_data_actions": _all_required_azure_data_actions(
                REQUIRED_AZURE_PERMISSIONS
            ),
        }

        result = _compare_permissions(role_info)

        assert result["summary"]["valid_layers"] == result["summary"]["total_layers"]
        assert result["summary"]["invalid_layers"] == 0

    def test_compare_permissions_missing_actions(self):
        """Test layer invalid when required actions missing."""
        from src.api.azure_credentials_checker import _compare_permissions

        role_info = {
            "assignments": [{"role_name": "Reader"}],
            "all_actions": {"*/read"},  # Only read actions
            "all_data_actions": set(),
        }

        result = _compare_permissions(role_info)

        # Should have missing actions
        assert result["summary"]["valid_layers"] < result["summary"]["total_layers"]

    def test_compare_permissions_none_role_info(self):
        """Test handling of None role_info (couldn't list)."""
        from src.api.azure_credentials_checker import _compare_permissions

        result = _compare_permissions(None)

        assert result["summary"]["total_layers"] == 0

    def test_compare_permissions_excludes_rbac_mutation_from_deployment_layers(self):
        """Deployment-layer requirements do not include role-assignment mutation."""
        from src.api.azure_credentials_checker import _compare_permissions

        role_info = {
            "assignments": [{"role_name": "Contributor"}],
            "all_actions": {"*"},
            "all_data_actions": set(),
            "permission_blocks": [
                {
                    "role_name": "Contributor",
                    "actions": {"*"},
                    "not_actions": {
                        "Microsoft.Authorization/roleAssignments/write",
                        "Microsoft.Authorization/roleAssignments/delete",
                    },
                    "data_actions": set(),
                    "not_data_actions": set(),
                }
            ],
        }

        result = _compare_permissions(role_info)

        layer_1_required = result["by_layer"]["layer_1"]["required_actions"]
        assert "Microsoft.Authorization/roleAssignments/write" not in layer_1_required
        assert "Microsoft.Authorization/roleAssignments/delete" not in layer_1_required

    def test_deployment_authority_rejects_role_assignment_actions(self):
        """The deployment principal must not retain RBAC mutation authority."""
        from src.api.azure_credentials_checker import _validate_deployment_authority

        role_info = {
            "assignments": [
                {"role_name": "Contributor"},
                {"role_name": "User Access Administrator"},
            ],
            "all_actions": {"*"},
            "all_data_actions": set(),
            "permission_blocks": [
                {
                    "role_name": "Contributor",
                    "actions": {"*"},
                    "not_actions": {
                        "Microsoft.Authorization/roleAssignments/write",
                        "Microsoft.Authorization/roleAssignments/delete",
                    },
                    "data_actions": set(),
                    "not_data_actions": set(),
                },
                {
                    "role_name": "User Access Administrator",
                    "actions": {
                        "Microsoft.Authorization/roleAssignments/write",
                        "Microsoft.Authorization/roleAssignments/delete",
                    },
                    "not_actions": set(),
                    "data_actions": set(),
                    "not_data_actions": set(),
                },
            ],
        }

        result = _validate_deployment_authority(role_info)

        assert result["status"] == "invalid"
        assert result["forbidden_actions"] == [
            "Microsoft.Authorization/roleAssignments/write",
            "Microsoft.Authorization/roleAssignments/delete",
        ]


def _all_required_azure_data_actions(required_permissions: dict) -> set[str]:
    return {
        action
        for layer in required_permissions.values()
        for action in layer.get("required_data_actions", [])
    }


class TestAzureCredentialsFromConfig:
    """Tests for loading credentials from project config."""

    @patch("src.api.azure_credentials_checker.check_azure_credentials")
    def test_from_config_with_project_name(self, mock_check, tmp_path):
        """Test loading credentials from specific project."""
        from src.api.azure_credentials_checker import (
            check_azure_credentials_from_config,
        )

        project_dir = tmp_path / "my-project"
        project_dir.mkdir()
        (project_dir / "config_credentials.json").write_text(
            json.dumps(
                {
                    "azure": {
                        "azure_subscription_id": "sub-123",
                        "azure_tenant_id": "tenant-123",
                        "azure_client_id": "client-123",
                        "azure_client_secret": "secret-123",
                    }
                }
            )
        )
        storage = MagicMock()
        storage.context.return_value.project_path = project_dir
        mock_check.return_value = {"status": "valid"}

        with patch(
            "src.core.project_storage.get_project_storage", return_value=storage
        ):
            result = check_azure_credentials_from_config("my-project")

        mock_check.assert_called_once()
        assert result["project_name"] == "my-project"

    def test_from_config_missing_azure_section(self, tmp_path):
        """Test error when Azure section missing from config."""
        from src.api.azure_credentials_checker import (
            check_azure_credentials_from_config,
        )

        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / "config_credentials.json").write_text('{"aws": {}}')
        storage = MagicMock()
        storage.context.return_value.project_path = project_dir

        with patch(
            "src.core.project_storage.get_project_storage", return_value=storage
        ):
            result = check_azure_credentials_from_config("test-project")

        assert result["status"] == "error"
        assert "No Azure credentials" in result["message"]


class TestRequiredPermissionsStructure:
    """Tests for the required permissions data structure."""

    def test_required_permissions_contains_all_layers(self):
        """Test all layers are defined in required permissions."""
        from src.api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS

        expected_layers = [
            "setup",
            "layer_0",
            "layer_1",
            "layer_2",
            "layer_3",
            "layer_4",
            "layer_5",
        ]

        for layer in expected_layers:
            assert layer in REQUIRED_AZURE_PERMISSIONS, f"Missing layer: {layer}"

    def test_layer_1_excludes_authorization_actions(self):
        """Role assignments belong exclusively to the preparation principal."""
        from src.api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS

        layer_1 = REQUIRED_AZURE_PERMISSIONS["layer_1"]
        required_actions = layer_1.get("required_actions", [])

        assert not any("Microsoft.Authorization" in a for a in required_actions)

    def test_layer_4_requires_data_actions(self):
        """Test layer_4 requires Digital Twins data plane actions."""
        from src.api.azure_credentials_checker import REQUIRED_AZURE_PERMISSIONS

        layer_4 = REQUIRED_AZURE_PERMISSIONS["layer_4"]
        data_actions = layer_4.get("required_data_actions", [])

        assert len(data_actions) > 0
        assert any("digitaltwins" in a for a in data_actions)

    def test_builtin_roles_contain_key_roles(self):
        """Test AZURE_BUILTIN_ROLES contains essential roles."""
        from src.api.azure_credentials_checker import AZURE_BUILTIN_ROLES

        essential_roles = [
            "Owner",
            "Contributor",
            "Reader",
            "User Access Administrator",
        ]

        for role in essential_roles:
            assert role in AZURE_BUILTIN_ROLES, f"Missing role: {role}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
