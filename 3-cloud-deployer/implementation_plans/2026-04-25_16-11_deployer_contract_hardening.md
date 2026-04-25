---
title: "Implementation Plan: Deployer Contract Hardening"
description: "Enterprise-grade plan for stabilizing deploy/destroy contracts, paths, streaming events, and error boundaries in 3-cloud-deployer."
tags: [implementation-plan, deployer, contracts, api, sse, enterprise]
lastUpdated: "2026-04-25"
version: "0.1"
---

<!-- SOURCES:
- documentation/concepts/CONCEPT_ENTERPRISE_TARGET_ARCHITECTURE.md
- ASSESSMENT.md Phase 2 "Deployer Contract Hardening"
- 3-cloud-deployer/implementation_plans/2026-04-24_14-40_deployer_architecture_canonicalization.md
- 3-cloud-deployer/src/api/deployment.py
- 3-cloud-deployer/src/api/dependencies.py
- 3-cloud-deployer/src/core/context.py
- 3-cloud-deployer/src/core/factory.py
- 3-cloud-deployer/src/providers/deployer.py
- 3-cloud-deployer/src/providers/terraform/deployer_strategy.py
- 3-cloud-deployer/tests/api/test_deployment_routes.py
EXTRACTED: 2026-04-25 | VERSION: 0.1
-->

# Implementation Plan: Deployer Contract Hardening

**Date:** 2026-04-25
**Scope:** `3-cloud-deployer`
**Base branch:** `master`
**Implementation branch:** `codex/deployer-contract-hardening-plan`
**Plan status:** Reviewed
**Implementation status:** Implemented and Docker-verified; audit review pending

---

## 1. Why This Phase Exists

Phase 1 removed the second production deployment architecture. The Deployer now has one canonical production path:

```text
src.api.deployment
  -> src.providers.deployer
  -> src.providers.terraform.TerraformDeployerStrategy
```

That solved the biggest structural ambiguity, but the new boundary is still too soft for enterprise-grade integration:

- deploy/destroy responses are plain dicts assembled in route functions,
- streaming events are hand-built strings,
- streaming routes still construct `/app/upload/{project}` paths directly,
- provider normalization accepts `google` but sometimes returns `google` instead of canonical `gcp`,
- route functions know too much about strategy creation,
- exceptions are still broad and mapped inconsistently,
- tests check current shapes but not a named contract model.

This phase turns the canonical path into a stable contract boundary so the Management API and Flutter can integrate against deliberate API behavior instead of accidental implementation details.

---

## 2. Executive Decision

`3-cloud-deployer` will expose deploy/destroy through explicit, test-backed contracts:

```text
HTTP request
  -> typed deployment request model
  -> DeploymentContext + DeploymentPaths
  -> canonical facade
  -> typed DeploymentResult / DestroyResult
  -> typed HTTP response or typed SSE event
```

The contract layer must be provider-neutral. AWS, Azure, and GCP may differ internally, but the route boundary must not leak provider-specific response structures except inside the existing `terraform_outputs` payload.

This phase is contract hardening, not a feature expansion. It must preserve public endpoint paths and existing Management API-compatible response keys.

---

## 3. Target State

### 3.1 HTTP Response Contracts

Deploy must return a stable shape:

```json
{
  "message": "Core and IoT services deployed successfully",
  "status": "success",
  "operation": "deploy",
  "project_name": "example-project",
  "provider": "aws",
  "terraform_outputs": {}
}
```

Destroy must return a stable shape:

```json
{
  "message": "Core and IoT services destroyed successfully",
  "status": "success",
  "operation": "destroy",
  "project_name": "example-project",
  "provider": "aws"
}
```

Compatibility rule: existing keys `message` and `terraform_outputs` must remain. New fields may be added only if tests assert they are stable.

### 3.2 SSE Event Contracts

Streaming deploy/destroy must emit a small set of structured event types:

```json
{"event": "log", "operation": "deploy", "message": "terraform init"}
{"event": "complete", "operation": "deploy", "success": true, "outputs": {}}
{"event": "error", "operation": "deploy", "success": false, "error": "details"}
```

Wire-format compatibility rule: the endpoint remains `text/event-stream`. Event payloads remain JSON-compatible. Existing clients that consume `complete` and `error` events must continue to work.

### 3.3 Path Resolution Contract

All deployment paths must be resolved in one place:

```text
DeploymentPaths
  project_root
  upload_root
  project_path
  terraform_dir
  tfvars_path
  state_path
```

Routes must not construct `/app/upload/{project}` manually. The canonical path source should be `src.core.factory` or a small dedicated module under `src/core`.

