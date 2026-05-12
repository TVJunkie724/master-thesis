---
title: "Implementation Plan: Backend Deployment Operation State"
description: "Enterprise-grade plan for persisting Deployer operation ids, typed error codes, and safe lifecycle state in the Management API."
tags: [implementation-plan, backend, deployment-state, observability, enterprise]
lastUpdated: "2026-05-12"
version: "0.1"
---

<!-- SOURCES:
- GitHub Issue #75 "Persist backend deployment operation state"
- 3-cloud-deployer/src/api/models/deployment.py
- twin2multicloud_backend/src/models/deployment.py
- twin2multicloud_backend/src/repositories/deployment_repository.py
- twin2multicloud_backend/src/services/deployment_service.py
- twin2multicloud_backend/src/api/routes/twins.py
- twin2multicloud_backend/src/api/routes/sse.py
- twin2multicloud_backend/tests/test_deployment_repository.py
- twin2multicloud_backend/tests/test_deployment_service.py
EXTRACTED: 2026-05-12 | VERSION: 0.1
-->

# Implementation Plan: Backend Deployment Operation State

**Date:** 2026-05-12
**Scope:** `twin2multicloud_backend`
**GitHub issue:** [#75](https://github.com/TVJunkie724/master-thesis/issues/75)
**Base branch:** `master`
**Implementation branch:** `codex/flutter-credential-ssot-runtime-config`
**Plan status:** Approved
**Implementation status:** Implemented

---

## 1. Why This Phase Exists

The Deployer now emits an enterprise-grade deploy/destroy contract:

- operation-scoped `operation_id`,
- typed `error_code`,
- safe redacted error messages,
- SSE terminal payloads with operation metadata.

The Management API still stores deployment history mostly as session-local
state: `session_id`, generic `status`, optional outputs, and a loose
`error_message`. That means Flutter, developer docs, and thesis debugging cannot
reliably answer: Which Deployer operation failed? Was it a validation,
Terraform, workspace sync, deploy, or destroy error? Which operation id should
be used to correlate backend logs with Deployer logs?

This slice makes the backend deployment history the source of truth for the
runtime lifecycle metadata that the Deployer now produces.

---

## 2. Target State

Each real deploy/destroy stream produces one backend `Deployment` record that
contains:

- backend `session_id`,
- Deployer `operation_id`,
- `operation_type` (`deploy` or `destroy`),
- lifecycle `status` (`running`, `success`, `failed`),
- typed `error_code` for failed operations,
- safe user-facing `error_message`,
- Terraform outputs for successful deploys,
- started/completed timestamps.

The public backend read paths expose this metadata:

- `GET /twins/{id}/deployment-status`
- `GET /twins/{id}/deployments`
- SSE terminal events under `/sse/deploy/{session_id}`

The implementation must preserve existing API paths and keep Flutter-compatible
response fields while adding metadata.

---

## 3. Scope

### In Scope

- Add `operation_id` and `error_code` to `Deployment`.
- Add idempotent SQLite migration for the new columns.
- Extend `DeploymentRepository` with operation metadata updates.
- Parse Deployer SSE terminal JSON into a typed backend internal result.
- Persist `operation_id`, `error_code`, and safe message for deploy/destroy.
- Forward terminal metadata to SSE clients.
- Add metadata to deployment status/history responses.
- Tests for repository, stream parsing, status/history output, and migration.

### Out of Scope

- Flutter UI changes.
- Full `twins.py` orchestrator extraction.
- Live cloud deploy/destroy execution.
- Replacing all SSE/session internals.
- External observability/metrics systems.

---

## 4. Implementation Slices

### Slice 1: Persistence Contract

**Files:**

- `src/models/deployment.py`
- `src/repositories/deployment_repository.py`
- `migrations/add_deployment_operation_state_columns.py`
- `tests/test_deployment_repository.py`
- migration test file

**Acceptance criteria:**

- New columns are nullable for backward compatibility.
- Repository can set/clear `operation_id` and `error_code` on success/failure.
- Migration can run repeatedly without failing.

### Slice 2: Deployer SSE Result Parsing

**Files:**

- `src/services/deployment_service.py`
- `tests/test_deployment_service.py`

**Acceptance criteria:**

- Backend parses Deployer terminal event payloads from `event: complete/error`
  followed by `data: {...}`.
- Parsed result includes `success`, `operation_id`, `error_code`, safe message,
  and outputs.
- Malformed terminal payloads fail safe without leaking raw credential material.

### Slice 3: Runtime State Persistence

**Files:**

- `src/services/deployment_service.py`
- `tests/test_deployment_service.py`

**Acceptance criteria:**

- Real deploy streams persist Deployer metadata on success/failure.
- Real destroy streams persist Deployer metadata on success/failure.
- Twin state transitions continue to use `DEPLOYED`, `DESTROYED`, and `ERROR`.
- Error paths store safe messages and typed codes.

### Slice 4: API Read Models

**Files:**

- `src/api/routes/twins.py`
- `src/api/routes/sse.py` if final event metadata requires transport support
- route tests

**Acceptance criteria:**

- `deployment-status` includes latest deployment metadata.
- `deployments` history includes `operation_id` and `error_code`.
- SSE final event includes metadata for Flutter without changing the endpoint.

---

## 5. Done Definition

- [x] GitHub Issue #75 is referenced by commits.
- [x] Plan exists in `implementation_plans/`.
- [x] Migration exists and is idempotent.
- [x] Deployment rows persist `operation_id` and `error_code`.
- [x] Deployer SSE terminal payload parsing is tested.
- [x] Status/history endpoints expose operation metadata.
- [x] Backend tests pass in Docker.
- [x] No raw secret/error traceback is introduced into persisted client-facing
      deployment state.

**Verification:**

```bash
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 pytest tests/test_deployment_repository.py tests/test_deployment_operation_state_migration.py tests/test_deployment_service.py tests/test_sse_session.py tests/test_twins.py -q
# 57 passed

docker exec -e PYTHONPATH=/app master-thesis-management-api-1 pytest tests -q
# 246 passed

docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m bandit -q /app/src/models/deployment.py /app/src/repositories/deployment_repository.py /app/src/services/deployment_service.py /app/src/api/routes/twins.py /app/src/api/routes/sse.py
# passed

docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m compileall -q /app/src/models/deployment.py /app/src/repositories/deployment_repository.py /app/src/services/deployment_service.py /app/src/api/routes/twins.py /app/src/api/routes/sse.py
# passed

git diff --check
# passed
```
