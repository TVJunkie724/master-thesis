# Gap Analysis Plan

## Goal
Identify any missing functionality in `3-cloud-deployer` by comparing it file-by-file with the reference `!!3-cloud-deployer`.

## Methodology
Compare the following files sequentially:
1.  `src/aws/globals_aws.py`
2.  `src/aws/core_deployer_aws.py`
3.  `src/aws/iot_deployer_aws.py`
4.  `src/aws/event_action_deployer_aws.py`
5.  `src/aws/lambda_manager.py`

## Findings
*(This section will be populated as analysis proceeds)*

### `src/aws/core_deployer_aws.py`
- [x] [MISSING] `destroy_hot_dynamodb_table` backup logic (Current just deletes, Reference creates backup first).
- [DIFFERENCE] `add_cors_to_twinmaker_s3_bucket`: Current impl is stricter (Grafana origin only). **User Approved: Retain strict logic.**

### `src/aws/event_action_deployer_aws.py`
- [MISSING] `pathToCode` support in `create_lambda_function`. Current hardcodes path. **User Decision: Keep static path. Do not restore.**

### `src/aws/globals_aws.py`
- [MINOR] `processor_lambda_function_name_local` missing but logic is inlined in `iot_deployer_aws`. No action needed.

### `src/aws/iot_deployer_aws.py`
- [VERIFIED] No regression.
- [VERIFIED] `processor_lambda_function_name_local` usage is safely handled via inline check.

## Verification
- [x] Run full test suite (`./run_tests.ps1`) to ensure no regressions.
- [x] Add specific test case to verify DynamoDB backup creation in `tests/integration/aws/test_aws_l3_storage.py`.

### `src/aws/event_action_deployer_aws.py`
- [MISSING] `pathToCode` support in `deploy_lambda_actions`. Reference listens to config override, Current hardcodes connection to `CONSTANTS.EVENT_ACTIONS_DIR_NAME`.

### `src/aws/lambda_manager.py`
- [NEW] No equivalent in Reference. Likely handles redeployment logic.

### `src/aws/iot_deployer_aws.py`
- [VERIFIED] No regression. Current has extra features (e.g. `attributePropertyValueReaderByEntity`).
