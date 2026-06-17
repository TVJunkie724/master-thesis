---
title: "Phase 3: Dashboard Pricing Health"
description: "Plan the Dashboard pricing readiness row and entry point into pricing review."
tags: [flutter, frontend-delta, dashboard, pricing]
lastUpdated: "2026-06-13"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- docs/plans/provider_access_pricing_review/phase_04_dashboard_pricing_health_row.md
- twin2multicloud_flutter/lib/screens/dashboard_screen.dart
EXTRACTED: 2026-06-13 | VERSION: 1.0
-->

# Phase 3: Dashboard Pricing Health

## Summary

Add a Dashboard row beneath the existing platform stat cards that summarizes
pricing readiness per provider and gives users a clear entry point to the
Pricing Review Center.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Provider health status cards | Starting provider refresh from cards |
| Account/project/subscription summary | Candidate review table |
| Missing/stale/review-required states | Credential editing |
| Navigation to Pricing Review Center | Wizard Step 2 refresh controls |

## Prerequisites

- Phase 1 contract baseline.
- Phase 2 access inventory concept is approved.
- `GET /optimizer/pricing-health` exists or has an approved backend
  implementation plan; this phase must not start before that contract is
  stable.

## Deliverables

- Dashboard placement and behavior concept.
- Provider state vocabulary: fresh, stale, missing credential, review required,
  failed, unavailable.
- Rule that Dashboard cards are status-only.
- Navigation concept for opening Pricing Review.
- Severity ordering for the row: failed, missing credential, review required,
  stale, unavailable, fresh.
- Desktop and compact Web row behavior.

## UI Shape

```text
Dashboard
|-- Platform Stat Cards
|
|-- Pricing Data Health
|   |-- AWS    Stale            Account 123456789012
|   |-- Azure  Fresh            Public API
|   |-- GCP    Review required  Project thesis-demo
|   `-- Open Pricing Review
|
`-- Twins Table
```

## Architecture Guardrails

- Dashboard consumes a typed Management API read model, not legacy optimizer log
  output.
- Dashboard cards are passive status cards; refresh starts only in Pricing
  Review Center.
- Reuse the existing dashboard/stat-card visual language where it fits, but the
  cards must remain provider-health cards, not editable credential cards.
- The feature state must expose loading, loaded, empty, partial-failure, and
  total-failure states.
- The architect implementation plan must include desktop and compact Web ASCII
  layouts before build work starts.

## Acceptance Criteria

- Pricing readiness is visible on the Dashboard without opening the Wizard.
- Each provider card shows status, source/account metadata, and last fetched age
  when available.
- Dashboard does not start refresh jobs directly.
- Missing credentials and review-required states are understandable.
- The most severe provider state is visible at row level so users can scan the
  Dashboard quickly.

## Verification

- Later implementation requires widget tests for every provider state.
- Navigation test confirms the Pricing Review entry point.
- Integration test confirms Flutter uses Management API only.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
