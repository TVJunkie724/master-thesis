"""
Integration tests for L4 (TwinMaker) and L5 (Grafana) using new provider pattern.
"""

import pytest
import boto3
from unittest.mock import MagicMock, patch
from moto import mock_aws


class TestTwinMaker:
    """Tests for TwinMaker (L4) components."""

    def test_create_twinmaker_s3_bucket(self, mock_provider):
        """Verify TwinMaker S3 bucket creation."""
        from src.providers.aws.layers.layer_4_twinmaker import create_twinmaker_s3_bucket
        
        create_twinmaker_s3_bucket(mock_provider)
        
        # Verify bucket was created
        bucket_name = mock_provider.naming.twinmaker_s3_bucket()
        response = mock_provider.clients["s3"].list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]
        assert bucket_name in bucket_names

    def test_destroy_twinmaker_s3_bucket(self, mock_provider):
        """Verify TwinMaker S3 bucket destruction."""
        from src.providers.aws.layers.layer_4_twinmaker import (
            create_twinmaker_s3_bucket, destroy_twinmaker_s3_bucket
        )
        
        create_twinmaker_s3_bucket(mock_provider)
        destroy_twinmaker_s3_bucket(mock_provider)
        
        # Verify bucket was deleted
        bucket_name = mock_provider.naming.twinmaker_s3_bucket()
        response = mock_provider.clients["s3"].list_buckets()
        bucket_names = [b["Name"] for b in response["Buckets"]]
        assert bucket_name not in bucket_names

    def test_create_twinmaker_iam_role(self, mock_provider):
        """Verify TwinMaker IAM role creation."""
        from src.providers.aws.layers.layer_4_twinmaker import create_twinmaker_iam_role
        
        create_twinmaker_iam_role(mock_provider)
        
        role_name = mock_provider.naming.twinmaker_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    def test_destroy_twinmaker_iam_role(self, mock_provider):
        """Verify TwinMaker IAM role destruction."""
        from src.providers.aws.layers.layer_4_twinmaker import (
            create_twinmaker_iam_role, destroy_twinmaker_iam_role
        )
        
        create_twinmaker_iam_role(mock_provider)
        destroy_twinmaker_iam_role(mock_provider)
        
        role_name = mock_provider.naming.twinmaker_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)

    def test_create_twinmaker_workspace(self, mock_provider):
        """Verify TwinMaker workspace creation (mocked TwinMaker API)."""
        from src.providers.aws.layers.layer_4_twinmaker import (
            create_twinmaker_s3_bucket, create_twinmaker_iam_role, create_twinmaker_workspace
        )
        
        # TwinMaker client is mocked
        mock_provider.clients["twinmaker"].create_workspace.return_value = {}
        
        create_twinmaker_s3_bucket(mock_provider)
        create_twinmaker_iam_role(mock_provider)
        create_twinmaker_workspace(mock_provider)
        
        mock_provider.clients["twinmaker"].create_workspace.assert_called()

    def test_destroy_twinmaker_workspace(self, mock_provider):
        """Verify TwinMaker workspace destruction (mocked)."""
        from src.providers.aws.layers.layer_4_twinmaker import destroy_twinmaker_workspace
        from botocore.exceptions import ClientError
        
        # Mock the TwinMaker behaviors
        mock_provider.clients["twinmaker"].list_entities.return_value = {"entitySummaries": []}
        mock_provider.clients["twinmaker"].list_scenes.return_value = {"sceneSummaries": []}
        mock_provider.clients["twinmaker"].list_component_types.return_value = {"componentTypeSummaries": []}
        mock_provider.clients["twinmaker"].delete_workspace.return_value = {}
        mock_provider.clients["twinmaker"].get_workspace.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}}, "get_workspace"
        )
        
        destroy_twinmaker_workspace(mock_provider)
        
        mock_provider.clients["twinmaker"].delete_workspace.assert_called()


class TestGrafana:
    """Tests for Grafana (L5) components."""

    def test_create_grafana_iam_role(self, mock_provider):
        """Verify Grafana IAM role creation."""
        from src.providers.aws.layers.layer_5_grafana import create_grafana_iam_role
        
        create_grafana_iam_role(mock_provider)
        
        role_name = mock_provider.naming.grafana_iam_role()
        response = mock_provider.clients["iam"].get_role(RoleName=role_name)
        assert response["Role"]["RoleName"] == role_name

    def test_destroy_grafana_iam_role(self, mock_provider):
        """Verify Grafana IAM role destruction."""
        from src.providers.aws.layers.layer_5_grafana import (
            create_grafana_iam_role, destroy_grafana_iam_role
        )
        
        create_grafana_iam_role(mock_provider)
        destroy_grafana_iam_role(mock_provider)
        
        role_name = mock_provider.naming.grafana_iam_role()
        with pytest.raises(mock_provider.clients["iam"].exceptions.NoSuchEntityException):
            mock_provider.clients["iam"].get_role(RoleName=role_name)

    def test_create_grafana_workspace(self, mock_provider):
        """Verify Grafana workspace creation (mocked Grafana API)."""
        from src.providers.aws.layers.layer_5_grafana import (
            create_grafana_iam_role, create_grafana_workspace
        )
        
        # Grafana client is mocked
        mock_provider.clients["grafana"].create_workspace.return_value = {"workspace": {"id": "g-123"}}
        mock_provider.clients["grafana"].describe_workspace.return_value = {"workspace": {"status": "ACTIVE"}}
        
        create_grafana_iam_role(mock_provider)
        create_grafana_workspace(mock_provider)
        
        mock_provider.clients["grafana"].create_workspace.assert_called()

    def test_destroy_grafana_workspace(self, mock_provider):
        """Verify Grafana workspace destruction (mocked)."""
        from src.providers.aws.layers.layer_5_grafana import destroy_grafana_workspace
        from botocore.exceptions import ClientError
        
        # Mock the Grafana behaviors - need to mock the paginator
        mock_provider.clients["grafana"].meta = MagicMock()
        mock_provider.clients["grafana"].meta.region_name = "eu-central-1"
        
        # Create a mock paginator that returns workspace data
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"workspaces": [{"id": "g-123", "name": mock_provider.naming.grafana_workspace()}]}
        ]
        mock_provider.clients["grafana"].get_paginator.return_value = mock_paginator
        
        mock_provider.clients["grafana"].delete_workspace.return_value = {}
        mock_provider.clients["grafana"].describe_workspace.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}}, "describe_workspace"
        )
        
        destroy_grafana_workspace(mock_provider)
        
        mock_provider.clients["grafana"].delete_workspace.assert_called()

