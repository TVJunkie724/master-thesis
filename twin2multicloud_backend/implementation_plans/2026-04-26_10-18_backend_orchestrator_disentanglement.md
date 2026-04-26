---
title: "Implementation Plan: Backend Orchestrator Disentanglement"
description: "Enterprise-grade plan for turning the Management API twin routes into thin HTTP adapters backed by repositories, lifecycle services, typed service clients, and a deployment orchestrator."
tags: [implementation-plan, backend, management-api, orchestration, enterprise]
lastUpdated: "2026-04-26"
version: "0.1"
---

<!-- SOURCES:
- ASSESSMENT.md Phase 3 "Backend Orchestrator entflechten"
- twin2multicloud_backend/src/api/routes/twins.py
- twin2multicloud_backend/src/api/routes/sse.py
- twin2multicloud_backend/src/api/routes/test_endpoints.py
- twin2multicloud_backend/src/services/deployment_service.py
- twin2multicloud_backend/src/models/twin.py
- twin2multicloud_backend/src/models/deployment.py
- twin2multicloud_backend/tests/test_twins.py
- twin2multicloud_backend/tests/test_twin_state_transitions.py
- twin2multicloud_backend/tests/test_deployment_service.py
EXTRACTED: 2026-04-26 | VERSION: 0.1
-->

# Implementation Plan: Backend Orchestrator Disentanglement

**Date:** 2026-04-26
**Scope:** `twin2multicloud_backend`
**Base branch:** `master`
**Implementation branch:** `codex/backend-orchestrator-plan`
**Plan status:** Reviewed
**Implementation status:** Not started

---

## 1. Why This Phase Exists

Phase 1 and Phase 2 stabilized the Deployer side of the system. The next highest-risk architecture debt is now the Management API orchestration boundary.

`twin2multicloud_backend/src/api/routes/twins.py` currently has 1601 lines and mixes at least seven responsibilities:

- Digital Twin CRUD and ownership checks.
- Twin state transition rules.
- Distributed "finish configuration" validation against Optimizer and Deployer.
- Deployment and destroy orchestration.
- Direct `httpx.AsyncClient` calls to Deployer.
- SSE session creation and background task spawning.
- Deployment history, outputs, log trace, verification, simulator download, and export behavior.

This makes the Management API hard to reason about: a route file is simultaneously an HTTP adapter, repository, lifecycle state machine, external API client, and deployment workflow coordinator.

The final state must make the Management API the clean orchestrator of the system, not an accidental container for all orchestration logic.

---

## 2. Executive Decision

Backend routes will become thin HTTP adapters. Business logic moves behind explicit application services and typed client boundaries:

```text
FastAPI routes
  -> TwinRepository / DeploymentRepository
  -> TwinLifecycleService
  -> ConfigurationValidationService
  -> DeploymentOrchestrator
  -> OptimizerClient / DeployerClient
```

Routes may keep FastAPI-specific concerns only:

- dependency injection,
- request/response schema binding,
- path/query/body parameter extraction,
- translating domain/service exceptions into `HTTPException`,
- returning `StreamingResponse` objects when the transport itself requires it.

Routes must not own SQLAlchemy query logic, raw external `httpx` calls, deployment state transitions, or session orchestration decisions.

This phase is an architecture disentanglement. It must preserve the public API paths and response shapes used by the Flutter app.

---

## 3. Target State

### 3.1 Package Layout

The backend should grow explicit boundaries without introducing a framework rewrite:

```text
twin2multicloud_backend/src/
  api/
    routes/
      twins.py                    # CRUD-only HTTP adapter, thin
      twin_deployments.py          # deployment/status/history HTTP adapter
      twin_verification.py         # log trace + verification HTTP adapter
      twin_artifacts.py            # simulator/export HTTP adapter
  clients/
    deployer_client.py             # all Deployer HTTP calls
    optimizer_client.py            # all Optimizer HTTP calls
  repositories/
    twin_repository.py             # DigitalTwin queries and ownership checks
    deployment_repository.py       # Deployment history/output queries
  services/
    twin_lifecycle_service.py      # legal state transitions and regression rules
    configuration_validation_service.py
    deployment_orchestrator.py
    verification_service.py
    artifact_service.py
```

If the implementation discovers that one service would become too small, services may be combined, but the ownership boundaries must stay clear.

