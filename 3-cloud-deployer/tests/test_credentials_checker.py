"""
Tests for the AWS Credentials Checker module.

Tests the permission checking logic with mocked AWS responses.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

from src.api.credentials_checker import (
    check_aws_credentials,
    check_aws_credentials_from_config,
    _get_all_required_permissions,
    _check_permission,
    _extract_permissions,
    REQUIRED_AWS_PERMISSIONS,
)


class TestRequiredPermissions:
    """Tests for the hardcoded permissions structure."""
    
    def test_required_permissions_has_all_layers(self):
        """Verify all 5 layers are defined."""
        assert "layer_1" in REQUIRED_AWS_PERMISSIONS
        assert "layer_2" in REQUIRED_AWS_PERMISSIONS
        assert "layer_3" in REQUIRED_AWS_PERMISSIONS
        assert "layer_4" in REQUIRED_AWS_PERMISSIONS
        assert "layer_5" in REQUIRED_AWS_PERMISSIONS
    
    def test_layer_1_has_core_services(self):
        """Layer 1 should have IAM, Lambda, IoT, STS."""
        layer_1 = REQUIRED_AWS_PERMISSIONS["layer_1"]
        assert "iam" in layer_1
        assert "lambda" in layer_1
        assert "iot" in layer_1
        assert "sts" in layer_1
    
    def test_layer_3_has_storage_services(self):
        """Layer 3 should have DynamoDB, S3, Events."""
        layer_3 = REQUIRED_AWS_PERMISSIONS["layer_3"]
        assert "dynamodb" in layer_3
        assert "s3" in layer_3
        assert "events" in layer_3
    
    def test_get_all_required_permissions_aggregates(self):
        """Test that aggregation works correctly."""
        result = _get_all_required_permissions()
        
        # IAM should be in multiple layers
        assert "iam" in result
        assert len(result["iam"]["actions"]) > 0
        assert len(result["iam"]["layers"]) >= 1


class TestPermissionChecking:
    """Tests for permission comparison logic."""
    
    def test_check_permission_exact_match(self):
        """Exact permission match."""
        available = {"iam:CreateRole", "iam:DeleteRole"}
        assert _check_permission("iam:CreateRole", available) is True
        assert _check_permission("iam:GetRole", available) is False
    
    def test_check_permission_wildcard_star(self):
        """Full admin wildcard covers everything."""
        available = {"*"}
        assert _check_permission("iam:CreateRole", available) is True
        assert _check_permission("s3:GetObject", available) is True
    
    def test_check_permission_service_wildcard(self):
        """Service wildcard like 's3:*' covers all s3 actions."""
        available = {"s3:*", "iam:CreateRole"}
        assert _check_permission("s3:GetObject", available) is True
        assert _check_permission("s3:PutObject", available) is True
        assert _check_permission("iam:CreateRole", available) is True
        assert _check_permission("iam:DeleteRole", available) is False


class TestExtractPermissions:
    """Tests for policy document parsing."""
    
    def test_extract_single_action(self):
        """Extract single action from policy."""
        policy = {
            "Statement": [{
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": "*"
            }]
        }
        permissions = set()
        _extract_permissions(policy, permissions)
        assert "s3:GetObject" in permissions
    
    def test_extract_multiple_actions(self):
        """Extract multiple actions from policy."""
        policy = {
            "Statement": [{
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject"],
                "Resource": "*"
            }]
        }
        permissions = set()
        _extract_permissions(policy, permissions)
        assert "s3:GetObject" in permissions
        assert "s3:PutObject" in permissions
    
    def test_extract_ignores_deny(self):
        """Deny statements should be ignored."""
        policy = {
            "Statement": [{
                "Effect": "Deny",
                "Action": "s3:DeleteBucket",
                "Resource": "*"
            }]
        }
        permissions = set()
        _extract_permissions(policy, permissions)
        assert "s3:DeleteBucket" not in permissions
    
    def test_extract_wildcard(self):
        """Wildcard actions are preserved."""
        policy = {
            "Statement": [{
                "Effect": "Allow",
                "Action": "*",
                "Resource": "*"
            }]
        }
        permissions = set()
        _extract_permissions(policy, permissions)
        assert "*" in permissions


class TestCheckAWSCredentials:
    """Tests for the main check_aws_credentials function."""
    
    def test_missing_credentials(self):
        """Test with missing credentials."""
        result = check_aws_credentials({})
        assert result["status"] == "invalid"
        assert "Missing required credentials" in result["message"]
    
    def test_missing_access_key(self):
        """Test with missing access key."""
        result = check_aws_credentials({
            "aws_secret_access_key": "secret",
            "aws_region": "us-east-1"
        })
        assert result["status"] == "invalid"
    
    @patch("src.api.credentials_checker.boto3.Session")
    def test_invalid_credentials(self, mock_session):
        """Test with invalid credentials."""
        from botocore.exceptions import ClientError
        
        mock_sts = Mock()
        mock_sts.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "InvalidClientTokenId", "Message": "Invalid"}},
            "GetCallerIdentity"
        )
        
        mock_session.return_value.client.return_value = mock_sts
        
        result = check_aws_credentials({
            "aws_access_key_id": "invalid",
            "aws_secret_access_key": "invalid",
            "aws_region": "us-east-1"
        })
        
        assert result["status"] == "invalid"
        assert "Invalid credentials" in result["message"]
    
    @patch("src.api.credentials_checker.boto3.Session")
    def test_valid_credentials_full_access(self, mock_session):
        """Test with valid credentials that have full admin access."""
        # Mock STS client
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/admin",
            "UserId": "AIDAEXAMPLE"
        }
        
        # Mock IAM client
        mock_iam = Mock()
        mock_iam.list_user_policies.return_value = {"PolicyNames": []}
        mock_iam.list_attached_user_policies.return_value = {
            "AttachedPolicies": [{"PolicyName": "Admin", "PolicyArn": "arn:aws:iam::aws:policy/AdministratorAccess"}]
        }
        mock_iam.list_groups_for_user.return_value = {"Groups": []}
        mock_iam.get_policy.return_value = {
            "Policy": {"DefaultVersionId": "v1"}
        }
        mock_iam.get_policy_version.return_value = {
            "PolicyVersion": {
                "Document": {
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": "*",
                        "Resource": "*"
                    }]
                }
            }
        }
        
        def client_factory(service_name):
            if service_name == "sts":
                return mock_sts
            return mock_iam
        
        mock_session.return_value.client.side_effect = client_factory
        
        result = check_aws_credentials({
            "aws_access_key_id": "valid",
            "aws_secret_access_key": "valid",
            "aws_region": "us-east-1"
        })
        
        assert result["status"] == "valid"
        assert result["caller_identity"]["account"] == "123456789012"
        assert result["can_list_policies"] is True
        assert result["summary"]["missing"] == 0
    
    @patch("src.api.credentials_checker.boto3.Session")
    def test_cannot_list_policies(self, mock_session):
        """Test when credentials can't list their own policies."""
        from botocore.exceptions import ClientError
        
        # Mock STS client - works
        mock_sts = Mock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/restricted",
            "UserId": "AIDAEXAMPLE"
        }
        
        # Mock IAM client - access denied
        mock_iam = Mock()
        mock_iam.list_user_policies.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "ListUserPolicies"
        )
        
        def client_factory(service_name):
            if service_name == "sts":
                return mock_sts
            return mock_iam
        
        mock_session.return_value.client.side_effect = client_factory
        
        result = check_aws_credentials({
            "aws_access_key_id": "restricted",
            "aws_secret_access_key": "restricted",
            "aws_region": "us-east-1"
        })
        
        assert result["status"] == "check_failed"
        assert result["can_list_policies"] is False
        assert result["missing_check_permission"] == "iam:ListUserPolicies"



