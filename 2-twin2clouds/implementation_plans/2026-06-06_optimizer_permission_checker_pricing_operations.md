# Implementation Plan: Optimizer Permission Checker Pricing Operations

Issue: #86
Branch: `codex/pricing-catalog-reliability`
Base branch: `master`

## Goal

Align Optimizer credential validation with the AWS Pricing API operations that
the pricing fetcher actually uses. A validation result must not pass when the
later pricing fetch would fail because `GetProducts` or attribute access is
missing.

## Scope

### AWS Checker

- Forward optional `aws_session_token` into `boto3.Session`.
- Keep STS identity validation as the authentication proof.
- Do not require `aws_region` for pricing validation; the checker intentionally
  uses `us-east-1` because the AWS Pricing API is queried there.
- Validate Pricing API access with representative calls for:
  - `pricing:DescribeServices`
  - `pricing:GetAttributeValues`
  - `pricing:GetProducts`
- Return a safe, permission-specific failure message when any required Pricing
  API operation is denied.

### Tests

- Update valid AWS credential tests to expect all required Pricing API calls.
- Add a regression test for missing `GetProducts` permission after
  `DescribeServices` succeeds.
- Add a regression test proving session token forwarding.
- Keep request-body permission endpoint tests green.

## Non-Goals

- No live AWS calls.
- No final cloud deployment least-privilege policy generation.
- No changes to Azure/GCP permissions beyond documenting the current checker
  behavior in this plan.

## Acceptance Criteria

- [ ] AWS checker exercises `DescribeServices`, `GetAttributeValues`, and
  `GetProducts`.
- [ ] AWS session token is passed to `boto3.Session` when supplied.
- [ ] AWS pricing validation works without `aws_region`.
- [ ] Missing Pricing API permissions return `status: invalid` and
  `can_fetch_pricing: false`.
- [ ] Failure messages do not include credential values.
- [ ] Credential checker tests pass in Docker.

## Verification

```bash
docker-compose run 2twin2clouds sh -lc \
  'cd /app && PYTHONPATH=/app pytest tests/integration/test_credentials_checker.py tests/integration/test_credentials_api.py -q'
```
