# Porting Step Functions, Events, and AWS Refactoring Implementation Plan

## Goal
Update `lambda_update`, `lambda_logs`, and `lambda_invoke` commands in `src/main.py` to support an optional `project_name` argument and enforce safety checks against `globals.CURRENT_PROJECT`.

## Proposed Changes
1.  **Imports**: Ensure `file_manager` is available in `src/main.py`.
2.  **Helper Function**: Extract the safety check logic used in `deploy` commands into a reusable function or block.
3.  **Command Logic**:
    - For `lambda_update`, `lambda_logs`, `lambda_invoke`:
        - Fetch list of valid projects using `file_manager.list_projects()`.
        - Check if the *last* argument is a valid project name.
        - If yes:
            - Pop it from `args`.
            - Validate it matches `globals.CURRENT_PROJECT`.
        - Proceed with original logic using the remaining `args`.

## Porting Missing Logic (Step Functions & Events)
### `src/aws/globals_aws.py`
- [x] Initialize `stepfunctions` client (`aws_sf_client`).
- [x] Add name helper functions:
    - `lambda_chain_iam_role_name`
    - `lambda_chain_step_function_name`
    - `event_feedback_iam_role_name`
    - `event_feedback_lambda_function_name`

### `src/aws/core_deployer_aws.py`
- **Step Functions**:
    - [x] Implement `create_lambda_chain_iam_role`.
    - [x] Implement `create_lambda_chain_step_function` (using `src/state_machines/aws_step_function.json`).
    - [x] Implement `destroy_` and `info_` counterparts.
- **Event Feedback**:
    - [x] Implement `create_event_feedback_iam_role`.
    - [x] Implement `create_event_feedback_lambda_function`.
    - [x] Implement `destroy_` and `info_` counterparts.
- **Event Checker Updates**:
    - [x] Update `create_event_checker_iam_role` to include `AWSStepFunctionsFullAccess` and `AWSLambda_ReadOnlyAccess`.
    - [x] Update `create_event_checker_lambda_function` to include `LAMBDA_CHAIN_STEP_FUNCTION_ARN` and `EVENT_FEEDBACK_LAMBDA_FUNCTION_ARN` in environment variables.

## Verification
- **Unit Tests**:
    - [x] Verify `globals_aws` has new client and functions.
- **Integration Tests (Manual/Scripted)**:
    - [x] Run `deploy aws <project>` and verify:
        - Step Function exists.
        - Event Feedback Lambda exists.
        - Event Checker Lambda has correct env vars.
    - [x] Run `destroy aws <project>` and verify cleanup.

## Refactoring AWS Utilities
- [x] Move `link_to_*` and `iot_rule_exists` from `src/util.py` to `src/aws/util_aws.py`.
- [x] Update imports in `src/aws/info_aws.py` (use `util_aws` instead of `util`).
- [x] Update imports in `src/aws/core_deployer_aws.py` (if any usages exist).
- [x] Verify `check aws` command still works.
- [x] Run full test suite.