### 3.2 Repository Boundary

`TwinRepository` owns common twin lookup patterns:

```python
repository.get_active_for_user(twin_id, user_id)
repository.list_active_for_user(user_id)
repository.name_exists_for_user(name, user_id, exclude_twin_id=None)
repository.get_with_configs_for_user(twin_id, user_id)
repository.soft_delete(twin)
```

`DeploymentRepository` owns deployment records:

```python
repository.get_latest_successful_outputs(twin_id)
repository.list_for_twin(twin_id, limit)
repository.create_running(...)
repository.mark_success(...)
repository.mark_failed(...)
```

Routes and orchestration services must not duplicate these queries.

### 3.3 Lifecycle Boundary

`TwinLifecycleService` is the only place that decides whether a state transition is legal:

```python
lifecycle.rename(twin, new_name)
lifecycle.mark_configured(twin)
lifecycle.start_deploy(twin)
lifecycle.rollback_deploy_start(twin)
lifecycle.complete_deploy(twin, outputs)
lifecycle.fail_deploy(twin, error)
lifecycle.start_destroy(twin)
lifecycle.rollback_destroy_start(twin)
lifecycle.complete_destroy(twin)
lifecycle.fail_destroy(twin, error)
```

The service should use explicit domain exceptions such as:

- `TwinNotFound`
- `TwinNameConflict`
- `InvalidTwinStateTransition`
- `OperationAlreadyInProgress`
- `ConfigurationValidationFailed`
- `ExternalServiceUnavailable`
- `ExternalServiceError`

FastAPI routes translate these exceptions to current HTTP status codes and response details.

### 3.4 Client Boundary

All external calls leave route files:

```text
OptimizerClient
  validate_optimizer_config(payload)

DeployerClient
  validate_deployer_complete(payload)
  check_cooldown(destroyed_at, uses_gcp_firestore)
  prepare_project(zip_bytes, resource_name)
  deploy_stream(provider, project_name)
  destroy_stream(provider, project_name)
  start_log_trace(project_name)
  stream_log_trace(project_name, trace_id)
  verify_infrastructure(project_name, provider)
  verify_dataflow(project_name, payload)
  download_simulator(project_name, provider)
```

Clients own:

- base URLs,
- timeouts,
- request parameter names,
- `httpx` exception mapping,
- response JSON parsing where the boundary is stable.

Routes must not instantiate `httpx.AsyncClient` directly.

### 3.5 Deployment Orchestrator Boundary

`DeploymentOrchestrator` coordinates deploy/destroy without knowing FastAPI:

```python
orchestrator.start_deploy(twin_id, user_id) -> OperationStartResult
orchestrator.start_destroy(twin_id, user_id) -> OperationStartResult
orchestrator.get_status(twin_id, user_id) -> DeploymentStatusView
orchestrator.get_outputs(twin_id, user_id) -> DeploymentOutputsView
orchestrator.get_history(twin_id, user_id, limit) -> DeploymentHistoryView
```

It owns the workflow:

1. Load twin with configs.
2. Validate ownership and state.
3. Check active SSE sessions.
4. Move twin to transient state.
5. Prepare project ZIP and upload to Deployer.
6. Create SSE session.
7. Spawn deployment background task.
8. Return `{session_id, sse_url}`.

The background stream handlers in `deployment_service.py` should either move into the orchestrator module or become a dedicated `DeploymentStreamRunner` dependency. They must not import route modules except the SSE session manager, and long term the SSE manager should be moved out of `api.routes`.

### 3.6 Route Boundary

Final route files are allowed to look like this:

```python
@router.post("/{twin_id}/deploy")
async def deploy_twin(...):
    try:
        return await orchestrator.start_deploy(twin_id, current_user.id)
    except DomainError as exc:
        raise map_domain_error(exc)
```

They must not contain:

- `db.query(...)`,
- `httpx.AsyncClient(...)`,
- `asyncio.create_task(...)` for domain workflows,
- provider/resource-name derivation,
- deployment state mutation,
- JSON payload assembly for Optimizer or Deployer validation.

### 3.7 Public API Compatibility

The following public paths must remain stable:

