# Pricing Review State API and Flutter Surface

## Issue

GitHub: #84

## Goal

Expose pricing quality as typed state instead of leaving users with refresh log
text. The Management API must provide a provider-scoped pricing review state that
Flutter can render before calculation. Logs remain diagnostic only.

## Final State

- Management API exposes `GET /optimizer/pricing-review-state?twin_id=...`.
- The response returns one typed state per provider:
  - `fresh`
  - `stale`
  - `review_required`
  - `missing`
  - `failed`
- Each provider state includes `review_required`, `can_calculate`,
  `calculation_source`, `pricing_freshness`, age metadata, missing keys, review
  reasons, and supported user actions.
- Existing Optimizer `pricing-status` responses remain backward-compatible.
- Flutter loads the typed review state through Management API.
- Flutter renders typed states in the Pricing Data section, including
  fresh/stale/review-required/failed/missing and last-known-good context.

## Scope Boundary

- This slice is read-only review-state surfacing.
- No provider catalog review workflow.
- No accepting candidates or changing mappings.
- No new DB migration.
- No live cloud E2E.
- Future Optimizer publication decisions from #83 can be passed through the same
  Management API contract when the refresh pipeline starts emitting them.

## Implementation Steps

1. Add Management API schema/service helpers for pricing review state.
2. Add `GET /optimizer/pricing-review-state` and tests for fresh, stale,
   review-required/incomplete, missing with last-known-good, and Optimizer
   failure.
3. Add Flutter model/service method for the review-state response.
4. Store review state in `TwinOverviewLoaded` and load it during overview load
   and refresh.
5. Extend `DataFreshnessCard` to render typed pricing review status without log
   parsing.
6. Add widget tests for fresh, stale, review-required, failed, and missing.

## Verification

- `pytest twin2multicloud_backend/tests/test_pricing_review_state.py -q`
- `flutter analyze`
- `flutter test test/widgets/data_freshness_card_test.dart`
