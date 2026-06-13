# Phase 4: Dashboard Pricing Health Row

**Status:** planned
**Primary owner:** Flutter Dashboard + Management API read contracts
**Depends on:** Phase 1, Phase 3 API contract

## Goal

Add a compact provider-health row below the existing Dashboard stat cards. It
shows global pricing status and the credential/account that would be used for a
provider refresh.

## Desktop Layout

```text
Dashboard
|-- Platform Stat Cards
|   |-- Deployed | Est. Cost | Total Twins | Draft
|
|-- Pricing Data Health
|   |-- AWS ProviderHealthCard
|   |   |-- Stale
|   |   |-- Account 123456789012
|   |   `-- Last fetched 2d ago
|   |
|   |-- Azure ProviderHealthCard
|   |   |-- Fresh
|   |   |-- Public API
|   |   `-- Last fetched 4h ago
|   |
|   |-- GCP ProviderHealthCard
|   |   |-- Review required
|   |   |-- Project thesis-demo
|   |   `-- Last fetched 15d ago
|   |
|   `-- Open Pricing Review
|
`-- Twins Table
```

## Compact Web Layout

```text
Dashboard
|-- Platform Stat Cards
|-- Pricing Data Health
|   |-- AWS compact card
|   |-- Azure compact card
|   |-- GCP compact card
|   `-- Open Pricing Review
`-- Twins Table
```

## Widget Tree

```text
DashboardScreen [MODIFY]
`-- DashboardBody [EXISTING]
    |-- StatsRow [EXISTING]
    |-- PricingDataHealthSection [NEW]
    |   |-- PricingHealthHeader [NEW]
    |   |-- ProviderHealthCardRow [NEW]
    |   |   `-- ProviderHealthCard [NEW]
    |   `-- OpenPricingReviewButton [NEW]
    `-- TwinsTable [EXISTING]
```

## Data Contract

Flutter reads one Management API payload:

```http
GET /optimizer/pricing-health
```

The response combines current pricing status with provider-access metadata:

```json
{
  "schema_version": "pricing-health.v1",
  "providers": {
    "aws": {
      "state": "stale",
      "age": "2 days",
      "last_fetched_at": "2026-06-11T00:00:00Z",
      "review_required": false,
      "credential_summary": {
        "connection_id": "cc-aws-pricing",
        "purpose": "pricing",
        "provider_account_id": "123456789012",
        "identity_label": "t2mc-pricing-reader"
      }
    }
  }
}
```

## UI Rules

- The Dashboard does not run provider refresh directly as the primary action.
- The only primary action is `Open Pricing Review`.
- Cards are status cards, not editable credential cards.
- Missing pricing credential is shown as `Missing credential`.
- Azure shows `Public API`.

## Verification

- Widget tests for fresh/stale/missing/review-required cards.
- Navigation test for `Open Pricing Review`.
- Integration test verifies the Dashboard reads Management API only.

## Definition Of Done

- [ ] Pricing Data Health appears below platform stats.
- [ ] AWS/Azure/GCP cards show status, source, and last fetched age.
- [ ] Missing credential state is clear.
- [ ] Button navigates to Pricing Review Center.
- [ ] No provider refresh is triggered from Dashboard cards.
- [ ] Tests cover loading/error/empty/provider states.
