"""
Tests for file_manager versioning functionality.

Tests the version archiving and project_info.json generation.
"""
import pytest
import os
import json
import io
import zipfile
import shutil
from datetime import datetime
from unittest.mock import patch, MagicMock

import file_manager
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
def valid_zip_bytes():
    """Create a valid project zip file in memory."""
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as zf:
        # config.json with digital_twin_name
        config = {
            "digital_twin_name": "test-twin",
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90,
            "mode": "DEBUG"
        }
        zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps(config))
        
        # Other required files
        zf.writestr(CONSTANTS.CONFIG_IOT_DEVICES_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_EVENTS_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_HIERARCHY_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_CREDENTIALS_FILE, json.dumps({
            "aws": {
                "aws_access_key_id": "test",
                "aws_secret_access_key": "testsecret",
                "aws_region": "us-east-1"
            }
        }))
        zf.writestr(CONSTANTS.CONFIG_PROVIDERS_FILE, json.dumps({
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws"
        }))
        zf.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, json.dumps({"result": {}}))
    
    bio.seek(0)
    return bio.getvalue()


# ==========================================
# Test: _archive_zip_version
# ==========================================
class TestArchiveZipVersion:
    """Tests for the _archive_zip_version helper function."""

    def test_archive_creates_versions_directory(self, temp_project_path, valid_zip_bytes):
        """Verify versions directory is created if it doesn't exist."""
        project_name = "test_project"
        target_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            project_name
        )
        os.makedirs(target_dir)
        
        zip_source = io.BytesIO(valid_zip_bytes)
        file_manager._archive_zip_version(zip_source, target_dir)
        
        versions_dir = os.path.join(target_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
        assert os.path.exists(versions_dir)

    def test_archive_creates_timestamped_zip(self, temp_project_path, valid_zip_bytes):
        """Verify zip is saved with timestamp filename."""
        project_name = "test_project"
        target_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            project_name
        )
        os.makedirs(target_dir)
        
        zip_source = io.BytesIO(valid_zip_bytes)
        file_manager._archive_zip_version(zip_source, target_dir)
        
        versions_dir = os.path.join(target_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
        zip_files = [f for f in os.listdir(versions_dir) if f.endswith('.zip')]
        
        assert len(zip_files) == 1
        # Verify timestamp format: YYYY-MM-DD_HH-MM-SS.zip
        filename = zip_files[0]
        assert len(filename) == 23  # 2025-12-09_22-00-00.zip

    def test_multiple_archives_create_multiple_files(self, temp_project_path, valid_zip_bytes):
        """Verify multiple uploads create multiple version files."""
        project_name = "test_project"
        target_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            project_name
        )
        os.makedirs(target_dir)
        
        # Use time mocking to ensure different timestamps
        with patch('file_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2025, 12, 9, 22, 0, 0)
            zip_source1 = io.BytesIO(valid_zip_bytes)
            file_manager._archive_zip_version(zip_source1, target_dir)
            
            mock_datetime.now.return_value = datetime(2025, 12, 9, 22, 0, 1)
            zip_source2 = io.BytesIO(valid_zip_bytes)
            file_manager._archive_zip_version(zip_source2, target_dir)
        
        versions_dir = os.path.join(target_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
        zip_files = [f for f in os.listdir(versions_dir) if f.endswith('.zip')]
        
        assert len(zip_files) == 2

    def test_archive_content_is_valid_zip(self, temp_project_path, valid_zip_bytes):
        """Verify archived content is a valid zip file."""
        project_name = "test_project"
        target_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            project_name
        )
        os.makedirs(target_dir)
        
        zip_source = io.BytesIO(valid_zip_bytes)
        file_manager._archive_zip_version(zip_source, target_dir)
        
        versions_dir = os.path.join(target_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
        zip_files = os.listdir(versions_dir)
        archived_path = os.path.join(versions_dir, zip_files[0])
        
        # Should be extractable
        with zipfile.ZipFile(archived_path, 'r') as zf:
            assert CONSTANTS.CONFIG_FILE in zf.namelist()


# ==========================================
# Test: _write_project_info
# ==========================================
class TestWriteProjectInfo:
    """Tests for the _write_project_info helper function."""

    def test_write_with_provided_description(self, temp_project_path, valid_zip_bytes):
        """Verify project_info.json is created with provided description."""
        project_name = "test_project"
        target_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            project_name
        )
        os.makedirs(target_dir)
        
        zip_source = io.BytesIO(valid_zip_bytes)
        file_manager._write_project_info(target_dir, zip_source, "My custom description")
        
        info_path = os.path.join(target_dir, CONSTANTS.PROJECT_INFO_FILE)
        assert os.path.exists(info_path)
        
        with open(info_path, 'r') as f:
            info = json.load(f)
        
        assert info["description"] == "My custom description"
        assert "created_at" in info

    def test_write_generates_default_description(self, temp_project_path, valid_zip_bytes):
        """Verify default description is generated from digital_twin_name."""
        project_name = "test_project"
        target_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            project_name
        )
        os.makedirs(target_dir)
        
        zip_source = io.BytesIO(valid_zip_bytes)
        file_manager._write_project_info(target_dir, zip_source, None)
        
        info_path = os.path.join(target_dir, CONSTANTS.PROJECT_INFO_FILE)
        with open(info_path, 'r') as f:
            info = json.load(f)
        
        # The zip's digital_twin_name starts with "test-twin"
        assert "test-twin" in info["description"] or "digital twin" in info["description"].lower()
        assert "Project builds the digital twin" in info["description"]

    def test_write_missing_twin_name_raises(self, temp_project_path):
        """Verify error if digital_twin_name is missing."""
        project_name = "test_project"
        target_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            project_name
        )
        os.makedirs(target_dir)
        
        # Create zip without digital_twin_name
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps({"mode": "DEBUG"}))
        bio.seek(0)
        
        with pytest.raises(ValueError, match="digital_twin_name"):
            file_manager._write_project_info(target_dir, bio, None)


# ==========================================
# Test: _extract_identity_from_zip
# ==========================================
class TestExtractIdentityFromZip:
    """Tests for the _extract_identity_from_zip helper function."""

    def test_extracts_twin_name_and_creds(self):
        """Verify extraction of digital_twin_name and credentials."""
        # Create a dedicated zip for this test with known values
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps({"digital_twin_name": "known-twin"}))
            zf.writestr(CONSTANTS.CONFIG_CREDENTIALS_FILE, json.dumps({
                "aws": {"aws_access_key_id": "AKIA123", "aws_region": "us-west-2"}
            }))
        bio.seek(0)
        
        twin_name, creds = file_manager._extract_identity_from_zip(bio)
        
        assert twin_name == "known-twin"
        assert "aws" in creds
        assert creds["aws"]["aws_region"] == "us-west-2"

    def test_handles_missing_config(self):
        """Verify graceful handling when config is missing."""
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr("other_file.txt", "content")
        bio.seek(0)
        
        twin_name, creds = file_manager._extract_identity_from_zip(bio)
        
        assert twin_name is None
        assert creds == {}

    def test_handles_missing_credentials(self, temp_project_path):
        """Verify graceful handling when credentials are missing."""
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps({"digital_twin_name": "twin"}))
        bio.seek(0)
        
        twin_name, creds = file_manager._extract_identity_from_zip(bio)
        
        assert twin_name == "twin"
        assert creds == {}
