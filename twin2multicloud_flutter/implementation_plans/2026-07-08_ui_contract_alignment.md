---
title: "UI Contract Alignment: Runtime, Pricing, Cloud Accounts, Wizard Cleanup"
date: "2026-07-08"
branch: "codex/flutter-ui-contract-alignment"
base: "codex/thesis-entrypoint"
status: "complete"
---

# UI Contract Alignment

## 0. Git Branch

- Branch: `codex/flutter-ui-contract-alignment`
- Base: `codex/thesis-entrypoint`
- Merge strategy: merge commit only after review.
- Scope: Flutter UI and Flutter-facing docs/tests only.

## 1. Goal

Align Flutter with the finalized Management API, CloudConnection, pricing review,
and root runtime contracts. The UI must stay behind the Management API boundary,
remain desktop/web ready, and preserve existing dashboard, wizard, pricing, and
twin-overview functionality.

## 2. Non-Goals

- Do not call Optimizer or Deployer directly from Flutter.
- Do not add mobile-specific UI.
- Do not run real cloud E2E tests.
- Do not build an OpenAI/AI review UI in this slice.
- Do not create a CloudConnection editor for secret payloads after creation.
  Existing credentials remain write-only.
- Do not redesign the whole visual system.

## 3. Current Delta

Already present:

- Runtime config reads `API_BASE_URL` and `DEV_AUTH_TOKEN` from Dart defines.
- Dashboard contains a Pricing Health row.
- Pricing Review screen exists and refreshes providers separately.
- Wizard Step 2 already points users to Dashboard/Pricing Review.
- CloudConnection widgets exist for Wizard Step 1.

Remaining work in this plan:

1. Make the Profile/Settings screen show and manage stored Cloud Connections.
2. Harden Pricing Review details so users can inspect provider state without
   parsing logs.
3. Clean Flutter docs and runtime commands around `./thesis.sh`.
4. Add focused tests for profile Cloud Accounts, Pricing Health, and Pricing
   Review edge states.

## 4. Visual Layout

### Settings/Profile Cloud Accounts

```text
Settings
+------------------------------------------------------------------+
| <- Settings                                      [theme] [avatar] |
+------------------------------------------------------------------+
|                                                                  |
| +---------------- Profile -------------------------------------+ |
| | Avatar | Name | Email | Auth provider                         | |
| +--------------------------------------------------------------+ |
|                                                                  |
| +---------------- Login Accounts ------------------------------+ |
| | Google                         Connected / Link               | |
| | UIBK                           Connected / Link               | |
| +--------------------------------------------------------------+ |
|                                                                  |
| +---------------- Cloud Accounts ------------------------------+ |
| | [Refresh]                                                     | |
| | AWS                                                           | |
| |   thesis-aws-dev    valid | last validated ...                | |
| |   Account: 123456789012 | Scope: eu-central-1                 | |
| |   [Validate] [Delete]                                        | |
| |   [New AWS connection]                                       | |
| | Azure                                                         | |
| |   No Azure connection stored                                  | |
| |   [New Azure connection]                                     | |
| | GCP                                                           | |
| |   thesis-gcp-dev    untested | project thesis-demo            | |
| |   [Validate] [Delete]                                        | |
| |   [New GCP connection]                                       | |
| +--------------------------------------------------------------+ |
+------------------------------------------------------------------+
```

Compact web: sections remain single-column; provider rows wrap actions below
metadata.

### Pricing Review Details

```text
Pricing Review
+------------------------------------------------------------------+
| Cloud pricing readiness                                          |
| Credential context [Twin dropdown]                               |
|                                                                  |
| + AWS Card + + Azure Card + + GCP Card +                         |
|                                                                  |
| > Review details                                                 |
|   Optimizer contract                                             |
|   AWS                                                           |
|     state / calculation source / freshness / selected source     |
|     review reasons                                               |
|     missing keys                                                 |
|     recommended actions                                          |
|   Azure ...                                                      |
|   GCP ...                                                        |
+------------------------------------------------------------------+
```

## 5. Widget Tree

```text
SettingsScreen [MODIFY]
  SelectableScaffold [REUSE]
    BrandedAppBar [REUSE]
    SingleChildScrollView [REUSE]
      ProfileCard [EXISTING METHOD -> TOKEN CLEANUP]
      LinkedAccountsCard [EXISTING METHOD -> TOKEN CLEANUP]
      CloudAccountsPanel [NEW]
        CloudAccountProviderSection [NEW]
          CloudAccountTile [NEW]
          CloudConnectionCreateDialog [REUSE]

PricingReviewScreen [MODIFY]
  _PricingReviewContent [MODIFY]
    DataFreshnessCard [REUSE]
    _PricingReviewDetails [MODIFY]
      _ProviderDetails [MODIFY]
      _DetailsSection [REUSE]
```

