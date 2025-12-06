# Test Implementation Plan - Multi-Project Support

## Goal
Achieve high test coverage for the newly implemented multi-project support features, including file management, global state management, and API endpoints.

## Proposed Changes

### 1. New Test File: `tests/test_multi_project.py`
This file will contain all unit and integration tests for the new features.

#### Unit Tests (`file_manager.py`, `globals.py`)
- **Zip Validation**:
    - Test valid zip (contains all required files).
    - Test invalid zip (missing files).
    - Test invalid zip (corrupt).
- **Project Creation**:
    - Test creating project from valid zip.
    - Test duplication error (project already exists).
    - Test naming validation (prevent directory traversal).
- **Project Switching**:
    - Test `set_active_project` with valid project.
    - Test `set_active_project` with invalid project.
    - Test `get_project_upload_path` reflects active project.
    - Test `get_path_in_project` resolution.

#### Integration/API Tests (`rest_api.py`)
- **GET /projects**: Verify listing.
- **POST /projects**: upload zip.
- **PUT /projects/{name}/activate**: Switch project.
- **PUT /projects/{name}/config**: Update config.
- **Safety Checks**:
    - Verify `POST /deploy` fails if `project_name` mismatch.
    - Verify `POST /destroy` fails if `project_name` mismatch.

### 2. Execution
- Use `pytest` to run the new tests and existing tests.
- Execute inside the Docker container to ensure environment consistency.

## Verification
- Run `pytest tests/test_multi_project.py` to verify new tests.
- Run `run_tests.sh` (or equivalent) to verify regression.