- `GET /twins/`
- `POST /twins/`
- `GET /twins/{twin_id}`
- `PUT /twins/{twin_id}`
- `DELETE /twins/{twin_id}`
- `GET /twins/{twin_id}/can-redeploy`
- `POST /twins/{twin_id}/deploy`
- `POST /twins/{twin_id}/destroy`
- `GET /twins/{twin_id}/deployment-status`
- `GET /twins/{twin_id}/outputs`
- `GET /twins/{twin_id}/deployments`
- `POST /twins/{twin_id}/log-trace/start`
- `GET /twins/{twin_id}/log-trace/stream/{trace_id}`
- `POST /twins/{twin_id}/verify/infrastructure`
- `POST /twins/{twin_id}/verify/dataflow`
- `GET /twins/{twin_id}/simulator/download`
- `GET /twins/{twin_id}/export`

Internal router files may change as long as these paths and response shapes remain stable.

Static architecture guards in this phase apply to the Twin route family only:

- `twin2multicloud_backend/src/api/routes/twins.py`
- `twin2multicloud_backend/src/api/routes/twin_deployments.py`
- `twin2multicloud_backend/src/api/routes/twin_verification.py`
- `twin2multicloud_backend/src/api/routes/twin_artifacts.py`

Other existing routes, including `optimizer.py`, `deployer.py`, `config.py`, `auth.py`, `dashboard.py`, `sse.py`, and `test_endpoints.py`, may still contain older patterns after this phase. They are not allowed to regress, but they are not part of this phase's exit gate unless a slice explicitly touches them.

---

## 4. Scope

### In Scope

- Introduce repository classes for twin and deployment persistence.
- Introduce lifecycle service for state transition rules.
- Introduce typed Optimizer and Deployer clients.
- Move configuration validation orchestration out of `twins.py`.
- Move deploy/destroy workflow coordination into `DeploymentOrchestrator`.
- Move deployment history/output/status logic out of route functions.
- Move log trace, verification, simulator, and export behavior behind services or dedicated routers.
- Keep public API paths stable.
- Add tests that enforce thin routes and client boundaries.

### Out of Scope

- Changing the Flutter API contract.
- Changing database schema unless a small, explicit migration is unavoidable.
- Replacing SQLAlchemy.
- Replacing FastAPI dependency injection.
- Rewriting the SSE session manager.
- Removing test endpoints completely.
- Introducing a message queue or worker process.
- Changing Deployer or Optimizer API behavior.
- Live cloud E2E.

---

## 5. Implementation Slices

### Slice 1: Repository Boundary

**Goal:** Remove repeated ownership and active-twin queries from routes.

**Expected files:**

- `twin2multicloud_backend/src/repositories/__init__.py`
- `twin2multicloud_backend/src/repositories/twin_repository.py`
- `twin2multicloud_backend/src/repositories/deployment_repository.py`
- `twin2multicloud_backend/tests/test_twin_repository.py`
- `twin2multicloud_backend/tests/test_deployment_repository.py`

**Acceptance criteria:**

- Common `DigitalTwin` queries are centralized.
- Duplicate-name logic is centralized and case-insensitive.
- Soft-delete behavior remains unchanged, including renamed inactive twins.
- Deployment output/history queries are centralized.
- Existing CRUD tests still pass.

---

### Slice 2: Lifecycle Service

**Goal:** Make state rules explicit and testable outside HTTP routes.

**Expected files:**

- `twin2multicloud_backend/src/services/twin_lifecycle_service.py`
- `twin2multicloud_backend/src/services/errors.py`
- `twin2multicloud_backend/tests/test_twin_lifecycle_service.py`

**Acceptance criteria:**

- Rename blocking for `deployed`, `deploying`, and `destroying` lives in the lifecycle service.
- Deploy is allowed only from `configured`, `destroyed`, or `error`.
- Destroy is allowed only from `deployed` or `error`.
- Config mutation regression rules remain covered by existing tests.
- Routes map lifecycle exceptions to the same HTTP status codes and detail strings currently expected by tests.

---

### Slice 3: Typed External Clients

**Goal:** Remove raw `httpx` calls from `twins.py`.

**Expected files:**

- `twin2multicloud_backend/src/clients/__init__.py`
- `twin2multicloud_backend/src/clients/optimizer_client.py`
- `twin2multicloud_backend/src/clients/deployer_client.py`
- `twin2multicloud_backend/tests/test_optimizer_client.py`
- `twin2multicloud_backend/tests/test_deployer_client.py`

