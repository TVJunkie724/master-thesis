---
title: "Implementation Plan: Wizard Step 2 Pricing Readiness"
description: "Replace the static pricing notice with typed readiness and backend-driven calculation gating."
tags: [flutter, wizard, pricing, optimizer]
lastUpdated: "2026-07-12"
version: "1.0"
---

# Wizard Step 2 Pricing Readiness

**Review status:** Approved for implementation after contract, architect, and
builder review on 2026-07-12.

## Goal

Wizard Step 2 owns workload intent, cost calculation, and result review. It
shows pricing readiness as compact read-only context but never refreshes,
reviews, or edits pricing.

```text
Pricing readiness  AWS Stale  Azure Fresh  GCP Review
Pricing is managed from the Dashboard. Last-known-good data may be used.

Calculation inputs
...
                                      [Calculate]
```

No link, refresh button, confirmation dialog, SSE/log panel, candidate table,
or trace detail is permitted.

## Calculation Gate

`GET /optimizer/pricing-health` is the sole UI readiness contract.

- Calculation is enabled only when AWS, Azure, and GCP are all present and
  each has `can_calculate=true`.
- `fresh`, `stale`, `review_required`, or missing refresh credentials are
  informative states. They do not override `can_calculate`.
- A missing provider, `can_calculate=false`, initial loading, or load error
  blocks calculation.
- The BLoC rechecks the gate when handling `WizardCalculateRequested`; widget
  disabling is not the security/correctness boundary.
- The calculation API remains authoritative and may still reject a request.

## Architecture

```text
Step2Optimizer
  -> WizardPricingHealthLoadRequested
  -> WizardBloc
  -> ApiService.getPricingHealth()
  -> Management API :5005

WizardState
  |-- PricingHealthResponse? pricingHealth
  |-- bool isPricingHealthLoading
  |-- String? pricingHealthError
  |-- bool pricingCanCalculate (derived, requires all providers)
  `-- List<String> pricingBlockingProviders (derived)
```

`PricingReadinessSummary` is stateless and presentation-only. The Wizard BLoC
owns loading, retry, error normalization, and the calculation guard. Existing
pricing snapshots saved with optimizer results remain unchanged.

## UI States

| State | Summary | Calculate |
|---|---|---|
| loading | bounded inline progress | disabled |
| all fresh | three success statuses | enabled |
| stale/LKG but calculable | warning status and source | enabled |
| review required but calculable | warning status | enabled |
| provider unavailable | provider error status and reason | disabled |
| load failed/incomplete contract | compact error + retry | disabled |

Wide layouts show the three statuses in one row. Below the existing pricing
breakpoint they wrap/stack. Long source labels ellipsize and state is always
communicated by text plus icon, never color alone.

## Files

- `lib/bloc/wizard/wizard_event.dart`
- `lib/bloc/wizard/wizard_state.dart`
- `lib/bloc/wizard/wizard_bloc.dart`
- `lib/models/pricing_health.dart`
- `lib/screens/wizard/step2_optimizer.dart`
- `lib/screens/wizard/wizard_screen.dart`
- `lib/widgets/pricing/pricing_readiness_summary.dart` (new)
- focused model/BLoC/widget/navigation tests
- provider-access and frontend-delta roadmap status

## Verification

- Model/state tests: complete, incomplete, stale, review-required, and blocked
  provider maps.
- BLoC tests: load, retry, failure preservation, fail-closed calculate handler,
  and calculable stale data.
- Widget tests: wide/compact, loading/error/retry, no refresh/log/navigation,
  source overflow.
- Navigation test: Calculate disabled until both form and pricing gates pass.
- Full analyzer, Flutter suite, web build, and macOS build.

No live provider fetch, pricing mutation, or deployment E2E is run.

## Definition Of Done

- [x] Static notice is replaced by typed compact readiness.
- [x] All three providers are required and backend `can_calculate` is honored.
- [x] Widget and BLoC both enforce the calculation gate.
- [x] Stale/last-known-good remains calculable when backend permits it.
- [x] Load errors and unsupported/incomplete contracts are retryable and fail closed.
- [x] Step 2 has no pricing maintenance or Pricing Review navigation.
- [x] Analyzer, 351 tests, and macOS/Web release builds pass.
- [x] Roadmaps and Issue #38 are updated.

## Completion Evidence

- `flutter analyze`: zero issues.
- `flutter test -r compact`: 351 tests passed.
- `flutter build web --dart-define-from-file=config/dev.json`: passed.
- `flutter build macos --dart-define-from-file=config/dev.json`: passed.
- Review findings fixed: unsupported schema versions fail closed; blocked
  providers expose the typed backend reason without adding maintenance UI.