### 3.4 Provider Normalization Contract

Provider names must be normalized once:

| Input | Canonical value |
| --- | --- |
| `aws` | `aws` |
| `azure` | `azure` |
| `gcp` | `gcp` |
| `google` | `gcp` |

The canonical value must be what `create_context`, facade functions, tests, and response contracts see.

### 3.5 Error Contract

This phase introduces the error boundary, not the full long-term taxonomy. Minimum categories:

| Category | HTTP status | Meaning |
| --- | --- | --- |
| `validation_error` | 400 | Bad provider, invalid project input, invalid project config |
| `project_conflict` | 409 | Requested project does not match active project while active-project guard still exists |
| `deployment_error` | 500 | Terraform/deployment failure |
| `unexpected_error` | 500 | Unknown internal error |

Broad `except Exception` blocks may remain only at the outer route boundary and must map to a contract-shaped error response or existing `HTTPException`.

---

## 4. Scope

### In Scope

- Add typed Python contract models for deploy/destroy requests, results, and stream events.
- Add a central path resolver for deployment paths.
- Normalize providers consistently to `aws`, `azure`, or `gcp`.
- Make `src/api/deployment.py` thinner by moving contract assembly into helpers or models.
- Preserve current public endpoint paths:
  - `POST /infrastructure/deploy`
  - `POST /infrastructure/destroy`
  - `POST /infrastructure/deploy/stream`
  - `POST /infrastructure/destroy/stream`
- Preserve existing response keys used by current tests and clients.
- Add hard contract tests for HTTP and SSE payloads.
- Keep all tests local/Docker-only; no real cloud calls.

### Out of Scope

- Removing `src/core/state.py` globally.
- Refactoring every API module that reads active project state.
- Management API changes.
- Flutter changes.
- Full error taxonomy implementation across every Deployer module.
- Terraform module redesign.
- Live cloud E2E.

Why `src/core/state.py` is out of scope: the assessment lists it as a broader P0-3 debt. Phase 2 can reduce the deployment boundary's dependency on implicit state, but removing global active-project behavior from all Deployer APIs is a later, larger migration.

---

## 5. Implementation Slices

### Slice 1: Contract Models

**Goal:** Make deploy/destroy shapes explicit and reusable.

**Expected files:**

- `3-cloud-deployer/src/api/models/deployment.py` or `3-cloud-deployer/src/core/contracts.py`
- `3-cloud-deployer/tests/unit/core_tests/test_deployment_contracts.py`

**Models:**

- `DeploymentOperation`: `deploy | destroy`
- `DeploymentStatus`: `success | error`
- `DeploymentRequest`: `project_name`, `provider`
- `DeploymentResult`: `message`, `status`, `operation`, `project_name`, `provider`, `terraform_outputs`
- `DestroyResult`: `message`, `status`, `operation`, `project_name`, `provider`
- `DeploymentStreamEvent`: `event`, `operation`, `success`, `message`, `outputs`, `error`

**Acceptance criteria:**

- Models serialize to dict/JSON without custom route-side string manipulation.
- Deploy result preserves `message` and `terraform_outputs`.
- Destroy result preserves `message`.
- Tests assert exact serialized shapes.

---

### Slice 2: Deployment Path Resolver

**Goal:** Remove hardcoded deployment path construction from routes.

**Expected files:**

- `3-cloud-deployer/src/core/factory.py`
- Possibly `3-cloud-deployer/src/core/paths.py`
- `3-cloud-deployer/tests/unit/core_tests/test_deployment_paths.py`

**Target API:**

```python
paths = resolve_deployment_paths(project_name)
paths.project_path
paths.terraform_dir
paths.tfvars_path
paths.state_path
```

**Acceptance criteria:**

- `src/api/deployment.py` contains no direct `Path(f"/app/upload/{project_name}")`.
- `DeploymentContext.project_path` and `DeploymentPaths.project_path` agree.
- Tests assert path values for a sample project.

---

### Slice 3: Provider Normalization

**Goal:** Treat `google` only as an inbound alias and use `gcp` internally.

**Expected files:**

- `3-cloud-deployer/src/api/dependencies.py`
- `3-cloud-deployer/src/core/factory.py` or a shared provider utility
- API tests

**Acceptance criteria:**

- `validate_provider("google") == "gcp"`.
- All deploy/destroy response contracts return `"provider": "gcp"` for input `google`.
- Error messages mention accepted inbound values.

---

### Slice 4: Route Contract Mapping

**Goal:** Keep routes as thin HTTP adapters.

