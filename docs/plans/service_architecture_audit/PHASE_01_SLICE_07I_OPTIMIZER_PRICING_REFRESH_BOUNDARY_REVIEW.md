---
title: "Phase 1 Slice 7i Review: Optimizer Pricing Refresh Boundary"
description: "Audit review for extracting pricing refresh credential materialization and Optimizer proxying from the Management API optimizer route."
tags: [management-api, optimizer, pricing-refresh, credentials, security, service-boundary, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/PHASE_01_02_MANAGEMENT_SERVICE_BOUNDARY_REVIEW.md
- twin2multicloud_backend/src/api/routes/optimizer.py
- twin2multicloud_backend/src/services/optimizer_pricing_refresh_service.py
- twin2multicloud_backend/src/services/secret_redaction.py
- twin2multicloud_backend/tests/test_optimizer_pricing_refresh_service.py
- twin2multicloud_backend/tests/test_credential_validation_service.py
- twin2multicloud_backend/tests/test_error_handling.py
- twin2multicloud_backend/tests/test_optimizer_stream.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1 Slice 7i Review: Optimizer Pricing Refresh Boundary

## Review Result

Slice 7i is implemented. Pricing refresh behavior now lives in
`OptimizerPricingRefreshService`. The FastAPI route authenticates, delegates to
the service, and maps typed not-found, validation, and downstream errors to the
existing HTTP contract.

This slice intentionally covers only `POST /optimizer/refresh-pricing/{provider}`.
SSE refresh remains route-owned for now and is the next dedicated slice because
it has streaming semantics and event formatting.

## Boundary Decisions

| Concern | Owner After Slice 7i |
|---|---|
| Supported refresh provider validation | `OptimizerPricingRefreshService` |
| Twin ownership lookup for credentialed refresh | `OptimizerPricingRefreshService` through `TwinRepository` |
| AWS/GCP credential completeness checks | `OptimizerPricingRefreshService` |
| AWS/GCP credential decryption for refresh | `OptimizerPricingRefreshService` |
| Azure public pricing refresh call | `OptimizerPricingRefreshService` |
| Optimizer credentialed refresh call | `OptimizerPricingRefreshService` |
| Downstream error redaction by known credential values | `secret_redaction.py` |
| HTTP 400/404/5xx mapping | `src/api/routes/optimizer.py` |

## Implementation Evidence

Files changed:

- `twin2multicloud_backend/src/services/optimizer_pricing_refresh_service.py`
- `twin2multicloud_backend/src/services/secret_redaction.py`
- `twin2multicloud_backend/src/services/credential_validation_service.py`
- `twin2multicloud_backend/src/api/routes/optimizer.py`
- `twin2multicloud_backend/tests/test_optimizer_pricing_refresh_service.py`
- `twin2multicloud_backend/tests/test_credential_validation_service.py`

Behavior preserved:

- Azure refresh still calls the Optimizer public pricing endpoint with
  `force_fetch=true` and no credential JSON body.
- AWS refresh still decrypts and forwards access key id, secret access key, and
  region to the Optimizer credentialed endpoint.
- GCP refresh still decrypts and forwards service-account JSON and region to
  the Optimizer credentialed endpoint.
- Invalid providers still return HTTP 400 with the existing provider guidance.
- Missing twins return HTTP 404.
- Missing configuration or provider credentials return HTTP 400.
- Optimizer connection, timeout, request, and non-200 errors still map to the
  existing status-code family.

## Security Hardening

Downstream non-200 response text is now redacted before returning to callers
when credentials were materialized. This prevents accidental leakage if the
Optimizer echoes a credential fragment in an error response.

The existing credential validation redaction helpers were moved into
`secret_redaction.py` so refresh, validation, and future downstream services can
share one redaction implementation.

## Test Coverage

New service tests cover:

- Azure refresh without credential body.
- AWS credential decryption and downstream payload shape.
- GCP service-account decryption and downstream payload shape.
- Invalid provider rejection before downstream calls.
- Missing twin and missing configuration handling.
- Incomplete AWS credentials.
- Optimizer non-200 mapping.
- Optimizer timeout mapping.
- Redaction of leaked credential values in Optimizer error text.

Focused verification:

```text
python -m pytest tests/test_optimizer_pricing_refresh_service.py tests/test_credential_validation_service.py tests/test_error_handling.py tests/test_optimizer_stream.py -q
59 passed, 5 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| The route initially missed the `TwinRepository` import for service construction. | Added the import and reran focused tests successfully. |
| Downstream non-200 text could include leaked credential values. | Added shared redaction and a regression test that simulates an echoed AWS secret. |
| The old route checked only `aws_access_key_id` before decrypting AWS credentials. | Service now requires both AWS access key id and secret access key before refresh. |

## Residual Risk

`stream_refresh_pricing` still performs credential lookup, decryption, Optimizer
SSE connection, and event formatting inside `optimizer.py`. It should be the
next Optimizer boundary slice. The lingering RuntimeWarnings in the existing SSE
tests are pre-existing mock-shape warnings and should be addressed when the SSE
boundary is extracted.
