# Refactor Upload Logic: Payloads, Descriptions, Validation & Versioning

## Implementation Progress

> **Status:** ✅ All phases complete, tests passing (331/331)

### Quick Reference: What's Done vs. Remaining

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Constants & Core Validation | ✅ Complete |
| Phase 2 | File Manager Enhancements | ✅ Complete |
| Phase 3 | API Layer | ✅ Complete |
| Phase 4 | Duplicate Detection | ✅ Complete |

---

## Completed Tasks

### API Endpoints (Phase 3)
- [x] **3.1** Update `create_project` endpoint in `src/api/projects.py` - add `description` query param
- [x] **3.2** Update `update_project_zip` endpoint - add `description` query param
- [x] **3.3** Add `DELETE /projects/{project_name}` endpoint
- [x] **3.4** Add `PATCH /projects/{project_name}/info` endpoint
- [x] **3.5** Fix `upload_simulator_payloads` path (remove provider subfolder)
- [x] **3.6** Update `list_projects` to include descriptions and version counts

### Tests Created (Extended Coverage)
- [x] **T1** `tests/unit/test_file_manager_versioning.py` - 10 tests
- [x] **T2** `tests/unit/test_file_manager_crud.py` - 9 tests
- [x] **T3** `tests/unit/test_validator_duplicate.py` - 15 tests
- [x] **T4** `tests/integration/test_api_projects_crud.py` - 12 tests
- [x] **T5** `tests/integration/test_api_projects_duplicate.py` - 7 tests


---

## 1. Executive Summary

### The Problem
The current project upload mechanism has significant limitations:
1.  **No Version History:** Uploading a new zip overwrites files with no rollback capability.
2.  **No Metadata:** Projects lack descriptions, making identification difficult.
3.  **Provider-Specific Payloads:** `payloads.json` is stored per-provider (`/aws/payloads.json`), but the data is actually shared.
4.  **Permissive Validation:** Missing function directories or provider mismatches are not caught.
5.  **No Deletion:** Users cannot delete projects via API.

### The Solution
1.  **Centralized Payloads:** Move `payloads.json` to `iot_device_simulator/` (provider-agnostic).
2.  **Project Metadata:** Add `project_info.json` in each project folder with optional description (auto-generated from mandatory `digital_twin_name` if not provided).
3.  **Zip Versioning:** Archive every uploaded zip to `versions/` with timestamp before extraction.
4.  **CRUD API:** Add `DELETE /projects/{name}` and `PATCH /projects/{name}/info`.
5.  **Strict Validation:**
    - If a provider folder exists in zip, verify all required function subdirectories are present (ERROR if missing).
    - If a provider is configured in `config_providers` + `config_credentials` but folder is missing, return WARNING.

### Impact
- **Rollback:** Users can restore previous versions.
- **Clarity:** Projects are self-documenting with descriptions.
- **Safety:** Strict validation prevents broken deployments.

---

## 2. Current State

### Project Upload Flow
```
┌─────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Client    │─────▶│  POST /projects │─────▶│   file_manager  │
│  (Flutter)  │      │   (projects.py) │      │   .create_...   │
└─────────────┘      └─────────────────┘      └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  validator.py   │
                                              │ validate_zip()  │
                                              └────────┬────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │   Extract to    │
                                              │  upload/{name}  │
                                              └─────────────────┘
```

### Current Problems
```python
# file_manager.py - No versioning, no metadata
def create_project_from_zip(project_name, zip_source, project_path=None):
    # ... validation ...
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)  # Direct overwrite, no history
```

```python
# api/projects.py - Payloads are provider-specific
path = os.path.join(..., "iot_device_simulator", provider)  # /aws/payloads.json
```

---

## 3. Proposed Changes

### Component: Constants

#### [MODIFY] constants.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/constants.py`
- **Description:** Add new file and directory constants.

```python
# Add after line 49 (STATE_MACHINES_DIR_NAME)
PROJECT_INFO_FILE = "project_info.json"
PAYLOADS_FILE = "payloads.json"
PROJECT_VERSIONS_DIR_NAME = "versions"
IOT_DEVICE_SIMULATOR_DIR_NAME = "iot_device_simulator"
```

