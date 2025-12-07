import pytest
import os
import shutil
import zipfile
import json
import io
from fastapi.testclient import TestClient

import globals
import file_manager
import src.validator as validator
import constants as CONSTANTS
import util
from rest_api import app

client = TestClient(app)

# Helper to create a valid zip in memory
def create_valid_zip_bytes():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as zf:
        for fname in CONSTANTS.REQUIRED_CONFIG_FILES:
            content = "{}"
            if fname == CONSTANTS.CONFIG_FILE:
                content = json.dumps({
                    "digital_twin_name": "digital-twin",
                    "hot_storage_size_in_days": 30,
                    "cold_storage_size_in_days": 90,
                    "mode": "DEBUG"
                })
            elif fname in [CONSTANTS.CONFIG_IOT_DEVICES_FILE, CONSTANTS.CONFIG_EVENTS_FILE, CONSTANTS.CONFIG_HIERARCHY_FILE]:
                content = "[]"
            elif fname == CONSTANTS.CONFIG_OPTIMIZATION_FILE:
                content = json.dumps({"result": {}})
            elif fname == CONSTANTS.CONFIG_PROVIDERS_FILE:
                content = json.dumps({
                    "layer_1_provider": "aws",
                    "layer_2_provider": "aws",
                    "layer_3_hot_provider": "aws"
                })
            
            zf.writestr(fname, content)
    bio.seek(0)
    return bio.getvalue()

@pytest.fixture(autouse=True)
def reset_globals():
    """Reset globals state before each test"""
    globals.CURRENT_PROJECT = "template"
    # Ensure template dir exists (it should in dev, but explicit check help)
    template_path = os.path.join(globals.project_path(), "upload", "template")
    if not os.path.exists(template_path):
        os.makedirs(template_path)
    # Cleanup any test projects
    upload_path = os.path.join(globals.project_path(), "upload")
    for item in os.listdir(upload_path):
        if item.startswith("test_proj_"):
            shutil.rmtree(os.path.join(upload_path, item))
    yield
    # Cleanup after
    globals.CURRENT_PROJECT = "template"
    for item in os.listdir(upload_path):
        if item.startswith("test_proj_"):
            shutil.rmtree(os.path.join(upload_path, item))

# --- Unit Tests: file_manager & globals ---

def test_validate_project_zip_valid():
    zip_bytes = create_valid_zip_bytes()
    # Should not raise
    validator.validate_project_zip(zip_bytes)

def test_validate_project_zip_missing_files():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w') as zf:
        zf.writestr("config.json", "{}")
    bio.seek(0)
    
    with pytest.raises(ValueError, match="Missing required configuration"):
        validator.validate_project_zip(bio.getvalue())

def test_create_project_from_zip_success():
    project_name = "test_proj_1"
    zip_bytes = create_valid_zip_bytes()
    
    file_manager.create_project_from_zip(project_name, zip_bytes)
    
    target_dir = os.path.join(globals.project_path(), "upload", project_name)
    assert os.path.exists(target_dir)
    assert os.path.exists(os.path.join(target_dir, "config.json"))

def test_create_project_duplicate_fail():
    project_name = "test_proj_dup"
    zip_bytes = create_valid_zip_bytes()
    file_manager.create_project_from_zip(project_name, zip_bytes)
    
    with pytest.raises(ValueError, match="already exists"):
        file_manager.create_project_from_zip(project_name, zip_bytes)

def test_create_project_invalid_name():
    with pytest.raises(ValueError, match="Invalid project name"):
        file_manager.create_project_from_zip("../traversal", create_valid_zip_bytes())

def test_set_active_project_success():
    project_name = "test_proj_active"
    file_manager.create_project_from_zip(project_name, create_valid_zip_bytes())
    
    globals.set_active_project(project_name)
    assert globals.CURRENT_PROJECT == project_name
    assert os.path.basename(globals.get_project_upload_path()) == project_name

def test_set_active_project_not_found():
    with pytest.raises(ValueError, match="does not exist"):
        globals.set_active_project("non_existent_project")

def test_get_path_in_project():
    globals.set_active_project("template") # Ensure default
    path = util.get_path_in_project("subdir/file.txt")
    expected = os.path.join(globals.project_path(), "upload", "template", "subdir", "file.txt")
    assert path == expected

# --- API Tests ---

def test_api_list_projects():
    project_name = "test_proj_list"
    file_manager.create_project_from_zip(project_name, create_valid_zip_bytes())
    
    response = client.get("/projects")
    assert response.status_code == 200
    data = response.json()
    assert project_name in data["projects"]
    assert "template" in data["projects"]
    assert data["active_project"] == "template"

def test_api_create_project():
    project_name = "test_proj_api_create"
    zip_bytes = create_valid_zip_bytes()
    
    files = {"file": ("project.zip", zip_bytes, "application/zip")}
    response = client.post(f"/projects?project_name={project_name}", files=files)
    
    assert response.status_code == 200
    assert f"Project '{project_name}' created" in response.json()["message"]
    assert os.path.exists(os.path.join(globals.project_path(), "upload", project_name))

def test_api_activate_project():
    project_name = "test_proj_api_activate"
    file_manager.create_project_from_zip(project_name, create_valid_zip_bytes())
    
    response = client.put(f"/projects/{project_name}/activate")
    assert response.status_code == 200
    assert globals.CURRENT_PROJECT == project_name

def test_api_activate_project_not_found():
    response = client.put("/projects/fake_project/activate")
    assert response.status_code == 404

def test_api_update_config():
    project_name = "test_proj_config"
    file_manager.create_project_from_zip(project_name, create_valid_zip_bytes())
    
    new_config = {
        "digital_twin_name": "digital-twin-updated",
        "hot_storage_size_in_days": 30,
        "cold_storage_size_in_days": 90,
        "mode": "DEBUG"
    }
    files = {"file": ("config.json", json.dumps(new_config), "application/json")}
    
    response = client.put(f"/projects/{project_name}/config/config", files=files)
    assert response.status_code == 200
    
    # Verify content
    with open(os.path.join(globals.project_path(), "upload", project_name, "config.json")) as f:
        stored_config = json.load(f)
    assert stored_config == new_config

def test_api_safety_check_deploy_mismatch():
    # Current is template
    response = client.post("/deploy?project_name=other_project&provider=aws")
    assert response.status_code == 409
    assert "SAFETY ERROR" in response.json()["detail"]

def test_api_safety_check_destroy_mismatch():
    # Current is template
    response = client.post("/destroy?project_name=other_project&provider=aws")
    assert response.status_code == 409
    assert "SAFETY ERROR" in response.json()["detail"]
