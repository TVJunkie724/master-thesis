"""
Unit tests for the credentials checker module.
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
import json

# Import the module under test
from backend import credentials_checker


# =============================================================================
# AWS Credential Tests
# =============================================================================

class TestAWSCredentials:
    """Tests for AWS credential validation."""
    
    def test_check_aws_credentials_missing(self):
        """Test when no credentials provided."""
        result = credentials_checker.check_aws_credentials(None)
        
        assert result["provider"] == "aws"
        assert result["status"] == "missing"
        assert result["config_present"] == False
        assert result["credentials_valid"] == False
    
    def test_check_aws_credentials_missing_fields(self):
        """Test when required fields are missing."""
        credentials = {"aws_access_key_id": "test"}  # Missing secret and region
        
        result = credentials_checker.check_aws_credentials(credentials)
        
        assert result["status"] == "invalid"
        assert "Missing required fields" in result["message"]
        assert result["config_present"] == False
    
    @patch("boto3.Session")
    def test_check_aws_credentials_valid(self, mock_session_class):
        """Test valid AWS credentials."""
        # Mock STS client
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
            "UserId": "AIDAEXAMPLE"
        }
        
        # Mock Pricing client
        mock_pricing = MagicMock()
        mock_pricing.describe_services.return_value = {"Services": []}
        
        # Configure session mock
        mock_session = MagicMock()
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "pricing": mock_pricing
        }.get(service, MagicMock())
        
        mock_session_class.return_value = mock_session
        
        credentials = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_region": "eu-central-1"
        }
        
        result = credentials_checker.check_aws_credentials(credentials)
        
        assert result["status"] == "valid"
        assert result["config_present"] == True
        assert result["credentials_valid"] == True
        assert result["can_fetch_pricing"] == True
        assert result["identity"]["account"] == "123456789012"
    
    @patch("boto3.Session")
    def test_check_aws_credentials_invalid_auth(self, mock_session_class):
        """Test AWS credentials that fail authentication."""
        from botocore.exceptions import ClientError
        
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ClientError(
            {"Error": {"Code": "InvalidClientTokenId", "Message": "Invalid token"}},
            "GetCallerIdentity"
        )
        mock_session.client.return_value = mock_sts
        mock_session_class.return_value = mock_session
        
        credentials = {
            "aws_access_key_id": "invalid",
            "aws_secret_access_key": "invalid",
            "aws_region": "eu-central-1"
        }
        
        result = credentials_checker.check_aws_credentials(credentials)
        
        assert result["status"] == "invalid"
        assert "InvalidClientTokenId" in result["message"]
        assert result["credentials_valid"] == False
    
    @patch("boto3.Session")
    def test_check_aws_credentials_no_pricing_permission(self, mock_session_class):
        """Test AWS credentials without pricing API permission."""
        from botocore.exceptions import ClientError
        
        # Mock STS client - success
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
            "UserId": "AIDAEXAMPLE"
        }
        
        # Mock Pricing client - access denied
        mock_pricing = MagicMock()
        mock_pricing.describe_services.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access Denied"}},
            "DescribeServices"
        )
        
        mock_session = MagicMock()
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "pricing": mock_pricing
        }.get(service, MagicMock())
        
        mock_session_class.return_value = mock_session
        
        credentials = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_region": "eu-central-1"
        }
        
        result = credentials_checker.check_aws_credentials(credentials)
        
        assert result["status"] == "invalid"
        assert result["credentials_valid"] == True  # Auth succeeded
        assert result["can_fetch_pricing"] == False  # But pricing failed
        assert "pricing" in result["message"].lower()


# =============================================================================
# GCP Credential Tests
# =============================================================================

class TestGCPCredentials:
    """Tests for GCP credential validation."""
    
    def test_check_gcp_credentials_missing(self):
        """Test when no credentials file provided."""
        result = credentials_checker.check_gcp_credentials(None)
        
        assert result["provider"] == "gcp"
        assert result["status"] == "missing"
        assert result["config_present"] == False
    
    def test_check_gcp_credentials_file_not_found(self):
        """Test when credentials file doesn't exist."""
        result = credentials_checker.check_gcp_credentials("/nonexistent/path.json")
        
        assert result["status"] == "invalid"
        assert "not found" in result["message"].lower()
        assert result["config_present"] == False
    
    @patch("os.path.isfile")
    @patch("google.oauth2.service_account.Credentials.from_service_account_file")
    @patch("google.cloud.billing_v1.CloudCatalogClient")
    def test_check_gcp_credentials_valid(self, mock_client_class, mock_from_file, mock_isfile):
        """Test valid GCP credentials."""
        mock_isfile.return_value = True
        
        # Mock credentials
        mock_creds = MagicMock()
        mock_creds.project_id = "my-project"
        mock_creds.service_account_email = "sa@my-project.iam.gserviceaccount.com"
        mock_from_file.return_value = mock_creds
        
        # Mock billing client
        mock_client = MagicMock()
        mock_service = MagicMock()
        mock_service.display_name = "Compute Engine"
        mock_client.list_services.return_value = iter([mock_service])
        mock_client_class.return_value = mock_client
        
        result = credentials_checker.check_gcp_credentials("/config/gcp_credentials.json")
        
        assert result["status"] == "valid"
        assert result["config_present"] == True
        assert result["credentials_valid"] == True
        assert result["can_fetch_pricing"] == True
        assert result["identity"]["project_id"] == "my-project"
    
    @patch("os.path.isfile")
    @patch("google.oauth2.service_account.Credentials.from_service_account_file")
    def test_check_gcp_credentials_invalid_file(self, mock_from_file, mock_isfile):
        """Test invalid GCP credentials file."""
        mock_isfile.return_value = True
        mock_from_file.side_effect = Exception("Invalid JSON")
        
        result = credentials_checker.check_gcp_credentials("/config/bad_credentials.json")
        
        assert result["status"] == "invalid"
        assert "Invalid JSON" in result["message"]