---

### Component: File Manager

#### [MODIFY] file_manager.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/file_manager.py`
- **Description:** Add versioning, metadata handling, and delete functionality.

**Before (create_project_from_zip):**
```python
def create_project_from_zip(project_name, zip_source, project_path: str = None):
    # ... validation ...
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
    logger.info(f"Created project '{project_name}' from zip.")
```

**After (create_project_from_zip):**
```python
def create_project_from_zip(project_name, zip_source, project_path: str = None, description: str = None):
    """
    Creates a new project from a validated zip file.
    
    Args:
        project_name: Name of the project to create.
        zip_source: Zip file source (bytes or BytesIO).
        project_path: Base project path. If None, auto-detected.
        description: Optional project description. If None, generated from digital_twin_name.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_name = os.path.basename(project_name)
    if safe_name != project_name:
        raise ValueError("Invalid project name.")
    
    if isinstance(zip_source, bytes):
        zip_source = io.BytesIO(zip_source)

    # Validate before extraction
    warnings = validator.validate_project_zip(zip_source)
    
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    if os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' already exists.")
        
    os.makedirs(target_dir)
    
    # Archive version before extracting
    _archive_zip_version(zip_source, target_dir)
    
    # Extract
    zip_source.seek(0)
    with zipfile.ZipFile(zip_source, 'r') as zf:
        zf.extractall(target_dir)
    
    # Write project_info.json
    _write_project_info(target_dir, zip_source, description)
        
    logger.info(f"Created project '{project_name}' from zip.")
    return {"message": f"Project '{project_name}' created.", "warnings": warnings}
```

**New Helper Functions:**
```python
from datetime import datetime

def _archive_zip_version(zip_source, target_dir):
    """
    Archives the uploaded zip to {target_dir}/versions/{timestamp}.zip.
    """
    versions_dir = os.path.join(target_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)
    os.makedirs(versions_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    version_path = os.path.join(versions_dir, f"{timestamp}.zip")
    
    zip_source.seek(0)
    with open(version_path, 'wb') as f:
        f.write(zip_source.read())
    
    logger.info(f"Archived version to {version_path}")


def _write_project_info(target_dir, zip_source, description: str = None):
    """
    Writes project_info.json with description.
    If description is None, generates from config.json's digital_twin_name.
    """
    if not description:
        # Read digital_twin_name from config.json in zip
        zip_source.seek(0)
        with zipfile.ZipFile(zip_source, 'r') as zf:
            for name in zf.namelist():
                if name.endswith(CONSTANTS.CONFIG_FILE):
                    with zf.open(name) as f:
                        config = json.load(f)
                        twin_name = config.get("digital_twin_name")
                        if not twin_name:
                            raise ValueError("Missing mandatory 'digital_twin_name' in config.json")
                        description = f"Project builds the digital twin with prefix name {twin_name}"
                        break
    
    info_path = os.path.join(target_dir, CONSTANTS.PROJECT_INFO_FILE)
    with open(info_path, 'w') as f:
        json.dump({"description": description, "created_at": datetime.now().isoformat()}, f, indent=2)


def delete_project(project_name, project_path: str = None):
    """
    Deletes an entire project directory.
    
    Args:
        project_name: Name of the project to delete.
        project_path: Base project path. If None, auto-detected.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_name = os.path.basename(project_name)
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    
    if not os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")
    
    shutil.rmtree(target_dir)
    logger.info(f"Deleted project '{project_name}'.")


def update_project_info(project_name, description: str, project_path: str = None):
    """
    Updates the description in project_info.json.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    safe_name = os.path.basename(project_name)
    target_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, safe_name)
    info_path = os.path.join(target_dir, CONSTANTS.PROJECT_INFO_FILE)
    
    if not os.path.exists(target_dir):
        raise ValueError(f"Project '{project_name}' does not exist.")
    
    info = {}
    if os.path.exists(info_path):
        with open(info_path, 'r') as f:
            info = json.load(f)
    
    info["description"] = description
    info["updated_at"] = datetime.now().isoformat()
    
    with open(info_path, 'w') as f:
        json.dump(info, f, indent=2)
    
    logger.info(f"Updated info for project '{project_name}'.")
```