**Acceptance criteria:**

- `twins.py` contains no `httpx.AsyncClient`.
- Client tests assert URLs, params, timeouts, and error mapping.
- Optimizer validation still calls `/validate/optimizer-config`.
- Deployer validation still calls `/validate/deployer-complete`.
- Cooldown still calls `/infrastructure/cooldown-check`.
- Log trace, verification, dataflow, and simulator paths are preserved.

---

### Slice 4: Configuration Validation Service

**Goal:** Move "Finish Configuration" validation out of `twins.py`.

**Expected files:**

- `twin2multicloud_backend/src/services/configuration_validation_service.py`
- `twin2multicloud_backend/tests/test_configuration_validation_service.py`
- Update `twin2multicloud_backend/tests/test_twin_state_transitions.py`

**Acceptance criteria:**

- Local Step 1 validation is service-owned.
- Optimizer and Deployer validation payload assembly is service-owned.
- Optimizer and Deployer validation run in parallel through clients.
- Validation failure response shape remains:

```json
{
  "code": "VALIDATION_FAILED",
  "message": "...",
  "errors": []
}
```

- `PUT /twins/{twin_id}` remains behavior-compatible.

---

### Slice 5: Deployment Orchestrator

**Goal:** Move deploy/destroy workflows out of routes.

**Expected files:**

- `twin2multicloud_backend/src/services/deployment_orchestrator.py`
- Possibly `twin2multicloud_backend/src/services/deployment_stream_runner.py`
- `twin2multicloud_backend/tests/test_deployment_orchestrator.py`

**Acceptance criteria:**

- Deploy route delegates to `DeploymentOrchestrator.start_deploy`.
- Destroy route delegates to `DeploymentOrchestrator.start_destroy`.
- Active SSE session checks are centralized.
- Test mode delegation is centralized behind the orchestrator or a `TestDeploymentRunner`.
- Project preparation rollback behavior remains unchanged.
- `{session_id, sse_url}` response shape remains unchanged.
- Existing deployment service tests still pass.

---

### Slice 6: Deployment Read Models

**Goal:** Move status, outputs, and history behavior behind service methods.

**Expected files:**

- `twin2multicloud_backend/src/services/deployment_query_service.py` or extend `deployment_orchestrator.py`
- `twin2multicloud_backend/tests/test_deployment_query_service.py`

**Acceptance criteria:**

- `GET /deployment-status` remains behavior-compatible, including active SSE session reporting.
- `GET /outputs` still returns `{outputs, deployed_at}`.
- `GET /deployments` still returns deployment records ordered newest first.
- Routes contain no deployment table query logic.

---

### Slice 7: Verification, Log Trace, and Artifacts

**Goal:** Remove the remaining Deployer proxy workflows from `twins.py`.

**Expected files:**

- `twin2multicloud_backend/src/services/verification_service.py`
- `twin2multicloud_backend/src/services/artifact_service.py`
- Optional routers:
  - `twin2multicloud_backend/src/api/routes/twin_verification.py`
  - `twin2multicloud_backend/src/api/routes/twin_artifacts.py`
- Tests:
  - `twin2multicloud_backend/tests/test_verification_service.py`
  - `twin2multicloud_backend/tests/test_artifact_service.py`

**Acceptance criteria:**

- Log trace start and stream no longer instantiate `httpx` in routes.
- Infrastructure verification delegates to a service.
- Dataflow verification SSE proxy delegates to a service.
- Simulator download delegates to a service.
- Export keeps using the existing ZIP builder but route no longer assembles business behavior.
- Public URLs remain unchanged.

---

### Slice 8: Route Split and Static Guards

**Goal:** Make thin-route architecture enforceable.

**Expected files:**

- `twin2multicloud_backend/src/api/routes/twins.py`
- `twin2multicloud_backend/src/api/routes/twin_deployments.py`
- `twin2multicloud_backend/src/api/routes/twin_verification.py`
- `twin2multicloud_backend/src/api/routes/twin_artifacts.py`
- `twin2multicloud_backend/src/main.py`
- `twin2multicloud_backend/tests/test_backend_architecture_boundaries.py`

**Acceptance criteria:**

