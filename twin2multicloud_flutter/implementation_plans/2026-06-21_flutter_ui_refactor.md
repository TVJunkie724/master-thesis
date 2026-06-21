---
title: "Flutter UI Refactor Roadmap"
date: "2026-06-21"
branch: "codex/flutter-ui-refactor"
base: "origin/codex/optimizer-finish"
issues: [38, 72, 73, 33, 100]
status: "complete"
---

# Flutter UI Refactor Roadmap

## Goal

Refactor the Twin2MultiCloud Flutter app toward a clean, enterprise-grade UI
architecture while preserving current workflows. The app must remain a Desktop
and Web frontend that talks only to the Management API.

## Non-Goals

- No direct calls from Flutter to Optimizer or Deployer.
- No live cloud deployment E2E tests.
- No visual redesign beyond the screens required to expose existing backend
  contracts clearly.
- No migration to a new state-management framework.
- No removal of working wizard behavior without regression coverage.

## Quality Gate for Every Phase

- `flutter analyze`
- Focused Flutter tests for touched code.
- Full `flutter test` when a phase changes shared models, services, BLoCs, or
  routing.
- `flutter build web` and `flutter build macos --debug` before final handoff.
- No new production `print()`.
- No hardcoded service URLs; use `ApiConfig`.
- No untyped dynamic traversal inside new widgets.

## Architecture Target

```
Management API
      |
      v
ApiService  -> typed DTO/model at boundary
      |
      v
Feature state (BLoC or Riverpod provider)
      |
      v
Screen smart widget
      |
      v
Focused dumb widgets
```

Dynamic JSON is allowed only at the infrastructure edge where the backend
contract itself is still flexible. New UI surfaces must receive typed models or
small view models.

## Phase 1 - Typed API Boundary Foundation

Status: Complete.

Verification:
- `flutter analyze` passed.
- `flutter test` passed.
- Focused model tests passed.

### Scope

- Add typed models for dashboard stats, pricing status/freshness, pricing
  refresh acknowledgement, deployment outputs/logs/status, and calculation
  trace metadata needed by Pricing Review.
- Add typed `ApiService` methods while preserving legacy Map-returning methods
  for existing callers.
- Update shared providers to expose typed data where already safe.

### Files

- `lib/models/dashboard_stats.dart`
- `lib/models/pricing_status.dart`
- `lib/models/deployment_models.dart`
- `lib/models/calc_result.dart`
- `lib/services/api_service.dart`
- `lib/providers/twins_provider.dart`
- Tests under `test/models/` and provider/service-oriented tests where feasible.

### Acceptance Criteria

- Dashboard stats provider no longer exposes `Map<String, dynamic>`.
- Calculation result can parse additive `intentTrace` and profile/evidence
  metadata without breaking legacy payloads.
- New parser failures are explicit and covered by tests.
- Legacy methods remain available for untouched screens.

## Phase 2 - Dashboard Pricing Health and Review Entry

Status: Complete.

Verification:
- `flutter analyze` passed.
- Focused pricing model/widget tests passed.
- Full `flutter test` passed.

### Scope

- Add a compact pricing health row below existing dashboard stat cards.
- Add a Pricing Review screen reachable from the dashboard flow.
- Provider cards show freshness, calculation source, review-required state,
  and which account/project is used when available from the API contract.
- Dashboard hints that Pricing Review lives on the dashboard; no wizard Step 2
  ownership of global pricing refresh UX.

### Files

- `lib/screens/dashboard_screen.dart`
- `lib/screens/pricing_review/pricing_review_screen.dart`
- `lib/widgets/pricing/`
- `lib/app.dart`
- Tests under `test/widgets/` and `test/models/`.

### Acceptance Criteria

- Dashboard shows pricing readiness for AWS, Azure, and GCP with loading,
  error, empty, and data states.
- Pricing Review screen can refresh providers independently.
- Trace/details are collapsed by default and inspectable on demand.
- UI uses Management API endpoints only.

Implementation Notes:
- Dashboard reads global pricing readiness without a `twin_id`.
- Provider refresh remains explicitly bound to a selected twin credential
  context because `/optimizer/refresh-pricing/{provider}` requires `twin_id`.
- Optimizer metadata from the Management API response is retained for collapsed
  review details.

## Phase 3 - Twin Overview Responsibility Split

Status: Complete.

Verification:
- `flutter analyze` passed.
- Focused Twin Overview widget/BLoC tests passed.
- Full `flutter test` passed.

### Scope

- Split `twin_overview_screen.dart` into focused widgets for header/status,
  actions, logs, deployment outputs, verification, and configuration snapshots.
- Add typed view models for deployment actions/logs where backend response
  shapes are stable.
- Keep the same routes and user workflows.

### Files

