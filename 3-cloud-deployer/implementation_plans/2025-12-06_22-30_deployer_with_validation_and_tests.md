# Implementation Plan - Deployer Enhancements & Validation

## Goal
Implement validation logic for project uploads, refactor state machine definitions to be user-configurable, and fix deployment logic for event actions, with comprehensive test coverage.

## User Review Required
> [!IMPORTANT]
> **State Machine Move**: `src/state_machines` will be moved to `upload/template/state_machines`.
> **Validation Logic**: Stricter validation will prevent deployment if `config_optimization.json` flags are set but corresponding files are missing.
> **Testing**: Detailed unit tests will be added to `tests/unit/test_validation.py` to cover all new structure checks.

## Proposed Changes

### 1. Refactor State Machines
#### [MOVE & MODIFY] State Machine Definitions
- Move `src/state_machines` content to `upload/template/state_machines`.
- **Files**:
    - `upload/template/state_machines/aws_step_function.json`
    - `upload/template/state_machines/azure_logic_app.json`

#### [MODIFY] [src/constants.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/constants.py)
- Add constants:
    - `STATE_MACHINES_DIR_NAME = "state_machines"`
    - `AWS_STATE_MACHINE_FILE = "aws_step_function.json"`
    - `AZURE_STATE_MACHINE_FILE = "azure_logic_app.json"`
    - `LAMBDA_FUNCTIONS_DIR_NAME = "lambda_functions"`

#### [MODIFY] [src/aws/core_deployer_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/core_deployer_aws.py)
- **Update `create_lambda_chain_step_function`**:
    - Change path resolution to use `util.get_path_in_project(CONSTANTS.STATE_MACHINES_DIR_NAME)`.
    - Use `CONSTANTS.AWS_STATE_MACHINE_FILE`.

### 2. Validation Logic (File Manager)
#### [MODIFY] [src/file_manager.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/file_manager.py)
- **Implement `verify_project_structure(project_name)`**:
    - **Step 1: Basic Configs**: Verify `REQUIRED_CONFIG_FILES` exist.
    - **Step 2: Optimization Dependencies**: Read `config_optimization.json` (if exists).
        - Check `result.optimization.useEventChecking` (bool).
        - **If True**:
            - Verify `config_events.json` exists.
            - **Event Actions**: For each event in `config_events.json` where `action.type == "lambda"`, verify folder `upload/{project_name}/event_actions/{action.functionName}` exists.
            - **Feedback**: If `result.optimization.returnFeedbackToDevice` is True, verify `upload/{project_name}/lambda_functions/event-feedback` exists.
            - **Workflows**: If `result.optimization.triggerNotificationWorkflow` is True, verify `upload/{project_name}/state_machines/{provider_file}` exists.
    - **Step 3: Schema Validation**: Call `validate_config_content` for all loaded JSONs.

#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/3-cloud-deployer/rest_api.py)
- Call `verify_project_structure(project_name)` in the validation endpoint or before major operations.

### 3. Fix Deployer Logic
#### [MODIFY] [src/aws/event_action_deployer_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/event_action_deployer_aws.py)
- Ensure `deploy_lambda_actions` is called inside `deploy_layer_2`.

### 4. Comprehensive Testing Strategy
#### [UPDATE] [tests/unit/test_validation.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/test_validation.py)
**New Test Cases for `verify_project_structure`:**
1.  **`test_verify_project_structure_missing_file`**: remove `config.json` -> Assert `ValueError`.
2.  **`test_verify_project_structure_success`**: Mock a full valid project structure -> Assert Success.
3.  **`test_verify_project_structure_optimization_events_missing`**:
    - Set `config_optimization` with `useEventChecking=True`.
    - Do NOT provide `config_events.json`.
    - Assert `ValueError("Missing config_events.json")`.
4.  **`test_verify_project_structure_missing_action_code`**:
    - `config_events.json` has action `func1`.
    - Mock filesystem `exists` to return False for `event_actions/func1`.
    - Assert `ValueError("Missing code for event action: func1")`.
5.  **`test_verify_project_structure_missing_feedback_code`**:
    - `returnFeedbackToDevice=True`.
    - Mock filesystem missing `lambda_functions/event-feedback`.
    - Assert `ValueError("Missing event-feedback function")`.
6.  **`test_verify_project_structure_missing_workflow_def`**:
    - `triggerNotificationWorkflow=True`.
    - Mock filesystem missing `state_machines/aws_step_function.json`.
    - Assert `ValueError("Missing state machine definition")`.

**Updates for Schema Validation:**
- Add test case for `config_optimization.json` schema validation specifically checking the nested `result.optimization` structure.

#### [CHECK] Testing Deploy Logic
- Verify calls to `deploy_lambda_actions` in `deploy_layer_2`.

## Verification Plan
- Run `pytest tests/unit/test_validation.py`.
