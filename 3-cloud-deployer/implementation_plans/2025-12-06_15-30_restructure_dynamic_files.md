# Restructure Dynamic Files to /upload

**Date:** 2025-12-06  
**Project:** 3-cloud-deployer

## Goal Description
To organize dynamic user-uploaded content by consolidating configuration files (`config*.json`), Lambda functions, and Event Actions into a dedicated `upload/` directory. This aligns with the "clean separation" principle and simplifies file management.

## User Review Required
> [!NOTE]
> This change moves core configuration files. Ensure any external scripts or CI/CD pipelines invoking the deployer are aware of the new location if they bind-mount files directly (Docker bind-mounts might need update if they mount specific files).
> **However**, the `development_guide.md` implies we work inside the container where `/app` is the root. The Dockerfile `COPY . /app` means `upload/` will be inside `/app/upload`, so code changes should be sufficient.

## Proposed Changes

### 3-cloud-deployer

#### [MOVE] File Consolidation
Move the following files/directories into `d:\Git\master-thesis\3-cloud-deployer\upload\`:
- `config.json`
- `config_credentials.json` (and `.example` if present)
- `config_events.json`
- `config_hierarchy.json`
- `config_iot_devices.json`
- `config_providers.json`
- directory: `lambda_functions/`
- directory: `event_actions/`

#### [MODIFY] [src/globals.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/globals.py)
*   Update `project_path()` or `initialize_*` functions to look for config files in `upload/`.

#### [MODIFY] [src/constants.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/constants.py)
*   Update `BASE_CONFIG_DIR` to point to `Path("upload")` instead of `Path(".")`.

#### [MODIFY] [src/aws/globals_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/globals_aws.py)
*   Update `lambda_functions_path` to `"upload/lambda_functions"`.
*   Update `event_actions_path` to `"upload/event_actions"`.

## Verification Plan

### Automated Tests
- [x] Run the full test suite within the Docker container.
    ```bash
    docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/
    ```

### Manual Verification
- [x] Verify the directory structure looks clean.
- [x] Check if `python src/main.py` (or entry point) starts correctly without `FileNotFoundError`.
