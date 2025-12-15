"""
Layer 0 (Glue) Component Edge Case Tests.

Tests for multi-cloud receiver components deployed by L0 adapter:
- Ingestion (L1→L2)
- Hot Writer (L2→L3)
- Cold Writer (L3 Hot→L3 Cold)
- Archive Writer (L3 Cold→L3 Archive)
- Hot Reader Function URLs (L3→L4)

Focus areas:
1. Missing configuration (fail-fast behavior)
2. Edge cases for inter-cloud tokens
3. Provider boundary detection
4. Function URL creation/destruction
"""

import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError


# ==========================================
# L2 Ingestion Edge Case Tests
# ==========================================

class TestIngestionEdgeCases:
    """Edge case tests for L2 Ingestion (L1→L2 boundary)."""
    
    def test_create_ingestion_iam_role_creates_role(self):
        """create_ingestion_iam_role() should create role and attach basic policy."""
        from src.providers.aws.layers.layer_0_glue import create_ingestion_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_iam_role.return_value = "test-ingestion-role"
        mock_provider.clients = {"iam": MagicMock()}
        
        create_ingestion_iam_role(mock_provider)
        
        mock_provider.clients["iam"].create_role.assert_called_once()
        mock_provider.clients["iam"].attach_role_policy.assert_called_once()
    
    def test_create_ingestion_lambda_missing_token_fails(self):
        """create_ingestion_lambda_function() should fail when expected_token is missing."""
        from src.providers.aws.layers.layer_0_glue import create_ingestion_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_lambda_function.return_value = "test-ingestion"
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        mock_config = MagicMock()
        mock_config.inter_cloud = {}  # Missing expected_token
        
        with pytest.raises(ValueError, match="expected_token not set"):
            create_ingestion_lambda_function(mock_provider, mock_config, "/mock/path")
    
    def test_create_ingestion_lambda_empty_token_fails(self):
        """create_ingestion_lambda_function() should fail when expected_token is empty."""
        from src.providers.aws.layers.layer_0_glue import create_ingestion_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_lambda_function.return_value = "test-ingestion"
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        mock_config = MagicMock()
        mock_config.inter_cloud = {"expected_token": ""}  # Empty token
        
        with pytest.raises(ValueError, match="expected_token not set"):
            create_ingestion_lambda_function(mock_provider, mock_config, "/mock/path")
    
    def test_destroy_ingestion_role_handles_not_found(self):
        """destroy_ingestion_iam_role() should handle NoSuchEntity gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_ingestion_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        
        # Simulate role not found
        mock_provider.clients["iam"].list_attached_role_policies.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "ListAttachedRolePolicies"
        )
        
        # Should not raise
        destroy_ingestion_iam_role(mock_provider)
    
    def test_destroy_ingestion_lambda_handles_not_found(self):
        """destroy_ingestion_lambda_function() should handle ResourceNotFoundException gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_ingestion_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_lambda_function.return_value = "test-ingestion"
        mock_provider.clients = {"lambda": MagicMock()}
        
        # Simulate function not found
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Function not found"}},
            "DeleteFunctionUrlConfig"
        )
        mock_provider.clients["lambda"].delete_function.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Function not found"}},
            "DeleteFunction"
        )
        
        # Should not raise
        destroy_ingestion_lambda_function(mock_provider)


# ==========================================
# L3 Hot Writer Edge Case Tests
# ==========================================

