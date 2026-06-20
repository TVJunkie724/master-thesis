---
title: "Phase 1.1: Management Route Responsibility Audit"
description: "Classify Management API route responsibilities before extracting service or repository boundaries."
tags: [management-api, routes, audit, architecture]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_01_MANAGEMENT_API_AUDIT.md
- twin2multicloud_backend/src/api/routes/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 1.1: Management Route Responsibility Audit

## Purpose

Classify every Management API route by actual responsibility so later refactors
move behavior deliberately instead of reshuffling code.

## Scope

| In scope | Out of scope |
|---|---|
| Route handler inventory | Code extraction |
| Controller/orchestration/proxy/persistence classification | Backend endpoint redesign |
| Risk ranking for oversized route files | Flutter changes |

## Deliverables

- Route inventory for all files under `twin2multicloud_backend/src/api/routes/`.
- Classification per endpoint: controller-only, orchestration, persistence,
  downstream proxy, stream/SSE, test-only, or mixed.
- Risk list for route handlers that write DB state and call downstream services
  in the same function.
- Recommended extraction order for Phase 1.2.
- Completed review artifact:
  [PHASE_01_01_MANAGEMENT_ROUTE_RESPONSIBILITY_REVIEW.md](../../PHASE_01_01_MANAGEMENT_ROUTE_RESPONSIBILITY_REVIEW.md)

## Acceptance Criteria

- Every route module is classified.
- `twins.py`, `config.py`, `deployer.py`, `optimizer.py`, `sse.py`, and
  `test_endpoints.py` have explicit split recommendations.
- Test-only endpoints are clearly separated from production endpoints.

## Verification

- Static route scan.
- Manual review of FastAPI router registrations.
- No live service calls.

## Parent Phase

[Phase 1: Management API Audit](../PHASE_01_MANAGEMENT_API_AUDIT.md)
