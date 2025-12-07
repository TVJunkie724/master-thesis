# Refactor Core Deployer AWS

## Goal Description
The `core_deployer_aws.py` file has grown too large (~2100 lines) and complex. The goal is to refactor this file by splitting its functionality into smaller, manageable modules based on the Deployment Layers (L1-L5) defined in the project roadmap. This will improve maintainability, readability, and testability.

## User Review Required
> [!IMPORTANT]
> This refactoring changes the internal file structure of the `src/aws` package. The `core_deployer_aws.py` file effectively becomes a facade.

## Proposed Changes

### Directory Structure
Create a new directory `src/aws/deployer_layers/` to house the new modules.

### New Modules
1.  **`src/aws/deployer_layers/layer_1_iot.py`**:
    *   Dispatcher IAM Role
    *   Dispatcher Lambda Function
    *   Dispatcher IoT Rule

2.  **`src/aws/deployer_layers/layer_2_compute.py`**:
    *   Persister IAM & Lambda
    *   Event Checker IAM & Lambda
    *   Lambda Chain (Step Function) Roles & logic
    *   Event Feedback IAM & Lambda

3.  **`src/aws/deployer_layers/layer_3_storage.py`**:
    *   Hot Storage (DynamoDB)
    *   Cold Storage (S3)
    *   Archive Storage (S3)
    *   Movers (Hot-to-Cold, Cold-to-Archive) - IAM, Lambdas, Rules
    *   Readers (Hot Reader, Last Entry) - IAM, Lambdas
    *   Writer Function
    *   API Gateway & Integration

4.  **`src/aws/deployer_layers/layer_4_twinmaker.py`**:
    *   TwinMaker Workspace, Roles, Buckets

5.  **`src/aws/deployer_layers/layer_5_grafana.py`**:
    *   Grafana Workspace, Roles
    *   CORS configuration for TwinMaker bucket

6.  **`src/aws/deployer_layers/__init__.py`**:
    *   Expose the layers as a package.

### Additional Cleanup
*   **Constants**: Move all AWS-specific constants (policy ARNs, cron expressions, file logic paths) to `src/constants.py`.
*   **Documentation**: Add detailed docstrings to every function, specifying:
    *   What the function does.
    *   Where the source code is located (e.g., `src/aws/lambda_functions` vs `upload/...`).
    *   Whether it is user-editable or core infrastructure.

### Update `src/aws/core_deployer_aws.py`
The file will be cleared of implementation logic and will instead import all functions from the `deployer_layers` modules and re-export them. This maintains backward compatibility for `src/deployers/core_deployer.py`.

## Verification Plan

### Automated Tests
*   Run the full regression suite `pytest -v` inside the Docker container.
*   The tests check deployment logic. If the refactoring works, all tests should pass without code changes in the tests.

### Manual Verification
*   Verify that `core_deployer_aws.py` exports all attributes expected by `core_deployer.py`.
