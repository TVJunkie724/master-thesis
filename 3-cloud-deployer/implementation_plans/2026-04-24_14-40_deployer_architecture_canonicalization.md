---
title: "Implementation Plan: Deployer Architecture Canonicalization"
description: "Enterprise-grade implementation plan for consolidating 3-cloud-deployer onto one canonical provider-neutral Terraform deployment path."
tags: [implementation-plan, deployer, architecture, terraform, enterprise]
lastUpdated: "2026-04-24"
version: "1.2"
---

<!-- SOURCES:
- documentation/concepts/CONCEPT_ENTERPRISE_TARGET_ARCHITECTURE.md
- ASSESSMENT.md Phase 1 "Deployer Architecture Canonicalization"
- integration_vision.md section 3 "System Architecture"
- FRONTEND_ARCHITECTURE.md "Architecture Overview" and section 5 "File Versioning: DB as Truth, Files via Deployer API"
- 3-cloud-deployer/src/api/deployment.py
- 3-cloud-deployer/src/providers/deployer.py
- 3-cloud-deployer/src/providers/terraform/
- 3-cloud-deployer/src/core/context.py
- 3-cloud-deployer/src/core/protocols.py
EXTRACTED: 2026-04-24 | VERSION: 1.2
-->

# Implementation Plan: Deployer Architecture Canonicalization

**Date:** 2026-04-24  
**Scope:** `3-cloud-deployer`  
**Base branch:** `master`
**Implementation branch:** `codex/deployer-architecture-canonicalization`  
**Plan status:** Reviewed  
**Implementation status:** Implemented, Docker-verified, and audit-approved for handoff

---

## 1. Executive Decision

`3-cloud-deployer` will have exactly one production deployment architecture:

```text
REST API / supported entrypoint
  -> src.api.deployment
  -> src.providers.deployer
  -> src.providers.terraform.TerraformDeployerStrategy
  -> src.providers.{aws,azure,gcp}.provider
  -> explicit DeploymentContext
```

The canonical path is `src/providers/*` plus `TerraformDeployerStrategy`. AWS must use the same provider-neutral Terraform strategy as Azure and GCP. No production code may import or execute the old direct `src/aws/*` deployment stack after this phase.

This phase is architectural consolidation only. It does not add provider features, change endpoint semantics, or redesign the full Management API orchestration model.

Every implementation slice in this document is mandatory. A builder may split a slice into smaller commits, but may not skip a slice, relax an acceptance criterion, or mark the phase complete while any Definition of Done item is false.

---

## 2. Target State

### 2.1 Production Flow

```text
Client
  |
  v
FastAPI deployment routes
  |
  v
Canonical deployer facade
  |
  +-- validates DeploymentContext
  +-- resolves provider implementation
  +-- invokes TerraformDeployerStrategy
  +-- returns typed deployment result / stream event
  |
  v
Provider implementation
  |
  v
Terraform module execution
```

### 2.2 Module Responsibilities

| Module | Final responsibility |
| --- | --- |
| `src/api/deployment.py` | HTTP request/response boundary only. No provider-specific deployment logic. |
| `src/providers/deployer.py` | Canonical deploy/destroy facade for production and tests. |
| `src/providers/terraform/*` | Terraform execution strategy and state handling. |
| `src/providers/{aws,azure,gcp}/provider.py` | Provider-specific configuration, credentials, resource naming, and Terraform variables. |
| `src/core/context.py` | Explicit deployment context and project configuration. |
| `src/core/protocols.py` | Provider and deployer contracts. |
| `src/core/registry.py` | Provider lookup/registration. |

### 2.3 Disallowed Final State

Production code must not contain:

```python
import aws.*
from aws import ...
from src.aws import ...
```

Production code must not call direct AWS SDK deployment managers as a parallel deployment implementation. Any cloud-specific SDK cleanup that remains temporarily must be isolated behind the canonical facade, documented as bounded cleanup behavior, and covered by tests.

