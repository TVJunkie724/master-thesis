# Bug Fix Plan: IAM 'Unknown Service' Error in Event Actions

## Symptoms
- `test_redeploy_event_actions` fails with `botocore.exceptions.UnknownServiceError: Unknown service: 'iam'`.
- Passess when run in isolation.
- Only fails in full suite run.

## Potential Causes
1. **Moto/Botocore State Pollution**: Previous tests (API or L4) might leave `botocore` or `moto` global state in a bad way.
2. **Resource Exhaustion**: Previous memory leak (now fixed) might have caused instability, but failure persists.
3. **Mocking Collision**: `rest_api` tests mock `core_deployer`? `test_aws_event_actions` mocks `globals`?
4. **Environment Variables**: `AWS_ACCESS_KEY_ID` etc. might be unset by a previous test?

## Action Items
1. Fix known S3 destruction bug first.
2. If `test_redeploy_event_actions` continues to fail in full suite:
    - Add `aws_credentials` fixture explicitly to `test_redeploy_event_actions` (though `mock_aws_context` has it).
    - Add explicit `boto3.setup_default_session()` in the test setup.
