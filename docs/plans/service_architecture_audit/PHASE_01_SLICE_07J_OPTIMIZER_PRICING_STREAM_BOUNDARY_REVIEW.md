---
title: "Phase 1 Slice 7j Review: Optimizer Pricing Stream Boundary"
description: "Audit review for extracting pricing refresh SSE event generation, credential materialization, and Optimizer stream relay from the Management API optimizer route."
tags: [management-api, optimizer, pricing-stream, sse, credentials, service-boundary, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/optimizer.py
- twin2multicloud_backend/src/services/optimizer_pricing_stream_service.py
- twin2multicloud_backend/tests/test_optimizer_pricing_stream_service.py
- twin2multicloud_backend/tests/test_optimizer_stream.py
- twin2multicloud_backend/tests/test_optimizer_pricing_refresh_service.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7j Review: Optimizer Pricing Stream Boundary

## Review Result

Slice 7j is implemented. Pricing refresh SSE behavior now lives in
`OptimizerPricingStreamService`. The FastAPI route validates through the service,
then returns a `StreamingResponse` around the service-owned async event iterator.

This preserves the UI-facing SSE contract while removing credential lookup,
credential decryption, Optimizer stream connection, buffering, and SSE event
formatting from `optimizer.py`.

## Boundary Decisions

| Concern | Owner After Slice 7j |
|---|---|
| Supported stream provider validation | `OptimizerPricingStreamService` |
| SSE event string formatting | `OptimizerPricingStreamService` |
| AWS/GCP credential lookup and decryption | `OptimizerPricingStreamService` |
| Azure no-credentials stream path | `OptimizerPricingStreamService` |
| Optimizer `/stream/fetch_pricing/{provider}` relay | `OptimizerPricingStreamService` |
| SSE chunk buffering and event splitting | `OptimizerPricingStreamService` |
| Streaming HTTP response headers | `src/api/routes/optimizer.py` |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/services/optimizer_pricing_stream_service.py`
- `twin2multicloud_backend/src/api/routes/optimizer.py`
- `twin2multicloud_backend/tests/test_optimizer_pricing_stream_service.py`
- `twin2multicloud_backend/tests/test_optimizer_stream.py`

Behavior preserved:

- Invalid providers still return HTTP 400 before a stream is opened.
- Successful streams still use `text/event-stream`.
- Startup/progress events are emitted before the Optimizer stream relay.
- Azure still streams without credentials.
- AWS/GCP still load credentials from the twin configuration and forward only
  the provider-specific credential payload to Optimizer.
- Optimizer stream events are relayed without changing event bodies.
- Optimizer connection/timeout failures still produce SSE `error` events.

## Test Coverage

New service tests cover:

- Invalid provider validation.
- AWS credential decryption and downstream stream JSON payload.
- Optimizer SSE event relay.
- Missing credentials emitted as an SSE error event.

Existing route stream tests were updated to mock the new service boundary with
real async context-manager objects instead of coroutine-returning stream mocks.
This removed the previous RuntimeWarnings from the focused stream test run.

Focused verification:

```text
python -m pytest tests/test_optimizer_pricing_stream_service.py tests/test_optimizer_stream.py tests/test_optimizer_pricing_refresh_service.py -q
23 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| Route-level SSE generator mixed HTTP response construction, credentials, Optimizer stream relay, and event formatting. | Extracted to `OptimizerPricingStreamService`; route now only builds and returns the stream. |
| Existing SSE tests used coroutine-returning `stream` mocks, causing RuntimeWarnings. | Replaced with `MockSSEStream`, an async context manager matching `httpx.AsyncClient.stream()`. |
| The old stream path checked only AWS access key before decrypting AWS credentials. | Service now requires both AWS access key id and secret access key before streaming. |

## Residual Risk

`optimizer.py` still owns the calculation proxy endpoint. That is the last
remaining direct `httpx.AsyncClient` call in this route and should be extracted
as the next Optimizer boundary slice.
