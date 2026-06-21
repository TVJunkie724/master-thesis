---
title: "Phase 1 Slice 7k Review: Optimizer Calculation Boundary"
description: "Audit review for extracting calculation proxying from the Management API optimizer route."
tags: [management-api, optimizer, calculation, service-boundary, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/optimizer.py
- twin2multicloud_backend/src/services/optimizer_calculation_service.py
- twin2multicloud_backend/tests/test_optimizer_calculation_service.py
- twin2multicloud_backend/tests/test_error_handling.py
- twin2multicloud_backend/tests/test_optimizer_stream.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7k Review: Optimizer Calculation Boundary

## Review Result

Slice 7k is implemented. Calculation proxy behavior now lives in
`OptimizerCalculationService`. The FastAPI route keeps the `CalcParams` request
schema, delegates the serialized payload to the service, and maps typed
downstream errors to the existing HTTP contract.

This removes the last direct `httpx.AsyncClient` call from `src/api/routes/optimizer.py`.

## Boundary Decisions

| Concern | Owner After Slice 7k |
|---|---|
| Optimizer `/calculate` HTTP call | `OptimizerCalculationService` |
| Calculation request payload forwarding | `OptimizerCalculationService` |
| Optimizer non-200 status mapping | `OptimizerCalculationService` |
| Connect, timeout, and request error classification | `OptimizerCalculationService` |
| Request schema validation | `src/api/routes/optimizer.py` through `CalcParams` |
| HTTP downstream error mapping | `src/api/routes/optimizer.py` |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/services/optimizer_calculation_service.py`
- `twin2multicloud_backend/src/api/routes/optimizer.py`
- `twin2multicloud_backend/tests/test_optimizer_calculation_service.py`

Behavior preserved:

- `PUT /optimizer/calculate` still accepts the existing `CalcParams` schema.
- Valid requests are forwarded to Optimizer as JSON.
- Successful Optimizer responses are returned without reshaping.
- Optimizer non-200 responses keep downstream status and response text.
- Optimizer connection and timeout failures still map to HTTP 503 and 504.
- Generic request failures still map to HTTP 502 with exception type only.

## Test Coverage

New tests cover:

- Service payload forwarding and response relay.
- Optimizer non-200 mapping.
- Optimizer timeout mapping.
- Route-level success with a valid `CalcParams` payload.
- Route-level timeout mapping.

Focused verification:

```text
python -m pytest tests/test_optimizer_calculation_service.py tests/test_error_handling.py tests/test_optimizer_stream.py -q
43 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| Existing sample calculation fixture violates current `CalcParams` constraints for some fields. | Route tests normalize only the fields required for the current schema constraints. |
| `optimizer.py` still owned the direct calculation `httpx` call. | Moved to `OptimizerCalculationService`; route now has no direct `httpx` imports. |

## Residual Risk

`optimizer_config.py` remains a separate Management API route file with
persistence behavior that still needs its own boundary audit. The main
`optimizer.py` route thinning target is complete.
