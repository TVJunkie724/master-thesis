"""
Integration tests for duplicate project detection.

Tests the API behavior when duplicate projects are detected.
"""
import pytest
import os
import json
import io
import zipfile
import shutil
import uuid
from fastapi.testclient import TestClient

import src.core.state as state
import file_manager
import constants as CONSTANTS
from rest_api import app

client = TestClient(app)


# ==========================================
# Test Fixtures
# ==========================================
def create_valid_zip_bytes(twin_name=None, creds=None):
    """Create a valid project zip file in memory."""
    unique_id = uuid.uuid4().hex[:8]
    if twin_name is None:
        twin_name = f"test-twin-{unique_id}"
    if creds is None:
        creds = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}",
                "aws_secret_access_key": f"secret{unique_id}",
                "aws_region": "us-east-1"
            }
        }
    
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as zf:
        config = {
            "digital_twin_name": twin_name,
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90,
            "mode": "DEBUG"
        }
        zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps(config))
        zf.writestr(CONSTANTS.CONFIG_IOT_DEVICES_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_EVENTS_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_HIERARCHY_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_CREDENTIALS_FILE, json.dumps(creds))
        zf.writestr(CONSTANTS.CONFIG_PROVIDERS_FILE, json.dumps({
            "layer_1_provider": "aws",
            "layer_2_provider": "aws",
            "layer_3_hot_provider": "aws",
            "layer_4_provider": "aws"
        }))
        zf.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, json.dumps({"result": {}}))
    bio.seek(0)
    return bio.getvalue()


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    state.reset_state()
    upload_path = state.get_project_upload_path()
    
    # Cleanup test projects
    for item in os.listdir(upload_path):
        if item.startswith("test_dup_"):
            shutil.rmtree(os.path.join(upload_path, item))
    
    yield
    
    # Cleanup after
    state.reset_state()
    for item in os.listdir(upload_path):
        if item.startswith("test_dup_"):
            shutil.rmtree(os.path.join(upload_path, item))


# ==========================================
# Test: Duplicate Detection on Create
# ==========================================
class TestDuplicateOnCreate:
    """Tests for duplicate detection during project creation."""

    def test_create_duplicate_twin_and_creds_400(self):
        """Upload with matching twin+creds fails with 400."""
        unique_id = uuid.uuid4().hex[:6]
        twin_name = f"shared-twin-{unique_id}"
        creds = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}",
                "aws_secret_access_key": f"secret{unique_id}",
                "aws_region": "us-east-1"
            }
        }
        
        # Create first project
        zip_bytes1 = create_valid_zip_bytes(twin_name=twin_name, creds=creds)
        files1 = {"file": ("project.zip", zip_bytes1, "application/zip")}
        response1 = client.post("/projects?project_name=test_dup_first", files=files1)
        assert response1.status_code == 200
        
        # Try to create second project with same twin_name and creds
        zip_bytes2 = create_valid_zip_bytes(twin_name=twin_name, creds=creds)
        files2 = {"file": ("project.zip", zip_bytes2, "application/zip")}
        response2 = client.post("/projects?project_name=test_dup_second", files=files2)
        
        assert response2.status_code == 400
        assert "duplicate" in response2.json()["detail"].lower()

    def test_create_same_twin_different_creds_ok(self):
        """Same twin name, different credentials succeeds."""
        unique_id = uuid.uuid4().hex[:6]
        twin_name = f"shared-twin-{unique_id}"
        creds1 = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}1",
                "aws_secret_access_key": f"secret{unique_id}1",
                "aws_region": "us-east-1"
            }
        }
        creds2 = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}2",
                "aws_secret_access_key": f"secret{unique_id}2",
                "aws_region": "eu-west-1"
            }
        }
        
        # Create first project
        zip_bytes1 = create_valid_zip_bytes(twin_name=twin_name, creds=creds1)
        files1 = {"file": ("project.zip", zip_bytes1, "application/zip")}
        response1 = client.post("/projects?project_name=test_dup_creds1", files=files1)
        assert response1.status_code == 200
        
        # Create second project with same twin_name but different creds
        zip_bytes2 = create_valid_zip_bytes(twin_name=twin_name, creds=creds2)
        files2 = {"file": ("project.zip", zip_bytes2, "application/zip")}
        response2 = client.post("/projects?project_name=test_dup_creds2", files=files2)
        
        assert response2.status_code == 200

    def test_create_different_twin_same_creds_ok(self):
        """Different twin name, same credentials succeeds."""
        unique_id = uuid.uuid4().hex[:6]
        creds = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}",
                "aws_secret_access_key": f"secret{unique_id}",
                "aws_region": "us-east-1"
            }
        }
        
        # Create first project
        zip_bytes1 = create_valid_zip_bytes(twin_name=f"twin-1-{unique_id}", creds=creds)
        files1 = {"file": ("project.zip", zip_bytes1, "application/zip")}
        response1 = client.post("/projects?project_name=test_dup_twin1", files=files1)
        assert response1.status_code == 200
        
        # Create second project with different twin_name but same creds
        zip_bytes2 = create_valid_zip_bytes(twin_name=f"twin-2-{unique_id}", creds=creds)
        files2 = {"file": ("project.zip", zip_bytes2, "application/zip")}
        response2 = client.post("/projects?project_name=test_dup_twin2", files=files2)
        
        assert response2.status_code == 200


