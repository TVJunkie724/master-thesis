"""
Tests for file_manager CRUD operations.

Tests delete_project and update_project_info functions.
"""
import pytest
import os
import json
import io
import zipfile
import shutil
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
    """Create a valid project zip file in memory with unique credentials."""
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as zf:
        config = {
            "digital_twin_name": f"test-twin-{unique_id}",
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90,
            "mode": "DEBUG"
        }
        zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps(config))
        zf.writestr(CONSTANTS.CONFIG_IOT_DEVICES_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_EVENTS_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_HIERARCHY_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_CREDENTIALS_FILE, json.dumps({
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}",
                "aws_secret_access_key": f"secret{unique_id}",
                "aws_region": "us-east-1"
            }
        }))
        zf.writestr(CONSTANTS.CONFIG_PROVIDERS_FILE, json.dumps({
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }))
        zf.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, json.dumps({"result": {}}))
        # Add required hierarchy file for layer_4_provider=aws
        zf.writestr("twin_hierarchy/aws_hierarchy.json", "[]")
    bio.seek(0)
    return bio.getvalue()


@pytest.fixture
def created_project(temp_project_path, valid_zip_bytes):
    """Create a project and return its name."""
    project_name = "test_crud_project"
    file_manager.create_project_from_zip(
        project_name, 
        valid_zip_bytes, 
        project_path=temp_project_path,
        description="Test project"
    )
    return project_name


# ==========================================
# Test: delete_project
# ==========================================
class TestDeleteProject:
    """Tests for the delete_project function."""

    def test_delete_removes_folder(self, temp_project_path, created_project):
        """Verify shutil.rmtree removes the project folder."""
        project_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            created_project
        )
        assert os.path.exists(project_dir)
        
        file_manager.delete_project(created_project, project_path=temp_project_path)
        
        assert not os.path.exists(project_dir)

    def test_delete_nonexistent_project_raises(self, temp_project_path):
        """Verify ValueError for missing project."""
        with pytest.raises(ValueError, match="does not exist"):
            file_manager.delete_project("nonexistent_project", project_path=temp_project_path)

    def test_delete_removes_all_contents(self, temp_project_path, created_project):
        """Verify all files and subdirectories are removed."""
        project_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            created_project
        )
        
        # Add some additional files
        extra_dir = os.path.join(project_dir, "extra_subdir")
        os.makedirs(extra_dir)
        with open(os.path.join(extra_dir, "extra_file.txt"), 'w') as f:
            f.write("extra content")
        
        file_manager.delete_project(created_project, project_path=temp_project_path)
        
        assert not os.path.exists(project_dir)

    def test_delete_with_versions(self, temp_project_path, created_project):
        """Verify deletion works when versions folder exists."""
        project_dir = os.path.join(
            temp_project_path, 
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME, 
            created_project
        )
        versions_dir = os.path.join(project_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
        
        # Versions should exist from creation
        assert os.path.exists(versions_dir)
        
        file_manager.delete_project(created_project, project_path=temp_project_path)
        
        assert not os.path.exists(project_dir)


# ==========================================
# Test: update_project_info
# ==========================================
class TestUpdateProjectInfo:
    """Tests for the update_project_info function."""

    def test_update_changes_description(self, temp_project_path, created_project):
        """Verify description is updated in project_info.json."""
        file_manager.update_project_info(
            created_project, 
            "Updated description", 
            project_path=temp_project_path
        )
        
        info_path = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            created_project,
            CONSTANTS.PROJECT_INFO_FILE
        )
        
        with open(info_path, 'r') as f:
            info = json.load(f)
        
        assert info["description"] == "Updated description"

    def test_update_adds_updated_at_timestamp(self, temp_project_path, created_project):
        """Verify updated_at timestamp is added."""
        file_manager.update_project_info(
            created_project, 
            "New description", 
            project_path=temp_project_path
        )
        
        info_path = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            created_project,
            CONSTANTS.PROJECT_INFO_FILE
        )
        
        with open(info_path, 'r') as f:
            info = json.load(f)
        
        assert "updated_at" in info

    def test_update_preserves_created_at(self, temp_project_path, created_project):
        """Verify created_at timestamp is preserved."""
        info_path = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            created_project,
            CONSTANTS.PROJECT_INFO_FILE
        )
        
        # Get original created_at
        with open(info_path, 'r') as f:
            original_info = json.load(f)
        original_created_at = original_info.get("created_at")
        
        file_manager.update_project_info(
            created_project, 
            "New description", 
            project_path=temp_project_path
        )
        
        with open(info_path, 'r') as f:
            updated_info = json.load(f)
        
        assert updated_info.get("created_at") == original_created_at

    def test_update_nonexistent_project_raises(self, temp_project_path):
        """Verify ValueError for missing project."""
        with pytest.raises(ValueError, match="does not exist"):
            file_manager.update_project_info(
                "nonexistent_project", 
                "description",
                project_path=temp_project_path
            )

    def test_update_creates_info_file_if_missing(self, temp_project_path, valid_zip_bytes):
        """Verify info file is created if it doesn't exist."""
        project_name = "project_no_info"
        project_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            project_name
        )
        os.makedirs(project_dir)
        
        # No project_info.json exists
        info_path = os.path.join(project_dir, CONSTANTS.PROJECT_INFO_FILE)
        assert not os.path.exists(info_path)
        
        file_manager.update_project_info(
            project_name, 
            "New description",
            project_path=temp_project_path
        )
        
        assert os.path.exists(info_path)
        with open(info_path, 'r') as f:
            info = json.load(f)
        assert info["description"] == "New description"