### 2.4 Contract Compatibility

This phase must preserve the existing Deployer HTTP boundary unless a test exposes an already-broken contract. In particular:

| Boundary | Required compatibility |
| --- | --- |
| `POST /infrastructure/deploy` | Request shape, status semantics, and response keys stay compatible. |
| `POST /infrastructure/destroy` | Request shape, status semantics, and response keys stay compatible. |
| Streaming deploy endpoint | Event media type and emitted event schema stay compatible. |
| Streaming destroy endpoint | Event media type and emitted event schema stay compatible. |
| Management API -> Deployer | The Management API must not need changes for this phase. |

If a route currently returns provider-specific fields, those fields must remain available or be mapped explicitly from the canonical result. No Flutter or Management API model change is part of this phase.

---

## 3. Scope

### In Scope

- Make `src/providers/deployer.py` the single production deploy/destroy facade.
- Align REST API deployment routes with that facade.
- Remove direct production imports of `src/aws/*`.
- Retire, delete, or convert legacy wrapper modules under `src/deployers/*`.
- Remove or isolate the old `src/aws/*` implementation once no production imports remain.
- Add static regression guards that fail when legacy AWS deployment imports re-enter production code.
- Update Deployer documentation so the canonical path is the only documented implementation path.

### Out of Scope

- Management API decomposition.
- Flutter UI changes.
- Flutter DTO/model changes.
- Provider feature expansion.
- Terraform module redesign beyond what is necessary to preserve current canonical behavior.
- Live cloud E2E execution as part of default CI.
- Broad exception taxonomy refactor. That belongs to the next phase.

### Side-Effect Guardrails

- Do not change public route paths.
- Do not change default Docker service names or ports.
- Do not change Optimizer or Management API code.
- Do not touch Flutter code.
- Do not introduce new cloud resource types.
- Do not run commands that create, update, or destroy real cloud resources.

---

## 4. Implementation Slices

### Slice 1: Import Boundary and Inventory Guard

**Goal:** Make the architecture boundary visible and enforceable before removing code.

**Changes:**

- Must add a focused test or script that scans production Python files under `3-cloud-deployer/src`.
- Must make the guard fail on direct legacy AWS deployment imports outside an explicitly allowed deletion window.
- Must record the current import graph in the implementation PR description or a small generated note under `3-cloud-deployer/implementation_plans/archive/` if needed for review.

**Acceptance criteria:**

- A failing static guard exists before migration changes are complete.
- The guard becomes green only when production code no longer imports `aws.*` / `src.aws.*`.
- The guard excludes tests only where the test name explicitly marks migration coverage.

**Recommended command:**

```bash
cd 3-cloud-deployer
rg -n '^(from|import) +(src\.)?aws\b|^(from|import) +aws\b' src --glob '*.py'
```

---

### Slice 2: Canonical Deployer Facade

**Goal:** `src/providers/deployer.py` becomes the stable production facade for deploy and destroy operations.

**Changes:**

- Must keep deploy/destroy entrypoints provider-neutral and context-based.
- Must ensure facade functions resolve provider implementations consistently through existing registry/factory paths.
- Must keep Terraform invocation centralized through `TerraformDeployerStrategy`.
- Must preserve existing public behavior for deploy and destroy results.
- If stream behavior currently bypasses the facade, must extract shared internal helpers so standard deploy/destroy and streaming deploy/destroy use the same provider resolution and Terraform strategy setup.

**Files expected to change:**

- `3-cloud-deployer/src/providers/deployer.py`
- `3-cloud-deployer/src/api/deployment.py`
- Possibly `3-cloud-deployer/src/core/registry.py`
- Possibly `3-cloud-deployer/src/core/context.py`

**Acceptance criteria:**

- Deploy and destroy use one provider resolution path.
- API routes do not duplicate provider setup logic.
- AWS, Azure, and GCP all enter deployment through the same facade.

