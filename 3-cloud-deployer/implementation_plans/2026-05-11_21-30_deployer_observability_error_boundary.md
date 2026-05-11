---
title: "Implementation Plan: Deployer Observability and Error Boundary"
description: "Enterprise-grade plan for operation-scoped logging, safe error responses, redaction, and deploy/destroy lifecycle visibility in 3-cloud-deployer."
tags: [implementation-plan, deployer, observability, errors, logging, enterprise]
lastUpdated: "2026-05-11"
version: "0.1"
---

<!-- SOURCES:
- GitHub Issue #74 "Harden deployer observability and error boundaries"
- 3-cloud-deployer/implementation_plans/2026-04-25_16-11_deployer_contract_hardening.md
- 3-cloud-deployer/src/api/deployment.py
- 3-cloud-deployer/src/api/models/deployment.py
- 3-cloud-deployer/src/core/workspace.py
- 3-cloud-deployer/src/providers/deployer.py
- 3-cloud-deployer/src/providers/terraform/deployer_strategy.py
- 3-cloud-deployer/src/terraform_runner.py
- 3-cloud-deployer/tests/api/test_deployment_routes.py
- 3-cloud-deployer/tests/unit/core_tests/test_deployer_workspace_boundary.py
EXTRACTED: 2026-05-11 | VERSION: 0.1
-->

# Implementation Plan: Deployer Observability and Error Boundary