class TestHotWriterEdgeCases:
    """Edge case tests for L3 Hot Writer (L2→L3 boundary)."""
    
    def test_create_hot_writer_iam_role_creates_role_with_dynamodb_policy(self):
        """create_hot_writer_iam_role() should create role with DynamoDB access."""
        from src.providers.aws.layers.layer_0_glue import create_hot_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_writer_iam_role.return_value = "test-hot-writer-role"
        mock_provider.naming.hot_dynamodb_table.return_value = "test-table"
        mock_provider.clients = {"iam": MagicMock()}
        
        create_hot_writer_iam_role(mock_provider)
        
        mock_provider.clients["iam"].create_role.assert_called_once()
        mock_provider.clients["iam"].attach_role_policy.assert_called_once()
        mock_provider.clients["iam"].put_role_policy.assert_called_once()
        
        # Verify DynamoDB policy was created
        call_args = mock_provider.clients["iam"].put_role_policy.call_args
        assert "DynamoDBWriteAccess" in str(call_args)
    
    def test_create_hot_writer_lambda_missing_token_fails(self):
        """create_hot_writer_lambda_function() should fail when expected_token is missing."""
        from src.providers.aws.layers.layer_0_glue import create_hot_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_writer_lambda_function.return_value = "test-hot-writer"
        mock_provider.naming.hot_writer_iam_role.return_value = "test-role"
        mock_provider.naming.hot_dynamodb_table.return_value = "test-table"
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        
        mock_config = MagicMock()
        mock_config.inter_cloud = {}  # Missing expected_token
        
        with pytest.raises(ValueError, match="expected_token not set"):
            create_hot_writer_lambda_function(mock_provider, mock_config, "/mock/path")
    
    def test_destroy_hot_writer_role_handles_not_found(self):
        """destroy_hot_writer_iam_role() should handle NoSuchEntity gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_hot_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_writer_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        
        # Simulate role not found
        mock_provider.clients["iam"].list_attached_role_policies.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "ListAttachedRolePolicies"
        )
        
        # Should not raise
        destroy_hot_writer_iam_role(mock_provider)
    
    def test_destroy_hot_writer_lambda_handles_not_found(self):
        """destroy_hot_writer_lambda_function() should handle ResourceNotFoundException gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_hot_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_writer_lambda_function.return_value = "test-hot-writer"
        mock_provider.clients = {"lambda": MagicMock()}
        
        # Simulate function not found
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Function not found"}},
            "DeleteFunctionUrlConfig"
        )
        mock_provider.clients["lambda"].delete_function.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Function not found"}},
            "DeleteFunction"
        )
        
        # Should not raise
        destroy_hot_writer_lambda_function(mock_provider)


# ==========================================
# L3 Cold Writer Edge Case Tests
# ==========================================

class TestColdWriterEdgeCases:
    """Edge case tests for L3 Cold Writer (L3 Hot→L3 Cold boundary)."""
    
    def test_create_cold_writer_iam_role_creates_role_with_s3_policy(self):
        """create_cold_writer_iam_role() should create role with S3 access."""
        from src.providers.aws.layers.layer_0_glue import create_cold_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.cold_writer_iam_role.return_value = "test-cold-writer-role"
        mock_provider.naming.cold_s3_bucket.return_value = "test-bucket"
        mock_provider.clients = {"iam": MagicMock()}
        
        create_cold_writer_iam_role(mock_provider)
        
        mock_provider.clients["iam"].create_role.assert_called_once()
        mock_provider.clients["iam"].attach_role_policy.assert_called_once()
        mock_provider.clients["iam"].put_role_policy.assert_called_once()
        
        # Verify S3 policy was created
        call_args = mock_provider.clients["iam"].put_role_policy.call_args
        assert "S3ColdWriteAccess" in str(call_args)
    
    def test_destroy_cold_writer_role_handles_not_found(self):
        """destroy_cold_writer_iam_role() should handle NoSuchEntity gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_cold_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.cold_writer_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        
        mock_provider.clients["iam"].list_attached_role_policies.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "ListAttachedRolePolicies"
        )
        
        # Should not raise
        destroy_cold_writer_iam_role(mock_provider)
    
    def test_destroy_cold_writer_lambda_handles_not_found(self):
        """destroy_cold_writer_lambda_function() should handle ResourceNotFoundException gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_cold_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.cold_writer_lambda_function.return_value = "test-cold-writer"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Function not found"}},
            "DeleteFunctionUrlConfig"
        )
        mock_provider.clients["lambda"].delete_function.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Function not found"}},
            "DeleteFunction"
        )
        
        # Should not raise
        destroy_cold_writer_lambda_function(mock_provider)


# ==========================================
# L3 Archive Writer Edge Case Tests
# ==========================================