# =============================================================================
# Azure Credential Tests
# =============================================================================

class TestAzureCredentials:
    """Tests for Azure credential validation."""
    
    def test_check_azure_credentials_missing(self):
        """Test when no credentials provided."""
        result = credentials_checker.check_azure_credentials(None)
        
        assert result["provider"] == "azure"
        assert result["status"] == "missing"
        assert result["can_fetch_pricing"] == True  # Public API
    
    def test_check_azure_credentials_missing_fields(self):
        """Test when required fields are missing."""
        credentials = {}
        
        result = credentials_checker.check_azure_credentials(credentials)
        
        assert result["status"] == "invalid"
        assert "Missing required fields" in result["message"]
        assert result["can_fetch_pricing"] == True  # Still possible - public API
    
    def test_check_azure_credentials_valid(self):
        """Test valid Azure credentials."""
        credentials = {
            "azure_subscription_id": "12345678-1234-1234-1234-123456789abc",
            "azure_region": "westeurope"
        }
        
        result = credentials_checker.check_azure_credentials(credentials)
        
        assert result["status"] == "valid"
        assert result["config_present"] == True
        assert result["credentials_valid"] == True
        assert result["can_fetch_pricing"] == True
        assert "note" in result
    
    def test_check_azure_credentials_invalid_uuid(self):
        """Test Azure credentials with invalid subscription ID format."""
        credentials = {
            "azure_subscription_id": "not-a-valid-uuid",
            "azure_region": "westeurope"
        }
        
        result = credentials_checker.check_azure_credentials(credentials)
        
        assert result["status"] == "invalid"
        assert "UUID" in result["message"]


# =============================================================================
# Response Structure Tests
# =============================================================================

class TestResponseStructure:
    """Tests for consistent response structure."""
    
    def test_aws_response_has_required_fields(self):
        """Test AWS response has all required fields."""
        result = credentials_checker.check_aws_credentials(None)
        
        required_fields = ["provider", "status", "message", "config_present", 
                          "credentials_valid", "can_fetch_pricing", "identity"]
        for field in required_fields:
            assert field in result
    
    def test_gcp_response_has_required_fields(self):
        """Test GCP response has all required fields."""
        result = credentials_checker.check_gcp_credentials(None)
        
        required_fields = ["provider", "status", "message", "config_present",
                          "credentials_valid", "can_fetch_pricing", "identity"]
        for field in required_fields:
            assert field in result
    
    def test_azure_response_has_required_fields(self):
        """Test Azure response has all required fields."""
        result = credentials_checker.check_azure_credentials(None)
        
        required_fields = ["provider", "status", "message", "config_present",
                          "credentials_valid", "can_fetch_pricing", "identity"]
        for field in required_fields:
            assert field in result
    
    def test_status_values_are_valid(self):
        """Test that status values are from the expected set."""
        valid_statuses = {"valid", "invalid", "error", "missing"}
        
        # AWS
        result = credentials_checker.check_aws_credentials(None)
        assert result["status"] in valid_statuses
        
        # GCP
        result = credentials_checker.check_gcp_credentials(None)
        assert result["status"] in valid_statuses
        
        # Azure
        result = credentials_checker.check_azure_credentials(None)
        assert result["status"] in valid_statuses