---

### Component: Validator

#### [MODIFY] validator.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/validator.py`
- **Description:** Add strict structure checks and warning logic. Return warnings list.

**Before (validate_project_zip signature):**
```python
def validate_project_zip(zip_source):
    # ... raises ValueError on error ...
```

**After (validate_project_zip):**
```python
def validate_project_zip(zip_source) -> list:
    """
    Validates zip file structure and content.
    
    Returns:
        list: Warnings (non-fatal issues).
    
    Raises:
        ValueError: On fatal validation errors.
    """
    warnings = []
    
    # ... existing checks ...
    
    # NEW: Strict Provider Structure Check
    # If a provider folder exists in zip, all functions must be present
    seen_providers = set()
    for member in zf.infolist():
        if f"{CONSTANTS.LAMBDA_FUNCTIONS_DIR_NAME}/" in member.filename:
            # Extract provider from path if discernible
            pass  # Logic below
    
    # Check active providers from configs
    active_providers = set()
    for layer_key in ["layer_1_provider", "layer_2_provider", "layer_3_hot_provider"]:
        if layer_key in prov_config:
            active_providers.add(prov_config[layer_key].lower())
    
    configured_creds = set(creds_config.keys()) if isinstance(creds_config, dict) else set()
    
    for provider in ["aws", "azure", "google"]:
        provider_in_providers = provider in active_providers
        provider_in_creds = provider in configured_creds
        provider_folder_exists = _check_provider_folder_in_zip(zf, provider)
        
        if provider_in_providers and provider_in_creds and not provider_folder_exists:
            warnings.append(f"Provider '{provider}' is configured but its assets folder is missing in zip.")
        
        if provider_folder_exists:
            # Strict: All required functions for this provider must exist
            missing = _check_required_functions_for_provider(zf, provider, prov_config)
            if missing:
                raise ValueError(f"Provider '{provider}' folder exists but missing required functions: {missing}")
    
    return warnings
```

---

### Component: API

#### [MODIFY] projects.py
- **Path:** `d:/Git/master-thesis/3-cloud-deployer/src/api/projects.py`
- **Description:** Add new endpoints and update existing ones.

**New Endpoints:**
```python
@router.delete("/projects/{project_name}", tags=["Projects"])
def delete_project_endpoint(project_name: str):
    """
    Deletes a project and all its versions.
    """
    try:
        # Check if active project
        if state.get_active_project() == project_name:
            state.set_active_project(None)
        
        file_manager.delete_project(project_name)
        return {"message": f"Project '{project_name}' deleted successfully."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/projects/{project_name}/info", tags=["Projects"])
async def update_project_info_endpoint(project_name: str, request: Request):
    """
    Updates project metadata (description).
    Body: {"description": "New description"}
    """
    try:
        body = await request.json()
        description = body.get("description")
        if not description:
            raise HTTPException(status_code=400, detail="Missing 'description' field.")
        
        file_manager.update_project_info(project_name, description)
        return {"message": f"Project info updated for '{project_name}'."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
```

**Modified create_project:**
```python
@router.post("/projects", tags=["Projects"])
async def create_project(
    request: Request, 
    project_name: str = Query(..., description="Name of the new project"),
    description: str = Query(None, description="Optional project description")
):
    """
    Upload a new project zip file with optional description.
    """
    try:
        content = await extract_file_content(request)
        result = file_manager.create_project_from_zip(project_name, content, description=description)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # ...
```