class TestArchiveWriterEdgeCases:
    """Edge case tests for L3 Archive Writer (L3 Cold→L3 Archive boundary)."""
    
    def test_create_archive_writer_iam_role_creates_role_with_s3_policy(self):
        """create_archive_writer_iam_role() should create role with S3 access."""
        from src.providers.aws.layers.layer_0_glue import create_archive_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.archive_writer_iam_role.return_value = "test-archive-writer-role"
        mock_provider.naming.archive_s3_bucket.return_value = "test-bucket"
        mock_provider.clients = {"iam": MagicMock()}
        
        create_archive_writer_iam_role(mock_provider)
        
        mock_provider.clients["iam"].create_role.assert_called_once()
        mock_provider.clients["iam"].attach_role_policy.assert_called_once()
        mock_provider.clients["iam"].put_role_policy.assert_called_once()
        
        # Verify S3 policy was created
        call_args = mock_provider.clients["iam"].put_role_policy.call_args
        assert "S3ArchiveWriteAccess" in str(call_args)
    
    def test_destroy_archive_writer_role_handles_not_found(self):
        """destroy_archive_writer_iam_role() should handle NoSuchEntity gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_archive_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.archive_writer_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        
        mock_provider.clients["iam"].list_attached_role_policies.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "ListAttachedRolePolicies"
        )
        
        # Should not raise
        destroy_archive_writer_iam_role(mock_provider)
    
    def test_destroy_archive_writer_lambda_handles_not_found(self):
        """destroy_archive_writer_lambda_function() should handle ResourceNotFoundException gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_archive_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.archive_writer_lambda_function.return_value = "test-archive-writer"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Function not found"}},
            "DeleteFunctionUrlConfig"
        )
        mock_provider.clients["lambda"].delete_function.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Function not found"}},
            "DeleteFunction"
        )
        
        # Should not raise
        destroy_archive_writer_lambda_function(mock_provider)


# ==========================================
# L0 Adapter Provider Boundary Tests
# ==========================================

class TestL0ProviderBoundaryDetection:
    """Tests for L0 adapter provider boundary detection."""
    
    def test_deploy_l0_same_cloud_skips_ingestion(self):
        """deploy_l0() should NOT deploy Ingestion when L1 == L2."""
        from src.providers.aws.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",  # Same as L1
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }
        mock_context.project_path.parent.parent = "/mock/path"
        
        mock_provider = MagicMock()
        
        deploy_l0(mock_context, mock_provider)
        
        # Ingestion should NOT have been deployed
        mock_provider.clients["iam"].create_role.assert_not_called()
    
    def test_deploy_l0_different_l1_l2_deploys_ingestion(self):
        """deploy_l0() should deploy Ingestion when L1 ≠ L2."""
        from src.providers.aws.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.hot_storage_size_in_days = 7
        mock_context.config.cold_storage_size_in_days = 30
        mock_context.config.mode = "dev"
        mock_context.config.iot_devices = []
        mock_context.config.events = []
        mock_context.config.providers = {
            "layer_1_provider": "azure",  # Different!
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }
        mock_context.project_path.parent.parent = "/mock/path"
        mock_context.config.inter_cloud = {"expected_token": "test-token"}
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_iam_role.return_value = "test-ingestion-role"
        mock_provider.naming.ingestion_lambda_function.return_value = "test-ingestion"
        mock_provider.naming.persister_lambda_function.return_value = "test-persister"
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["iam"].get_role.return_value = {"Role": {"Arn": "arn:aws:iam::123:role/test"}}
        mock_provider.clients["lambda"].create_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        with patch("src.providers.aws.layers.l0_adapter._check_setup_deployed"):
            with patch("src.core.config_loader.save_inter_cloud_connection"):
                with patch("src.util.compile_lambda_function", return_value=b"mock-zip"):
                    deploy_l0(mock_context, mock_provider)
        
        # Ingestion should have been deployed
        mock_provider.clients["iam"].create_role.assert_called()
    
    def test_deploy_l0_missing_layer_1_provider_fails(self):
        """deploy_l0() should fail when layer_1_provider is missing."""
        from src.providers.aws.layers.l0_adapter import deploy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            # Missing: "layer_1_provider"
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }
        
        mock_provider = MagicMock()
        
        with pytest.raises(KeyError, match="layer_1_provider"):
            deploy_l0(mock_context, mock_provider)
    
    def test_destroy_l0_missing_provider_fails(self):
        """destroy_l0() should fail when provider config is missing."""
        from src.providers.aws.layers.l0_adapter import destroy_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {}  # Empty
        
        mock_provider = MagicMock()
        
        with pytest.raises(KeyError):
            destroy_l0(mock_context, mock_provider)


