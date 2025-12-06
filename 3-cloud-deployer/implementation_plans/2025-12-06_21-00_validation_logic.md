# Implementation Plan - Validation Logic & Code Updates

**Goal**: Enhance `file_manager.py` with content validation for configuration files and add a new function `update_function_code_file` for updating Lambda code.

## User Review Required
> [!IMPORTANT]
> **Validation Logic**:
> - `config_credentials.json` will be validated against `REQUIRED_CREDENTIALS_FIELDS` for the selected provider.
> - `config.json` will require `digital_twin_name` and `mode`.
> - Other configs will have basic structure validation (e.g. `config_events.json` must be a list).

## Proposed Changes

### 1. Configuration Constants in [src/constants.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/constants.py)
#### [MODIFY] `REQUIRED_CONFIG_FILES`
- Add `CONFIG_OPTIMIZATION_FILE` to the list.

#### [NEW] `CONFIG_SCHEMAS`
- Define expected fields for each config file based on code analysis:
    - **config.json**: `["digital_twin_name", "auth_files_path", "endpoint", "root_ca_cert_path", "topic", "payload_file_path", "hot_storage_size_in_days", "cold_storage_size_in_days", "mode"]`
    - **config_iot_devices.json**: List of objects with `["id", "type"]`.
    - **config_events.json**: List of objects with `["condition", "action"]`.
        - **Nested Check**: `action` must have `type`, `functionName`.
        - **If `type` == "lambda"`**: optional `feedback` object must have `["iotDeviceId", "payload"]`.
    - **config_optimization.json**: `["result"]`. (Nested check: `result.inputParamsUsed`).
    - **config_hierarchy.json**: List of objects.
        - **Type "entity"**: Must have `["id", "type"]`. Optional `children` (recursive list).
        - **Type "component"**: Must have `["name", "type"]`. If `componentTypeId` is missing, `iotDeviceId` is required.
    - **config_credentials.json**: Defined by `REQUIRED_CREDENTIALS_FIELDS`.

#### [NEW] `FUNCTION_LAYER_MAPPING`
- Map known function types (suffixes or full names) to providers defined in `config_providers.json`:
    - `dispatcher`, `persister`, `event-checker`, `event-feedback`: `"layer_2_provider"`
    - `hot-reader`: `"layer_3_hot_provider"`
    - `hot-to-cold-mover`: `"layer_3_hot_provider"`
    - `cold-to-archive-mover`: `"layer_3_cool_provider"`
    - Note: Device processors (e.g. `*-processor`) implicitly map to `"layer_2_provider"`.

### 2. Validation Logic in [src/file_manager.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/file_manager.py)
> [!IMPORTANT]
> **Universal Validation**: The following modifications ensure that *every* write operation to the file system passes through validation logic.
> - `update_config_file`: Validates content schema.
> - `create_project_from_zip` / `update_project_from_zip`: Validates entire zip content.
> - `update_function_code_file`: Validates python syntax and handler.

#### [NEW] `validate_config_content(filename, content)`
- **Logic**:
    - **JSON Structure**: Ensure valid JSON.
    - **Schema Check**:
        - Use `CONSTANTS.CONFIG_SCHEMAS` to validate presence of required keys.
        - **Credentials Special Case**: If `filename == CONSTANTS.CONFIG_CREDENTIALS_FILE`, validate fields based on the *keys* present (providers) using `CONSTANTS.REQUIRED_CREDENTIALS_FIELDS`.

#### [MODIFY] `update_config_file`
- **Logic**: Call `validate_config_content` before writing to disk. (This covers the existing `PUT /config` endpoint).

#### [MODIFY] `validate_project_zip(zip_source)`
- **Enhancement**: 
    - Iterate through all files in the zip.
    - If a file matches a known config filename (e.g. `config.json`), extract it to memory and call `validate_config_content(filename, content)`.
    - Recursively validate `config_optimization` or any other embedded structures if needed.

#### [NEW] `update_project_from_zip(project_name, zip_source)`
- **Purpose**: Update an existing project from a zip file (merging/overwriting).
- **Logic**:
    - Call `validate_project_zip(zip_source)`.
    - Extract zip to `upload/{project_name}/`, overwriting existing files.

### 3. Provider-Aware Code Validation
#### [NEW] `validate_python_code_aws(code_content)`
- Check for `def lambda_handler(event, context):` using AST.

#### [NEW] `validate_python_code_azure(code_content)`
- Check for `def main(req: func.HttpRequest) -> func.HttpResponse:` (signature check via AST).

#### [NEW] `validate_python_code_google(code_content)`
- Check for a valid entry point function (default to `main` or generic check).

#### [NEW] `get_provider_for_function(project_name, function_name)`
- **Logic**:
    - Load `config_providers.json` for the project.
    - Determine layer based on `function_name` vs `CONSTANTS.FUNCTION_LAYER_MAPPING`.
        - If name ends with `-processor`, assume `"layer_2_provider"`.
    - Return the provider string (e.g., "aws").
    - **Dependency Check**:
        - Check if `config_providers.json` exists for `project_name`.
        - **Crucial**: If missing, raise `ValueError("Missing Project Configuration: config_providers.json must be uploaded before validating function code.")`.

### 4. Function Code Update in [src/file_manager.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/file_manager.py)
#### [NEW] `update_function_code_file(project_name, function_name, file_name, code_content)`
- **Validation**:
    - Verify directory exists.
    - If `file_name.endswith(".py")`:
        - `provider = get_provider_for_function(project_name, function_name)`
        - If `provider == "aws"`: `validate_python_code_aws(code_content)`
        - If `provider == "azure"`: `validate_python_code_azure(code_content)`
        - If `provider == "google"`: `validate_python_code_google(code_content)`
    - Write content.

### 5. API Endpoints (Upload & Validation) in [rest_api.py](file:///d:/Git/master-thesis/3-cloud-deployer/rest_api.py)
#### [NEW] `POST /projects/{project_name}/upload/zip`
- **Input**: `file: UploadFile`
- **Logic**:
    - Read content.
    - Call `file_manager.update_project_from_zip(project_name, content)`.
    - Return success.

#### [NEW] `POST /projects/{project_name}/functions/{function_name}/file`
- **Input**: 
    - `file: UploadFile`
    - `target_filename: str` (Query param, required). **Crucial**: This ensures the file is saved with the correct name (e.g. `lambda_function.py`) regardless of the uploaded file's name.
- **Logic**:
    - Read content.
    - Call `file_manager.update_function_code_file(project_name, function_name, target_filename, content)`.
    - Return success.

#### [NEW] `POST /validate/zip`
- **Input**: `file: UploadFile`
- **Logic**: 
    - Read content.
    - Call `file_manager.validate_project_zip(content)`.
    - Return `{"message": "Project zip is valid."}`.

#### [NEW] `POST /validate/config/{config_type}`
- **Input**: `config_type` (e.g. 'events'), `file: UploadFile`
- **Logic**:
    - Map `config_type` to filename.
    - Read content.
    - Call `file_manager.validate_config_content(filename, json_content)`.
    - Return success.

#### [NEW] `POST /validate/function`
- **Input**: JSON Body `{ "project_name": "...", "function_name": "...", "filename": "...", "code": "..." }`
- **Logic**:
    - `provider = file_manager.get_provider_for_function(project_name, function_name)`
    - Select validator based on provider.
    - Call validator (e.g. `validate_python_code_aws`).
    - Return success.

### 7. Safety & Robustness (Critical Error Prevention)
#### [NEW] Global Safety Measures
- **Path Traversal Prevention ("Zip Slip")**:
    - In `validate_project_zip` and `update_project_from_zip`, strictly validate that `member.filename` does not contain `..` or absolute paths before extraction.
    - **Action**: Raise `ValueError("Malicious file path detected in zip.")` if found.
- **AST Parsing Safety**:
    - In `validate_python_code_*`, wrap `ast.parse(code_content)` in a `try/except SyntaxError` block.
    - **Action**: Catch `SyntaxError` and raise a `ValueError` with the specific line number and error message, ensuring a 400 Bad Request instead of 500 Internal Server Error.
- **Corrupted Config Resilience**:
    - In `get_provider_for_function`, protect the `json.load` call.
    - **Action**: If `config_providers.json` is corrupted (`JSONDecodeError`), raise `ValueError("Project configuration is corrupted. Please re-upload config_providers.json.")`.
- **File Size Limits**:
    - Enforce a reasonable limit (e.g., 50MB) for uploads in `rest_api.py` before reading into memory, if possible, or check length after read.

## Verification Plan

### Automated Tests
- [NEW] **Create [tests/unit/test_validation.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/test_validation.py)**
    - Test `validate_config_content` with valid/invalid credentials, valid/invalid config.json, etc.
    - **Test Dependency**: Call `get_provider_for_function` on a project *without* `config_providers.json` -> Assert `ValueError`.
    - **Test Lambda Validation**: 
        - Prepare a mock project with `config_providers.json` (Layer 2 = AWS).
        - Pass valid AWS Lambda code -> Assert Success.
        - Pass Azure Function code -> Assert Failure.
    - **Test Zip Upload**: call `update_project_from_zip` with mixed valid/invalid zips.
    - **Test Safety**:
        - **Zip Slip**: Create a zip with `../../evil.txt` and assert `ValueError`.
        - **Syntax Error**: Pass invalid Python code `def foo(` -> Assert `ValueError` (not crash).
        - **Corrupted Config**: Mock a corrupted `config_providers.json` -> Assert safe error message.

- [MODIFY] **Update [tests/unit/test_file_manager.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/test_file_manager.py)**
    - Test `update_config_file` now rejects invalid content.
    - Test `update_function_code_file` updates files correctly and handles missing directories.
- [NEW] **Test API Endpoints**:
    - Verify `POST /projects/{project_name}/upload/zip` updates verification.
    - Verify `POST /projects/{project_name}/functions/...` triggers code validation logic.
