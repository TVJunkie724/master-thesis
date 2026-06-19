---
title: "Phase 2.4: Optimizer Calculation Correctness Audit"
description: "Audit calculation formulas, provider layer models, pricing units, and known tiering gaps against thesis intent."
tags: [optimizer, calculation, formulas, tiering]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/backend/calculation_v2/
- integration_vision.md section "Theoretical Foundation"
EXTRACTED: 2026-06-19 | VERSION: 1.0
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

- Formula inventory for all enabled layers and providers.
- Unit compatibility matrix from pricing source to formula input.
- Tiering gap register for IoT Hub, Digital Twins, storage, transfer, and
  equivalent provider services.
- Required regression test list for corrected formulas.

## Acceptance Criteria

- Each formula declares expected input units.
- Provider tiering differences are either modeled, rejected, or documented as
  unsupported.
- Calculation output can explain which pricing evidence was used.

## Verification

- Static formula review.
- Existing unit test coverage mapping.
- No paid cloud tests.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
