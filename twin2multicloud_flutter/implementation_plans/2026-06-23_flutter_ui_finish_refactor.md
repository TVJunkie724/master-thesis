---
title: "Flutter UI Finish Refactor"
date: "2026-06-23"
branch: "codex/flutter-ui-refactor"
base: "origin/codex/optimizer-finish"
status: "in_progress"
---

# Flutter UI Finish Refactor

## Goal

Finish the remaining Flutter architecture cleanup after the first UI refactor:
remove legacy credential UI, move verification and pricing workflows behind
feature state, reduce wizard monolith responsibilities, document extension
points, and replace dynamic UI traversal with typed view models where contracts
are stable.

## Non-Goals

- No live cloud E2E tests.
- No direct Flutter calls to Optimizer or Deployer ports.
- No backend schema changes.
- No visual redesign beyond the structure needed to preserve existing workflows.
- No TODO/FIXME/HACK comments in production code; future work is tracked in
  this plan and GitHub issues.

## Quality Gate Per Phase

- `flutter analyze`
- Focused tests for changed models/BLoCs/widgets
- Full `flutter test` after each feature-state or shared-model change
- `git diff --check`
- No production `print()`
- No direct calls from dumb widgets to `ApiService`
- No new hardcoded Optimizer/Deployer URLs

## Architecture Target

```
Screen
  |
  v
Feature BLoC / Controller
  |
  v
Service boundary (Management API only)
  |
  v
Typed model / view model
  |
  v
Dumb widgets
```

Dynamic JSON is allowed only at the API boundary or for intentionally raw user
artifacts. Display widgets receive typed models or small view models.

## Phase 1 - Deployment Verification Feature State

Status: Complete.

Verification:
- `flutter analyze` passed.
- Focused deployment verification model, BLoC, and widget tests passed.
- Full `flutter test` passed.

### Scope

- Replace `DeploymentVerificationCard` service orchestration with a dedicated
  feature BLoC.
- Keep infrastructure check, data-flow verification, SSE logs, payload editor,
  error handling, and result display behavior.
- Introduce typed models for infrastructure checks, data-flow logs, SSE events,
  and verification summary where response shape is stable.

### Files

- `lib/bloc/deployment_verification/`
- `lib/models/deployment_verification.dart`
- `lib/widgets/deployment_verification/`
- `lib/widgets/deployment_verification_card.dart`
- `lib/screens/twin_overview/twin_overview_screen.dart`
- tests under `test/bloc/deployment_verification/` and
  `test/widgets/deployment_verification/`

### Acceptance Criteria

- `DeploymentVerificationCard` no longer receives `ApiService`.
- SSE subscription lifecycle is owned by the BLoC and cancelled in `close()`.
- Widget layer is pure presentation plus event callbacks.
- Infrastructure and data-flow states cover idle, loading, data, error, and
  terminal complete states.
- Existing Twin Overview verification entry remains available.

Implementation Notes:
- Added typed deployment verification models for infrastructure checks,
  summaries, data-flow logs, payload initialization, and data-flow summaries.
- Added `DeploymentVerificationBloc` as the single owner of infrastructure API
  calls, data-flow API calls, SSE subscription lifecycle, SSE parsing, and
  verification errors.
- Rebuilt `DeploymentVerificationCard` as a presentation component that renders
  BLoC state and dispatches verification events.

## Phase 2 - Remove Legacy CredentialSection

Status: Complete.

Verification:
- `flutter analyze` passed.
- Focused CloudConnection, cloud credential status, and model tests passed.
- Full `flutter test` passed.

### Scope

- Remove unused legacy `CredentialSection` and its direct credential/API/file
  handling from production `lib/`.
- Confirm CloudConnection UI remains the credential SSOT entry point.
- Add/adjust tests that assert current CloudConnection wizard flow still works.

### Files

- `lib/widgets/credential_section.dart`
- `lib/widgets/credentials/`
- `lib/widgets/cloud_connections/`
- wizard credential tests

### Acceptance Criteria

- No production widget stores raw service-account JSON outside the current
  CloudConnection form flow.
- No dead legacy credential widget remains in `lib/`.
- Existing CloudConnection create/select/save tests still pass.

Implementation Notes:
- Removed the unused legacy `CredentialSection` production widget, including
  its direct Dio/API/file/process credential handling.
