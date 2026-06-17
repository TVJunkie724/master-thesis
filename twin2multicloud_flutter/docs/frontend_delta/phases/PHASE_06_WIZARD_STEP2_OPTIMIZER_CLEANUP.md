---
title: "Phase 6: Wizard Step 2 Optimizer Cleanup"
description: "Plan the Wizard Step 2 cleanup after pricing maintenance moves to Dashboard and Pricing Review Center."
tags: [flutter, frontend-delta, wizard, optimizer, pricing]
lastUpdated: "2026-06-13"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- docs/plans/provider_access_pricing_review/phase_07_optimizer_step2_cleanup.md
- FRONTEND_ARCHITECTURE.md Wizard Step 2 section
- twin2multicloud_flutter/lib/screens/wizard/step2_optimizer.dart
- twin2multicloud_flutter/lib/widgets/calc_form/calc_form.dart
EXTRACTED: 2026-06-13 | VERSION: 1.0
-->

# Phase 6: Wizard Step 2 Optimizer Cleanup

## Summary

Refocus Wizard Step 2 on workload parameters, cost calculation, and result
review. Pricing maintenance becomes read-only readiness information with a
Dashboard-managed hint.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Compact pricing readiness summary | Provider refresh buttons |
| Calculation form and result display | Pricing SSE log window |
| Backend-driven calculation gating | Candidate review workflow |
| Compact result quality summary | Direct Pricing Review navigation |

## Prerequisites

- Phase 3 Dashboard Pricing Health exists.
- Phase 4 Pricing Review Center exists.
- Pricing readiness contract is stable.

## Deliverables

- Step 2 responsibility boundary.
- Removal criteria for refresh cards, dialogs, and local SSE state.
- Calculation blocking/warning rules based on backend readiness.
- Result quality summary rules using typed pricing state.
- Explicit boundary that full pricing trace/candidate evidence belongs to
  Pricing Review Center, not Wizard Step 2.

## UI Shape

```text
Wizard Step 2
|-- Pricing Readiness Summary
|   |-- AWS stale
|   |-- Azure fresh
|   |-- GCP review required
|   `-- Pricing data is managed from the Dashboard.
|-- Workload / Calculation Form
|-- Calculate
`-- Cost Results
    `-- Pricing quality badges only
```

## Architecture Guardrails

- Step 2 reads typed pricing readiness through the Wizard BLoC/service layer.
- Step 2 does not create a pricing refresh service, SSE subscription, or
  provider fetch command.
- Step 2 does not render candidate tables, full provider traces, or AI review
  details.
- The architect implementation plan must include desktop and compact Web ASCII
  layouts before build work starts.

## Acceptance Criteria

- Step 2 has no pricing refresh controls.
- Step 2 says pricing data is managed from the Dashboard.
- Step 2 does not link to Pricing Review.
- Calculation uses backend readiness rules rather than log parsing.
- Result display can explain whether pricing was fresh, stale, last-known-good,
  or review-required.
- Full intent-to-result fetch traces are not shown in Step 2; users inspect
  those in the Dashboard-owned Pricing Review Center.

## Verification

- Later implementation requires widget tests proving refresh controls and logs
  are gone.
- BLoC/unit tests cover calculation gating.
- Regression tests cover fresh, stale, review-required, missing, and failed
  pricing readiness states.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