**Modified upload_simulator_payloads (fix path):**
```python
@router.put("/projects/{project_name}/simulator/payloads", tags=["Projects"])
async def upload_simulator_payloads(project_name: str, request: Request):
    """
    Uploads payloads.json for the simulator (provider-agnostic).
    """
    try:
        content = await extract_file_content(request)
        content_str = content.decode('utf-8')
        
        is_valid, errors, warnings = validator.validate_simulator_payloads(content_str, project_name=project_name)
        
        if not is_valid:
            raise ValueError(f"Payload validation failed: {errors}")
            
        # Save to iot_device_simulator root (not per-provider)
        path = os.path.join(state.get_project_base_path(), "upload", project_name, CONSTANTS.IOT_DEVICE_SIMULATOR_DIR_NAME)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, CONSTANTS.PAYLOADS_FILE), "w") as f:
            f.write(content_str)
            
        return {"message": "Payloads uploaded successfully.", "warnings": warnings}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 4. Implementation Phases

### Phase 1: Constants & Core Validation
| Step | File | Action |
|------|------|--------|
| 1.1  | `src/constants.py` | Add `PROJECT_INFO_FILE`, `PAYLOADS_FILE`, `PROJECT_VERSIONS_DIR_NAME`, `IOT_DEVICE_SIMULATOR_DIR_NAME`. |
| 1.2  | `src/validator.py` | Update `validate_project_zip` to return warnings list. |
| 1.3  | `src/validator.py` | Implement `_check_provider_folder_in_zip` helper. |
| 1.4  | `src/validator.py` | Implement `_check_required_functions_for_provider` helper. |
| 1.5  | `src/validator.py` | Add strict structure check (error if folder exists but functions missing). |
| 1.6  | `src/validator.py` | Add warning logic (provider configured but folder missing). |

### Phase 2: File Manager Enhancements
| Step | File | Action |
|------|------|--------|
| 2.1  | `src/file_manager.py` | Add `from datetime import datetime` import. |
| 2.2  | `src/file_manager.py` | Implement `_archive_zip_version` helper. |
| 2.3  | `src/file_manager.py` | Implement `_write_project_info` helper. |
| 2.4  | `src/file_manager.py` | Update `create_project_from_zip` signature and logic. |
| 2.5  | `src/file_manager.py` | Update `update_project_from_zip` signature and logic. |
| 2.6  | `src/file_manager.py` | Implement `delete_project`. |
| 2.7  | `src/file_manager.py` | Implement `update_project_info`. |

### Phase 3: API Layer
| Step | File | Action |
|------|------|--------|
| 3.1  | `src/api/projects.py` | Update `create_project` endpoint signature (add `description`). |
| 3.2  | `src/api/projects.py` | Update `update_project_zip` endpoint signature (add `description`). |
| 3.3  | `src/api/projects.py` | Add `DELETE /projects/{project_name}` endpoint. |
| 3.4  | `src/api/projects.py` | Add `PATCH /projects/{project_name}/info` endpoint. |
| 3.5  | `src/api/projects.py` | Fix `upload_simulator_payloads` path (remove provider subfolder). |
| 3.6  | `src/api/projects.py` | Update `list_projects` to include descriptions and version counts. |

---

## 5. Verification Checklist

**Environment:** All tests run inside Docker.
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v
```

### 5.1 Unit Tests to Create

| Test File | Test Case | Description |
|-----------|-----------|-------------|
| `tests/unit/test_file_manager_versioning.py` | `test_archive_zip_version_creates_file` | Verify zip is saved to `versions/` with timestamp. |
| `tests/unit/test_file_manager_versioning.py` | `test_archive_zip_multiple_versions` | Verify multiple uploads create multiple version files. |
| `tests/unit/test_file_manager_versioning.py` | `test_write_project_info_with_description` | Verify `project_info.json` is created with provided description. |
| `tests/unit/test_file_manager_versioning.py` | `test_write_project_info_default_description` | Verify description is auto-generated from `digital_twin_name`. |
| `tests/unit/test_file_manager_versioning.py` | `test_write_project_info_missing_twin_name_raises` | Verify error if `digital_twin_name` is missing. |
| `tests/unit/test_file_manager_crud.py` | `test_delete_project_removes_folder` | Verify `shutil.rmtree` is called. |
| `tests/unit/test_file_manager_crud.py` | `test_delete_nonexistent_project_raises` | Verify `ValueError` for missing project. |
| `tests/unit/test_file_manager_crud.py` | `test_update_project_info_updates_description` | Verify `project_info.json` is updated. |
| `tests/unit/test_validator_strict.py` | `test_strict_provider_folder_missing_function_raises` | Verify error if `lambda_functions/dispatcher` is missing when AWS folder exists. |
| `tests/unit/test_validator_strict.py` | `test_warning_provider_configured_but_folder_missing` | Verify warning is returned (not error). |
| `tests/unit/test_validator_strict.py` | `test_missing_digital_twin_name_raises` | Verify mandatory field check. |

