---
title: "Phase 1.2 Review: Management Service Boundary Plan"
description: "Implementation-ready service, repository, client, and route ownership plan for the Management API refactor."
tags: [management-api, services, repositories, architecture, issue-102]
lastUpdated: "2026-06-21"
version: "1.5"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/BASELINE_AUDIT_RUBRIC.md
- docs/plans/service_architecture_audit/PHASE_01_01_MANAGEMENT_ROUTE_RESPONSIBILITY_REVIEW.md
- docs/plans/service_architecture_audit/phases/subphases/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_PLAN.md
- twin2multicloud_backend/src/api/routes/
- twin2multicloud_backend/src/services/
- twin2multicloud_backend/tests/
EXTRACTED: 2026-06-21 | VERSION: 1.5
-->

# Phase 1.2 Review: Management Service Boundary Plan

## Review Result

Phase 1.2 is complete as a planning slice. The Management API currently has no
repository package and only two service modules:
`src/services/deployment_service.py` and `src/services/twin_helpers.py`.
`deployment_service.py` already contains useful deployment helpers, but it still
mixes ZIP generation, credential materialization, downstream HTTP upload,
background SSE handling, direct DB sessions, broad errors, and container logs.

The target architecture below is the required implementation contract for the
Management API refactor. It keeps all existing API routes stable while moving
behavior under explicit service, repository, and downstream-client boundaries.

## Target Package Layout

| Path | Owner | Purpose |
|---|---|---|
| `src/repositories/__init__.py` | Repository package | Public repository exports only |
| `src/repositories/twin_repository.py` | `TwinRepository` | Twin ownership queries, active twin filtering, duplicate-name checks, soft delete mutations |
| `src/repositories/deployment_repository.py` | `DeploymentRepository` | Deployment records, latest status, history, output persistence |
| `src/repositories/configuration_repository.py` | `ConfigurationRepository` | Twin configuration, optimizer configuration, deployer configuration lookups |
| `src/services/twin_read_service.py` | `TwinReadService` | Twin list/detail DTO sourcing and ownership enforcement |
| `src/services/twin_lifecycle_service.py` | `TwinLifecycleService` | Create, update, soft delete, state transition orchestration |
| `src/services/deployment_read_service.py` | `DeploymentReadService` | Redeploy eligibility, deployment status, outputs, history |
| `src/services/deployment_operation_service.py` | `DeploymentOperationService` | Deploy/destroy command preparation, state changes, background-task dispatch |
| `src/services/deployment_stream_service.py` | `DeploymentStreamService` | SSE operation lifecycle, log persistence, final state persistence |
| `src/services/test_deployment_service.py` | `TestDeploymentService` | Test-only deploy, destroy, log-trace, simulator behavior behind runtime gate |
| `src/services/verification_service.py` | `DeploymentVerificationService` | Infrastructure and dataflow verification orchestration |
| `src/services/simulator_service.py` | `SimulatorDownloadService` | Simulator archive construction and response metadata |
| `src/services/twin_export_service.py` | `TwinExportService` | Twin export payload construction |
| `src/clients/deployer_client.py` | `DeployerClient` | Typed Management-to-Deployer HTTP calls |
| `src/clients/optimizer_client.py` | `OptimizerClient` | Typed Management-to-Optimizer HTTP calls |

No empty abstraction files are allowed. A new class is added only in the same
slice that moves behavior into it and adds tests for the moved behavior.

## Boundary Rules

| Boundary | Rule |
|---|---|
| Routes | Authenticate, parse FastAPI schemas, call exactly one use-case service, map service result to response. Routes do not call `httpx`, `SessionLocal`, `asyncio.create_task`, encryption helpers, ZIP builders, or downstream route modules. |
| Services | Own use-case orchestration, validation order, transaction timing, background-task creation, and service-level errors. Services do not build raw HTTP responses. |
| Repositories | Own SQLAlchemy query and mutation details. Repositories never commit, rollback, create sessions, call downstream services, or raise `HTTPException`. |
| Clients | Own `httpx` calls, timeout policy, endpoint paths, retry category, downstream error mapping, and redaction. Clients never receive ORM models or decrypted credentials unless the use case explicitly requires a deployment credential bundle. |
| SSE registry | Own in-memory sessions, TTL cleanup, event buffering, and lookup. It does not decide twin state. |
| Stream service | Owns deployment log persistence and final deployment state transitions for real and test streams. |
| Credential materialization | Happens only inside an explicit deployment credential bundle builder used by deployment operations. Plaintext secrets never pass through routes, repository methods, logs, or generic exception text. |
| Test endpoints | Registered only behind the explicit runtime gate. Test services share DTOs and stream contracts, but production deployment services do not call test services. |