# ==========================================
# L3→L4 Hot Reader Function URL Edge Case Tests
# ==========================================

class TestHotReaderFunctionUrlEdgeCases:
    """Edge case tests for Hot Reader Function URLs (L3→L4 boundary)."""
    
    def test_create_hot_reader_url_updates_lambda_with_token(self):
        """create_hot_reader_function_url() should update Lambda with INTER_CLOUD_TOKEN."""
        from src.providers.aws.layers.layer_0_glue import create_hot_reader_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-hot-reader"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_configuration.return_value = {
            "Environment": {"Variables": {"EXISTING_VAR": "value"}}
        }
        mock_provider.clients["lambda"].create_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        result = create_hot_reader_function_url(mock_provider, "test-token")
        
        # Verify Lambda was updated with token
        mock_provider.clients["lambda"].update_function_configuration.assert_called_once()
        call_args = mock_provider.clients["lambda"].update_function_configuration.call_args
        env_vars = call_args[1]["Environment"]["Variables"]
        assert env_vars["INTER_CLOUD_TOKEN"] == "test-token"
        assert env_vars["EXISTING_VAR"] == "value"
        
        # Verify URL was created
        assert "lambda-url" in result
    
    def test_create_hot_reader_last_entry_url_updates_lambda_with_token(self):
        """create_hot_reader_last_entry_function_url() should update Lambda with token."""
        from src.providers.aws.layers.layer_0_glue import create_hot_reader_last_entry_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_last_entry_lambda_function.return_value = "test-reader-last"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_configuration.return_value = {
            "Environment": {"Variables": {}}
        }
        mock_provider.clients["lambda"].create_function_url_config.return_value = {
            "FunctionUrl": "https://test2.lambda-url.us-east-1.on.aws/"
        }
        
        result = create_hot_reader_last_entry_function_url(mock_provider, "another-token")
        
        # Verify token was set
        call_args = mock_provider.clients["lambda"].update_function_configuration.call_args
        assert call_args[1]["Environment"]["Variables"]["INTER_CLOUD_TOKEN"] == "another-token"
        assert "lambda-url" in result
    
    def test_destroy_hot_reader_url_handles_not_found(self):
        """destroy_hot_reader_function_url() should handle ResourceNotFoundException gracefully."""
        from src.providers.aws.layers.layer_0_glue import destroy_hot_reader_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-reader"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "URL not found"}},
            "DeleteFunctionUrlConfig"
        )
        
        # Should not raise
        destroy_hot_reader_function_url(mock_provider)
    
    def test_destroy_hot_reader_last_entry_url_handles_not_found(self):
        """destroy_hot_reader_last_entry_function_url() should handle ResourceNotFoundException."""
        from src.providers.aws.layers.layer_0_glue import destroy_hot_reader_last_entry_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_last_entry_lambda_function.return_value = "test-last-entry"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "URL not found"}},
            "DeleteFunctionUrlConfig"
        )
        
        # Should not raise
        destroy_hot_reader_last_entry_function_url(mock_provider)
    
    def test_create_hot_reader_url_adds_public_permission(self):
        """create_hot_reader_function_url() should add public access permission."""
        from src.providers.aws.layers.layer_0_glue import create_hot_reader_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-reader"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_configuration.return_value = {
            "Environment": {"Variables": {}}
        }
        mock_provider.clients["lambda"].create_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        create_hot_reader_function_url(mock_provider, "token")
        
        # Verify public permission was added
        mock_provider.clients["lambda"].add_permission.assert_called_once()
        call_args = mock_provider.clients["lambda"].add_permission.call_args
        assert call_args[1]["Principal"] == "*"
        assert call_args[1]["StatementId"] == "FunctionURLPublicAccess"