- `twins.py` becomes CRUD-focused and materially smaller.
- Public endpoint paths are unchanged after router split.
- The Twin route family contains no direct `httpx.AsyncClient`.
- The Twin route family contains no direct deployment workflow `asyncio.create_task` calls.
- The Twin route family contains no direct `db.query(...)` except narrowly allowed transitional code if explicitly documented.
- Boundary tests fail if raw external calls or repository queries re-enter the Twin route family.

---

### Slice 9: Documentation and Roadmap Update

**Goal:** Keep the architecture source of truth current.

**Expected files:**

- `ASSESSMENT.md`
- This implementation plan

**Acceptance criteria:**

- `ASSESSMENT.md` links to this Phase 3 plan.
- Phase 3 scope is clear: Management API orchestrator disentanglement now, broader UI recomposition and non-Twin route cleanup later.
- This plan's implementation status reflects the real final state after implementation and verification.

---

## 6. Test Strategy

This phase must increase confidence, not only move code. Every extracted boundary needs direct unit coverage and every preserved public endpoint needs route-level regression coverage. Tests must use hard assertions for response shapes, status codes, state transitions, database side effects, and external-client call parameters.

### Coverage Matrix

| Boundary | Required coverage |
| --- | --- |
| `TwinRepository` | Active-user filtering, inactive exclusion, not-found behavior, case-insensitive duplicate names, exclude-current-twin rename check, eager config loading, soft-delete rename semantics. |
| `DeploymentRepository` | Latest successful deploy/test output lookup, empty output response, history ordering, `limit` behavior, running record creation, success/failure completion fields. |
| `TwinLifecycleService` | Rename blocked states, allowed rename states, configured transition handoff, deploy allowed states, deploy disallowed states, deploy rollback, deploy success/failure, destroy allowed states, destroy disallowed states, destroy rollback, destroy success/failure. |
| `OptimizerClient` | Exact validation URL, payload pass-through, timeout, non-200 mapping, request failure mapping. |
| `DeployerClient` | Exact endpoint/params for validation, cooldown, deploy/destroy streams, log trace, infrastructure verification, dataflow verification, simulator download; non-200 and request-error mapping. |
| `ConfigurationValidationService` | Step 1 local errors, optimizer errors, deployer errors, parallel success, parallel partial failure, malformed stored JSON behavior, exact `VALIDATION_FAILED` response payload. |
| `DeploymentOrchestrator` | Active session conflict, state mutation order, preparation failure rollback, test-mode delegation, real deploy session creation, real destroy session creation, provider/resource-name derivation, `{session_id, sse_url}` response shape. |
| Query/verification/artifact services | Deployment status active-session reporting, outputs shape, history shape, log-trace start/stream mapping, infrastructure verification mapping, dataflow SSE proxy, simulator download headers, export ZIP reuse. |
| Route adapters | Public paths, status codes, response shapes, domain-exception-to-HTTP mapping, dependency wiring. |
| Architecture guards | No raw `httpx.AsyncClient`, no direct deployment workflow `asyncio.create_task`, no direct `db.query(...)` in the Twin route family. |

### Enterprise Quality Gates

- Every new service/client/repository must have direct unit tests.
- Every route touched in this phase must keep at least one behavior-level regression test.
- Every external HTTP boundary must have tests for success, non-2xx response, and request failure.
- Every state transition must be tested from both allowed and disallowed source states.
- Every rollback path that mutates `DigitalTwin.state` must be tested.
- No test may assert only "not null" or "status code 200" when a concrete value is knowable.
- Integration tests may mock external Optimizer/Deployer only at the service-client boundary for unit tests; route/integration tests must exercise the real Management API app and database.
- No test may call real cloud APIs or trigger live deploy/destroy.

### Required Commands

```bash
docker compose up -d management-api
docker exec master-thesis-management-api-1 python -m compileall -q src
docker exec master-thesis-management-api-1 python -m pytest tests -v
```

If the compose service name differs locally, use the actual running Management API container name and keep the command semantics identical.

### Focused Test Groups

```bash
docker exec master-thesis-management-api-1 python -m pytest \
  tests/test_twins.py \
  tests/test_twin_state_transitions.py \
  tests/test_deployment_service.py \
  -q
```

Add and run:

```bash
docker exec master-thesis-management-api-1 python -m pytest \
  tests/test_twin_repository.py \
  tests/test_deployment_repository.py \
  tests/test_twin_lifecycle_service.py \
  tests/test_configuration_validation_service.py \
  tests/test_deployment_orchestrator.py \
  tests/test_backend_architecture_boundaries.py \
  -q
```

