---
title: "Phase 2.2: Optimizer Pricing Source Audit"
description: "Classify every Optimizer pricing value by source type, evidence, refreshability, and failure behavior."
tags: [optimizer, pricing, sources, evidence]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/json/
- 2-twin2clouds/backend/fetch_data/
EXTRACTED: 2026-06-19 | VERSION: 1.0
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

- Pricing field inventory for AWS, Azure, and GCP.
- Source classification: dynamic API, static official table, derived formula,
  manual override, or unsupported.
- Evidence requirements for selected and rejected candidate rows.
- Drift and stale-data behavior recommendation.

## Acceptance Criteria

- No required pricing field can be silently populated by an undocumented
  fallback.
- Static values are explicitly sourced and marked non-fetchable.
- Dynamic values record enough evidence for later user/developer review.

## Verification

- Static review of pricing JSON and fetcher outputs.
- Provider-by-provider source matrix.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