---

### Slice 3: API Boundary Alignment

**Goal:** FastAPI routes remain transport adapters, not deployment orchestrators.

**Changes:**

- Must keep route handlers responsible for:
  - request parsing,
  - active project/context resolution,
  - invoking the canonical deployer facade,
  - mapping results/errors to HTTP responses or stream events.
- Must move any repeated deployment setup out of route functions and into the canonical facade or a small private helper.
- Must preserve route paths and response shape unless tests prove current behavior is already inconsistent.
- Must add or update route tests with hard assertions for response keys, status fields, and streaming event shape.

**Files expected to change:**

- `3-cloud-deployer/src/api/deployment.py`
- Related deployment tests under `3-cloud-deployer/tests`

**Acceptance criteria:**

- Route tests verify the facade call boundary.
- Streaming and non-streaming routes share canonical setup logic.
- There is no direct import of legacy AWS deployment modules from API code.

---

### Slice 4: Legacy Entrypoint Isolation

**Goal:** Remove production reachability of the old AWS deployment hierarchy.

**Changes:**

- `src/main.py`
  - Must convert to a supported provider-neutral CLI entrypoint only if it is actively used.
  - Otherwise must remove it from production packaging/docs or replace with a clear non-production message.
- `src/info.py`
  - Must route provider information through provider abstractions if still needed.
  - Otherwise must remove it from production reachability.
- `src/deployers/core_deployer.py`
- `src/deployers/iot_deployer.py`
- `src/deployers/additional_deployer.py`
- `src/deployers/event_action_deployer.py`
  - Must prefer deletion if unreferenced.
  - If external compatibility is required, must convert each module to a thin compatibility wrapper that delegates to the canonical facade and emits a deprecation signal.
  - Compatibility wrappers must not import `src/aws/*`.

**Acceptance criteria:**

- No production file outside an explicitly removed legacy folder imports `src/aws/*`.
- Compatibility wrappers, if retained, contain no direct AWS SDK deployment logic.
- Documentation points users to the REST API/canonical deployer path only.

---

### Slice 5: Remove Legacy AWS Deployment Source

**Goal:** Eliminate the second implementation path.

**Changes:**

- Must delete `3-cloud-deployer/src/aws/*` once all production imports and tests have been migrated.
- Must migrate useful constants, variable mappings, or provider facts into provider modules only when they are required by the canonical Terraform path.
- Must not copy old manager-style orchestration into the new path.

**Acceptance criteria:**

- `3-cloud-deployer/src/aws` is gone, or contains only a documented non-production archive marker excluded from runtime imports.
- Static import guard passes.
- Provider/Terraform tests are the source of behavior coverage.

---

### Slice 6: Documentation and Source-of-Truth Cleanup

**Goal:** The repository tells one architecture story.

**Changes:**

- Must update Deployer docs to describe only the canonical deployment path.
- Must remove or revise stale references to direct AWS deployment managers.
- Must resolve active `!!3-cloud-deployer` migration references in `TODOS.md`.
- Must keep this implementation plan linked from `ASSESSMENT.md`.

**Files expected to change:**

- `3-cloud-deployer/README.md`
- `3-cloud-deployer/development_guide.md`
- `3-cloud-deployer/run_tests/e2e/README.md`
- `TODOS.md`, if it contains active `!!3-cloud-deployer` migration items
- `ASSESSMENT.md`

**Acceptance criteria:**

- Docs describe one production architecture.
- `TODOS.md` is no longer a parallel architecture backlog for this phase.
- New contributors can identify the canonical path without reading archived plans.

---

## 5. Test Strategy

Tests must contain hard assertions. A test that only checks that a call does not raise is not sufficient for this phase.

### Static Architecture Guards

Run after each slice:

```bash
cd 3-cloud-deployer
rg -n '^(from|import) +(src\.)?aws\b|^(from|import) +aws\b' src --glob '*.py'
```