class TestCheckAWSCredentialsFromConfig:
    """Tests for loading credentials from config."""
    
    @patch("src.api.credentials_checker.os.path.exists")
    @patch("src.core.state.get_project_upload_path")
    def test_project_not_found(self, mock_get_path, mock_exists):
        """Test validation when project doesn't exist."""
        mock_get_path.return_value = "/tmp/upload"
        mock_exists.return_value = False
        
        result = check_aws_credentials_from_config("nonexistent_project")
        
        assert result["status"] == "error"
        assert "Invalid project" in result["message"]

    @patch("src.api.credentials_checker.check_aws_credentials")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("src.api.credentials_checker.os.path.exists")
    @patch("src.core.state.get_active_project")
    @patch("src.core.state.get_project_upload_path")
    def test_success_from_active_project(self, mock_get_path, mock_get_active, mock_exists, mock_open, mock_check):
        """Test successful loading from active project."""
        mock_get_path.return_value = "/tmp/upload"
        mock_get_active.return_value = "my_project"
        mock_exists.return_value = True # Both project dir and config file exist
        
        # Mock file content
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = '{"aws": {"aws_access_key_id": "key", "aws_secret_access_key": "secret"}}'
        # Fix json.load to use read data or just mock json.load? 
        # Easier to mock mock_open properly or patch json.load.
        # Let's patch json.load to be safe and simple
        with patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"aws": {"aws_access_key_id": "key", "aws_secret_access_key": "secret"}}
            mock_check.return_value = {"status": "valid"}

            result = check_aws_credentials_from_config() # Uses active project
            
            assert result["status"] == "valid"
            mock_check.assert_called_once()  

    @patch("src.api.credentials_checker.os.path.exists")
    @patch("src.core.state.get_active_project")
    @patch("src.core.state.get_project_upload_path")
    def test_config_file_missing(self, mock_get_path, mock_get_active, mock_exists):
        """Test when config file is missing."""
        mock_get_path.return_value = "/tmp/upload"
        mock_get_active.return_value = "my_project"
        mock_exists.return_value = False
        
        result = check_aws_credentials_from_config()
        
        assert result["status"] == "error"
        assert "No config_credentials.json" in result["message"]


class TestSessionTokenSupport:
    """Tests for temporary credentials with session token."""
    
    @patch("src.api.credentials_checker.boto3.Session")
    def test_session_token_passed(self, mock_session):
        """Verify session token is passed to boto3."""
        from botocore.exceptions import ClientError
        
        mock_session.return_value.client.return_value.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "InvalidClientTokenId", "Message": "Invalid"}},
            "GetCallerIdentity"
        )
        
        check_aws_credentials({
            "aws_access_key_id": "key",
            "aws_secret_access_key": "secret",
            "aws_region": "us-east-1",
            "aws_session_token": "token123"
        })
        
        # Verify Session was created with session token
        mock_session.assert_called_once_with(
            aws_access_key_id="key",
            aws_secret_access_key="secret",
            region_name="us-east-1",
            aws_session_token="token123"
        )