# ==========================================
# Check Function Edge Case Tests
# ==========================================

class TestIngestionCheckFunctions:
    """Edge case tests for Ingestion check functions."""
    
    def test_check_ingestion_iam_role_exists_returns_true(self):
        """check_ingestion_iam_role() should return True when role exists."""
        from src.providers.aws.layers.layer_0_glue import check_ingestion_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.region = "us-east-1"
        mock_provider.clients = {"iam": MagicMock()}
        
        result = check_ingestion_iam_role(mock_provider)
        
        assert result is True
        mock_provider.clients["iam"].get_role.assert_called_once()
    
    def test_check_ingestion_iam_role_missing_returns_false(self):
        """check_ingestion_iam_role() should return False when role doesn't exist."""
        from src.providers.aws.layers.layer_0_glue import check_ingestion_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        mock_provider.clients["iam"].get_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "GetRole"
        )
        
        result = check_ingestion_iam_role(mock_provider)
        
        assert result is False
    
    def test_check_ingestion_lambda_exists_with_url_returns_true(self):
        """check_ingestion_lambda_function() should return True with Function URL."""
        from src.providers.aws.layers.layer_0_glue import check_ingestion_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_lambda_function.return_value = "test-func"
        mock_provider.region = "us-east-1"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        result = check_ingestion_lambda_function(mock_provider)
        
        assert result is True
    
    def test_check_ingestion_lambda_missing_returns_false(self):
        """check_ingestion_lambda_function() should return False when missing."""
        from src.providers.aws.layers.layer_0_glue import check_ingestion_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_lambda_function.return_value = "test-func"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetFunction"
        )
        
        result = check_ingestion_lambda_function(mock_provider)
        
        assert result is False


class TestHotWriterCheckFunctions:
    """Edge case tests for Hot Writer check functions."""
    
    def test_check_hot_writer_iam_role_exists_returns_true(self):
        """check_hot_writer_iam_role() should return True when role exists."""
        from src.providers.aws.layers.layer_0_glue import check_hot_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_writer_iam_role.return_value = "test-role"
        mock_provider.region = "us-east-1"
        mock_provider.clients = {"iam": MagicMock()}
        
        result = check_hot_writer_iam_role(mock_provider)
        
        assert result is True
    
    def test_check_hot_writer_iam_role_missing_returns_false(self):
        """check_hot_writer_iam_role() should return False when missing."""
        from src.providers.aws.layers.layer_0_glue import check_hot_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_writer_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        mock_provider.clients["iam"].get_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "GetRole"
        )
        
        result = check_hot_writer_iam_role(mock_provider)
        
        assert result is False
    
    def test_check_hot_writer_lambda_exists_returns_true(self):
        """check_hot_writer_lambda_function() should return True when exists."""
        from src.providers.aws.layers.layer_0_glue import check_hot_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_writer_lambda_function.return_value = "test-func"
        mock_provider.region = "us-east-1"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        result = check_hot_writer_lambda_function(mock_provider)
        
        assert result is True


class TestColdWriterCheckFunctions:
    """Edge case tests for Cold Writer check functions."""
    
    def test_check_cold_writer_iam_role_exists_returns_true(self):
        """check_cold_writer_iam_role() should return True when role exists."""
        from src.providers.aws.layers.layer_0_glue import check_cold_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.cold_writer_iam_role.return_value = "test-role"
        mock_provider.region = "us-east-1"
        mock_provider.clients = {"iam": MagicMock()}
        
        result = check_cold_writer_iam_role(mock_provider)
        
        assert result is True
    
    def test_check_cold_writer_iam_role_missing_returns_false(self):
        """check_cold_writer_iam_role() should return False when missing."""
        from src.providers.aws.layers.layer_0_glue import check_cold_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.cold_writer_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        mock_provider.clients["iam"].get_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "GetRole"
        )
        
        result = check_cold_writer_iam_role(mock_provider)
        
        assert result is False
    
    def test_check_cold_writer_lambda_exists_returns_true(self):
        """check_cold_writer_lambda_function() should return True when exists."""
        from src.providers.aws.layers.layer_0_glue import check_cold_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.cold_writer_lambda_function.return_value = "test-func"
        mock_provider.region = "us-east-1"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        result = check_cold_writer_lambda_function(mock_provider)
        
        assert result is True


