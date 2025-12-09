"""
Tests for validator duplicate detection functionality.

Tests check_duplicate_project and _hash_credentials functions.
"""
import pytest
import os
import json
import io
import zipfile
from unittest.mock import patch, MagicMock

import src.validator as validator
import constants as CONSTANTS


# ==========================================
# Test Fixtures
# ==========================================
@pytest.fixture
def temp_project_path(tmp_path):
    """Create a temporary project path for testing."""
    upload_dir = tmp_path / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
    upload_dir.mkdir()
    return str(tmp_path)


@pytest.fixture
def create_project_fixture(temp_project_path):
    """Factory fixture to create projects with specific configs."""
    def _create_project(project_name, twin_name, credentials):
        project_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            project_name
        )
        os.makedirs(project_dir)
        
        # Write config.json
        config_path = os.path.join(project_dir, CONSTANTS.CONFIG_FILE)
        with open(config_path, 'w') as f:
            json.dump({"digital_twin_name": twin_name}, f)
        
        # Write config_credentials.json
        creds_path = os.path.join(project_dir, CONSTANTS.CONFIG_CREDENTIALS_FILE)
        with open(creds_path, 'w') as f:
            json.dump(credentials, f)
        
        return project_dir
    
    return _create_project


# ==========================================
# Test: _hash_credentials
# ==========================================
class TestHashCredentials:
    """Tests for the _hash_credentials helper function."""

    def test_same_input_same_output(self):
        """Verify deterministic hashing."""
        creds = {
            "aws": {"aws_access_key_id": "AKIA123", "aws_region": "us-east-1"}
        }
        
        hash1 = validator._hash_credentials(creds)
        hash2 = validator._hash_credentials(creds)
        
        assert hash1 == hash2

    def test_different_region_different_hash(self):
        """Verify region affects hash."""
        creds1 = {
            "aws": {"aws_access_key_id": "AKIA123", "aws_region": "us-east-1"}
        }
        creds2 = {
            "aws": {"aws_access_key_id": "AKIA123", "aws_region": "eu-west-1"}
        }
        
        hash1 = validator._hash_credentials(creds1)
        hash2 = validator._hash_credentials(creds2)
        
        assert hash1 != hash2

    def test_ignores_secrets(self):
        """Verify secrets don't affect hash (only identity fields)."""
        creds1 = {
            "aws": {
                "aws_access_key_id": "AKIA123",
                "aws_region": "us-east-1",
                "aws_secret_access_key": "secret1"
            }
        }
        creds2 = {
            "aws": {
                "aws_access_key_id": "AKIA123",
                "aws_region": "us-east-1",
                "aws_secret_access_key": "different_secret"
            }
        }
        
        hash1 = validator._hash_credentials(creds1)
        hash2 = validator._hash_credentials(creds2)
        
        assert hash1 == hash2

    def test_different_providers_different_hash(self):
        """Verify different providers produce different hashes."""
        creds_aws = {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}}
        creds_azure = {"azure": {"azure_subscription_id": "sub", "azure_region": "eastus"}}
        
        hash1 = validator._hash_credentials(creds_aws)
        hash2 = validator._hash_credentials(creds_azure)
        
        assert hash1 != hash2

    def test_empty_credentials(self):
        """Verify empty credentials produce consistent hash."""
        hash1 = validator._hash_credentials({})
        hash2 = validator._hash_credentials({})
        
        assert hash1 == hash2

    def test_multi_provider_credentials(self):
        """Verify multi-provider credentials are handled."""
        creds = {
            "aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"},
            "azure": {"azure_subscription_id": "sub", "azure_region": "eastus"}
        }
        
        # Should not raise
        hash_result = validator._hash_credentials(creds)
        assert len(hash_result) == 64  # SHA256 hex length


