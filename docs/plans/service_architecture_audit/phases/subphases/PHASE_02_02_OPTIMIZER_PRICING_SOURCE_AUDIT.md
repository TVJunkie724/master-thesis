---
title: "Phase 2.2: Optimizer Pricing Source Audit"
description: "Classify every Optimizer pricing value by source type, evidence, refreshability, and failure behavior."
tags: [optimizer, pricing, sources, evidence]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/json/
- 2-twin2clouds/backend/fetch_data/
EXTRACTED: 2026-06-21 | VERSION: 1.1
-->

# Phase 2.2: Optimizer Pricing Source Audit

## Purpose

Make pricing values explainable and maintainable by declaring where each value
comes from and how it is verified.

## Scope

| In scope | Out of scope |
|---|---|
| Dynamic/static/derived/unsupported classification | Scraping unofficial web pages |
| Evidence and refreshability rules | Immediate formula changes |
| No-fallback policy | Full pricing editor UI |

## Deliverables

- Complete. `2-twin2clouds/backend/calculation_v2/pricing_source_inventory.py`
  builds a pricing field inventory for AWS, Azure, and GCP from the strategy
  contract.
- Complete. Source classification covers dynamic API, static official table,
  reviewed decision, derived calculation, and unsupported values.
- Complete. Evidence requirements and emergency fallback visibility are exposed
  per field.
- Complete. Drift and stale-data behavior is represented as reject, require
  review, use reviewed decision, derive from usage model, or mark unsupported.

## Acceptance Criteria

- No required pricing field can be silently populated by an undocumented
  fallback.
- Static values are explicitly sourced and marked non-fetchable.
- Dynamic values record enough evidence for later user/developer review.

## Verification

- Complete. Static review captured in
  [Phase 2.2 Review](../../PHASE_02_02_OPTIMIZER_PRICING_SOURCE_REVIEW.md).
- Complete. Provider-by-provider source matrix is documented in the review.
- Complete. Focused Dockerized tests:
  `python -m pytest tests/unit/calculation_v2/test_strategy_contracts.py tests/unit/calculation_v2/test_pricing_source_inventory.py -q`.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
