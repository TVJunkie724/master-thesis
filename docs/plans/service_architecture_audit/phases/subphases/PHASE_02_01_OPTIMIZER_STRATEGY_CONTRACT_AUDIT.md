---
title: "Phase 2.1: Optimizer Strategy Contract Audit"
description: "Audit the contract that binds optimization objective, pricing intent, fetchers, calculators, formulas, and evidence."
tags: [optimizer, strategy, contracts, pricing]
lastUpdated: "2026-06-19"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/backend/calculation_v2/
- 2-twin2clouds/backend/fetch_data/
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 2.1: Optimizer Strategy Contract Audit

## Purpose

Ensure each optimization strategy has a coherent contract from user intent to
pricing source, formula, calculation result, and evidence trace.

## Scope

| In scope | Out of scope |
|---|---|
| Strategy contract target model | Implementing new objectives |
| Cost objective compatibility | AI-assisted row selection implementation |
| Formula ownership rules | Flutter UI work |

## Deliverables

- Complete. `2-twin2clouds/backend/calculation_v2/strategy_contracts.py`
  declares target contract fields for objective, intent, source, fetcher,
  calculator, formula, unit normalization, and evidence.
- Complete. Formula bindings reference declared pricing intents and expose
  required usage inputs, normalizers, and calculation entrypoints.
- Complete. Latency, emissions, and resilience are explicit disabled future
  objectives and cannot be selected at runtime.

## Acceptance Criteria

- Cost optimization remains the only enabled objective unless explicitly
  implemented later.
- Future objectives can be added without changing current cost semantics.
- Pricing intent and calculation formula cannot drift silently.

## Verification

- Complete. Static review of calculation and fetcher abstractions captured in
  [Phase 2.1 Review](../../PHASE_02_01_OPTIMIZER_STRATEGY_CONTRACT_REVIEW.md).
- Complete. Contract gap list is assigned to Phase 2.2, 2.3, 2.4, and 2.5.
- Complete. Focused Dockerized tests:
  `python -m pytest tests/unit/calculation_v2/test_strategy_contracts.py -q`.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
