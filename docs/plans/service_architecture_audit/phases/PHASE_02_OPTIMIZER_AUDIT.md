---
title: "Phase 2: Optimizer Audit"
description: "Audit the Optimizer for pricing fetcher reliability, strategy/calculation contracts, evidence traceability, error handling, API contracts, and tests."
tags: [optimizer, pricing, audit, architecture, quality]
lastUpdated: "2026-06-21"
version: "1.7"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md
- 2-twin2clouds/backend/fetch_data/
- 2-twin2clouds/backend/calculation_v2/
- 2-twin2clouds/api/
- 2-twin2clouds/json/
- 2-twin2clouds/tests/
- 2-twin2clouds/implementation_plans/
EXTRACTED: 2026-06-21 | VERSION: 1.7
-->

# Phase 2: Optimizer Audit

## Summary

Audit the Optimizer as the cost and pricing authority. This phase should
prepare the service for the pricing reliability roadmap: intent-driven fetching,
evidence-backed candidate selection, strategy-bound formulas, and future
optimization metrics.

## Scope

| In scope | Out of scope |
|---|---|
| Pricing fetcher architecture and evidence handling | Live paid cloud deployment |
| Calculation strategy and formula ownership | Replacing provider pricing APIs |
| API request/response schema review | Building the Flutter Pricing Review UI |
| Error/log/security review | Using AI as an automatic source of truth |
| Static vs dynamic pricing source policy | Implementing new optimization objectives immediately |

## Audit Findings To Address

| Finding | Evidence |
|---|---|
| Pricing/fetching and calculation files remain large and provider-specific. | `calculate_up_to_date_pricing.py` has 775 lines; provider fetchers are ~384-427 lines; provider layer files are ~373-450 lines. |
| Strategy contracts need to bind optimization objective, pricing intent, calculation model, formulas, and verification evidence. | Current roadmap discussions require this to avoid mismatched units and pricing models. |
| Provider API matching cannot rely on naive string selection. | Pricing APIs return heterogeneous SKUs, meters, tiers, units, and regions. |
| Error/log behavior needs standardization. | 49 broad `except Exception` matches and 12 `print()` matches were found. |
| Tooling is not centrally declared. | Only `requirements.txt` was found at project root. |

## Subphases

| Subphase | Status | Deliverable |
|---|---|---|
| 2.1 | Complete | [Strategy Contract Audit](subphases/PHASE_02_01_OPTIMIZER_STRATEGY_CONTRACT_AUDIT.md) |
| 2.2 | Complete | [Pricing Source Audit](subphases/PHASE_02_02_OPTIMIZER_PRICING_SOURCE_AUDIT.md) |
| 2.3 | Complete | [Fetcher Reliability Audit](subphases/PHASE_02_03_OPTIMIZER_FETCHER_RELIABILITY_AUDIT.md) |
| 2.4 | Complete | [Calculation Correctness Audit](subphases/PHASE_02_04_OPTIMIZER_CALCULATION_CORRECTNESS_AUDIT.md) |
| 2.5 | Complete | [API Contract Audit](subphases/PHASE_02_05_OPTIMIZER_API_CONTRACT_AUDIT.md) |
| 2.6 | Complete | [Test Matrix](subphases/PHASE_02_06_OPTIMIZER_TEST_MATRIX.md) |

## Acceptance Criteria

- Every supported pricing field has a declared source type and verification
  strategy.
- Fallback values are emergency-only, visible, and never silently treated as
  successful pricing.
- Calculation formulas are bound to the strategy contract that selected their
  pricing inputs.
- Provider-specific unit/tier mismatches are explicitly normalized or rejected.
- Tests cover representative dynamic, static, rejected, and unsupported pricing
  cases.

## Verification Gates

- Static review of pricing JSON/schema files and fetcher code.
- Unit test inventory for formulas, pricing keys, and provider fetchers.
- Integration test inventory for pricing endpoints without paid cloud resource
  creation.
- Security review for credential validation endpoints and logs.
- No live deployment E2E tests.

## Roadmap Anchor

[Service Architecture Audit Roadmap](../ROADMAP_SERVICE_ARCHITECTURE_AUDIT.md)