**Expected files:**

- `3-cloud-deployer/src/api/deployment.py`
- `3-cloud-deployer/src/providers/deployer.py`
- Route tests

**Changes:**

- Standard deploy route maps facade output to `DeploymentResult`.
- Standard destroy route maps facade completion to `DestroyResult`.
- Streaming routes use `DeploymentStreamEvent`.
- Strategy setup uses the central path resolver.

**Acceptance criteria:**

- Route functions do not assemble response dicts ad hoc.
- Streaming routes do not assemble JSON strings ad hoc except for the final SSE wire formatting helper.
- Route tests assert exact HTTP response shapes.
- Route tests assert exact SSE event JSON payloads.

---

### Slice 5: Error Boundary

**Goal:** Make route-level failures predictable without redesigning all internals.

**Expected files:**

- `3-cloud-deployer/src/api/deployment.py`
- Possibly `3-cloud-deployer/src/core/errors.py`
- Route tests for invalid provider/project/facade failure

**Acceptance criteria:**

- Invalid provider returns 400 with stable error detail.
- Active-project mismatch remains 409 while the active-project guard exists.
- Facade exceptions map to 500 without leaking stack traces in API response.
- Logs still capture details.

---

### Slice 6: Documentation and Assessment Update

**Goal:** Keep the architecture source of truth current.

**Expected files:**

- `3-cloud-deployer/README.md`
- `ASSESSMENT.md`
- This implementation plan

**Acceptance criteria:**

- README documents the stable contract shape for deploy/destroy and SSE at a high level.
- `ASSESSMENT.md` links to this Phase 2 plan.
- Phase 2 scope is clear: contract hardening now, global state removal later.

---

## 6. Test Strategy

### Required Commands

```bash
docker compose up -d 3cloud-deployer
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m compileall -q src
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit tests/api tests/integration -v --ignore=tests/e2e
```

### Focused Contract Tests

```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest \
  tests/api/test_deployment_routes.py \
  tests/unit/core_tests/test_deployment_contracts.py \
  tests/unit/core_tests/test_deployment_paths.py \
  -q
```

### Static Guards

```bash
rg -n 'Path\(f"/app/upload|/app/upload/\{project_name\}|json\.dumps' 3-cloud-deployer/src/api/deployment.py
rg -n '^(from|import) +(src\.)?aws\b|^(from|import) +aws\b' 3-cloud-deployer/src --glob '*.py'
```

Expected final result:

- no route-local `/app/upload/{project_name}` construction,
- no route-local JSON event construction outside a named SSE helper,
- no legacy `aws.*` imports.

---

## 7. Definition of Done

- [x] Deploy/destroy result contracts are typed and tested.
- [x] Streaming events are typed and tested.
- [x] `google` is normalized to `gcp` at the boundary.
- [x] Route functions preserve existing public paths.
- [x] Route functions preserve existing compatibility keys.
- [x] Route functions no longer build deployment filesystem paths manually.
- [x] Route functions are thinner and delegate contract creation.
- [x] Invalid provider and active-project mismatch are covered by tests.
- [x] Facade failure mapping is covered by tests.
- [x] Full Docker unit/API/integration suite passes without live cloud credentials.
- [x] README and `ASSESSMENT.md` describe the hardened contract boundary.
- [x] No Management API, Flutter, or Optimizer code changed in this phase.

---

## 8. Risks and Controls

| Risk | Control |
| --- | --- |
| Management API expects old deploy response keys | Preserve `message` and `terraform_outputs`; add fields only with tests. |
| SSE clients expect old event names | Preserve `complete` and `error`; add structured JSON payloads behind tests. |
| Provider alias change breaks GCP callers | Accept both `google` and `gcp`; return canonical `gcp` intentionally. |
| Path resolver changes Docker behavior | Assert exact `/app/upload/<project>`-compatible paths in tests. |
| Error taxonomy grows too broad | Limit this phase to deployment route boundary errors. |
| Scope creeps into global state removal | Keep `src/core/state.py` migration as a follow-up phase unless required by deployment contract tests. |

---

## 9. Implementation Notes

- Prefer Pydantic models if they are already natural at the API boundary; otherwise dataclasses are acceptable for internal contracts.
- Keep the route-level response shape explicit. Hidden `dict(result)` conversions are acceptable only if tests assert exact output.
- Avoid renaming public endpoints.
- Avoid changing Terraform strategy internals unless needed to return typed outputs.
- Do not introduce live cloud calls.
- Keep commits structured:
  1. contract/path models,
  2. route/facade wiring,
  3. tests,
  4. docs.
