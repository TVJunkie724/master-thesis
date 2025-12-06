# Implementation Plan - Refactor Constants

**Goal**: Centralize configuration filenames, directory names, and default project settings into `src/constants.py` to eliminate hardcoded strings across the codebase.

## User Review Required
> [!NOTE]
> This is a retroactive implementation plan documenting the refactoring work completed on 2025-12-06.

## Proposed Changes

### Constants Definition
#### [MODIFY] [constants.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/constants.py)
- Add constants for:
    - `PROJECT_UPLOAD_DIR_NAME = "upload"`
    - `DEFAULT_PROJECT_NAME = "template"`
    - `CONFIG_FILE = "config.json"`
    - `CONFIG_IOT_DEVICES_FILE = "config_iot_devices.json"`
    - `CONFIG_EVENTS_FILE = "config_events.json"`
    - `CONFIG_HIERARCHY_FILE = "config_hierarchy.json"`
    - `CONFIG_CREDENTIALS_FILE = "config_credentials.json"`
    - `CONFIG_PROVIDERS_FILE = "config_providers.json"`
- Update `REQUIRED_CONFIG_FILES` list to use these new constants.

### Codebase Usage Updates
#### [MODIFY] [globals.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/globals.py)
- Import `constants as CONSTANTS` (already present).
- Replace all hardcoded `"config*.json"` strings with their respective `CONSTANTS.*`.
- Replace `"upload"` with `CONSTANTS.PROJECT_UPLOAD_DIR_NAME`.
- Replace `"template"` with `CONSTANTS.DEFAULT_PROJECT_NAME` for `CURRENT_PROJECT` default.

#### [MODIFY] [file_manager.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/file_manager.py)
- Replace `"upload"` with `CONSTANTS.PROJECT_UPLOAD_DIR_NAME` in `create_project_from_zip`, `list_projects`, and `update_config_file`.
- Replace hardcoded config filenames in the hot-reload logic with constants.

#### [MODIFY] [main.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/main.py)
- Import `constants as CONSTANTS`.
- Replace default `project = "template"` with `CONSTANTS.DEFAULT_PROJECT_NAME`.

## Verification Plan

### Automated Tests
- [x] Run full test suite to ensure no regressions.
    - Command: `./run_tests.ps1` (or `docker exec ... pytest ...`)
    - **Result**: 80/80 tests passed.