Expected final result: no production matches.

### Python Validation

Preferred container path:

```bash
docker compose up -d 3cloud-deployer
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m compileall src
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/unit tests/api tests/integration -v --ignore=tests/e2e
docker compose down
```

Local fallback:

```bash
cd 3-cloud-deployer
PYTHONPATH="$PWD/src:$PWD" python -m compileall src
PYTHONPATH="$PWD/src:$PWD" python -m pytest tests/unit tests/api tests/integration -v --ignore=tests/e2e
```

### Required Coverage

- Provider registry resolves AWS, Azure, and GCP through canonical providers.
- `DeploymentContext` is passed into facade/strategy boundaries explicitly.
- Deploy route invokes canonical facade and asserts response status, provider, and result keys.
- Destroy route invokes canonical facade and asserts response status, provider, and result keys.
- Streaming deploy/destroy paths use the same provider resolution as non-streaming paths and assert emitted event shape.
- Static guard blocks reintroduction of direct legacy AWS deployment imports.
- Existing Management API -> Deployer compatibility is preserved without Management API code changes.

### E2E Policy

Real cloud E2E is not part of the default phase gate. E2E tests may be run manually with explicit credentials after unit/API/integration gates pass.

---

## 6. Risk Controls

| Risk | Control |
| --- | --- |
| Removing legacy modules breaks hidden imports | Run import guard first, then delete only after route/test migration. |
| API behavior changes unintentionally | Preserve endpoint paths and response contracts; add route boundary tests. |
| Streaming path diverges from normal deployment | Share provider resolution and Terraform strategy setup. |
| Useful AWS-specific facts are lost during deletion | Move only required data into `src/providers/aws/provider.py` or Terraform variables. |
| Documentation keeps pointing to old architecture | Docs cleanup is part of the phase Definition of Done. |

---

## 7. Definition of Done

Phase 1 is complete only when every checkbox is true:

- [x] `src/providers/deployer.py` is the only production deploy/destroy facade.
- [x] `src/api/deployment.py` routes use the canonical facade or shared canonical helpers.
- [x] AWS, Azure, and GCP deploy through `TerraformDeployerStrategy`.
- [x] No production Python file imports `aws.*` or `src.aws.*`.
- [x] `src/aws/*` is deleted or fully unreachable from runtime code.
- [x] `src/deployers/*`, `src/main.py`, and `src/info.py` no longer expose the old AWS deployment stack.
- [x] Public deploy/destroy route paths, request shapes, response keys, and streaming event schemas remain compatible.
- [x] Unit/API/integration tests pass without live cloud credentials.
- [x] Tests contain hard assertions for provider resolution, deploy result shape, destroy result shape, and streaming event shape.
- [x] Static import guard is present and green.
- [x] Deployer docs describe only the canonical architecture.
- [x] `TODOS.md` no longer acts as a parallel Deployer architecture backlog for this phase.
- [x] `ASSESSMENT.md` links to this plan.
- [x] No Optimizer, Management API, or Flutter code was changed for this phase.

---

## 8. Review Gates

1. **Plan review:** Validate that the target state, slices, tests, and Done criteria are sufficient.
2. **Builder implementation:** Implement one slice at a time, keeping tests green between slices where practical.
3. **Audit review:** Verify final implementation against this plan with zero tolerance for direct legacy deployment imports.

---

## 9. Builder Notes

- Keep changes narrow and architectural.
- Prefer deleting unreachable legacy code over preserving compatibility by default.
- Add compatibility wrappers only when a real caller exists and cannot be migrated in this phase.
- Do not introduce a new orchestration abstraction if `src/providers/deployer.py` can serve as the canonical facade cleanly.
- Do not silently change REST API contracts.
- Do not run live cloud operations as part of normal validation.
- Do not mark the implementation complete until all Definition of Done checkboxes are satisfied.