- Updated stale deployment config comments that referenced the removed widget.
- Verified that CloudConnection widgets remain the credential SSOT UI path.

## Phase 3 - Wizard State Boundary Split

Status: Complete.

Verification:
- `flutter analyze` passed.
- Focused Wizard service, ZIP service, L4/L5, and Step 3 widget tests passed.
- Full `flutter test` passed.
- `git diff --check` passed.

### Scope

- Extract Wizard use-case handlers from the monolithic `WizardBloc` into
  injectable services/helpers with clear responsibilities.
- Remove production `print()`.
- Move Step 3 validation helper out of `screens/` and away from `BuildContext`
  service lookup where feasible.

### Files

- `lib/bloc/wizard/wizard_bloc.dart`
- `lib/bloc/wizard/services/`
- `lib/bloc/wizard/helpers/`
- `lib/screens/wizard/helpers/step3_validation_helper.dart`
- Step 3 validation tests and WizardBloc regression tests

### Acceptance Criteria

- WizardBloc delegates GLB cleanup and Step 3 validation orchestration to
  focused services.
- No `print()` or analyzer ignores for print remain.
- Step 3 validation returns typed validation results at the boundary.
- Wizard behavior and existing tests remain unchanged.

Implementation Notes:
- Added `WizardGlbCleanupService` and delegated L4 GLB cleanup from
  `WizardBloc`.
- Added `WizardDeployerValidationService` and moved Step 3 config, L2, and L4
  validation out of the screen helper into a BLoC-adjacent service boundary.
- Added a typed `ValidationResult` model for deployer validation responses.
- Removed the legacy screen helper and the noisy ZIP validation debug output.

## Phase 4 - Pricing Review Feature State and Extension Points

Status: Complete.

Verification:
- `flutter analyze` passed.
- Focused Pricing Review BLoC, pricing state model, pricing health row, and
  data freshness widget tests passed.
- Full `flutter test` passed.
- `git diff --check` passed.

### Scope

- Move Pricing Review refresh/feedback state from the screen into a dedicated
  feature BLoC or controller.
- Document Flutter extension points for pricing review decisions, AI-assisted
  candidate review, CloudConnection account display, and future profile/role
  gating.
- Keep AI disabled unless backend/env contract is provided later.

### Files

- `lib/bloc/pricing_review/`
- `lib/screens/pricing_review/pricing_review_screen.dart`
- `lib/widgets/pricing/`
- `docs/frontend/FRONTEND_EXTENSION_POINTS.md`
- Pricing Review tests

### Acceptance Criteria

- Pricing Review screen owns layout only.
- Refresh command state is testable without pumping the full screen.
- Extension points are documented outside production TODO comments.
- Dashboard and Pricing Review still use Management API only.

Implementation Notes:
- Added `PricingReviewBloc` for selected credential context, active provider
  refresh, command feedback, and refresh revision invalidation.
- Converted `PricingReviewScreen` from local `setState` command handling to a
  BLoC-driven view that keeps Management API data loading in typed providers.
- Added frontend extension-point documentation for pricing review decisions,
  optional AI support, CloudConnection account display, optimization strategy
  selection, deployment verification, and wizard services.

## Phase 5 - Typed DTO and View-Model Completion

Status: Pending.

### Scope

- Replace remaining dynamic traversal in Twin Overview configuration review and
  calculation trace display with typed view models where backend contracts are
  stable.
- Keep raw JSON artifacts viewable/downloadable for debugging and thesis
  traceability.

### Files

- `lib/models/calc_result.dart`
- `lib/models/twin_configuration_view.dart`
- `lib/widgets/twin_overview/twin_overview_configuration_review.dart`
- `lib/widgets/results/calculation_trace_summary.dart`
- model/widget tests

### Acceptance Criteria

- Twin Overview configuration display does not cast nested maps in build
  methods for stable fields.
- Trace/profile extension fields remain forward-compatible and visible.
- Raw artifact access remains available through existing viewer/download
  callbacks.

## Phase 6 - Final Quality Gate

Status: Pending.

### Scope

- Run full Flutter quality gate.
- Update this plan with completed statuses and residual risks.

### Acceptance Criteria

- `flutter analyze` passes.
- Full `flutter test` passes.
- `flutter build web --dart-define-from-file=config/dev.json` passes.
- `flutter build macos --debug --dart-define-from-file=config/dev.json`
  passes.
- Working tree is clean after commits.