## Transaction Rules

1. The FastAPI `get_db` session remains the request-scoped unit of work for
   synchronous route calls during the first extraction.
2. A service method owns commit and rollback decisions. Routes and repositories
   do not call `commit()` after extraction.
3. Repositories accept a `Session` and return ORM objects or typed read models.
4. Downstream HTTP calls are not made while an uncommitted state mutation is
   pending. The service commits local state first, calls the client, then opens
   a new state update when the downstream result is known.
5. Background tasks create their own SQLAlchemy session via `SessionLocal` and
   close it in `finally`.
6. Long-running deploy, destroy, pricing, verification, and log-trace flows
   record an operation/session identifier before the downstream call starts.

## Error And Logging Rules

| Layer | Error behavior | Logging behavior |
|---|---|---|
| Route | Maps service exceptions to existing API status codes and response shapes | Logs request-level correlation only |
| Service | Raises typed domain/application exceptions with user-safe messages | Logs operation, twin id, provider, session id, and phase |
| Repository | Raises persistence exceptions only when the service cannot classify them | Logs no secrets and no raw SQL payloads |
| Client | Converts downstream failures into typed gateway exceptions | Logs downstream service, endpoint family, status code, and sanitized message |
| Stream service | Persists sanitized log events and final operation result | Never persists plaintext credential values or local secret file contents |

## Implementation Slices

### Slice 1: Deployment Read Boundary

Status: Complete. Review artifact:
[PHASE_01_SLICE_01_DEPLOYMENT_READ_BOUNDARY_REVIEW.md](PHASE_01_SLICE_01_DEPLOYMENT_READ_BOUNDARY_REVIEW.md)

Files:

- Add `src/repositories/deployment_repository.py`.
- Add `src/services/deployment_read_service.py`.
- Update read-only handlers in `src/api/routes/twins.py`.
- Add or extend `tests/test_can_redeploy.py` and deployment history/status
  tests.

Moves:

- `GET /twins/{twin_id}/can-redeploy`
- `GET /twins/{twin_id}/deployment-status`
- `GET /twins/{twin_id}/outputs`
- `GET /twins/{twin_id}/deployments`

Gate:

- Existing endpoint contracts remain byte-for-byte compatible for status codes
  and response fields.
- Unit tests cover no-deployment, running, success, failed, and user-isolation
  cases.

### Slice 2: Twin Read And Lifecycle Boundary

Status: Complete. Review artifact:
[PHASE_01_SLICE_02_TWIN_LIFECYCLE_BOUNDARY_REVIEW.md](PHASE_01_SLICE_02_TWIN_LIFECYCLE_BOUNDARY_REVIEW.md)

Files:

- Add `src/repositories/twin_repository.py`.
- Add `src/services/twin_read_service.py`.
- Add `src/services/twin_lifecycle_service.py`.
- Update CRUD handlers in `src/api/routes/twins.py`.
- Extend `tests/test_twins.py` and `tests/test_twin_state_transitions.py`.

Moves:

- `GET /twins/`
- `POST /twins/`
- `GET /twins/{twin_id}`
- `PUT /twins/{twin_id}`
- `DELETE /twins/{twin_id}`

Gate:

- Duplicate-name behavior, case-insensitive matching, soft-delete behavior,
  user isolation, and configured-state validation remain covered.
- The repository never commits; lifecycle service owns transaction boundaries.

### Slice 3: SSE Registry And Stream Boundary

Status: Complete. Review artifact:
[PHASE_01_SLICE_03_SSE_STREAM_BOUNDARY_REVIEW.md](PHASE_01_SLICE_03_SSE_STREAM_BOUNDARY_REVIEW.md)

Files:

- Add `src/services/deployment_stream_service.py`.
- Move session registry behavior out of route-level globals in
  `src/api/routes/sse.py`.
- Keep `src/api/routes/sse.py` as the streaming HTTP adapter.
- Extend `tests/test_optimizer_stream.py` or add Management SSE unit tests.

Moves:

- Session creation, lookup, active-session checks, TTL cleanup, completion
  handling, and batch log persistence.

Gate:

- `/sse/deploy/{session_id}` contract remains unchanged.
- Tests cover pending, streaming, completed, missing session, active-session
  collision, and cleanup behavior.

### Slice 4: Deployment Command Boundary

Status: Complete. Review artifact:
[PHASE_01_SLICE_04_DEPLOYMENT_COMMAND_BOUNDARY_REVIEW.md](PHASE_01_SLICE_04_DEPLOYMENT_COMMAND_BOUNDARY_REVIEW.md)

