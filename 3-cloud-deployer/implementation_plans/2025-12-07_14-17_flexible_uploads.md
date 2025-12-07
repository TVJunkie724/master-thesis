# Flexible Upload Endpoints (Binary & Base64)

## Goal Description
Enable API endpoints that handle file uploads to accept either:
1.  **Multipart/Form-Data** (Standard binary upload).
2.  **Application/JSON** (Base64 encoded string).

This addresses the user's need for variable input types while maintaining a unified API surface.

## User Review Required
- **Design Pattern**: Endpoints will inspect the `Content-Type` header.
    - If `multipart/form-data`, it expects a file field (e.g., `file`).
    - If `application/json`, it expects a JSON body with a `file_base64` field (and optional `filename`).
- **Swagger UI**: Note that due to this dynamic behavior, Swagger/OpenAPI auto-generation might show the endpoint as generic or defaulting to one type unless manually overlaid. I will attempt to document both.

## Proposed Changes

### `3-cloud-deployer`

#### [NEW] `api/utils.py`
- [x] `async def extract_file_content(request: Request, file_field: str = "file", base64_field: str = "file_base64") -> bytes`
    - Checks `Content-Type`.
    - Handles logic for determining the content.
    - Returns `bytes`.

#### [MODIFY] `api/dependencies.py`
- [x] Add `Base64FileRequest` Pydantic model:
  ```python
  class Base64FileRequest(BaseModel):
      file_base64: str
      filename: Optional[str] = None
  ```

#### [MODIFY] `api/projects.py`
Refactor the following endpoints to use `request: Request` and `api.utils.extract_file_content`:
- [x] `POST /projects` (Create)
- [x] `POST /projects/{project_name}/upload/zip`
- [x] `PUT /projects/{project_name}/config/{config_type}`
- [x] `POST /projects/{project_name}/functions/{function_name}/file`
- [x] `PUT /projects/{project_name}/state_machines/{provider}`

#### [MODIFY] `api/validation.py`
Refactor the following endpoints:
- [x] `POST /validate/zip`
- [x] `POST /validate/config/{config_type}`
- [x] `POST /validate/state-machine`

## Verification Plan

### Automated Tests
- [x] **New Test File**: `tests/api/test_uploads.py`
    - [x] **Test 1**: Upload zip as **Binary** (Regression).
    - [x] **Test 2**: Upload zip as **Base64** string.
    - [x] **Test 3**: Upload config as **Binary**.
    - [x] **Test 4**: Upload config as **Base64**.
    - [x] **Test 5**: Test invalid Base64 string (should 400).
    - [x] **Test 6**: Test mismatched Content-Type.