- `lib/screens/twin_overview/twin_overview_screen.dart`
- `lib/widgets/twin_overview/`
- `lib/bloc/twin_overview/`
- `lib/models/deployment_models.dart`
- Widget tests for each extracted section.

### Acceptance Criteria

- The top-level screen owns BLoC wiring only.
- Child widgets receive constructor data/callbacks and do not call services.
- Deployment logs/status actions remain available.
- Existing dashboard to overview navigation still works.

Implementation Notes:
- Extracted project/resource name cards, command center, deployment terminal
  panel, Terraform output display wiring, and configuration review sections.
- View/download behavior is routed through `TwinOverviewCodeArtifact` callbacks
  so file/dialog side effects stay in the smart screen.
- The previous no-op "View Logs" path now opens available deployment or terminal
  logs in the code viewer dialog.

## Phase 4 - Wizard Step 2 Boundary Cleanup

Status: Complete.

Verification:
- `flutter analyze` passed.
- Focused calculation trace widget/model tests passed.
- Full `flutter test` passed.

### Scope

- Keep Step 2 focused on workload inputs, calculation execution, and result
  review for the current twin.
- Move global pricing freshness/refresh concerns to Dashboard/Pricing Review.
- Use typed `CalcResult` and trace metadata for results.

### Files

- `lib/screens/wizard/step2_optimizer.dart`
- `lib/widgets/calc_form/`
- `lib/widgets/results/`
- `lib/bloc/wizard/`
- Tests for calculation result persistence and Step 2 state transitions.

### Acceptance Criteria

- Step 2 no longer deep-traverses calculation maps in widget code.
- Result details can show collapsed trace metadata when available.
- Calculate/save-next behavior remains unchanged.

Implementation Notes:
- Removed Step 2-local pricing refresh state, SSE subscription handling, and
  provider freshness cards.
- Step 2 now shows a concise notice that provider pricing refresh/review is
  owned by Dashboard Pricing Review.
- Added `CalculationTraceSummary` to expose typed intent/result trace metadata
  from `CalcResult` without relying on separate pricing review state.

## Phase 5 - Wizard Step 3 Deployer UI Split

Status: Complete.

Verification:
- `flutter analyze` passed.
- Focused Step 3 widget, ZIP upload, and Cloud Connection wizard tests passed.
- Full `flutter test` passed.

### Scope

- Split `step3_deployer.dart` into section widgets matching deployment artifact
  responsibilities.
- Keep existing validation/upload/save/finish behavior intact.
- Leave backend artifact schema untouched.

### Files

- `lib/screens/wizard/step3_deployer.dart`
- `lib/widgets/step3/`
- `lib/widgets/file_inputs/`
- `lib/bloc/wizard/helpers/`
- Widget and BLoC regression tests.

### Acceptance Criteria

- Step 3 screen becomes a coordinator, not a 1k+ line monolith.
- User-editable artifacts remain visible and validatable.
- Zip upload, explicit clears, artifact-only changes, and finish flow stay
  covered by tests.

Implementation Notes:
- Extracted Step 3 quick upload, manual separator, flow header/footer, layer
  row, no-result message, and GLB upload card into focused widgets.
- Kept file picker, API, SnackBar, and BLoC side effects inside the smart
  screen while presentation widgets receive constructor callbacks.
- Reduced `step3_deployer.dart` below 1,000 lines without changing deployer
  artifact schema, upload limits, validation entry points, or finish behavior.

## Phase 6 - Final Quality Gate and Documentation Update

Status: Complete.

Verification:
- `flutter analyze` passed.
- Full `flutter test` passed.
- `flutter build web --dart-define-from-file=config/dev.json` passed.
- `flutter build macos --debug --dart-define-from-file=config/dev.json`
  passed.

### Scope

- Run full Flutter verification.
- Update this roadmap with completed checkboxes and residual risks.
- Comment/update GitHub issues with evidence.

### Acceptance Criteria

- `flutter analyze` passes.
- `flutter test` passes.
- `flutter build web` passes.
- `flutter build macos --debug` passes.
- Issues #38, #72, #73, #33, and #100 are updated with what was completed and
  what remains intentionally deferred.

Implementation Notes:
- Flutter UI now has typed dashboard/pricing/review model boundaries, a
  dashboard-owned Pricing Review entry, a split Twin Overview presentation
  layer, a focused Step 2 optimizer screen, and a Step 3 deployer screen that
  delegates presentation to focused widgets.
- Remaining intentionally deferred work: full pricing review editor UX,
  provider credential/account management screens, simulator-log repair, and
  deeper Flutter feature-module extraction after the backend contracts settle.

Residual Warnings:
- Flutter reports that `file_saver` does not yet support Swift Package Manager
  for macOS; this is pre-existing dependency metadata and did not block builds.
- `WizardZipService` tests still emit existing debug validation output during
  test runs; this is not introduced by the UI refactor and should be cleaned in
  a separate logging/test-noise pass if desired.
