---
title: "Phase 2.1: Optimizer Strategy Contract Audit"
description: "Audit the contract that binds optimization objective, pricing intent, fetchers, calculators, formulas, and evidence."
tags: [optimizer, strategy, contracts, pricing]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/backend/calculation_v2/
- 2-twin2clouds/backend/fetch_data/
EXTRACTED: 2026-06-19 | VERSION: 1.0
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

- Target contract fields for objective, intent, source, fetcher, calculator,
  formula, unit normalization, and evidence.
- Compatibility rules that prevent a price from being used with the wrong
  formula or metric.
- Extension notes for disabled future objectives such as latency or emissions.

## Acceptance Criteria

- Cost optimization remains the only enabled objective unless explicitly
  implemented later.
- Future objectives can be added without changing current cost semantics.
- Pricing intent and calculation formula cannot drift silently.

## Verification

- Static review of calculation and fetcher abstractions.
- Contract gap list for implementation planning.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