### 5.2 Integration Tests to Create

| Test File | Test Case | Description |
|-----------|-----------|-------------|
| `tests/integration/test_api_projects_crud.py` | `test_create_project_with_description` | POST with description, verify `project_info.json`. |
| `tests/integration/test_api_projects_crud.py` | `test_create_project_default_description` | POST without description, verify auto-generated. |
| `tests/integration/test_api_projects_crud.py` | `test_create_project_creates_version` | Verify `versions/` folder created with zip. |
| `tests/integration/test_api_projects_crud.py` | `test_update_project_creates_new_version` | Verify second upload creates second version. |
| `tests/integration/test_api_projects_crud.py` | `test_delete_project_success` | DELETE project, verify removed. |
| `tests/integration/test_api_projects_crud.py` | `test_delete_active_project_clears_state` | DELETE active project, verify state reset. |
| `tests/integration/test_api_projects_crud.py` | `test_delete_nonexistent_project_404` | DELETE missing project, verify 404. |
| `tests/integration/test_api_projects_crud.py` | `test_patch_project_info` | PATCH description, verify updated. |
| `tests/integration/test_api_projects_crud.py` | `test_upload_payloads_provider_agnostic` | Upload payloads, verify path is `iot_device_simulator/payloads.json`. |

### 5.3 Edge Case Tests

| Test File | Test Case | Description |
|-----------|-----------|-------------|
| `tests/integration/test_api_projects_edge.py` | `test_upload_corrupt_zip_no_version_created` | Corrupt zip fails validation, no `versions/` entry. |
| `tests/integration/test_api_projects_edge.py` | `test_upload_zip_missing_config_file` | Missing `config.json` raises 400. |
| `tests/integration/test_api_projects_edge.py` | `test_upload_zip_invalid_json_config` | Malformed JSON in `config.json` raises 400. |
| `tests/integration/test_api_projects_edge.py` | `test_upload_zip_missing_digital_twin_name` | Missing mandatory field raises 400. |
| `tests/integration/test_api_projects_edge.py` | `test_upload_zip_provider_configured_no_folder_warning` | AWS in config but no folder → warning returned. |
| `tests/integration/test_api_projects_edge.py` | `test_upload_zip_provider_folder_exists_missing_function_error` | AWS folder exists but `dispatcher` missing → 400. |
| `tests/integration/test_api_projects_edge.py` | `test_create_project_already_exists_400` | Duplicate name raises 400. |
| `tests/integration/test_api_projects_edge.py` | `test_update_info_nonexistent_project_404` | PATCH missing project returns 404. |
| `tests/integration/test_api_projects_edge.py` | `test_timestamp_format_in_version_filename` | Verify version filename matches `YYYY-MM-DD_HH-MM-SS.zip`. |

---

## 6. Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Timestamp format:** `YYYY-MM-DD_HH-MM-SS` | Human-readable, filesystem-safe, sortable. |
| **Warnings vs. Errors:** Provider folder missing = WARNING, Function missing in existing folder = ERROR | Allows partial uploads while catching structural problems. |
| **Mandatory `digital_twin_name`:** | Core identifier; cannot generate meaningful default description without it. |
| **Payloads provider-agnostic:** | Payload structure is identical across providers; reduces duplication. |
| **`project_info.json` in project root:** | Keeps metadata co-located with project files for portability. |
| **Duplicate Detection:** Same `digital_twin_name` + same credentials = conflict | Prevents accidental resource collisions in cloud deployments. |

