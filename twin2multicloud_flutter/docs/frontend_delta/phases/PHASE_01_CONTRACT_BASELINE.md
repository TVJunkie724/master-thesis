---
title: "Phase 1: Contract Baseline"
description: "Define the stable Management API contracts Flutter needs before UI delta implementation starts."
tags: [flutter, frontend-delta, api-contracts, management-api]
lastUpdated: "2026-06-13"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- docs/plans/provider_access_pricing_review/phase_01_credential_purpose_model.md
- docs/plans/provider_access_pricing_review/phase_05_reviewed_decisions_persistence.md
- docs/plans/provider_access_pricing_review/phase_06_pricing_review_center_ui.md
- twin2multicloud_backend/src/api/routes/cloud_connections.py
- twin2multicloud_backend/src/api/routes/optimizer.py
EXTRACTED: 2026-06-13 | VERSION: 1.0
-->

# Phase 1: Contract Baseline

## Summary

Freeze the Management API read/write contracts that Flutter must consume for
credentials, pricing readiness, pricing review, deployer configuration, and
deployment operations.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Contract inventory for required Flutter screens | Flutter UI implementation |
| DTO field requirements and redaction rules | Direct Optimizer/Deployer calls |
| Missing endpoint list for backend work | Live cloud E2E |
| Compatibility decision for existing drafts | Schema-less dynamic UI payloads |

## Prerequisites

- Credential SSOT model exists or has an approved implementation plan.
- Pricing review and provider access roadmap is approved.
- Backend routes are owned by the Management API boundary.

## Deliverables

- Contract checklist for:
  - `GET /cloud-access` (backend read model implemented; Flutter DTO work remains)
  - `GET /optimizer/pricing-health` (backend read model implemented; Flutter DTO work remains)
  - provider pricing refresh start/stream routes (backend run contract implemented; Flutter DTO work remains)
  - pricing candidate review routes (backend contract implemented; Flutter DTO
    work remains)
  - pricing reviewed decision routes (backend contract implemented; Flutter DTO
    work remains)
  - pricing trace/evidence read routes for intent-to-result inspection
    (backend contract implemented; raw Optimizer candidate enrichment remains
    tracked under #100)
  - CloudConnection preflight routes
  - Twin Overview simulator/test utility routes
  - typed deployer configuration read/write routes
- Flutter DTO readiness matrix.
- Backend gaps classified as feature requests or bugs.
- Compatibility rule for legacy drafts and CloudConnection-only twins.
- Implementation plan and audit:
  [2026-06-17_frontend_delta_phase_01_contract_baseline.md](../../../implementation_plans/2026-06-17_frontend_delta_phase_01_contract_baseline.md)

## Required Contract Decisions

The contract baseline must explicitly answer these questions before UI
implementation starts:

| Area | Required decision |
|---|---|
| Pricing trace | Which Management API route returns the full sanitized fetch trace for a provider/intent/review run? |
| Pricing trace shape | How are intent, provider query scope, candidate rows, rejected rows, selected row, hard checks, normalization, AI suggestion, and reviewed decision linked? |
| Pricing trace safety | Which raw provider fields are safe to display in a collapsed debug/evidence panel? |
| Simulator tests | Which Twin Overview action starts a simulator/test message run, and which route returns status/log output? |
| Preflight | Which route returns deployment credential readiness, permission-set status, and remediation actions? |
| Legacy drafts | Which fields are accepted only for read/migration compatibility and which fields must not be written by new Flutter saves? |

## Acceptance Criteria

- All future Flutter phases reference typed Management API contracts.
- Required fields are explicitly listed, including credential purpose, scope,
  identity label, account/project/subscription, permission-set status, pricing
  freshness, review state, selected candidate metadata, pricing trace metadata,
  and simulator/test operation state.
- No contract returns secret values, local file paths, or admin credentials.
- No phase depends on RBAC until a real role model exists.
- Every route used by Flutter has a typed loading/success/error shape that can
  be rendered without parsing log text.

## Verification

- Contract review against existing backend route files.
- OpenAPI or route-level schema review where available.
- Manual checklist proving each downstream UI phase has its required fields.
- Backend pricing review contract tests:
  `docker compose run --rm management-api sh -lc 'cd /app && PYTHONPATH=/app python -m pytest tests/test_pricing_review_contracts.py -q'`
- Local contract smoke, when the stack is available:
  `docker compose ps` and Management API `/openapi.json` inspection.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
