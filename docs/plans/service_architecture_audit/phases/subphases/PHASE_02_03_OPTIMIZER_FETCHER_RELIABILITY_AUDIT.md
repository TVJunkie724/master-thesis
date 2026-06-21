---
title: "Phase 2.3: Optimizer Fetcher Reliability Audit"
description: "Audit provider price fetchers for deterministic candidate matching, unit normalization, tier handling, and evidence capture."
tags: [optimizer, price-fetcher, reliability, evidence]
lastUpdated: "2026-06-21"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/service_architecture_audit/phases/PHASE_02_OPTIMIZER_AUDIT.md
- 2-twin2clouds/backend/fetch_data/
- 2-twin2clouds/tests/unit/pricing/
EXTRACTED: 2026-06-21 | VERSION: 1.1
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

- Complete. Provider fetcher behavior matrix is captured in
  [Phase 2.3 Review](../../PHASE_02_03_OPTIMIZER_FETCHER_RELIABILITY_REVIEW.md).
- Complete. Candidate selection criteria now produce evidence for service name,
  SKU/row, meter, region, unit, price, and rejection reason where supported.
- Complete. Rejected-candidate evidence is modeled through
  `RejectedCandidate` and `FieldMatchEvidence`.
- Complete. Ambiguous paid candidates are review-required and not successful
  automatic matches at the hardened matching boundary.

## Acceptance Criteria

- Fetchers never treat ambiguous candidates as successful automatic matches.
- Units such as per million, per 100k, GB, GiB, seconds, and requests are
  normalized before calculation.
- All selected rows can be inspected later by Management API/UI.

## Verification

- Complete. Static fetcher review captured in the Phase 2.3 review.
- Complete. Fixture tests cover multi-candidate ambiguity for AWS, Azure, and
  GCP matching helpers.
- Complete. No live cloud deployment tests.

## Parent Phase

[Phase 2: Optimizer Audit](../PHASE_02_OPTIMIZER_AUDIT.md)