---

## 7. Additional Validation: Duplicate Project Detection

### 7.1 Problem
If two projects have the **same `digital_twin_name`** AND use **the same cloud credentials**, deploying both would create conflicting resources (e.g., same IoT Thing names, same Lambda function names, same DynamoDB table prefixes). This must be prevented.

### 7.2 Solution
Implement a **duplicate detection check** that:
1. **On Upload:** Scans all existing projects, compares `digital_twin_name` and credentials hash.
2. **Before Deployment:** Re-validates to catch projects created after the initial upload.

### 7.3 Implementation

#### [NEW] validator.py - `check_duplicate_project`
```python
import hashlib

def _hash_credentials(creds: dict) -> str:
    """
    Creates a deterministic hash of credentials for comparison.
    Only hashes the keys that identify the account (not secrets).
    """
    # Use account-identifying fields only
    identity_fields = {
        "aws": ["aws_access_key_id", "aws_region"],
        "azure": ["azure_subscription_id", "azure_tenant_id", "azure_region"],
        "gcp": ["gcp_project_id", "gcp_region"]
    }
    
    hash_input = ""
    for provider, fields in identity_fields.items():
        if provider in creds:
            for field in fields:
                hash_input += str(creds[provider].get(field, ""))
    
    return hashlib.sha256(hash_input.encode()).hexdigest()


def check_duplicate_project(new_twin_name: str, new_creds: dict, exclude_project: str = None, project_path: str = None) -> str | None:
    """
    Checks if another project exists with the same digital_twin_name AND same credentials.
    
    Args:
        new_twin_name: The digital_twin_name of the new/updated project.
        new_creds: The credentials config of the new/updated project.
        exclude_project: Project name to exclude from check (for updates).
        project_path: Base project path.
    
    Returns:
        Name of conflicting project if found, None otherwise.
    """
    if project_path is None:
        project_path = _get_project_base_path()
    
    new_creds_hash = _hash_credentials(new_creds)
    upload_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME)
    
    if not os.path.exists(upload_dir):
        return None
    
    for project_name in os.listdir(upload_dir):
        if project_name == exclude_project:
            continue
        
        project_dir = os.path.join(upload_dir, project_name)
        if not os.path.isdir(project_dir):
            continue
        
        # Read config.json
        config_path = os.path.join(project_dir, CONSTANTS.CONFIG_FILE)
        creds_path = os.path.join(project_dir, CONSTANTS.CONFIG_CREDENTIALS_FILE)
        
        if not os.path.exists(config_path) or not os.path.exists(creds_path):
            continue
        
        try:
            with open(config_path, 'r') as f:
                existing_config = json.load(f)
            with open(creds_path, 'r') as f:
                existing_creds = json.load(f)
            
            existing_twin_name = existing_config.get("digital_twin_name")
            existing_creds_hash = _hash_credentials(existing_creds)
            
            if existing_twin_name == new_twin_name and existing_creds_hash == new_creds_hash:
                return project_name
        except Exception:
            continue
    
    return None
```

#### [MODIFY] file_manager.py - `create_project_from_zip`
Add duplicate check after validation:
```python
def create_project_from_zip(project_name, zip_source, project_path: str = None, description: str = None):
    # ... existing code ...
    
    # Validate before extraction
    warnings = validator.validate_project_zip(zip_source)
    
    # NEW: Extract twin_name and creds from zip for duplicate check
    zip_source.seek(0)
    twin_name, creds = _extract_identity_from_zip(zip_source)
    
    conflicting_project = validator.check_duplicate_project(twin_name, creds, exclude_project=project_name, project_path=project_path)
    if conflicting_project:
        raise ValueError(f"Duplicate project detected: '{conflicting_project}' has the same digital_twin_name and credentials.")
    
    # ... rest of existing code ...
```