### Static Guards

```bash
rg -n 'httpx\.AsyncClient' \
  twin2multicloud_backend/src/api/routes/twins.py \
  twin2multicloud_backend/src/api/routes/twin_deployments.py \
  twin2multicloud_backend/src/api/routes/twin_verification.py \
  twin2multicloud_backend/src/api/routes/twin_artifacts.py
rg -n 'db\.query\(' \
  twin2multicloud_backend/src/api/routes/twins.py \
  twin2multicloud_backend/src/api/routes/twin_deployments.py \
  twin2multicloud_backend/src/api/routes/twin_verification.py \
  twin2multicloud_backend/src/api/routes/twin_artifacts.py
rg -n 'asyncio\.create_task' \
  twin2multicloud_backend/src/api/routes/twins.py \
  twin2multicloud_backend/src/api/routes/twin_deployments.py \
  twin2multicloud_backend/src/api/routes/twin_verification.py \
  twin2multicloud_backend/src/api/routes/twin_artifacts.py
```

Expected final result:

- No `httpx.AsyncClient` usage in the Twin route family.
- No direct deployment workflow `asyncio.create_task` in the Twin route family.
- No `db.query(...)` in the Twin route family, unless a route has a documented temporary exception accepted by this plan.

---

## 7. Definition of Done

- [ ] `TwinRepository` owns common twin persistence queries.
- [ ] `DeploymentRepository` owns deployment persistence queries.
- [ ] `TwinLifecycleService` owns state transition rules.
- [ ] Optimizer HTTP calls go through `OptimizerClient`.
- [ ] Deployer HTTP calls go through `DeployerClient`.
- [ ] Configuration validation lives outside `twins.py`.
- [ ] Deployment and destroy start workflows live outside `twins.py`.
- [ ] Status, outputs, and history read models live outside route functions.
- [ ] Log trace, verification, simulator download, and export behavior are service-backed.
- [ ] Public API paths and response shapes remain stable.
- [ ] The Twin route family contains no raw external `httpx.AsyncClient` calls.
- [ ] The Twin route family contains no direct deployment workflow `asyncio.create_task` calls.
- [ ] The Twin route family contains no direct `db.query(...)` except approved transitional exceptions.
- [ ] Architecture boundary tests enforce the above constraints.
- [ ] `ASSESSMENT.md` links to this Phase 3 plan.
- [ ] Coverage matrix is implemented with hard assertions for every touched boundary.
- [ ] Full backend test suite passes in Docker.
- [ ] No Deployer, Optimizer, Flutter, or Brain behavior is changed in this phase.

---

## 8. Risks and Controls

| Risk | Control |
| --- | --- |
| Flutter expects current response shapes | Preserve all public paths and add route-level regression tests before moving logic. |
| Big-bang extraction breaks deployment flows | Slice repository/lifecycle/client/orchestrator work into separately testable commits. |
| SSE session behavior changes accidentally | Keep `src/api/routes/sse.py` behavior stable in this phase; only consume it from services. |
| Test mode behavior drifts from real endpoints | Centralize test delegation behind the orchestrator and assert response parity. |
| External service errors become less diagnosable | Typed clients must preserve current HTTP status mapping and log details internally. |
| Services become an anemic pass-through layer | Services own decisions: state transitions, orchestration order, rollback, and exception semantics. |
| Scope creeps into infrastructure redesign | Do not introduce queues, workers, schema redesign, or cloud E2E in this phase. |

---

## 9. Implementation Notes

- Keep commits structured:
  1. repositories,
  2. lifecycle service and errors,
  3. clients,
  4. configuration validation,
  5. deployment orchestrator,
  6. query/verification/artifact services,
  7. route split and static guards,
  8. docs/status updates.
- Prefer small dataclasses or Pydantic models for service return values when they make route adapters clearer.
- Preserve current exception details where tests or Flutter likely depend on them.
- Do not hide external error details from logs; only API responses should be normalized.
- Keep `deployment_service.py` ZIP-building helpers unless and until a later phase splits artifact construction.
- Treat route LOC reduction as a signal, not the goal. The goal is clear ownership and enforceable boundaries.
