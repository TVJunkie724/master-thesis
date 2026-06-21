---
title: "Phase 2.6: Optimizer Test Matrix"
description: "Map Optimizer tests to pricing sources, fetchers, formulas, API contracts, and security risks."
tags: [optimizer, tests, pricing, quality]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/tests/
EXTRACTED: 2026-06-21 | VERSION: 1.1
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

- Complete. Test-to-risk matrix is captured in
  [Phase 2.6 Review](../../PHASE_02_06_OPTIMIZER_TEST_MATRIX_REVIEW.md).
- Complete. Missing fixture and future-work gaps are registered in the review.
- Complete. Safe Docker command plan for Optimizer verification is documented.

## Acceptance Criteria

- Every pricing source type has at least one planned regression test.
- Every formula correction has unit tests before and after changes.
- API failure paths are covered with user-safe errors.

## Verification

- Complete. Static test inventory captured in Phase 2.6 review.
- Complete. Mapping against Phase 2.1 through Phase 2.5 findings captured in
  the risk matrix.
- Complete. No paid cloud resource tests.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
