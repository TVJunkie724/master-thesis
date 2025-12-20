# REST API Comprehensive Test Suite - Implementation Plan

## Summary
Create comprehensive tests for all REST API endpoints in the 3-cloud-deployer project, covering:
- **Happy paths**: Valid inputs, successful operations
- **Invalid inputs**: Missing required fields, invalid types, malformed data
- **Error cases**: Non-existent resources, permission errors, server errors
- **Edge cases**: Boundary values, special characters, concurrent access

## Current Test Coverage Analysis

### Existing Test Files
- `test_rest_api.py` - Basic health check, state machine upload (4 tests)
- `test_rest_api_edge_cases.py` - Deployment edge cases, config validation (9 tests)
- `test_simulator.py` - Payload validation, WebSocket, download (29 tests)
- `test_uploads.py` - Binary/base64 uploads (6 tests)
- `test_azure_credentials_checker.py` - Azure permissions (16 tests)

### Gaps Identified
1. **Projects API** - No tests for list, get config, delete, update info, cleanup
2. **Functions API** - No tests for get_updatable_functions, update_function, build_function_zip
3. **Status API** - No tests for infrastructure status endpoint
4. **Deployment API** - Limited edge cases
5. **Validation API** - Missing tests for processor, state-machine endpoints
6. **Credentials API** - No tests for AWS or GCP permission checks from body/config

---

## Proposed Changes

### [NEW] `tests/api/test_projects_api.py`
Comprehensive tests for `/projects` endpoints:

**1. `GET /` (list_projects)**
- Happy: Returns project list with metadata
- Edge: Empty project list
- Edge: Projects with missing info files

**2. `POST /projects` (create_project)**
- Happy: Create with valid zip (multipart)
- Happy: Create with valid zip (base64)
- Invalid: Missing project_name parameter
- Invalid: Invalid project name (special chars)
- Invalid: Duplicate project name with same twin+creds
- Error: Corrupted zip file

**3. `GET /projects/{name}/validate` (validate_project_structure)**
- Happy: Valid project structure
- Invalid: Non-existent project
- Error: Corrupted config files

**4. `GET /projects/{name}/config/{type}` (get_project_config)**
- Happy: Get each config type (config, iot, events, providers, etc.)
- Invalid: Non-existent project
- Invalid: Invalid config type
- Edge: Config file missing but project exists

**5. `PUT /projects/{name}/config/{type}` (update_config)**
- Happy: Update config with valid content
- Invalid: Invalid JSON content
- Invalid: Schema validation failure
- Invalid: Non-existent project

**6. `PUT /projects/{name}/upload/zip` (update_project_zip)**
- Happy: Update existing project
- Invalid: Non-existent project
- Invalid: Invalid zip

**7. `DELETE /projects/{name}` (delete_project)**
- Happy: Delete existing project
- Invalid: Non-existent project
- Edge: Delete active project resets to default

**8. `PATCH /projects/{name}` (update_project_info)**
- Happy: Update description
- Invalid: Missing description field
- Invalid: Non-existent project

**9. `PUT /projects/{name}/state_machines/{provider}` (upload_state_machine)**
- Happy: Upload valid AWS step function
- Invalid: Invalid provider
- Invalid: Invalid state machine schema

**10. `PUT /projects/{name}/simulator/payloads` (upload_simulator_payloads)**
- Happy: Upload valid payloads
- Invalid: Missing iotDeviceId

**11. `DELETE /projects/{name}/cleanup/aws-twinmaker` (cleanup_aws_twinmaker)**
- Invalid: Non-existent project
- Error: Non-AWS project

---

### [NEW] `tests/api/test_functions_api.py`
Comprehensive tests for `/functions` endpoints:

**1. `GET /functions/updatable_functions`**
- Happy: Returns function list for template project
- Invalid: Non-existent project
- Edge: Project with no user functions (only system functions)
- Edge: Cache invalidation works

**2. `POST /functions/update_function/{name}`**
- Invalid: Non-existent function name
- Invalid: Non-existent project
- Edge: Force update flag

**3. `POST /functions/build_function_zip`**
- Happy: Build AWS Lambda zip from valid Python
- Happy: Build Azure Function zip from valid Python
- Happy: Build GCP Cloud Function zip from valid Python
- Invalid: Invalid Python syntax
- Invalid: Missing entry point (lambda_handler for AWS, main for Azure)
- Invalid: Invalid provider
- Edge: With requirements.txt

---

### [NEW] `tests/api/test_status_api.py`
Tests for `/infrastructure/status` endpoint:

**1. `GET /infrastructure/status`**
- Happy: Returns status structure (even if nothing deployed)
- Invalid: Non-existent project
- Edge: With detailed=True flag
- Edge: No terraform state file

---

### [NEW] `tests/api/test_credentials_api.py`
Tests for `/permissions` endpoints:

**1. `POST /permissions/aws/check` (from body)**
- Invalid: Missing required credentials fields
- Invalid: Invalid region format
- Edge: With session token

**2. `GET /permissions/aws/check` (from config)**
- Invalid: Non-existent project
- Edge: Project with no AWS credentials

**3. `POST /permissions/azure/check` (from body)**
- Invalid: Missing required fields
- Invalid: Invalid subscription_id format

**4. `GET /permissions/azure/check` (from config)**
- Invalid: Non-existent project
- Edge: Project with no Azure credentials

**5. `POST /permissions/gcp/check` (from body)**
- Invalid: Missing required fields

**6. `GET /permissions/gcp/check` (from config)**
- Invalid: Non-existent project

---

### [NEW] `tests/api/test_validation_api.py`
Additional tests for `/validate` endpoints:

**1. `POST /validate/zip`**
- Happy: Valid zip passes
- Invalid: Missing required files
- Invalid: Zip slip attack (path traversal)
- Invalid: Invalid JSON in configs

**2. `POST /validate/config/{type}`**
- Happy: Each config type validates successfully
- Invalid: Each config type with schema errors

**3. `POST /validate/state-machine`**
- Happy: Valid AWS step function
- Happy: Valid Azure logic app
- Happy: Valid Google workflow
- Invalid: Invalid JSON
- Invalid: Missing required keys

**4. `POST /validate/function-code`**
- Happy: Valid AWS Lambda code
- Happy: Valid Azure function code
- Invalid: Syntax error
- Invalid: Missing entry point

**5. `POST /validate/processor`**
- Happy: Valid processor with process(event)
- Invalid: Missing process function
- Invalid: Wrong function signature

**6. `POST /validate/payloads-with-devices`**
- Happy: All device IDs match
- Invalid: Unknown device ID
- Invalid: Malformed payloads JSON
- Invalid: Malformed devices JSON

---

### [MODIFY] `tests/api/test_rest_api_edge_cases.py`
Add additional deployment edge cases:
- Test `/infrastructure/deploy` with invalid project context
- Test `/infrastructure/destroy` with non-existent state

---

## Verification Plan

### Automated Tests

Run the full test suite after implementation:
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/api/ -v --tb=short
```

### Test Coverage Check
Run with coverage to verify new tests add significant coverage:
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/api/ --cov=src/api --cov-report=term-missing
```

---

## Implementation Order

1. **Phase 1**: `test_projects_api.py` - Core project management (highest priority)
2. **Phase 2**: `test_validation_api.py` - Input validation endpoints
3. **Phase 3**: `test_functions_api.py` - Function management
4. **Phase 4**: `test_status_api.py` - Status checking
5. **Phase 5**: `test_credentials_api.py` - Permission verification
