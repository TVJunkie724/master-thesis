---
title: "Phase 2.5: Optimizer API Contract Audit"
description: "Audit Optimizer REST endpoints for typed contracts, safe errors, pricing evidence, and Management API compatibility."
tags: [optimizer, api, contracts, errors]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/api/
- 2-twin2clouds/rest_api.py
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 2.5: Optimizer API Contract Audit

## Purpose

Ensure Optimizer endpoints expose stable, Management-API-compatible contracts.

## Scope

| In scope | Out of scope |
|---|---|
| Calculation/pricing/regions/status endpoint review | Flutter UI work |
| Error model and validation review | Deployer API changes |
| Evidence and review-required response shape | OpenAI integration implementation |

## Deliverables

- Complete. Endpoint-to-response-model matrix is captured in
  [Phase 2.5 Review](../../PHASE_02_05_OPTIMIZER_API_CONTRACT_REVIEW.md).
- Complete. `GET /pricing/source_inventory` adds a schema-versioned response
  model for pricing source governance.
- Complete. Error response compatibility notes are captured for the new
  endpoint and legacy endpoints.
- Complete. Required pricing evidence/source fields for review UI handoff are
  exposed by the new response model.

## Acceptance Criteria

- Management API can proxy Optimizer responses without guessing payload shape.
- User-safe errors do not leak credentials or provider internals.
- Pricing refresh results distinguish success, review-required, failed, and
  unsupported states.

## Verification

- Complete. Static route/schema review captured in Phase 2.5 review.
- Complete. REST contract tests implemented in
  `tests/integration/test_pricing_source_inventory_api.py`.
- Complete. No live cloud deployment tests.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