Files:

- Add `src/services/deployment_operation_service.py`.
- Add `src/clients/deployer_client.py`.
- Keep existing ZIP helpers in `deployment_service.py` until a later credential
  bundle slice splits them safely.
- Update deploy and destroy handlers in `src/api/routes/twins.py`.
- Extend `tests/test_twin_state_transitions.py` and deployment route tests.

Moves:

- `POST /twins/{twin_id}/deploy`
- `POST /twins/{twin_id}/destroy`
- Background-task dispatch for real deploy and destroy operations.

Gate:

- State transitions for draft, configured, deploying, deployed, destroying,
  destroyed, and error states remain covered.
- Deployer downstream calls are mocked through `DeployerClient`.
- No live cloud or Deployer E2E calls run by default.

### Slice 5: Test Endpoint Quarantine

Status: In progress. Router quarantine complete:
[PHASE_01_SLICE_05A_TEST_ROUTER_QUARANTINE_REVIEW.md](PHASE_01_SLICE_05A_TEST_ROUTER_QUARANTINE_REVIEW.md)

Files:

- Add `src/services/test_deployment_service.py`.
- Update `src/api/routes/test_endpoints.py`.
- Update `src/main.py` to register the router only when the runtime gate is
  enabled.
- Extend tests for disabled and enabled test endpoint behavior.

Moves:

- `POST /twins/{twin_id}/test-deploy`
- `POST /twins/{twin_id}/test-destroy`
- `POST /twins/{twin_id}/test-log-trace/start`
- `GET /twins/{twin_id}/simulator/test-download`

Gate:

- Disabled test endpoints return 404 without route-specific logic executing.
- Production deployment services do not import `test_endpoints.py`.

### Slice 6: Verification, Simulator, And Export Boundary

Files:

- Add `src/services/verification_service.py`.
- Add `src/services/simulator_service.py`.
- Add `src/services/twin_export_service.py`.
- Update the remaining non-CRUD handlers in `src/api/routes/twins.py`.
- Extend `tests/test_simulator_download.py` and add verification/export tests.

Moves:

- `POST /twins/{twin_id}/verify/infrastructure`
- `POST /twins/{twin_id}/verify/dataflow`
- `GET /twins/{twin_id}/simulator/download`
- `GET /twins/{twin_id}/export`

Gate:

- Simulator archive content remains compatible with current tests.
- Verification client failures map to sanitized API errors.
- Export output does not include plaintext credentials.

### Slice 7: Config, Deployer, And Optimizer Route Thinning

Files:

- Add `src/repositories/configuration_repository.py`.
- Add focused services for config, deployer config, pricing refresh, and
  calculation bridge behavior.
- Add or extend tests in `tests/test_config_routes.py`,
  `tests/test_config.py`, and optimizer route tests.

Moves:

- `config.py`, `deployer.py`, `optimizer.py`, and `optimizer_config.py`
  route logic that performs DB writes or downstream HTTP calls.

Gate:

- Cloud credential SSOT behavior remains intact.
- Validation messages stay redacted.
- Optimizer and Deployer clients carry all downstream HTTP behavior.

## Compatibility Strategy

| Existing contract | Compatibility rule |
|---|---|
| API paths and operation ids | No path or operation id changes during Phase 1. |
| Response JSON shape | Preserve existing keys and status codes unless a separate contract phase approves a change. |
| Database schema | No schema changes in service-boundary slices unless Phase 1.5 approves a migration. |
| Flutter behavior | Flutter remains unaware of internal service extraction. |
| Existing tests | Current route tests remain the regression baseline and are extended rather than replaced. |
| Live cloud behavior | No default test invokes live cloud APIs or cloud-costing E2E flows. |

## Immediate Next Implementation Step

The first code slice is Slice 1: Deployment Read Boundary. It is read-only,
small enough to review completely, and creates the repository/service pattern
used by later write-heavy slices. It also reduces risk in `twins.py` before
touching deploy/destroy commands.

## Verification Evidence

| Check | Result |
|---|---|
| Existing Management service package reviewed | Passed |
| Existing Management route tests reviewed | Passed |
| Phase 1.1 route classification compared against target services | Passed |
| Repository package existence checked | No repository package exists yet |
| Live service or cloud calls | Not run by design |

## Residual Risk

This phase defines the implementation contract but does not change runtime code.
The architecture risk remains open under GitHub issue
[#102](https://github.com/caroline877/master-thesis/issues/102) until the
implementation slices above are completed and verified.
