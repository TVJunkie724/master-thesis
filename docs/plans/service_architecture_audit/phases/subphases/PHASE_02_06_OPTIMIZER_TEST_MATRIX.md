---
title: "Phase 2.6: Optimizer Test Matrix"
description: "Map Optimizer tests to pricing sources, fetchers, formulas, API contracts, and security risks."
tags: [optimizer, tests, pricing, quality]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/tests/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 2.6: Optimizer Test Matrix

## Purpose

Ensure Optimizer hardening has broad enough tests to prove pricing and
calculation behavior without paid resource creation.

## Scope

| In scope | Out of scope |
|---|---|
| Unit/integration test inventory | Live cloud deployment |
| Pricing fixture coverage | Flutter tests |
| Security and error tests | Full billing reconciliation |

## Deliverables

- Test-to-risk matrix for pricing sources, fetcher matching, formulas, API
  contracts, validation, and credentials.
- Missing fixtures for selected, rejected, ambiguous, unsupported, static, and
  stale pricing cases.
- Safe Docker command plan for Optimizer verification.

## Acceptance Criteria

- Every pricing source type has at least one planned regression test.
- Every formula correction has unit tests before and after changes.
- API failure paths are covered with user-safe errors.

## Verification

- Static test inventory.
- Mapping against Phase 2.1 through Phase 2.5 findings.
- No paid cloud resource tests.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
