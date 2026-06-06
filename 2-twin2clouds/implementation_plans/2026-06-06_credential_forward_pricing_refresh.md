# Implementation Plan: Credential-Forward Pricing Refresh Boundaries

Issue: #85
Branch: `codex/pricing-catalog-reliability`
Base branch: `master`

## Goal

Make credential-forward pricing refresh respect the credentials supplied by the
Management API. Request-body refresh must not silently fall back to local
`config_credentials.json`, and Azure public pricing must not require local
credential-file entries.

## Scope

### Optimizer API

- Extend credential-forward request parsing to accept AWS session tokens.
- Keep file-based AWS/GCP refresh restricted to explicit local-cloud mode.
- Keep Azure refresh public and independent of local credential files.
- Preserve existing response shape for now; richer pricing result metadata is
  deferred to #81/#83.

### Pricing Orchestration

- Add a provider-credential normalizer for AWS request-body credentials.
- Pass request-body AWS credentials into `fetch_aws_data`.
- Let `fetch_aws_data` load local AWS credentials only when no explicit client
  credentials were provided.
- Add an Azure public orchestration path that loads service mapping and region
  map without loading the credentials file.
- Keep GCP request-body refresh explicit by requiring request credentials to
  build the billing client.

### Tests

- AWS credential-forward refresh must not call local AWS credential loading.
- AWS session token must be forwarded to the AWS pricing client.
- Azure credential-forward refresh must not call `load_credentials_file`.
- GCP request-body refresh should fail on invalid/missing service-account JSON
  instead of falling back to local credentials.
- Existing pricing and streaming tests must remain green.

## Non-Goals

- No catalog snapshot model.
- No mapping registry.
- No pricing drift detection.
- No live provider calls or E2E cloud tests.
- No final least-privilege policy validation; covered by #86/#79.

## Acceptance Criteria

- [ ] AWS credential-forward refresh does not call local credential loading.
- [ ] Azure request-body/public refresh can run without local credential-file entries.
- [ ] GCP request-body refresh does not silently use local credentials.
- [ ] AWS session token is included when supplied.
- [ ] Regression tests cover the credential boundaries.

## Verification

```bash
docker compose run --rm 2twin2clouds sh -lc \
  'cd /app && PYTHONPATH=/app pytest tests/unit/pricing tests/unit/test_pricing_streaming.py -q'
```