# ==========================================
# Test: check_duplicate_project
# ==========================================
class TestCheckDuplicateProject:
    """Tests for the check_duplicate_project function."""

    def test_no_conflict_empty_upload(self, temp_project_path):
        """No existing project → returns None."""
        result = validator.check_duplicate_project(
            "new-twin",
            {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}},
            project_path=temp_project_path
        )
        
        assert result is None

    def test_finds_conflict(self, temp_project_path, create_project_fixture):
        """Same twin name + creds → returns project name."""
        creds = {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}}
        create_project_fixture("existing_project", "my-twin", creds)
        
        result = validator.check_duplicate_project(
            "my-twin",
            creds,
            project_path=temp_project_path
        )
        
        assert result == "existing_project"

    def test_excludes_self(self, temp_project_path, create_project_fixture):
        """Exclude own project during update."""
        creds = {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}}
        create_project_fixture("my_project", "my-twin", creds)
        
        result = validator.check_duplicate_project(
            "my-twin",
            creds,
            exclude_project="my_project",
            project_path=temp_project_path
        )
        
        assert result is None

    def test_different_twin_name_ok(self, temp_project_path, create_project_fixture):
        """Same creds but different twin name → no conflict."""
        creds = {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}}
        create_project_fixture("existing_project", "twin-1", creds)
        
        result = validator.check_duplicate_project(
            "twin-2",  # Different twin name
            creds,
            project_path=temp_project_path
        )
        
        assert result is None

    def test_different_creds_ok(self, temp_project_path, create_project_fixture):
        """Same twin name but different creds → no conflict."""
        creds1 = {"aws": {"aws_access_key_id": "key1", "aws_region": "us-east-1"}}
        creds2 = {"aws": {"aws_access_key_id": "key2", "aws_region": "eu-west-1"}}
        
        create_project_fixture("existing_project", "my-twin", creds1)
        
        result = validator.check_duplicate_project(
            "my-twin",
            creds2,  # Different credentials
            project_path=temp_project_path
        )
        
        assert result is None

    def test_corrupted_existing_project_skipped(self, temp_project_path):
        """Corrupted project config doesn't crash check."""
        project_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            "corrupted_project"
        )
        os.makedirs(project_dir)
        
        # Write invalid JSON
        config_path = os.path.join(project_dir, CONSTANTS.CONFIG_FILE)
        with open(config_path, 'w') as f:
            f.write("{invalid json")
        
        # Should not raise, just skip the corrupted project
        result = validator.check_duplicate_project(
            "new-twin",
            {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}},
            project_path=temp_project_path
        )
        
        assert result is None

    def test_partial_credentials_handled(self, temp_project_path, create_project_fixture):
        """Missing credential fields don't crash."""
        # Create project with partial credentials
        partial_creds = {"aws": {"aws_access_key_id": "key"}}  # Missing region
        create_project_fixture("partial_project", "twin", partial_creds)
        
        full_creds = {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}}
        
        # Should handle gracefully (different hashes due to missing field)
        result = validator.check_duplicate_project(
            "twin",
            full_creds,
            project_path=temp_project_path
        )
        
        # Should NOT find conflict because hashes differ
        assert result is None

    def test_missing_config_file_skipped(self, temp_project_path):
        """Project without config file is skipped."""
        project_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            "no_config_project"
        )
        os.makedirs(project_dir)
        # No config.json created
        
        result = validator.check_duplicate_project(
            "twin",
            {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}},
            project_path=temp_project_path
        )
        
        assert result is None

    def test_missing_credentials_file_skipped(self, temp_project_path):
        """Project without credentials file is skipped."""
        project_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            "no_creds_project"
        )
        os.makedirs(project_dir)
        
        # Only config, no credentials
        config_path = os.path.join(project_dir, CONSTANTS.CONFIG_FILE)
        with open(config_path, 'w') as f:
            json.dump({"digital_twin_name": "twin"}, f)
        
        result = validator.check_duplicate_project(
            "twin",
            {"aws": {"aws_access_key_id": "key", "aws_region": "us-east-1"}},
            project_path=temp_project_path
        )
        
        assert result is None