# ==========================================
# Test: Duplicate Detection on Update
# ==========================================
class TestDuplicateOnUpdate:
    """Tests for duplicate detection during project update."""

    def test_update_project_no_self_conflict(self):
        """Updating own project doesn't trigger duplicate error."""
        unique_id = uuid.uuid4().hex[:6]
        twin_name = f"update-twin-{unique_id}"
        creds = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}",
                "aws_secret_access_key": f"secret{unique_id}",
                "aws_region": "us-west-2"
            }
        }
        
        # Create project
        zip_bytes = create_valid_zip_bytes(twin_name=twin_name, creds=creds)
        files = {"file": ("project.zip", zip_bytes, "application/zip")}
        response1 = client.post("/projects?project_name=test_dup_update", files=files)
        assert response1.status_code == 200
        
        # Update same project with same config (should not conflict with self)
        zip_bytes2 = create_valid_zip_bytes(twin_name=twin_name, creds=creds)
        files2 = {"file": ("project.zip", zip_bytes2, "application/zip")}
        response2 = client.post("/projects/test_dup_update/upload/zip", files=files2)
        
        assert response2.status_code == 200

    def test_update_to_conflicting_config_fails(self):
        """Updating to conflict with existing project fails."""
        unique_id = uuid.uuid4().hex[:6]
        conflict_twin = f"conflict-twin-{unique_id}"
        creds = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}",
                "aws_secret_access_key": f"secret{unique_id}",
                "aws_region": "ap-south-1"
            }
        }
        
        # Create first project with the "conflict" config
        zip_bytes1 = create_valid_zip_bytes(twin_name=conflict_twin, creds=creds)
        files1 = {"file": ("project.zip", zip_bytes1, "application/zip")}
        response1 = client.post("/projects?project_name=test_dup_exist", files=files1)
        assert response1.status_code == 200
        
        # Create second project with different config
        zip_bytes2 = create_valid_zip_bytes(twin_name=f"safe-twin-{unique_id}", creds=creds)
        files2 = {"file": ("project.zip", zip_bytes2, "application/zip")}
        response2 = client.post("/projects?project_name=test_dup_change", files=files2)
        assert response2.status_code == 200
        
        # Try to update second project to have conflicting config
        zip_bytes3 = create_valid_zip_bytes(twin_name=conflict_twin, creds=creds)
        files3 = {"file": ("project.zip", zip_bytes3, "application/zip")}
        response3 = client.post("/projects/test_dup_change/upload/zip", files=files3)
        
        assert response3.status_code == 400
        assert "duplicate" in response3.json()["detail"].lower()


# ==========================================
# Test: Edge Cases
# ==========================================
class TestDuplicateEdgeCases:
    """Edge case tests for duplicate detection."""

    def test_duplicate_with_multi_provider_creds(self):
        """Duplicate detection works with multi-provider credentials."""
        unique_id = uuid.uuid4().hex[:6]
        twin_name = f"multi-provider-{unique_id}"
        creds = {
            "aws": {
                "aws_access_key_id": f"AKIA{unique_id}",
                "aws_secret_access_key": f"secret{unique_id}",
                "aws_region": "us-east-1"
            },
            "azure": {
                "azure_subscription_id": f"sub{unique_id}",
                "azure_tenant_id": f"tenant{unique_id}",
                "azure_client_id": f"client{unique_id}",
                "azure_client_secret": f"secret{unique_id}",
                "azure_region": "eastus",
                "azure_region_iothub": "eastus",
                "azure_region_digital_twin": "eastus"
            }
        }
        
        # Create first project
        zip_bytes1 = create_valid_zip_bytes(twin_name=twin_name, creds=creds)
        files1 = {"file": ("project.zip", zip_bytes1, "application/zip")}
        response1 = client.post("/projects?project_name=test_dup_multi1", files=files1)
        assert response1.status_code == 200
        
        # Try duplicate
        zip_bytes2 = create_valid_zip_bytes(twin_name=twin_name, creds=creds)
        files2 = {"file": ("project.zip", zip_bytes2, "application/zip")}
        response2 = client.post("/projects?project_name=test_dup_multi2", files=files2)
        
        assert response2.status_code == 400
