---
title: "Phase 1 Slice 7h Review: Optimizer Pricing Export Boundary"
description: "Audit review for extracting pricing snapshot export proxying from the Management API optimizer route."
tags: [management-api, optimizer, pricing-export, service-boundary, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/optimizer.py
- twin2multicloud_backend/src/services/optimizer_pricing_export_service.py
- twin2multicloud_backend/tests/test_optimizer_pricing_export_service.py
- twin2multicloud_backend/tests/test_error_handling.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7h Review: Optimizer Pricing Export Boundary

## Review Result

Slice 7h is implemented. Pricing snapshot export behavior now lives in
`OptimizerPricingExportService`. The FastAPI route authenticates, delegates to
the service, and maps typed validation/downstream errors to the existing HTTP
contract.

This slice intentionally covers only `GET /optimizer/pricing/export/{provider}`.
Pricing refresh, SSE refresh, and calculation remain separate slices because
they involve credential materialization, streaming behavior, and calculation DTO
contracts.

## Boundary Decisions

| Concern | Owner After Slice 7h |
|---|---|
| Supported export provider validation | `OptimizerPricingExportService` |
| Optimizer `/pricing/export/{provider}` HTTP call | `OptimizerPricingExportService` |
| Optimizer non-200 status mapping | `OptimizerPricingExportService` |
| Connect, timeout, and request error classification | `OptimizerPricingExportService` |
| HTTP 400/5xx mapping | `src/api/routes/optimizer.py` |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/services/optimizer_pricing_export_service.py`
- `twin2multicloud_backend/src/api/routes/optimizer.py`
- `twin2multicloud_backend/tests/test_optimizer_pricing_export_service.py`
- `twin2multicloud_backend/tests/test_error_handling.py`

Behavior preserved:

- `GET /optimizer/pricing/export/{provider}` still supports only `aws`,
  `azure`, and `gcp`.
- Invalid providers still return HTTP 400 with `Invalid provider: <provider>`.
- Successful Optimizer responses are returned as JSON without reshaping.
- Optimizer non-200 responses keep the downstream status code and response text.
- Optimizer timeout failures still map to HTTP 504.
- Generic request failures still map to HTTP 502 with the exception type only.

## Test Coverage

New service tests cover:

- Successful provider export payload relay.
- Invalid provider rejection before downstream calls.
- Optimizer non-200 mapping.
- Timeout mapping.

Route regression tests cover:

- Successful export response.
- Invalid provider HTTP 400 without downstream call.
- Timeout HTTP 504.

Focused verification:

```text
python -m pytest tests/test_optimizer_pricing_export_service.py tests/test_error_handling.py -q
35 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| Pricing export still performed provider validation and `httpx` calls inside the route. | Moved provider validation and downstream call handling into `OptimizerPricingExportService`. |
| Existing tests did not cover pricing export. | Added service and route regression tests for success, invalid provider, non-200, and timeout paths. |

## Residual Risk

`optimizer.py` still contains direct `httpx.AsyncClient` calls in pricing
refresh, SSE refresh, and calculation endpoints. Those are intentionally left
for dedicated slices because they involve credential handling, streaming, and
calculation contracts.