class TestArchiveWriterCheckFunctions:
    """Edge case tests for Archive Writer check functions."""
    
    def test_check_archive_writer_iam_role_exists_returns_true(self):
        """check_archive_writer_iam_role() should return True when role exists."""
        from src.providers.aws.layers.layer_0_glue import check_archive_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.archive_writer_iam_role.return_value = "test-role"
        mock_provider.region = "us-east-1"
        mock_provider.clients = {"iam": MagicMock()}
        
        result = check_archive_writer_iam_role(mock_provider)
        
        assert result is True
    
    def test_check_archive_writer_iam_role_missing_returns_false(self):
        """check_archive_writer_iam_role() should return False when missing."""
        from src.providers.aws.layers.layer_0_glue import check_archive_writer_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.archive_writer_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        mock_provider.clients["iam"].get_role.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "GetRole"
        )
        
        result = check_archive_writer_iam_role(mock_provider)
        
        assert result is False
    
    def test_check_archive_writer_lambda_exists_returns_true(self):
        """check_archive_writer_lambda_function() should return True when exists."""
        from src.providers.aws.layers.layer_0_glue import check_archive_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.archive_writer_lambda_function.return_value = "test-func"
        mock_provider.region = "us-east-1"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        result = check_archive_writer_lambda_function(mock_provider)
        
        assert result is True


class TestHotReaderUrlCheckFunctions:
    """Edge case tests for Hot Reader URL check functions."""
    
    def test_check_hot_reader_function_url_exists_returns_true(self):
        """check_hot_reader_function_url() should return True when URL exists."""
        from src.providers.aws.layers.layer_0_glue import check_hot_reader_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-reader"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        result = check_hot_reader_function_url(mock_provider)
        
        assert result is True
    
    def test_check_hot_reader_function_url_missing_returns_false(self):
        """check_hot_reader_function_url() should return False when URL missing."""
        from src.providers.aws.layers.layer_0_glue import check_hot_reader_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-reader"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetFunctionUrlConfig"
        )
        
        result = check_hot_reader_function_url(mock_provider)
        
        assert result is False
    
    def test_check_hot_reader_last_entry_url_exists_returns_true(self):
        """check_hot_reader_last_entry_function_url() should return True when URL exists."""
        from src.providers.aws.layers.layer_0_glue import check_hot_reader_last_entry_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_last_entry_lambda_function.return_value = "test-last"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        result = check_hot_reader_last_entry_function_url(mock_provider)
        
        assert result is True
    
    def test_check_hot_reader_last_entry_url_missing_returns_false(self):
        """check_hot_reader_last_entry_function_url() should return False when URL missing."""
        from src.providers.aws.layers.layer_0_glue import check_hot_reader_last_entry_function_url
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_last_entry_lambda_function.return_value = "test-last"
        mock_provider.clients = {"lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "GetFunctionUrlConfig"
        )
        
        result = check_hot_reader_last_entry_function_url(mock_provider)
        
        assert result is False


