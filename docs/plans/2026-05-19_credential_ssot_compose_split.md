# Credential SSOT And Compose Split Implementation Plan

**Date:** 2026-05-19  
**GitHub issue:** [#6](https://github.com/TVJunkie724/master-thesis/issues/6)  
**Roadmap phase:** Phase 4 - Runtime Credentials & Deployment State  
**Status:** Active

## 1. Goal

Finish the credential source-of-truth transition without losing the current
valid local test credentials.

The target state is:

- default local development starts without live cloud credentials,
- real cloud credentials are an explicit opt-in local-cloud mode,
- user/twin deployments reference Management API `CloudConnection` records,
- bootstrap/admin credentials are temporary input only,
- legacy per-twin encrypted credentials remain only as migration fallback,
- Deployer project packages may contain operation-local credential files, but
  repository files, templates, and generated runtime folders are not credential
  sources of truth.

## 2. Current Audit

### Compose Profiles

| File | Current behavior | Assessment |
|------|------------------|------------|
| `compose.yaml` | Starts Optimizer, Deployer, Management API, docs, LaTeX profiles. Management API has `SEED_DATA=false`. No root credential mounts. | Good default baseline. Keep credential-free. |
| `compose.cloud.local.yaml` | Mounts `.secrets/local/config.json`, `.secrets/local/config_credentials.json`, `.secrets/local/google-credentials.json`, and `.secrets/local/gcp_credentials.json` into services. Enables Management API seeding with credential files. | Canonical local-cloud override. |
| `compose.credentials.local.yaml` | Deprecated compatibility alias for local cloud tests. Uses the same `.secrets/local/` mount sources. | Keep temporarily for older notes/scripts, then remove after docs and workflows converge on `compose.cloud.local.yaml`. |
| `compose.debug.yaml` | Debug override only. | Not part of credential SSOT unless it starts mounting secrets later. |

### Credential Files And Ownership

| Path group | Current role | Target role |
|------------|--------------|-------------|
| `config_credentials.json`, `gcp_credentials.json`, `google-credentials.json` at repo root | Ignored local credential files from the older local workflow. | No longer mounted by Compose. The user may manually move/copy valid files to `.secrets/local/`. |
| `config.json` at repo root | Tracked runtime config file. | Keep only if it is non-secret. Otherwise replace with example-driven config. |
| `3-cloud-deployer/upload/template/*credentials*.json` | Ignored local test credentials in the legacy template/testing folder. User confirmed these may still be valid and must not be deleted casually. | Preserve until local-cloud tests have an alternative. Do not document as canonical. |
| `3-cloud-deployer/upload/digital-twin/*credentials*.json` | Ignored generated/runtime credential artifacts. | Runtime artifact only; should be generated per operation and disposable. |
| `3-cloud-deployer/templates/digital-twin/config_credentials.json.example` | Versioned example file. | Keep as schema/example only. |
| `*.example` credential files | Placeholder examples. | Keep, but ensure they contain no live values. |

### Code Paths

| Component | Current behavior | Risk |
|-----------|------------------|------|
| Management API CloudConnections | User-scoped encrypted CloudConnection storage exists; twins can bind provider CloudConnections. | Foundation is good, but legacy fallback remains. |
| Management API seed script | Reads `SEED_CREDENTIALS_FILE` and `SEED_GCP_CREDENTIALS_FILE`; creates encrypted user-scoped CloudConnections and binds seeded twins to them. | SSOT-aligned. Legacy per-twin field seeding is disabled by default and available only via explicit compatibility flag. |
| Management API deployment package | Resolves credentials from CloudConnection first, legacy fallback second; writes operation-local `config_credentials.json` and optional `gcp_credentials.json` into the generated Deployer package. | Acceptable transitional boundary, because package is generated from backend state and manifest is secrets-free. |
| Deployer | Current canonical deployment contract still consumes project-local `config_credentials.json` and provider-specific GCP credential file. | Acceptable transitional file contract, but Deployer must not discover repo-root/template credentials. |
| Optimizer | Permission endpoints and pricing fetchers still support `/config/config_credentials.json` and `/config/gcp_credentials.json`. | Should become request/CloudConnection driven for app flows; local project-config verification can remain dev-only. |
| Flutter | CloudConnection UI exists, but the broader wizard still needs later feature slicing and CloudConnection-only UX hardening. | Tracked under Phase 7, especially #38/#72/#73. |

## 3. Target Runtime Modes

| Mode | Compose entrypoint | Credentials | Intended use |
|------|--------------------|-------------|--------------|
| Base dev | `docker compose up -d` | none | Start services, use UI, create CloudConnections manually, run non-cloud tests. |
| Docs | `docker compose --profile docs up -d docs` | none | Documentation authoring. |
| Demo | `compose.demo.yaml` or profile, to be added if needed | fake/demo data only | Thesis demo without real deployments. |
| Local cloud supervised | `compose.cloud.local.yaml` | `.secrets/local/` mounts only | Intentional local cloud validation/deployment with real credentials. |

## 4. Implementation Slices

### Slice 1: Guardrails And Documentation

**Work**

- Document this audit and target runtime model.
- Update #6 with the exact remaining scope.
- Update the refactoring roadmap to mark #6 as the active Phase 4 work item.
- Add a non-destructive credential location check or extend #3 if the check is broader.

**Acceptance**

- Roadmap and issue reflect the actual state.
- No credentials are moved, printed, deleted, or committed.

### Slice 2: Secret Location Normalization

**Status:** Implemented

**Work**

- [x] Introduce `.secrets/local/` as the only local-cloud credential mount source.
- [x] Add `.secrets/` to `.gitignore`.
- [x] Keep placeholder setup docs only; do not commit `.secrets/local/` examples.
- [x] Replace root credential mounts in the local cloud override with `.secrets/local/` mounts.
- [x] Keep a compatibility note for existing root credential files until the user moves them.

**Acceptance**

- `docker compose up -d` remains credential-free.
- Local-cloud mode is explicit.
- No root credential file is required for normal dev.
- Existing valid credentials are not deleted by the change.

### Slice 3: CloudConnection-Based Seed Path

**Status:** Implemented

**Work**

- [x] Convert Management API seeding from legacy per-twin encrypted credential fields to user-scoped CloudConnections.
- [x] Seed twins bind CloudConnections by provider instead of copying credentials into every twin.
- [x] Keep legacy field seeding behind an explicit compatibility flag only if needed.

**Acceptance**

- [x] Seeded twins use CloudConnection references.
- [x] Seed path does not create fresh legacy per-twin secret duplicates by default.
- [x] Tests prove seeded CloudConnection-only twins can validate configured state.
- [x] Tests prove seeded CloudConnection-only twins can generate deployment packages.

### Slice 4: Optimizer And Deployer Local Credential Boundaries

**Work**

- Ensure app-driven validation uses request payloads/CloudConnection-derived payloads, not mounted root files.
- Keep project-config credential verification only for explicit Deployer project/debug APIs.
- Mark legacy `/config` file verification as dev/local-cloud behavior in docs and OpenAPI descriptions.

**Acceptance**

- Normal app flows do not require mounted credential files.
- File-based validation endpoints are clearly transitional or debug-only.
- Tests cover no-credential default behavior.

### Slice 5: Legacy Fallback Exit Plan

**Work**

- Create or update a follow-up issue for removing legacy encrypted per-twin credential fields.
- Define DB migration/backfill constraints.
- Keep fallback code until CloudConnection-only demo/deployment path is verified.

**Acceptance**

- Legacy fallback has a removal plan.
- Current fallback is documented, tested, and lower priority than CloudConnections.

## 5. Security Requirements

- Never read or print real credential file contents during migration.
- Never commit `.secrets/` or live credential files.
- Admin/bootstrap credentials are request-scoped only.
- CloudConnection payloads stay encrypted at rest and redacted in responses/logs.
- Generated deployment packages are operation-local and represented by a
  secrets-free manifest.
- Any file-based credential verification must be explicitly local/dev/debug
  behavior, not the app-level source of truth.

## 6. Verification Plan

```bash
docker compose config
docker compose -f compose.yaml config
docker compose -f compose.yaml -f compose.cloud.local.yaml config
docker compose -f compose.yaml -f compose.credentials.local.yaml config

docker compose run --rm management-api sh -lc \
  'cd /app && PYTHONPATH=/app pytest tests/test_cloud_connections.py tests/test_config_routes.py tests/test_credential_resolution_service.py tests/test_deployment_service.py -q'

docker compose run --rm management-api sh -lc \
  'cd /app && PYTHONPATH=/app pytest tests -q'

docker compose --profile docs run --rm docs mkdocs build --strict

git diff --check
```

## 7. Open Decisions

| Decision | Recommendation |
|----------|----------------|
| Rename `compose.credentials.local.yaml`? | Implemented by adding `compose.cloud.local.yaml`; the old file remains as a deprecated compatibility alias. |
| Move current valid credentials automatically? | No. Document manual move to `.secrets/local/` and never script-copy secret files in a generic migration. |
| Keep root credential compatibility? | No Docker compatibility remains for root credential files. Existing files stay untouched locally until the user manually migrates them. |
| Seed sample twins by default? | No. Keep `SEED_DATA=false` in base compose. |
| Seed through CloudConnections? | Yes. That should be the next implementation slice. |
