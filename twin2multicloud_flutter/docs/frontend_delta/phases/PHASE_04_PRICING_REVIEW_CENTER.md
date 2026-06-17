---
title: "Phase 4: Pricing Review Center"
description: "Plan the dedicated provider pricing refresh and candidate review workspace."
tags: [flutter, frontend-delta, pricing, review]
lastUpdated: "2026-06-13"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- docs/plans/provider_access_pricing_review/phase_05_reviewed_decisions_persistence.md
- docs/plans/provider_access_pricing_review/phase_06_pricing_review_center_ui.md
- 2-twin2clouds/implementation_plans/2026-06-13_ai_assisted_pricing_candidate_review.md
EXTRACTED: 2026-06-13 | VERSION: 1.0
-->

# Phase 4: Pricing Review Center

## Summary

Create a dedicated workflow for provider-specific pricing refresh, credential
confirmation, candidate/evidence review, optional AI semantic review, and
explicit reviewed decisions.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Provider-specific refresh workflow | Full pricing registry editor |
| Credential confirmation before refresh | AI key management in Flutter |
| Candidate table and collapsed evidence/trace details | Direct raw provider payload editing |
| Agreement/ambiguity/disagreement states | Automatic publishable AI decisions |
| Reviewed decision submission | Live cloud deployment E2E |

## Prerequisites

- Phase 1 contract baseline.
- Phase 3 Dashboard entry point approved.
- Reviewed decision persistence exists in Management API.
- Candidate review contracts exist behind Management API.

## Deliverables

- Pricing Review Center concept.
- Provider selector behavior.
- Credential confirmation behavior for AWS/GCP and public API behavior for
  Azure.
- Candidate/evidence review requirements.
- AI disabled/enabled/failed presentation rules.
- Approval and unresolved decision behavior.
- Collapsed pricing trace details for users who need to inspect the complete
  fetch and match path.

## UI Shape

```text
Pricing Review Center
|-- Provider Selector
|-- Credential Confirmation
|-- Refresh Progress
|-- Candidate Summary
|-- Candidate Table
|-- Evidence / Trace Details
|   |-- collapsed by default
|   `-- expanded: intent, query scope, candidates, rejected rows, checks,
|       selected row, normalization, AI suggestion, reviewed decision
`-- Actions: Approve Selection | Mark Unresolved
```

## Evidence And Trace Rules

- The default view must show the user only the decision-relevant summary.
- Detailed trace output is collapsed by default and can be expanded per
  provider and intent.
- The expanded trace must show:
  - pricing intent id and expected unit/model,
  - provider request/search scope,
  - selected candidate row,
  - close candidate rows,
  - rejected rows with rejection reasons,
  - hard contract checks,
  - unit/tier/currency/region normalization,
  - AI suggestion and rationale when AI is enabled,
  - reviewed decision and stale/fingerprint state when available.
- The trace must be sanitized by the backend before Flutter receives it.
- Flutter displays trace data; it does not recompute pricing correctness.

## Architecture Guardrails

- Pricing Review Center owns state through a feature BLoC; widgets do not call
  services directly.
- The service layer calls Management API review/refresh routes only.
- SSE progress events are operational feedback, not the source of pricing truth.
- Reuse existing terminal/log components only for progress output; candidate
  evidence needs structured UI, not raw log text.
- The architect implementation plan must include desktop and compact Web ASCII
  layouts before build work starts.

## Acceptance Criteria

- User can refresh one provider at a time and see progress.
- User can inspect deterministic candidate selection, AI suggestion, and close
  alternatives.
- User can expand sanitized trace details to inspect the full intent-to-result
  path without overwhelming the default view.
- User can choose contract-valid candidates or mark unresolved.
- AI suggestion may preselect a row but never persists without explicit user
  approval.
- Flutter never receives OpenAI keys, cloud credentials, or raw unbounded
  provider payloads.

## Verification

- Later implementation requires BLoC tests for provider selection, refresh,
  candidate selection, approval, unresolved, and failures.
- Widget tests cover AI disabled, AI agreement, AI disagreement, missing
  credential, blocked validation, Azure public API, and collapsed/expanded trace
  panels.
- Integration tests use Management API/SSE without live cloud deployment E2E.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
