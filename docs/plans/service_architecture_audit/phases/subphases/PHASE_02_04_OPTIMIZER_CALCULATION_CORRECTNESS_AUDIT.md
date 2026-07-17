---
title: "Phase 2.4: Optimizer Calculation Correctness Audit"
description: "Audit calculation formulas, provider layer models, pricing units, and known tiering gaps against thesis intent."
tags: [optimizer, calculation, formulas, tiering]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/backend/calculation_v2/
- integration_vision.md section "Theoretical Foundation"
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 2.4: Optimizer Calculation Correctness Audit

## Purpose

Verify that formulas consume pricing values with the intended unit, tier,
provider, and layer semantics.

## Scope

| In scope | Out of scope |
|---|---|
| Formula-to-intent review | Rewriting all formulas immediately |
| AWS/Azure/GCP layer calculations | Live billing validation |
| Known tiering gaps | New non-cost objectives |

## Deliverables

- Complete. Formula inventory status is captured in
  [Phase 2.4 Review](../../PHASE_02_04_OPTIMIZER_CALCULATION_CORRECTNESS_REVIEW.md).
- Complete. Azure Digital Twins unit compatibility was corrected in the
  strategy contract and calculator.
- Complete. Azure IoT Hub capacity-tier gaps were fixed. Azure Digital Twins
  was subsequently corrected in Phase 17 to use normalized flat usage meters
  plus explicit operation, routed-message, and query-unit workload quantities;
  remaining storage/transfer refinements are assigned to later provider-model
  work.
- Complete. Required regression tests are implemented in
  `tests/unit/calculation_v2/test_azure_tiered_calculations.py`.

## Acceptance Criteria

- Each formula declares expected input units.
- Provider tiering differences are either modeled, rejected, or documented as
  unsupported.
- Calculation output can explain which pricing evidence was used.

## Verification

- Complete. Static formula review captured in the Phase 2.4 review.
- Complete. Existing and new unit test coverage is mapped in the review.
- Complete. No paid cloud tests.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
