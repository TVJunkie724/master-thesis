# Provider Bootstrap And Permission Preflight Plan

**Date:** 2026-05-21  
**GitHub issue:** [#7](https://github.com/TVJunkie724/master-thesis/issues/7)  
**Roadmap phase:** Phase 4 - Runtime Credentials & Deployment State  
**Status:** Active

## 1. Goal

Make cloud credential creation repeatable, least-privilege oriented, and
preflightable before a deployment starts.

The target state is:

- bootstrap/admin credentials are temporary input only,
- generated deployment identities become CloudConnections,
- provider setup is driven by versioned, reviewable bootstrap artifacts,
- missing permissions, APIs, billing, and region constraints fail before
  Terraform/deployment execution,
- every provider gap is explicit rather than hidden in manual console steps.

## 2. Architecture Decision

Bootstrap is a setup boundary, not the normal credential source of truth.

```text
Admin/bootstrap session
  -> provider bootstrap artifact
  -> constrained deployment identity
  -> Management API CloudConnection
  -> admin/bootstrap material discarded
```

The first implementation slice is manual-first and static:

- scripts live under `bootstrap/<provider>/`,
- scripts default to dry-run and require `--apply` for mutations,
- scripts never accept admin secrets as command-line arguments,
- scripts refuse silent long-lived secret/key sprawl for existing identities,
- local output files are not overwritten unless explicitly requested,
- scripts emit CloudConnection create payloads for the currently supported
  auth types,
- provider policy/role definitions stay versioned and reviewable.

This keeps the thesis implementation clean without pretending that a fully
automated enterprise identity broker exists already.

## 3. Implementation Slices

### Slice 1: Versioned Static Bootstrap Artifacts

**Status:** Implemented

**Work**

- [x] Add provider bootstrap scripts for AWS, Azure, and GCP.
- [x] Keep scripts dry-run by default.
- [x] Require `--apply` before cloud mutation.
- [x] Reuse existing provider permission artifacts as reviewable inputs.
- [x] Add explicit rotation flags for existing deployment secrets.
- [x] Refuse to overwrite local output files unless requested.
- [x] Emit CloudConnection-compatible JSON only after generated deployment
  credentials exist.

**Acceptance**

- [x] Each provider has a versioned bootstrap script with placeholders only.
- [x] Admin/bootstrap material is never passed as a script argument.
- [x] Existing deployment identities do not silently accumulate new long-lived
  secrets.
- [x] Generated output matches the currently supported CloudConnection auth
  types: AWS `access_key`, Azure `service_principal`, GCP
  `service_account_key`.

### Slice 2: Management API Bootstrap Contract

**Status:** Implemented

**Work**

- [x] Add request/response schemas for provider bootstrap dry-run and result
  import.
- [x] Keep admin/bootstrap payloads out of the API contract.
- [x] Persist only the generated CloudConnection.
- [x] Add unit tests that simulate provider command results without live cloud
  access.

**Acceptance**

- [x] `POST /cloud-bootstrap/{provider}/plan` returns reviewable dry-run and
  apply commands without executing provider CLIs.
- [x] Plan requests reject undeclared admin material.
- [x] `POST /cloud-bootstrap/import` imports generated bootstrap output through
  the existing CloudConnection service.
- [x] API responses remain secret-safe.

### Slice 3: Provider Preflight Result Model

**Status:** Implemented

**Work**

- [x] Standardize provider preflight responses across Management API and Deployer.
- [x] Map missing APIs, missing roles, billing errors, and region constraints into
  actionable error codes.
- [x] Keep live cloud calls out of default unit/integration tests.

**Acceptance**

- [x] `POST /cloud-connections/{connection_id}/preflight` returns normalized
  preflight checks for Optimizer and Deployer.
- [x] Missing permissions map to `MISSING_PERMISSIONS` with actionable guidance.
- [x] Preflight responses are redacted and do not persist validation status.

### Slice 4: Provider-Specific Hardening

**Status:** Planned

**Work**

- AWS: decide final shape for IAM user vs role/assume-role and Managed Grafana
  Identity Center prerequisites.
- Azure: reduce broad role assignments where feasible and document unavoidable
  role-assignment permissions.
- GCP: verify custom role coverage and API enablement for the current supported
  layers.

## 4. Security Requirements

- Never commit generated CloudConnection output files.
- Never log bootstrap/admin secrets or generated deployment secrets.
- `--apply` scripts must verify active provider account/project/subscription.
- Existing deployment credentials are rotated only through explicit
  provider-specific flags.
- Existing local secret output files are overwritten only with
  `--overwrite-output`.
- Generated credentials should be rotated manually after demos/tests if they
  are printed to a terminal or written to a local file.
- Future API-driven bootstrap must redact downstream provider errors before
  storing validation messages.

## 5. Verification

```bash
bash -n bootstrap/aws/bootstrap_deployment_identity.sh
bash -n bootstrap/azure/bootstrap_deployment_identity.sh
bash -n bootstrap/gcp/bootstrap_deployment_identity.sh
python3 -m json.tool 3-cloud-deployer/docs/references/aws_deployer_policy.json >/dev/null
python3 -m json.tool 3-cloud-deployer/docs/references/azure_deployer_policy.json >/dev/null
docker compose --profile docs run --rm docs mkdocs build --strict
git diff --check
```
