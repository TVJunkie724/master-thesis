# Complete Lifecycle Coverage Plan

## Proposed Changes

We will ensure **Complete Lifecycle Coverage** by adding destruction tests for all components in Layers 2, 3, and 4.

### [Test Suite Updates]
#### [MODIFY] [test_aws_l2_compute.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/integration/aws/test_aws_l2_compute.py)
   - Add `test_destroy_persister_iam_role`
   - Add `test_destroy_persister_lambda_function`
   - Add `test_destroy_event_checker_lambda_function`

#### [MODIFY] [test_aws_l3_storage.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/integration/aws/test_aws_l3_storage.py)
   - Add destruction tests for DynamoDB, S3 Buckets, and Movers.

#### [MODIFY] [test_aws_l3_movers.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/integration/aws/test_aws_l3_movers.py)
   - Add destruction tests for Mover roles, lambdas, and event rules.

#### [MODIFY] [test_aws_l3_readers.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/integration/aws/test_aws_l3_readers.py)
   - Add destruction tests for Reader roles and lambdas.

#### [MODIFY] [test_aws_l4_l5_mocked.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/integration/aws/test_aws_l4_l5_mocked.py)
   - Add `test_destroy_twinmaker_workspace` (mocked)
   - Add `test_destroy_twinmaker_iam_role`
   - Add `test_destroy_twinmaker_s3_bucket`
   - Add `test_create_twinmaker_workspace` (mocked)
   - Add `test_create_twinmaker_iam_role`
   - Add `test_create_twinmaker_s3_bucket`
   - Add `test_create_grafana_workspace` (mocked)
   - Add `test_create_grafana_iam_role`
   - Add `test_destroy_grafana_workspace` (mocked)
   - Add `test_destroy_grafana_iam_role`

#### [NEW] [test_aws_event_actions.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/integration/aws/test_aws_event_actions.py)
   - `test_redeploy_event_actions`: Verify `deploy_lambda_actions` and `destroy_lambda_actions` logic.

#### [MODIFY] [test_rest_api.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/api/test_rest_api.py)
   - Add `test_recreate_updated_events`: Verify the API endpoint calls the underlying deployers correctly.

#### [NEW] [test_aws_api_gateway.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/integration/aws/test_aws_api_gateway.py)
    - `test_create_destroy_api`: Verify API Gateway creation/destruction.
    - `test_create_destroy_api_integration`: Verify Lambda integration and routes.

### [Unit Test Updates]
#### [NEW] [test_util.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/test_util.py)
    - `test_validate_credentials`: Verify credential validation logic.
    - `test_contains_provider`: Verify provider config check.
    - `test_resolve_folder_path`: Verify path resolution (mocked fs).
    - `test_zip_directory`: Verify zipping logic (mocked).

#### [NEW] [test_util_aws.py](file:///d:/Git/master-thesis/3-cloud-deployer/tests/unit/test_util_aws.py)
    - `test_iot_rule_exists`: Verify paginator logic (mocked).
    - `test_link_generation`: Verify console link construction for all resources.
    - `test_compile_lambda_function`: Verify zip compilation (mocked).

## Verification Plan

### Automated Tests
- [ ] Run `pytest tests/` to execute the expanded suite (Integration + Unit).
- [ ] Ensure all new tests pass and increased code coverage.