class TestInfoL0AdapterFunction:
    """Edge case tests for info_l0 adapter function."""
    
    def test_info_l0_no_boundaries_logs_no_components_needed(self):
        """info_l0() should log no components needed when all same cloud."""
        from src.providers.aws.layers.l0_adapter import info_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }
        
        mock_provider = MagicMock()
        
        # Should not raise
        info_l0(mock_context, mock_provider)
    
    def test_info_l0_l1_l2_boundary_checks_ingestion(self):
        """info_l0() should check Ingestion when L1 != L2."""
        from src.providers.aws.layers.l0_adapter import info_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "azure",  # Different!
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }
        
        mock_provider = MagicMock()
        mock_provider.region = "us-east-1"
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.naming.ingestion_lambda_function.return_value = "test-func"
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        # Should not raise and should call check functions
        info_l0(mock_context, mock_provider)
        
        mock_provider.clients["iam"].get_role.assert_called()
        mock_provider.clients["lambda"].get_function.assert_called()
    
    def test_info_l0_l3_l4_boundary_checks_hot_reader_urls(self):
        """info_l0() should check Hot Reader URLs when L3 != L4."""
        from src.providers.aws.layers.l0_adapter import info_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "azure"  # Different!
        }
        
        mock_provider = MagicMock()
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-reader"
        mock_provider.naming.hot_reader_last_entry_lambda_function.return_value = "test-last"
        mock_provider.clients = {"lambda": MagicMock()}
        
        # Should not raise and should call check functions
        info_l0(mock_context, mock_provider)
        
        mock_provider.clients["lambda"].get_function_url_config.assert_called()
    
    def test_info_l0_all_boundaries_checks_all_components(self):
        """info_l0() should check all components when all boundaries differ."""
        from src.providers.aws.layers.l0_adapter import info_l0
        
        mock_context = MagicMock()
        mock_context.config.digital_twin_name = "test-twin"
        mock_context.config.providers = {
            "layer_1_provider": "azure",  # Different from L2
            "layer_2_provider": "gcp",    # Different from L3
            "layer_3_hot_provider": "aws",
            "layer_3_cold_provider": "azure",  # Different from Hot
            "layer_3_archive_provider": "gcp",  # Different from Cold
            "layer_4_provider": "azure"   # Different from L3 Hot
        }
        
        mock_provider = MagicMock()
        mock_provider.region = "us-east-1"
        mock_provider.naming.ingestion_iam_role.return_value = "test-ingestion-role"
        mock_provider.naming.ingestion_lambda_function.return_value = "test-ingestion"
        mock_provider.naming.hot_writer_iam_role.return_value = "test-hot-writer-role"
        mock_provider.naming.hot_writer_lambda_function.return_value = "test-hot-writer"
        mock_provider.naming.cold_writer_iam_role.return_value = "test-cold-writer-role"
        mock_provider.naming.cold_writer_lambda_function.return_value = "test-cold-writer"
        mock_provider.naming.archive_writer_iam_role.return_value = "test-archive-writer-role"
        mock_provider.naming.archive_writer_lambda_function.return_value = "test-archive-writer"
        mock_provider.naming.hot_reader_lambda_function.return_value = "test-reader"
        mock_provider.naming.hot_reader_last_entry_lambda_function.return_value = "test-last"
        mock_provider.clients = {"iam": MagicMock(), "lambda": MagicMock()}
        mock_provider.clients["lambda"].get_function_url_config.return_value = {
            "FunctionUrl": "https://test.lambda-url.us-east-1.on.aws/"
        }
        
        # Should not raise
        info_l0(mock_context, mock_provider)
        
        # Should have checked multiple IAM roles and Lambda functions
        assert mock_provider.clients["iam"].get_role.call_count >= 4
        assert mock_provider.clients["lambda"].get_function.call_count >= 4


# ==========================================
# AWS SDK Error Handling Tests (Phase 5)
# ==========================================