**Date:** 2026-05-11
**Scope:** `3-cloud-deployer`
**GitHub issue:** [#74](https://github.com/TVJunkie724/master-thesis/issues/74)
**Base branch:** `master`
**Implementation branch:** `codex/flutter-credential-ssot-runtime-config`
**Plan status:** Approved
**Implementation status:** Implemented

---

## 1. Why This Phase Exists

The Deployer now has a canonical production path and deploy/destroy operations run in ephemeral runtime workspaces. That fixes major state and artifact boundaries, but failures during real cloud setup are still hard to diagnose because observability is inconsistent:

- API routes map errors ad hoc.
- Streaming endpoints emit untyped failure strings.
- Terraform errors may contain command output, paths, or provider messages.
- Logs do not consistently carry project/provider/operation context.
- Workspace sync, Terraform, provider initialization, SDK post-deploy, and cleanup phases do not have one lifecycle vocabulary.

This phase makes deployment failures debuggable without making client responses or GitHub issues unsafe.

---

## 2. Executive Decision

`3-cloud-deployer` gets a small internal observability/error boundary, not a large external telemetry platform.

The final state is:

```text
HTTP/SSE request
  -> OperationContext(operation_id, project, provider, operation)
  -> deployment facade / workspace / Terraform strategy
  -> structured lifecycle logs
  -> typed, redacted API/SSE errors
```

The Deployer remains local/Docker-friendly for the master thesis. External services such as OpenTelemetry collectors, Prometheus, Grafana alerting, or cloud logging integrations are out of scope for this slice.

---

## 3. Target State

### 3.1 Operation Context

Every deploy/destroy request gets an operation id.

The operation id is included in:

- synchronous deploy/destroy success responses,
- synchronous deploy/destroy error details,
- SSE log/complete/error events,
- server logs emitted by the route/facade boundary.

### 3.2 Error Contract

Deployment errors use stable error codes:

| Code | Boundary |
| --- | --- |
| `VALIDATION_ERROR` | invalid project/provider/config before deployment starts |
| `DEPLOYMENT_ERROR` | deploy/apply/post-deploy failed |
| `DESTRUCTION_ERROR` | destroy/cleanup failed |
| `TERRAFORM_ERROR` | Terraform command failed |
| `WORKSPACE_SYNC_ERROR` | durable runtime output sync failed |
| `UNEXPECTED_ERROR` | defensive fallback for unknown failures |

Client responses and SSE failure events must be safe by default. Full diagnostic detail belongs in server logs after redaction.

### 3.3 Redaction Contract

One central redactor handles:

- upload paths,
- ephemeral workspace paths,
- private key blocks,
- common secret keys such as `password`, `token`, `secret`, `client_secret`, `private_key`, `access_key`,
- common credential fragments in JSON-ish, CLI-ish, and Python repr-ish strings.

### 3.4 Lifecycle Logging

Deployment phases log start/success/failure and duration:

- request preparation,
- workspace preparation,
- Terraform deployment/destroy,
- SDK cleanup,
- stream execution,
- runtime output sync.

The first implementation can use standard Python logging with `extra` metadata and readable messages. JSON log formatting is a later optional hardening, not required here.

---

## 4. Scope

### In Scope

- Add internal observability helpers under `src/core`.
- Extend deployment API/SSE models with operation id and error code.
- Centralize redaction for deployment API and SSE errors.
- Add typed deployment error helpers for mapping exceptions to safe client details.
- Add operation-scoped logs around deploy/destroy route and facade boundaries.
- Add tests for redaction, operation id propagation, HTTP error mapping, and SSE error mapping.
- Run full Deployer test suite without E2E and Bandit on touched modules.

### Out of Scope

- Full replacement of the global logger across the whole repository.
- Refactoring every non-deployment API route.
- Live cloud deploy/destroy tests.
- External telemetry backend.
- Frontend display changes for operation ids or error codes.

---

## 5. Implementation Slices

### Slice 1: Core Observability Helpers

**Files:**

- `src/core/observability.py`
- `tests/unit/core_tests/test_observability.py`

**Acceptance criteria:**

- `OperationContext` creates stable operation metadata.
- Redaction removes representative paths and secrets.
- Step logging records start/success/failure duration without leaking secret text.

### Slice 2: Deployment Error Mapping

**Files:**

- `src/core/deployment_errors.py`
- `tests/unit/core_tests/test_deployment_errors.py`

**Acceptance criteria:**

- Known deployment exceptions map to stable error codes.
- Client-safe payloads include operation id, error code, and redacted message.
- Terraform failures preserve diagnostics for logs while client payloads stay safe.

### Slice 3: API and SSE Contract Extension

**Files:**

- `src/api/models/deployment.py`
- `src/api/deployment.py`
- `tests/api/test_deployment_routes.py`

**Acceptance criteria:**

- Sync success responses include `operation_id`.
- Sync error responses use structured `detail`.
- SSE log/complete/error events include `operation_id`.
- SSE errors include `error_code`.

### Slice 4: Facade Lifecycle Logging

**Files:**

- `src/providers/deployer.py`
- `src/core/workspace.py`
- `tests/unit/core_tests/test_deployer_workspace_boundary.py`
- `tests/unit/core_tests/test_workspace.py`

**Acceptance criteria:**

- Deployer facade accepts/passes operation context.
- Workspace sync failures are mapped to `WORKSPACE_SYNC_ERROR`.
- Deploy/destroy phases log with operation metadata.

### Slice 5: Verification and Handoff

**Commands:**

```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/api/test_deployment_routes.py tests/unit/core_tests/test_observability.py tests/unit/core_tests/test_deployment_errors.py tests/unit/core_tests/test_deployer_workspace_boundary.py tests/unit/core_tests/test_workspace.py -q
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -q
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m bandit -q /app/src/api/deployment.py /app/src/core /app/src/providers/deployer.py /app/src/terraform_runner.py
```

---

## 6. Done Definition

- [x] GitHub Issue #74 is linked from commits.
- [x] Plan exists in `implementation_plans/`.
- [x] Operation id is present in sync and SSE deploy/destroy contracts.
- [x] Error code is present in sync and SSE failure contracts.
- [x] Redaction is centralized and tested.
- [x] Workspace/terraform/deployer boundary logs are operation-scoped.
- [x] Deployer API and core unit suites pass locally.
- [x] Bandit passes for touched observability/error modules.

**Verification note:** Verified in the OrbStack-backed Deployer container with
`docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -q`
(`1029 passed, 1 skipped, 2 warnings`). Bandit and compile checks passed for the
touched observability/error modules.
