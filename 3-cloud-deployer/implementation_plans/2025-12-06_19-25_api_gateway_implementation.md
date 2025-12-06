# Implementation Plan - API Gateway Data Access Layer

**Goal**: Implement the missing `create_api`, `destroy_api`, and Hot Reader Integration logic in `src/aws/core_deployer_aws.py` to support Layer 3 Data Access.

## User Review Required
> [!NOTE]
> This utilizes the existing `aws_apigateway_client` (v2/HTTP API) initialized in `globals_aws.py`.
> The implementation matches the logic provided by the user, adapted to use the project's `globals_aws` context.

## Proposed Changes

### AWS Core Deployer
#### [MODIFY] [core_deployer_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/src/aws/core_deployer_aws.py)
- Implement `create_api()`: Creates HTTP API and `$default` auto-deployed stage.
- Implement `destroy_api()`: Deletes the API by ID (using helper).
- Implement `create_api_hot_reader_integration()`:
    - Creates `AWS_PROXY` integration for Hot Reader Lambda.
    - Creates Route `GET /{function_name}`.
    - Adds Lambda permission for API Gateway invoke.
- Implement `destroy_api_hot_reader_integration()`:
    - Removes Lambda permission.
    - Deletes Route and Integration.

## Verification Plan

### Automated Tests
- [x] Run **existing** tests in `tests/integration/aws/test_aws_api_gateway.py` which mimic the creation/destruction flow.
    - Command: `./run_tests.ps1` (or specific file via docker)
    - *Note*: These tests confirm the function calls are structurally correct and use the clients properly.

### Manual Verification
- None required as this is a library capability; integration tests cover the logic.