class TestAWSSDKErrorHandling:
    """Tests for AWS SDK error handling (throttling, service errors)."""
    
    def test_throttling_exception_on_role_creation_handled(self):
        """create_ingestion_iam_role() should raise ThrottlingException for caller."""
        from src.providers.aws.layers.layer_0_glue import create_ingestion_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        
        mock_provider.clients["iam"].create_role.side_effect = ClientError(
            {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            "CreateRole"
        )
        
        # Should raise for caller to handle
        with pytest.raises(ClientError) as exc_info:
            create_ingestion_iam_role(mock_provider)
        
        assert exc_info.value.response["Error"]["Code"] == "Throttling"
    
    def test_access_denied_on_iam_role_creation_raises(self):
        """create_ingestion_iam_role() should raise on AccessDenied."""
        from src.providers.aws.layers.layer_0_glue import create_ingestion_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        
        mock_provider.clients["iam"].create_role.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}},
            "CreateRole"
        )
        
        with pytest.raises(ClientError) as exc_info:
            create_ingestion_iam_role(mock_provider)
        
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
    
    def test_invalid_parameter_on_role_creation_raises(self):
        """create_ingestion_iam_role() should raise on InvalidParameterValue."""
        from src.providers.aws.layers.layer_0_glue import create_ingestion_iam_role
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_iam_role.return_value = "test-role"
        mock_provider.clients = {"iam": MagicMock()}
        
        mock_provider.clients["iam"].create_role.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterValue", "Message": "Invalid"}},
            "CreateRole"
        )
        
        with pytest.raises(ClientError) as exc_info:
            create_ingestion_iam_role(mock_provider)
        
        assert exc_info.value.response["Error"]["Code"] == "InvalidParameterValue"
    
    def test_service_exception_on_destroy_raises(self):
        """destroy_ingestion_lambda_function() should raise on ServiceException."""
        from src.providers.aws.layers.layer_0_glue import destroy_ingestion_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.ingestion_lambda_function.return_value = "test-ingestion"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function.side_effect = ClientError(
            {"Error": {"Code": "ServiceException", "Message": "Internal failure"}},
            "DeleteFunction"
        )
        
        with pytest.raises(ClientError) as exc_info:
            destroy_ingestion_lambda_function(mock_provider)
        
        assert exc_info.value.response["Error"]["Code"] == "ServiceException"


# ==========================================
# Cold Writer Lambda Tests (Phase 5)
# ==========================================

class TestColdWriterLambdaCreation:
    """Tests for Cold Writer Lambda function destruction."""
    
    def test_destroy_cold_writer_handles_not_found(self):
        """destroy_cold_writer_lambda_function() should handle ResourceNotFoundException."""
        from src.providers.aws.layers.layer_0_glue import destroy_cold_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.cold_writer_lambda_function.return_value = "test-cold-writer"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DeleteFunctionUrlConfig"
        )
        
        # Should not raise
        destroy_cold_writer_lambda_function(mock_provider)
    
    def test_destroy_cold_writer_handles_service_exception(self):
        """destroy_cold_writer_lambda_function() should raise on ServiceException."""
        from src.providers.aws.layers.layer_0_glue import destroy_cold_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.cold_writer_lambda_function.return_value = "test-cold-writer"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ServiceException", "Message": "Internal error"}},
            "DeleteFunctionUrlConfig"
        )
        
        with pytest.raises(ClientError) as exc_info:
            destroy_cold_writer_lambda_function(mock_provider)
        
        assert exc_info.value.response["Error"]["Code"] == "ServiceException"


# ==========================================
# Archive Writer Lambda Tests (Phase 5)
# ==========================================

class TestArchiveWriterLambdaCreation:
    """Tests for Archive Writer Lambda function destruction."""
    
    def test_destroy_archive_writer_handles_not_found(self):
        """destroy_archive_writer_lambda_function() should handle ResourceNotFoundException."""
        from src.providers.aws.layers.layer_0_glue import destroy_archive_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.archive_writer_lambda_function.return_value = "test-archive-writer"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}},
            "DeleteFunctionUrlConfig"
        )
        
        # Should not raise
        destroy_archive_writer_lambda_function(mock_provider)
    
    def test_destroy_archive_writer_handles_service_exception(self):
        """destroy_archive_writer_lambda_function() should raise on ServiceException."""
        from src.providers.aws.layers.layer_0_glue import destroy_archive_writer_lambda_function
        
        mock_provider = MagicMock()
        mock_provider.naming.archive_writer_lambda_function.return_value = "test-archive-writer"
        mock_provider.clients = {"lambda": MagicMock()}
        
        mock_provider.clients["lambda"].delete_function_url_config.side_effect = ClientError(
            {"Error": {"Code": "ServiceException", "Message": "Internal error"}},
            "DeleteFunctionUrlConfig"
        )
        
        with pytest.raises(ClientError) as exc_info:
            destroy_archive_writer_lambda_function(mock_provider)
        
        assert exc_info.value.response["Error"]["Code"] == "ServiceException"
