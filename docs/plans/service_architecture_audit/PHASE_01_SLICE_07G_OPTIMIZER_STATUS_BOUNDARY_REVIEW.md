---
title: "Phase 1 Slice 7g Review: Optimizer Status Boundary"
description: "Audit review for extracting pricing and regions freshness status proxying from the Management API optimizer route."
tags: [management-api, optimizer, status, service-boundary, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/optimizer.py
- twin2multicloud_backend/src/services/optimizer_status_service.py
- twin2multicloud_backend/tests/test_optimizer_status_service.py
- twin2multicloud_backend/tests/test_error_handling.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7g Review: Optimizer Status Boundary

## Review Result

Slice 7g is implemented. Read-only Optimizer freshness checks now live in
`OptimizerStatusService`. The FastAPI route delegates to the service and maps
typed downstream errors to the existing HTTP status codes.

This slice intentionally covers only `pricing-status` and `regions-status`.
Pricing export, pricing refresh, SSE refresh, and calculation remain separate
slices because they involve different contracts: provider validation,
credential materialization, streaming semantics, and calculation DTOs.

## Boundary Decisions

| Concern | Owner After Slice 7g |
|---|---|
| Provider fan-out for AWS/Azure/GCP status | `OptimizerStatusService` |
| Optimizer `/pricing_age/{provider}` calls | `OptimizerStatusService` |
| Optimizer `/regions_age/{provider}` calls | `OptimizerStatusService` |
| Per-provider non-200 fallback shape | `OptimizerStatusService` |
| Connect, timeout, and request error classification | `OptimizerStatusService` |
| HTTP status mapping | `src/api/routes/optimizer.py` |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/services/optimizer_status_service.py`
- `twin2multicloud_backend/src/api/routes/optimizer.py`
- `twin2multicloud_backend/tests/test_optimizer_status_service.py`
- `twin2multicloud_backend/tests/test_error_handling.py`

Behavior preserved:

- `GET /optimizer/pricing-status` still returns provider-keyed status data.
- `GET /optimizer/regions-status` still returns provider-keyed status data.
- Non-200 provider responses still become `{"error": "Failed to fetch"}` for
  that provider.
- Optimizer connection failures still map to HTTP 503.
- Optimizer timeout failures still map to HTTP 504 without exposing the raw
  timeout message.
- Generic request failures still map to HTTP 502 with the exception type only.

## Test Coverage

New service tests cover:

- Pricing status aggregation across all providers.
- Region status fallback for a failed provider.
- ConnectError mapping.
- Timeout mapping.

Route regression tests were updated to mock the new service boundary:

```text
python -m pytest tests/test_optimizer_status_service.py tests/test_error_handling.py -q
32 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| Existing route tests mocked route-level `httpx.AsyncClient`. | Updated status tests to mock `src.services.optimizer_status_service.httpx.AsyncClient`. |
| `optimizer.py` still contains direct `httpx.AsyncClient` calls. | Accepted for this slice; remaining calls belong to export, refresh, SSE refresh, and calculation endpoints. |

## Residual Risk

The remaining Optimizer route methods still mix HTTP proxying, credential
materialization, SSE event formatting, and calculation forwarding. They should be
split into separate follow-up slices instead of one broad rewrite.
