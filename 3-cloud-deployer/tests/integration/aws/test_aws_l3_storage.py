"""
Integration tests for L3 Storage components using new provider pattern.
"""

import pytest
import boto3
from unittest.mock import MagicMock, patch
from moto import mock_aws


class TestHotStorage:
    """Tests for Hot Storage (DynamoDB) components."""

    def test_create_hot_dynamodb_table(self, mock_provider):
        """Verify DynamoDB table creation."""
        from src.providers.aws.layers.layer_3_storage import create_hot_dynamodb_table
        
        create_hot_dynamodb_table(mock_provider)
        
        table_name = mock_provider.naming.hot_dynamodb_table()
        response = mock_provider.clients["dynamodb"].describe_table(TableName=table_name)
        assert response["Table"]["TableName"] == table_name

    def test_destroy_hot_dynamodb_table(self, mock_provider):
        """Verify DynamoDB table destruction."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_dynamodb_table, destroy_hot_dynamodb_table
        )
        
        create_hot_dynamodb_table(mock_provider)
        destroy_hot_dynamodb_table(mock_provider)
        
        table_name = mock_provider.naming.hot_dynamodb_table()
        with pytest.raises(mock_provider.clients["dynamodb"].exceptions.ResourceNotFoundException):
            mock_provider.clients["dynamodb"].describe_table(TableName=table_name)


class TestColdStorage:
    """Tests for Cold Storage (S3) components."""

    def test_create_cold_s3_bucket(self, mock_provider):
        """Verify Cold S3 bucket creation."""
        from src.providers.aws.layers.layer_3_storage import create_cold_s3_bucket
        
        create_cold_s3_bucket(mock_provider)
        
        bucket_name = mock_provider.naming.cold_s3_bucket()
        response = mock_provider.clients["s3"].list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]
        assert bucket_name in bucket_names

    def test_destroy_cold_s3_bucket(self, mock_provider):
        """Verify Cold S3 bucket destruction."""
        from src.providers.aws.layers.layer_3_storage import (
            create_cold_s3_bucket, destroy_cold_s3_bucket
        )
        
        create_cold_s3_bucket(mock_provider)
        destroy_cold_s3_bucket(mock_provider)
        
        bucket_name = mock_provider.naming.cold_s3_bucket()
        response = mock_provider.clients["s3"].list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]
        assert bucket_name not in bucket_names


class TestArchiveStorage:
    """Tests for Archive Storage (S3) components."""

    def test_create_archive_s3_bucket(self, mock_provider):
        """Verify Archive S3 bucket creation."""
        from src.providers.aws.layers.layer_3_storage import create_archive_s3_bucket
        
        create_archive_s3_bucket(mock_provider)
        
        bucket_name = mock_provider.naming.archive_s3_bucket()
        response = mock_provider.clients["s3"].list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]
        assert bucket_name in bucket_names

    def test_destroy_archive_s3_bucket(self, mock_provider):
        """Verify Archive S3 bucket destruction."""
        from src.providers.aws.layers.layer_3_storage import (
            create_archive_s3_bucket, destroy_archive_s3_bucket
        )
        
        create_archive_s3_bucket(mock_provider)
        destroy_archive_s3_bucket(mock_provider)
        
        bucket_name = mock_provider.naming.archive_s3_bucket()
        response = mock_provider.clients["s3"].list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]
        assert bucket_name not in bucket_names


class TestHotColdMover:
    """Tests for Hot-to-Cold Mover components."""

    def test_create_hot_cold_mover_iam_role(self, mock_provider):
        """Verify Hot-Cold Mover IAM role creation."""
        from src.providers.aws.layers.layer_3_storage import create_hot_cold_mover_iam_role
        
        create_hot_cold_mover_iam_role(mock_provider)
        
        role_name = mock_provider.naming.hot_cold_mover_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    def test_destroy_hot_cold_mover_components(self, mock_provider):
        """Verify Hot-Cold Mover destruction."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_cold_mover_iam_role, destroy_hot_cold_mover_iam_role
        )
        
        create_hot_cold_mover_iam_role(mock_provider)
        destroy_hot_cold_mover_iam_role(mock_provider)
        
        role_name = mock_provider.naming.hot_cold_mover_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)

    @patch("util.compile_lambda_function")
    def test_create_hot_cold_mover_lambda_function(self, mock_compile, mock_provider, mock_config, project_path):
        """Verify Hot-Cold Mover Lambda creation."""
        from src.providers.aws.layers.layer_3_storage import (
            create_hot_cold_mover_iam_role, create_hot_cold_mover_lambda_function
        )
        
        # Mock lambda compilation
        mock_compile.return_value = b"fake-zip-content"
        
        create_hot_cold_mover_iam_role(mock_provider)
        create_hot_cold_mover_lambda_function(mock_provider, mock_config, project_path)
        
        function_name = mock_provider.naming.hot_cold_mover_lambda_function()
        response = mock_provider.clients["lambda"].get_function(FunctionName=function_name)
        assert response["Configuration"]["FunctionName"] == function_name
