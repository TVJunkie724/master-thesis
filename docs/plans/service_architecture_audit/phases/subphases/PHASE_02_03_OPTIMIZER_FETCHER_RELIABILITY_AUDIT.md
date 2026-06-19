---
title: "Phase 2.3: Optimizer Fetcher Reliability Audit"
description: "Audit provider price fetchers for deterministic candidate matching, unit normalization, tier handling, and evidence capture."
tags: [optimizer, price-fetcher, reliability, evidence]
lastUpdated: "2026-06-19"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/backend/fetch_data/
- 2-twin2clouds/tests/unit/pricing/
EXTRACTED: 2026-06-19 | VERSION: 1.0
-->

# Phase 2.3: Optimizer Fetcher Reliability Audit

## Purpose

Review provider fetchers so pricing matches are deterministic, explainable, and
reject unsafe ambiguity.

## Scope

| In scope | Out of scope |
|---|---|
| AWS/Azure/GCP fetcher matching rules | Paid resource creation |
| Candidate evidence and rejection reasons | AI as source of truth |
| Unit/tier normalization plan | Full registry editor |

## Deliverables

- Provider fetcher behavior matrix.
- Candidate selection criteria for service name, SKU, meter, region, tier,
  unit, currency, and term.
- Rejected-candidate evidence requirements.
- Ambiguity behavior: review-required instead of silent fallback.

## Acceptance Criteria

- Fetchers never treat ambiguous candidates as successful automatic matches.
- Units such as per million, per 100k, GB, GiB, seconds, and requests are
  normalized before calculation.
- All selected rows can be inspected later by Management API/UI.

## Verification

- Static fetcher review.
- Fixture/test gap list for multi-candidate and no-candidate cases.
- No live cloud deployment tests.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
