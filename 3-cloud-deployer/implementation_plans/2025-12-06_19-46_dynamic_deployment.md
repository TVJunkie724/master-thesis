# Implementation Plan - Dynamic Deployment Logic

**Goal**: Implement dynamic deployment conditionals using `config_optimization.json`. This ensures optional L2 features and L3 API Gateway are only deployed when required, and Lambda functions gracefully handle disabled features.

## User Review Required
> [!IMPORTANT]
> **Logic Dependencies Confirmed**:
> The Data Pipeline is: `Dispatcher -> Processor -> Persister -> Event Checker -> [Step Functions | Feedback]`.
>
> **Deployment Logic**:
> 1. `Event Checker`: Deployed if `useEventChecking` is True.
> 2. `Step Functions`: Deployed if `useEventChecking` **AND** `triggerNotificationWorkflow` are True.
> 3. `Feedback`: Deployed if `useEventChecking` **AND** `returnFeedbackToDevice` are True.
> 4. `API Gateway`: Deployed **ONLY IF**:
>    - The provider currently being deployed IS the `Layer 3 (Hot)` provider.
>    - **AND** (`Layer 3 (Hot)` != `Layer 4` **OR** `Layer 3 (Hot)` != `Layer 5`).

## Proposed Changes

### 1. Configuration Infrastructure
#### [MODIFY] [constants.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/constants.py)
- Add `CONFIG_OPTIMIZATION_FILE = "config_optimization.json"`.

#### [MODIFY] [globals.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/globals.py)
- Add `config_optimization = {}`.
- Implement `initialize_config_optimization()`.
- Add `is_optimization_enabled(param_key)` helper.
- Add `should_deploy_api_gateway(current_provider)` helper:
    - Get `l3_hot`, `l4`, `l5` from `config_providers`.
    - Function returns `True` if `current_provider == l3_hot` **AND** (`l3_hot != l4` OR `l3_hot != l5`).

#### [NEW] [config_optimization.json](file:///d:/Git/master-thesis/3-cloud-deployer/upload/template/config_optimization.json)
- Create template with user-provided JSON.

### 2. Lambda Function Logic Updates
#### [MODIFY] [src/aws/lambda_functions/persister/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/lambda_functions/persister/lambda_function.py)
- **Logic**: Check `os.environ.get("USE_EVENT_CHECKING") == "true"` before invoking Event Checker.

#### [MODIFY] [src/aws/lambda_functions/event-checker/lambda_function.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/lambda_functions/event-checker/lambda_function.py)
- **Logic**:
    - Add support for `action["type"] == "step_function"`.
    - Check `os.environ.get("USE_STEP_FUNCTIONS") == "true"` before invoking Step Function.
    - Check `os.environ.get("USE_FEEDBACK") == "true"` before invoking Feedback Lambda.

### 3. Deployer Logic Updates
#### [MODIFY] [src/aws/core_deployer_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/core_deployer_aws.py)
- Update `create_persister_lambda_function`: Inject `USE_EVENT_CHECKING` env var.
- Update `create_event_checker_lambda_function`: Inject `USE_STEP_FUNCTIONS` and `USE_FEEDBACK` env vars.

#### [MODIFY] [src/deployers/core_deployer.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/deployers/core_deployer.py)
- **`deploy_l2`**:
    - `should_check = is_optimization_enabled("useEventChecking")`
    - `should_workflow = should_check and is_optimization_enabled("triggerNotificationWorkflow")`
    - `should_feedback = should_check and is_optimization_enabled("returnFeedbackToDevice")`
    - **Actions**:
        - If `should_check`: `create_event_checker_*`
        - If `should_workflow`: `create_lambda_chain_step_function` + role
        - If `should_feedback`: `create_event_feedback_*`
- **`deploy_l3`** (or `deploy_l3_hot`):
    - Check `globals.should_deploy_api_gateway(provider)`.
    - If True: `core_aws.create_api()` and `core_aws.create_api_hot_reader_integration()`.

## Verification Plan

### Automated Tests
- [NEW] **Create [tests/integration/aws/test_aws_dynamic_deployment.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/integration/aws/test_aws_dynamic_deployment.py)**
    - **Test 1: Full Deployment** (All flags True, Provider Mismatch) -> Verify all L2/L3 resources created.
    - **Test 2: Minimal Deployment** (All flags False, Provider Match) -> Verify only L2 Persister created, NO API Gateway.
    - **Test 3: Dependency Check** (EventChecking=False, Workflow=True) -> Verify Workflow NOT created.
- [x] **Run All Tests**: Execute `./run_tests.ps1` to ensure no regressions in existing tests.
- [NEW] **Unit Testing for Lambda Logic**:
    - [x] Create [tests/unit/lambda_functions/test_persister.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/lambda_functions/test_persister.py) to verify conditional invocation of Event Checker.
    - [x] Create [tests/unit/lambda_functions/test_event_checker.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/lambda_functions/test_event_checker.py) to verify conditional triggering of Step Functions and Feedback.

## Refinements during Execution
- **Dependency Reordering**: Modified `deploy_l2` in `core_deployer.py` to deploy `Feedback` and `Workflow` *before* `Event Checker`, but nested within the `useEventChecking` block, to ensure ARNs are available for environment variable injection.
- **Path Corrections**: Updated `core_deployer_aws.py` to use `util.get_path_in_project` for `event-feedback` (located in upload) vs `CORE_LAMBDA_DIR` for core services.
- **Bug Fixes**: Restored missing `destroy_event_checker_lambda_function` definition line to prevent immediate deletion during creation.
