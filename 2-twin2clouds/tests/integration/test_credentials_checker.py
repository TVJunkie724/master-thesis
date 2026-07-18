"""
Unit tests for the credentials checker module.
"""
from unittest.mock import MagicMock, patch

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
        assert not result["config_present"]
        assert not result["credentials_valid"]
    
    def test_check_aws_credentials_missing_fields(self):
        """Test when required fields are missing."""
        credentials = {"aws_access_key_id": "test"}  # Missing secret
        
        result = credentials_checker.check_aws_credentials(credentials)
        
        assert result["status"] == "invalid"
        assert "Missing required fields" in result["message"]
        assert not result["config_present"]
    
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
        mock_pricing.get_attribute_values.return_value = {"AttributeValues": []}
        mock_pricing.get_products.return_value = {"PriceList": []}
        mock_twinmaker = MagicMock()
        mock_twinmaker.get_pricing_plan.return_value = {
            "currentPricingPlan": {
                "pricingMode": "STANDARD",
                "billableEntityCount": 0,
            }
        }
        
        # Configure session mock
        mock_session = MagicMock()
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "pricing": mock_pricing,
            "iottwinmaker": mock_twinmaker,
        }.get(service, MagicMock())
        
        mock_session_class.return_value = mock_session
        
        credentials = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_region": "eu-central-1"
        }
        
        result = credentials_checker.check_aws_credentials(credentials)
        
        assert result["status"] == "valid"
        assert result["config_present"]
        assert result["credentials_valid"]
        assert result["can_fetch_pricing"]
        assert result["identity"]["account"] == "123456789012"
        mock_pricing.describe_services.assert_called_once_with(MaxResults=1)
        mock_pricing.get_attribute_values.assert_called_once_with(
            ServiceCode="AmazonEC2",
            AttributeName="location",
            MaxResults=1,
        )
        mock_pricing.get_products.assert_called_once_with(
            ServiceCode="AmazonEC2",
            MaxResults=1,
        )

    @patch("boto3.Session")
    def test_check_aws_credentials_forwards_session_token(self, mock_session_class):
        """Temporary AWS credentials must forward the STS session token."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:sts::123456789012:assumed-role/test/session",
            "UserId": "AIDAEXAMPLE"
        }
        mock_pricing = MagicMock()
        mock_pricing.describe_services.return_value = {"Services": []}
        mock_pricing.get_attribute_values.return_value = {"AttributeValues": []}
        mock_pricing.get_products.return_value = {"PriceList": []}
        mock_twinmaker = MagicMock()
        mock_twinmaker.get_pricing_plan.return_value = {
            "currentPricingPlan": {
                "pricingMode": "STANDARD",
                "billableEntityCount": 0,
            }
        }

        mock_session = MagicMock()
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "pricing": mock_pricing,
            "iottwinmaker": mock_twinmaker,
        }.get(service, MagicMock())
        mock_session_class.return_value = mock_session

        credentials = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_session_token": "temporary-session-token",
            "aws_region": "eu-central-1"
        }

        result = credentials_checker.check_aws_credentials(credentials)

        assert result["status"] == "valid"
        mock_session_class.assert_called_once_with(
            aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            aws_session_token="temporary-session-token",
            region_name="eu-central-1",
        )

    @patch("boto3.Session")
    def test_check_aws_credentials_region_is_required_for_twinmaker(
        self,
        mock_session_class,
    ):
        """TwinMaker pricing is regional, so the target region is mandatory."""
        result = credentials_checker.check_aws_credentials(
            {
                "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            }
        )

        assert result["status"] == "invalid"
        assert "aws_region" in result["message"]
        mock_session_class.assert_not_called()
    
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
        assert result["error_code"] == "AWS_TWINMAKER_PLAN_AUTHENTICATION_FAILED"
        assert not result["credentials_valid"]

    @patch("boto3.Session")
    def test_check_aws_credentials_requires_twinmaker_plan_permission(
        self,
        mock_session_class,
    ):
        from botocore.exceptions import ClientError

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
        }
        mock_twinmaker = MagicMock()
        mock_twinmaker.get_pricing_plan.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "Access denied",
                }
            },
            "GetPricingPlan",
        )
        mock_session = MagicMock()
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "iottwinmaker": mock_twinmaker,
        }.get(service, MagicMock())
        mock_session_class.return_value = mock_session

        result = credentials_checker.check_aws_credentials(
            {
                "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
                "aws_secret_access_key": (
                    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                ),
                "aws_region": "eu-central-1",
            }
        )

        assert result["status"] == "invalid"
        assert result["credentials_valid"] is True
        assert result["can_fetch_pricing"] is False
        assert result["error_code"] == "AWS_TWINMAKER_PLAN_PERMISSION_DENIED"
    
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
        mock_twinmaker = MagicMock()
        mock_twinmaker.get_pricing_plan.return_value = {
            "currentPricingPlan": {
                "pricingMode": "STANDARD",
                "billableEntityCount": 0,
            }
        }
        
        mock_session = MagicMock()
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "pricing": mock_pricing,
            "iottwinmaker": mock_twinmaker,
        }.get(service, MagicMock())
        
        mock_session_class.return_value = mock_session
        
        credentials = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_region": "eu-central-1"
        }
        
        result = credentials_checker.check_aws_credentials(credentials)
        
        assert result["status"] == "invalid"
        assert result["credentials_valid"]  # Auth succeeded
        assert not result["can_fetch_pricing"]  # But pricing failed
        assert "pricing" in result["message"].lower()

    @patch("boto3.Session")
    def test_check_aws_credentials_missing_get_products_permission(self, mock_session_class):
        """DescribeServices alone is not enough for the pricing fetcher."""
        from botocore.exceptions import ClientError

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
            "UserId": "AIDAEXAMPLE"
        }

        mock_pricing = MagicMock()
        mock_pricing.describe_services.return_value = {"Services": []}
        mock_pricing.get_attribute_values.return_value = {"AttributeValues": []}
        mock_pricing.get_products.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access Denied"}},
            "GetProducts"
        )
        mock_twinmaker = MagicMock()
        mock_twinmaker.get_pricing_plan.return_value = {
            "currentPricingPlan": {
                "pricingMode": "STANDARD",
                "billableEntityCount": 0,
            }
        }

        mock_session = MagicMock()
        mock_session.client.side_effect = lambda service, **kwargs: {
            "sts": mock_sts,
            "pricing": mock_pricing,
            "iottwinmaker": mock_twinmaker,
        }.get(service, MagicMock())
        mock_session_class.return_value = mock_session

        credentials = {
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "aws_region": "eu-central-1"
        }

        result = credentials_checker.check_aws_credentials(credentials)

        assert result["status"] == "invalid"
        assert result["credentials_valid"]
        assert not result["can_fetch_pricing"]
        assert "GetProducts" in result["message"]


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
        assert not result["config_present"]
    
    def test_check_gcp_credentials_file_not_found(self):
        """Test when credentials file doesn't exist."""
        result = credentials_checker.check_gcp_credentials("/nonexistent/path.json")
        
        assert result["status"] == "invalid"
        assert "not found" in result["message"].lower()
        # Note: config_present is True because we received input (just not a valid file)
        assert result["config_present"]
    
    @patch("backend.gcp_utils.parse_gcp_service_account")
    @patch("google.cloud.billing_v1.CloudCatalogClient")
    def test_check_gcp_credentials_valid(self, mock_client_class, mock_parse):
        """Test valid GCP credentials."""
        # Mock the shared utility
        mock_creds = MagicMock()
        mock_parse.return_value = (
            {"type": "service_account", "project_id": "my-project", "client_email": "sa@my-project.iam.gserviceaccount.com"},
            {"project_id": "my-project", "client_email": "sa@my-project.iam.gserviceaccount.com", "private_key_id": "abc123..."},
            mock_creds
        )
        
        # Mock billing client
        mock_client = MagicMock()
        mock_service = MagicMock()
        mock_service.display_name = "Compute Engine"
        mock_client.list_services.return_value = iter([mock_service])
        mock_client_class.return_value = mock_client
        
        result = credentials_checker.check_gcp_credentials("/config/gcp_credentials.json")
        
        assert result["status"] == "valid"
        assert result["config_present"]
        assert result["credentials_valid"]
        assert result["can_fetch_pricing"]
        assert result["identity"]["project_id"] == "my-project"
    
    @patch("backend.gcp_utils.parse_gcp_service_account")
    def test_check_gcp_credentials_invalid_file(self, mock_parse):
        """Test invalid GCP credentials file."""
        mock_parse.side_effect = ValueError("Invalid JSON in service account file")
        
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
        assert result["can_fetch_pricing"]  # Public API
    
    def test_check_azure_credentials_missing_fields(self):
        """Test when required fields are missing."""
        credentials = {}
        
        result = credentials_checker.check_azure_credentials(credentials)
        
        assert result["status"] == "invalid"
        assert "Missing required fields" in result["message"]
        assert result["can_fetch_pricing"]  # Still possible - public API
    
    def test_check_azure_credentials_valid(self):
        """Test valid Azure credentials."""
        credentials = {
            "azure_subscription_id": "12345678-1234-1234-1234-123456789abc",
            "azure_region": "westeurope"
        }
        
        result = credentials_checker.check_azure_credentials(credentials)
        
        assert result["status"] == "valid"
        assert result["config_present"]
        assert result["credentials_valid"]
        assert result["can_fetch_pricing"]
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