## 6. State and Services

### Cloud Accounts

- State owner: Riverpod `FutureProvider<List<CloudConnection>>`.
- Service boundary: existing `ApiService` methods:
  - `listCloudConnections`
  - `createCloudConnection`
  - `validateCloudConnection`
  - `deleteCloudConnection`
- UI must invalidate the provider after create/validate/delete.
- Delete failures must show a user-facing message. A backend `409` means the
  connection is still bound to a twin and must not disappear optimistically.

### Pricing Review

- State owner remains `PricingReviewBloc`.
- The screen must use only `getPricingReviewState` and `refreshPricing` through
  the Management API.
- Details must render structured fields already present in
  `PricingReviewStateResponse`; no log parsing.

## 7. Responsive Behavior

- Wide desktop: settings content max width stays constrained; Cloud Accounts is
  a full-width card with provider subsections.
- Narrow desktop/web: provider metadata and actions wrap using `Wrap`; no
  horizontal scrolling.
- Buttons must remain reachable by keyboard and expose tooltips where icon-only.

## 8. Error, Loading, Empty States

Cloud Accounts:

- Loading: card-level progress indicator.
- Error: message plus Retry button.
- Empty: per-provider empty state plus New Connection action.
- Delete conflict: SnackBar with backend error text; list remains unchanged.
- Validation failure: SnackBar plus refreshed validation state if backend stores
  it.

Pricing Review:

- Existing loading/error branches remain.
- Provider details render empty/missing/action sections only when present.
- Unknown provider state remains non-crashing and visibly "Unknown".

## 9. Accessibility

- Buttons have text labels or tooltips.
- Status badges use text plus color.
- Destructive delete requires confirmation.
- Provider sections use semantic headings via normal `Text` hierarchy.

## 10. Tests

Required focused tests:

- `CloudAccountsPanel` renders loading, empty, data, and error states.
- `CloudAccountsPanel` exposes create, validate, and confirmed delete actions
  through callbacks without direct HTTP calls.
- Delete conflicts are surfaced by `SettingsScreen` through the same API error
  handling path as other CloudConnection action failures.
- Pricing Review details render review reasons, missing keys, and actions.
- Pricing Health row keeps Review Pricing entry reachable.

Verification commands:

```bash
cd twin2multicloud_flutter
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/dev.json
```

No real cloud E2E tests are part of this plan.

## 11. Documentation

- Update `twin2multicloud_flutter/README.md` to use the root `./thesis.sh`
  entrypoint.
- Keep implementation details in this plan; broader docs-site updates can
  reference the finished behavior after merge.

## 12. Definition of Done

- [x] Settings/Profile exposes Cloud Accounts grouped by AWS, Azure, GCP.
- [x] Cloud Accounts supports create, validate, delete, refresh, loading, empty,
      error, and delete-conflict states.
- [x] Pricing Review details expose structured provider review state.
- [x] No Flutter code calls Optimizer or Deployer directly.
- [x] No real secrets are printed or persisted by the UI beyond create request
      submission.
- [x] Runtime docs point to `./thesis.sh` and `config/dev.json`.
- [x] Focused widget/BLoC/model tests pass.
- [x] `flutter analyze` passes.
- [x] `flutter test` passes.
- [x] `flutter build web --dart-define-from-file=config/dev.json` passes.
- [x] `flutter build macos --dart-define-from-file=config/dev.json` passes.

## 13. Verification Evidence

- `flutter analyze` passed with no issues.
- Focused tests passed:
  - `test/widgets/cloud_connections/cloud_accounts_panel_test.dart`
  - `test/widgets/pricing/pricing_review_details_test.dart`
  - `test/widgets/pricing/pricing_health_row_test.dart`
- Full `flutter test` passed: 321 tests.
- `flutter build web --dart-define-from-file=config/dev.json` passed.
- `flutter build macos --dart-define-from-file=config/dev.json` passed.
- `git diff --check` passed.

Known residual scope:

- Full pricing candidate-row evidence is not yet exposed by the Management API
  review-state contract. The UI now renders all structured fields available in
  `PricingReviewStateResponse`; candidate-row drill-down requires a backend
  evidence-detail endpoint in a later slice.
