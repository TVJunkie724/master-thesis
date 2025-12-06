# Multi-Project Support Implementation Plan

## Goal
Enable the `3-cloud-deployer` application to manage multiple distinct digital twin configurations ("projects"), allowing users to switch between them dynamically, upload new projects as zip files, and ensure safe deployment operations.

## Proposed Changes

### 1. File System Restructuring
- **Root Directory**: `upload/` becomes the root for all projects.
- **Template Project**: Move all existing configuration files from `upload/` to `upload/template/`.
- **Dynamic Paths**: All code reference to `upload/` files must be updated to use a dynamic path based on the *active* project.

### 2. Core Logic Updates
- **`src/globals.py`**:
    - Add `CURRENT_PROJECT` variable (default: "template").
    - Add `set_active_project(name)` function.
    - Add `get_project_upload_path()` helper.
    - Update `initialize_*` functions to load files from `get_project_upload_path()`.
- **`src/util.py`**:
    - Add `get_path_in_project(subpath)` helper for consumers.

### 3. New Module: `src/file_manager.py`
- **Purpose**: specific logic for handling project files (uploads, validation).
- **Functions**:
    - `create_project_from_zip(name, zip_source)`: Extracts zip to `upload/<name>`.
    - `validate_project_zip(zip_source)`: Checks for required config files.
    - `list_projects()`: Returns available directories in `upload/`.
    - `update_config_file`: Updates a specific JSON file and triggers hot-reload.

### 4. CLI (`src/main.py`) Integration
- **New Commands**:
    - `set_project <name>`
    - `list_projects`
    - `create_project <zip> <name>`
- **Safety Checks**:
    - `deploy`, `destroy`, `check` commands must verify that the requested project context matches `globals.CURRENT_PROJECT`.

### 5. API (`rest_api.py`) Integration
- **New Endpoints**:
    - `GET /projects`
    - `POST /projects` (Upload zip)
    - `PUT /projects/{name}/activate`
    - `PUT /projects/{name}/config/{type}`
- **Safety Checks**:
    - All state-dependent endpoints must accept `project_name` query param and validate it against `globals.CURRENT_PROJECT`.

## Verification Strategy
- **Automated Script**: `src/verify_projects.py` to test creation, switching, and cleanup.
- **Manual Check**: Startup check in Docker.
