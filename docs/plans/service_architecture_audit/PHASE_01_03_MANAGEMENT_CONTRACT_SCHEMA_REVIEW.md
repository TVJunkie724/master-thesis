---
title: "Phase 1.3 Review: Management Contract And Schema Audit"
description: "Audit review for Management API OpenAPI response contracts and raw payload exceptions."
tags: [management-api, openapi, schemas, contracts, tests, issue-102]
lastUpdated: "2026-06-21"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/subphases/PHASE_01_03_MANAGEMENT_CONTRACT_SCHEMA_AUDIT.md
- twin2multicloud_backend/src/api/routes/
- twin2multicloud_backend/src/schemas/
- twin2multicloud_backend/tests/test_management_contracts.py
EXTRACTED: 2026-06-21 | VERSION: 1.0
-->

# Phase 1.3 Review: Management Contract And Schema Audit

## Review Result

Phase 1.3 is implemented for the Management API contract surface. Stable
Flutter-facing JSON endpoints now expose explicit response models in OpenAPI.
Endpoints that stream data, return files, redirect, serve XML, or pass through
dynamic downstream payloads remain unmodeled by design and are registered below
as raw payload exceptions.

## Typed Contract Additions

New schema module:

- `twin2multicloud_backend/src/schemas/management_contracts.py`

New response models:

| Model | Used by |
|---|---|
| `AuthUrlResponse` | Google and UIBK login URL endpoints |
| `AuthProvidersResponse` | Available auth providers endpoint |
| `CurrentUserResponse` | Current-user get and update endpoints |
| `HealthResponse` | Health check endpoint |
| `MessageResponse` | Delete/acknowledgement endpoints |
| `OperationSessionResponse` | Deploy and destroy command endpoints |
| `RedeployReadinessResponse` | Redeploy cooldown endpoint |
| `DeploymentStatusResponse` | Deployment status endpoint |
| `DeploymentOutputsResponse` | Terraform outputs endpoint |
| `DeploymentHistoryResponse` | Deployment history endpoint |
| `SceneGlbUploadResponse` | Scene GLB upload endpoint |
| `DualCredentialValidationResponse` | Inline and stored dual credential validation |

Existing model reused:

- `CheapestPathResponse` for
  `GET /twins/{twin_id}/optimizer-config/cheapest-path`

## Endpoint Matrix

| Endpoint | Contract state |
|---|---|
| `GET /auth/google/login` | `AuthUrlResponse` |
| `GET /auth/uibk/login` | `AuthUrlResponse` |
| `GET /auth/me` | `CurrentUserResponse` |
| `PATCH /auth/me` | `CurrentUserResponse` |
| `GET /auth/providers` | `AuthProvidersResponse` |
| `GET /health` | `HealthResponse` |
| `DELETE /twins/{twin_id}` | `MessageResponse` |
| `GET /twins/{twin_id}/can-redeploy` | `RedeployReadinessResponse` |
| `POST /twins/{twin_id}/deploy` | `OperationSessionResponse` |
| `POST /twins/{twin_id}/destroy` | `OperationSessionResponse` |
| `GET /twins/{twin_id}/deployment-status` | `DeploymentStatusResponse` |
| `GET /twins/{twin_id}/outputs` | `DeploymentOutputsResponse` |
| `GET /twins/{twin_id}/deployments` | `DeploymentHistoryResponse` |
| `POST /twins/{twin_id}/config/validate-stored/{provider}` | `DualCredentialValidationResponse` |
| `POST /config/validate-dual` | `DualCredentialValidationResponse` |
| `GET /twins/{twin_id}/optimizer-config/cheapest-path` | `CheapestPathResponse` |
| `POST /twins/{twin_id}/deployer/upload-glb` | `SceneGlbUploadResponse` |
| `DELETE /twins/{twin_id}/deployer/upload-glb` | `MessageResponse` |

## Raw Payload Exception Register

| Endpoint | Reason |
|---|---|
| `GET /auth/google/callback` | Redirect response with token-bearing frontend callback URL |
| `POST /auth/uibk/callback` | Redirect response with token-bearing frontend callback URL |
| `GET /auth/uibk/metadata` | XML SAML metadata response |
| `GET /twins/{twin_id}/log-trace/stream/{trace_id}` | SSE stream |
| `GET /twins/{twin_id}/simulator/download` | ZIP file download |
| `GET /twins/{twin_id}/export` | ZIP file download |
| `GET /sse/deploy/{session_id}` | SSE stream |
| `POST /twins/{twin_id}/deployer/upload-zip` | Dynamic Deployer extraction payload; route preserves downstream shape for Step-3 auto-population |
| `PUT /optimizer/calculate` | Dynamic Optimizer calculation payload; strategy-contract hardening owns the final typed calculation model |
| `GET /optimizer/pricing-status` | Dynamic Optimizer status payload; Optimizer audit owns provider-specific pricing status contracts |
| `GET /optimizer/regions-status` | Dynamic Optimizer status payload; Optimizer audit owns provider-specific region status contracts |
| `GET /optimizer/pricing/export/{provider}` | Provider-specific pricing evidence payload |
| `POST /optimizer/refresh-pricing/{provider}` | Provider-specific pricing refresh payload |
| `GET /optimizer/stream/refresh-pricing/{provider}` | SSE stream |

## Security Review

- No new response model exposes plaintext credential fields.
- Dual validation responses include only `valid`, user-safe `message`, and
  sanitized `permissions` payloads from the existing validation service.
- Terraform outputs remain typed as `dict[str, Any] | None` because the content
  is deployment evidence, not credential input. Redaction remains owned by the
  deployment/export services.

## Verification Evidence

Focused verification:

```text
python -m pytest tests/test_management_contracts.py -q
2 passed, 3 warnings
```

Full Management API verification:

```text
python -m pytest tests -q
287 passed, 3 warnings
```

## Review Findings

| Finding | Resolution |
|---|---|
| Stable JSON command/read endpoints lacked response models in OpenAPI. | Added focused response models and bound them to the routes. |
| `upload-zip` initially looked typeable, but existing route tests prove the Deployer may omit canonical sections while the Management API preserves the raw response. | Kept `upload-zip` unmodeled and registered it as an explicit raw payload exception. |
| OpenAPI response-model regressions were not covered by tests. | Added `tests/test_management_contracts.py` with schema reference assertions and raw-exception assertions. |

## Residual Risk

Optimizer pricing and calculation responses remain dynamic until the Optimizer
strategy-contract and pricing-source phases finalize provider-specific payload
contracts. This is tracked by Phase 2 of the Service Architecture Audit Roadmap.