#### [MODIFY] deployment.py - Pre-deploy check
Add duplicate validation before starting deployment:
```python
def deploy_layer(project_name, layer, ...):
    # NEW: Pre-deployment duplicate check
    project_dir = os.path.join(project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name)
    config = load_config(os.path.join(project_dir, CONSTANTS.CONFIG_FILE))
    creds = load_config(os.path.join(project_dir, CONSTANTS.CONFIG_CREDENTIALS_FILE))
    
    conflicting_project = validator.check_duplicate_project(
        config.get("digital_twin_name"), 
        creds, 
        exclude_project=project_name
    )
    if conflicting_project:
        raise ValueError(f"Cannot deploy: Project '{conflicting_project}' has conflicting digital_twin_name and credentials.")
    
    # ... existing deployment logic ...
```

---

## 8. Updated Implementation Phases (with Duplicate Detection)

### Phase 4: Duplicate Detection
| Step | File | Action |
|------|------|--------|
| 4.1  | `src/validator.py` | Implement `_hash_credentials` helper. |
| 4.2  | `src/validator.py` | Implement `check_duplicate_project` function. |
| 4.3  | `src/file_manager.py` | Implement `_extract_identity_from_zip` helper. |
| 4.4  | `src/file_manager.py` | Add duplicate check to `create_project_from_zip`. |
| 4.5  | `src/file_manager.py` | Add duplicate check to `update_project_from_zip`. |
| 4.6  | `src/api/deployment.py` | Add pre-deployment duplicate check. |

---

## 9. Additional Tests for Duplicate Detection

### 9.1 Unit Tests

| Test File | Test Case | Description |
|-----------|-----------|-------------|
| `tests/unit/test_validator_duplicate.py` | `test_hash_credentials_same_input_same_output` | Verify deterministic hashing. |
| `tests/unit/test_validator_duplicate.py` | `test_hash_credentials_different_region_different_hash` | Verify region affects hash. |
| `tests/unit/test_validator_duplicate.py` | `test_hash_credentials_ignores_secrets` | Verify secrets don't affect hash. |
| `tests/unit/test_validator_duplicate.py` | `test_check_duplicate_no_conflict` | No existing project → returns None. |
| `tests/unit/test_validator_duplicate.py` | `test_check_duplicate_finds_conflict` | Same twin name + creds → returns project name. |
| `tests/unit/test_validator_duplicate.py` | `test_check_duplicate_excludes_self` | Exclude own project during update. |
| `tests/unit/test_validator_duplicate.py` | `test_check_duplicate_different_twin_name_ok` | Same creds but different twin name → no conflict. |
| `tests/unit/test_validator_duplicate.py` | `test_check_duplicate_different_creds_ok` | Same twin name but different creds → no conflict. |

### 9.2 Integration Tests

| Test File | Test Case | Description |
|-----------|-----------|-------------|
| `tests/integration/test_api_projects_duplicate.py` | `test_create_project_duplicate_twin_and_creds_400` | Upload with matching twin+creds fails. |
| `tests/integration/test_api_projects_duplicate.py` | `test_create_project_same_twin_different_creds_ok` | Same twin name, different credentials succeeds. |
| `tests/integration/test_api_projects_duplicate.py` | `test_update_project_no_self_conflict` | Updating own project doesn't trigger duplicate error. |
| `tests/integration/test_api_projects_duplicate.py` | `test_deploy_blocked_if_duplicate_exists` | Deployment fails if conflict detected. |

### 9.3 Edge Cases

| Test File | Test Case | Description |
|-----------|-----------|-------------|
| `tests/integration/test_api_projects_duplicate_edge.py` | `test_check_duplicate_corrupted_existing_project_skipped` | Corrupted project config doesn't crash check. |
| `tests/integration/test_api_projects_duplicate_edge.py` | `test_check_duplicate_partial_credentials_handled` | Missing credential fields don't crash. |
| `tests/integration/test_api_projects_duplicate_edge.py` | `test_deploy_race_condition_check` | Duplicate created after upload but before deploy is caught. |
