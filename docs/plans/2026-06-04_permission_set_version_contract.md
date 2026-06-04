# Permission-Set Version Contract

**Date:** 2026-06-04
**GitHub issue:** [#79](https://github.com/TVJunkie724/master-thesis/issues/79)
**Roadmap phase:** Phase 4 - Runtime Credentials & Deployment State
**Status:** Implemented - offline gates complete, provider hardening in progress

## 1. Executive Summary

### The Problem

Provider bootstrap and preflight mechanics are implemented, but the generated
deployment identities do not yet carry an auditable permission-set version.
That means a CloudConnection can be valid from a raw credential perspective
while still being ambiguous against the current deployer permission baseline.

### The Solution

Introduce `thesis-demo-v1` as the first versioned permission-set contract across
Deployer artifacts, bootstrap output, Deployer preflight responses, and
Management API CloudConnections.

### Impact

Cloud setup becomes reviewable and migratable: existing or stale
CloudConnections can be flagged as `OUTDATED_PERMISSION_SET`, while future
least-privilege hardening can move to `least-privilege-v2` without silently
changing the meaning of stored credentials.

## 2. Current State

```text
bootstrap script
  -> CloudConnection JSON without version
  -> Management API stores encrypted payload
  -> preflight validates provider permissions
  -> no auditable permission-set comparison
```

## 3. Target State

```text
bootstrap script
  -> CloudConnection JSON with permission_set_version
  -> Management API stores version metadata outside the encrypted secret
  -> preflight compares stored version with active provider baseline
  -> OUTDATED_PERMISSION_SET is returned before deployment
```

## 4. Proposed Changes

### Deployer Permission Contract

- **[NEW]** `3-cloud-deployer/src/api/permission_sets.py`
  - Owns the active provider permission-set version and comparison helper.
- **[NEW]** `3-cloud-deployer/docs/references/permission_sets/*.json`
  - Documents `thesis-demo-v1` provider baselines, source artifacts,
    capabilities, known gaps, and verification commands.
  - Includes `deployer_permission_inventory.json`, checked against current
    Terraform provider resource/data types.
- **[MODIFY]** `3-cloud-deployer/src/api/preflight.py`
  - Adds version fields to preflight responses and emits
    `OUTDATED_PERMISSION_SET` when request metadata is missing or stale.
- **[MODIFY]** `3-cloud-deployer/src/api/credentials.py`
  - Accepts optional `permission_set_version` metadata in provider preflight
    requests.
- **[MODIFY]** `3-cloud-deployer/tests/api/test_preflight_api.py`
  - Verifies version fields and outdated behavior.
- **[MODIFY]** `3-cloud-deployer/tests/api/test_bootstrap_permission_artifacts.py`
  - Verifies permission-set artifacts, source-artifact coverage, GCP wildcard
    constraints, and bootstrap metadata.

### Management API Metadata

- **[MODIFY]** `twin2multicloud_backend/src/models/cloud_connection.py`
  - Adds `permission_set_version` as non-secret CloudConnection metadata.
- **[MODIFY]** `twin2multicloud_backend/src/schemas/cloud_connection.py`
  - Adds create/update/read/preflight fields for permission-set metadata.
- **[MODIFY]** `twin2multicloud_backend/src/services/cloud_connection_service.py`
  - Persists the version and exposes it in secret-safe responses.
- **[MODIFY]** `twin2multicloud_backend/src/api/routes/cloud_connections.py`
  - Returns `OUTDATED_PERMISSION_SET` in stored-connection preflight when the
    connection version does not match the active baseline.
- **[NEW]** `twin2multicloud_backend/migrations/add_cloud_connection_permission_set_version.py`
  - Adds the metadata column for existing SQLite databases.
- **[MODIFY]** Management API tests
  - Covers bootstrap import persistence, legacy/unknown connection behavior,
    and migration idempotency.

### Bootstrap And Docs

- **[MODIFY]** `bootstrap/*/bootstrap_deployment_identity.sh`
  - Emits `permission_set_version` in dry-run output and generated
    CloudConnection JSON.
- **[MODIFY]** `docs-site/docs/cloud-setup/index.md`
  - Explains bootstrap/admin permissions, generated deployment permissions,
    versioning, and upgrade behavior.
- **[MODIFY]** `docs-site/docs/architecture/refactoring-roadmap.md`
  - Marks the #79 work as the active Stage 2 contract.

### AWS Pre-E2E Hardening

- **[MODIFY]** `3-cloud-deployer/src/api/credentials_checker.py`
  - Adds CloudWatch Logs permissions for Terraform-managed
    `aws_cloudwatch_log_group` resources.
- **[MODIFY]** `3-cloud-deployer/docs/references/aws_deployer_policy.json`
  - Adds the corresponding `ObservabilityCloudWatchLogs` policy statement.
- **[NEW]** `3-cloud-deployer/docs/references/permission_sets/aws_thesis_demo_v1_scope_review.json`
  - Classifies each AWS policy statement as `global_required`,
    `prefix_scope_candidate`, or `conditioned`.
  - Explicitly records that this is `offline_pre_e2e` validation and requires
    supervised E2E/provider validation before a final least-privilege claim.
- **[MODIFY]** AWS permission artifact tests
  - Ensure every AWS policy statement has a scope-review entry.
  - Ensure checker-required AWS actions are represented in the policy.
  - Ensure `iam:PassRole` remains constrained to `lambda.amazonaws.com`.

## 5. Design Decisions

- `thesis-demo-v1` is a validated thesis/demo baseline, not a claim that every
  provider permission is already perfect least privilege.
- Permission source artifacts remain provider-native. The new permission-set
  artifacts bind those sources to a version and document gaps rather than
  duplicating every action in another manually maintained file.
- Missing permission-set metadata is treated as outdated in deployment
  preflight. This is intentionally conservative: legacy credentials should be
  rotated or re-imported through the versioned bootstrap flow.
- Default tests stay offline. Live cloud smoke validation is documented but not
  run automatically.
- AWS CloudWatch Logs permissions are part of the v1 baseline because Terraform
  creates log groups when `enable_aws_logging` is active. This was caught before
  E2E through the Terraform resource inventory and offline policy/checker
  alignment tests.

## 6. Verification Checklist

- [x] `docker compose run --rm 3cloud-deployer sh -lc 'cd /app && PYTHONPATH=/app:/app/src pytest tests/api/test_bootstrap_permission_artifacts.py tests/api/test_preflight_api.py -q'`
- [x] `docker compose run --rm 3cloud-deployer sh -lc 'cd /app && PYTHONPATH=/app:/app/src pytest tests --ignore=tests/e2e -q'`
- [x] `docker compose run --rm management-api sh -lc 'cd /app && PYTHONPATH=/app pytest tests/test_cloud_bootstrap.py tests/test_cloud_connections.py tests/test_cloud_connections_migration.py tests/test_config_routes.py tests/test_credential_resolution_service.py -q'`
- [x] `docker compose --profile docs run --rm docs mkdocs build --strict`
- [x] `git diff --check`
- [ ] `aws accessanalyzer validate-policy --policy-document file://3-cloud-deployer/docs/references/aws_deployer_policy.json --policy-type IDENTITY_POLICY`

Supervised provider validation with live cloud credentials remains a separate
manual activity. The default test suite intentionally does not mutate cloud
resources.
