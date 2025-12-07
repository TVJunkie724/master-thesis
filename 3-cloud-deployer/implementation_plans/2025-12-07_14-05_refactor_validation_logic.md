# Refactoring Validation Logic and Extending API Coverage

## Goal Description
1.  Move all validation functions from `src/file_manager.py` to a new module `src/validator.py` to decouple logical checks from file operations.
2.  Implement missing API endpoints to fully expose the validation mechanisms available in the system, including stateless validation for function code.

## User Review Required
- **Move to `src/validator.py`**:
    - [x] `validate_config_content`
    - [x] `validate_project_zip`
    - [x] `validate_state_machine_content`
    - [x] `verify_project_structure`
    - [x] `validate_python_code_aws`
    - [x] `validate_python_code_azure`
    - [x] `validate_python_code_google`
    - [x] `get_provider_for_function`
- **New Endpoints**:
    - [x] `POST /validate/state-machine`: Validate a state machine definition file against the provider's schema (AWS/Azure/Google).
    - [x] `GET /projects/{project_name}/validate`: Trigger `verify_project_structure` to check the integrity of an uploaded project.
    - [x] `POST /validate/function-code`: **(New)** Validate Python code for a specific provider *without* requiring a project context.

## Proposed Changes

### `3-cloud-deployer`

#### [NEW] `src/validator.py`
- [x] Will contain all logic previously in `file_manager.py` between lines 13 and 200, and 328-556.
- [x] Imports: `json`, `ast`, `zipfile`, `os`, `io`, `constants`, `globals`, `logger`.

#### [MODIFY] `src/file_manager.py`
- [x] Remove moved functions.
- [x] Import `validator`.
- [x] Update `create_project_from_zip`, `update_project_from_zip`, `update_config_file`, `update_function_code_file` to use `validator` module.

#### [MODIFY] `api/validation.py`
- [x] Import `validator`.
- [x] **Existing**: Update `validate_zip`, `validate_config`, `validate_function` to use `validator`.
- [x] **New Endpoints**:
    - `POST /validate/state-machine`: Input `file` + `provider` query. Calls `validator.validate_state_machine_content`.
    - `POST /validate/function-code`: Input JSON `{ "provider": "aws", "code": "..." }`. Calls `validator.validate_python_code_{provider}`.

#### [MODIFY] `api/projects.py`
- [x] **New Endpoint**:
    - `GET /projects/{project_name}/validate`: Calls `validator.verify_project_structure`. Returns {valid: true, modules: [...]}.

#### [MODIFY] `api/dependencies.py`
- [x] Add `FunctionCodeValidationRequest` model (provider, code).

## Verification Plan

### Automated Tests
1.  **Refactor Check**: Run `api/check` endpoint.
2.  **State Machine Validation**: `curl -X POST /validate/state-machine...`
3.  **Project Validation**: `curl -X GET /projects/template/validate`
4.  **Function Code Validation**:
    - `curl -X POST /validate/function-code -d '{"provider": "aws", "code": "def lambda_handler(event, context): pass"}'`
    - Verify 200 OK.
    - Test invalid code returns 400.
