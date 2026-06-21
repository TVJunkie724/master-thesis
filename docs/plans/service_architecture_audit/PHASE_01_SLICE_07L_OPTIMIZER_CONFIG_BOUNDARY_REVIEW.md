---
title: "Phase 1 Slice 7l Review: Optimizer Config Boundary"
description: "Audit review for extracting optimizer configuration persistence from the Management API optimizer-config route."
tags: [management-api, optimizer, optimizer-config, service-boundary, persistence, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/optimizer_config.py
- twin2multicloud_backend/src/services/optimizer_configuration_service.py
- twin2multicloud_backend/src/services/optimizer_config_projection.py
- twin2multicloud_backend/src/services/twin_configuration_service.py
- twin2multicloud_backend/tests/test_optimizer_configuration_service.py
- twin2multicloud_backend/tests/test_optimizer_config.py
- twin2multicloud_backend/tests/test_twin_configuration_service.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7l Review: Optimizer Config Boundary

## Review Result

Slice 7l is implemented. Optimizer configuration persistence now lives in
`OptimizerConfigurationService`. The FastAPI router authenticates the request,
keeps the existing request and response schemas, delegates to the service, and
maps typed not-found errors to the existing HTTP 404 contract.

The slice also centralizes optimizer-result projection in
`optimizer_config_projection.py`, so Step-1 config saves and Step-2 optimizer
config saves populate `cheapest_l*` columns through the same code path.

## Boundary Decisions

| Concern | Owner After Slice 7l |
|---|---|
| Twin ownership and active-twin enforcement | `TwinRepository` via `OptimizerConfigurationService` |
| Default optimizer config creation | `OptimizerConfigurationService` |
| Optimizer params persistence | `OptimizerConfigurationService` |
| Optimizer result and pricing evidence persistence | `OptimizerConfigurationService` |
| Cheapest-path response for deployment logic | `OptimizerConfigurationService` |
| JSON encode/decode and timestamp parsing | `optimizer_config_projection.py` |
| `cheapestPath` and `calculationResult` column projection | `optimizer_config_projection.py` |
| HTTP status mapping | `src/api/routes/optimizer_config.py` |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/api/routes/optimizer_config.py`
- `twin2multicloud_backend/src/services/optimizer_configuration_service.py`
- `twin2multicloud_backend/src/services/optimizer_config_projection.py`
- `twin2multicloud_backend/src/services/twin_configuration_service.py`
- `twin2multicloud_backend/tests/test_optimizer_configuration_service.py`
- `twin2multicloud_backend/tests/test_optimizer_config.py`

Behavior preserved:

- `GET /twins/{twin_id}/optimizer-config/` still creates and returns an empty
  optimizer configuration when a user-owned active twin has no config.
- `PUT /twins/{twin_id}/optimizer-config/params` still persists params without
  triggering calculation.
- `PUT /twins/{twin_id}/optimizer-config/result` still persists params, result,
  pricing snapshots, pricing timestamps, calculated timestamp, and cheapest
  provider columns.
- `GET /twins/{twin_id}/optimizer-config/cheapest-path` still returns HTTP 404
  until an optimizer result with `cheapest_l1` exists.
- Invalid pricing timestamp strings are ignored for that provider instead of
  failing the entire save.

Enterprise hardening added:

- The router no longer performs DB writes, commits, JSON serialization, JSON
  parsing, timestamp parsing, or cheapest-column projection.
- The service uses active-twin ownership enforcement through `TwinRepository`.
- Explicit cheapest-path values and optimizer-result-derived values are
  normalized to lowercase provider identifiers through a shared projection
  helper.
- Step-1 and Step-2 optimizer result saves now use one projection function,
  preventing divergent cheapest-column behavior.

## Test Coverage

New and extended tests cover:

- Default optimizer config creation.
- Param persistence without calculation result.
- Result persistence with explicit cheapest path, pricing snapshots, and
  timestamp handling.
- Result persistence with cheapest path derived from `calculationResult`.
- Cheapest-path 404 behavior before calculation.
- Inactive twin rejection through the service boundary.
- Route-level save-result and cheapest-path regression.
- Existing Step-1 optimizer result projection behavior after sharing the
  projection helper.

Focused verification:

```text
python -m pytest tests/test_optimizer_configuration_service.py tests/test_optimizer_config.py tests/test_twin_configuration_service.py -q
19 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| `optimizer_config.py` owned DB commits, JSON parsing, and projection logic. | Moved to `OptimizerConfigurationService` and `optimizer_config_projection.py`. |
| Cheapest-column projection existed only inside `TwinConfigurationService`, while `optimizer_config.py` had a separate explicit-map path. | Replaced the private Step-1 helper with the shared projection helper and used it in the new service. |
| The route used the older `get_user_twin` helper instead of the repository boundary. | Route now constructs the service with `TwinRepository`; active ownership checks live below the route. |

## Residual Risk

`src/api/routes/twins.py` still contains direct optimizer config reads for some
legacy response-shaping paths. Those reads are outside the `optimizer_config.py`
route boundary and remain in scope for the later `twins.py` route-thinning
slices.
