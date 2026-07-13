# Phase 6: Pricing Review Center UI

**Status:** done
**Primary owner:** Flutter + Management API + Optimizer proxy contracts
**Depends on:** Phase 1, Phase 4, Phase 5, AI candidate review contracts

## Goal

Provide a dedicated workspace for provider-specific pricing refresh, candidate
review, and explicit approval/unresolved decisions.

## Desktop Layout

```text
Pricing Review
|-- Header
|   |-- Pricing Data Review
|   |-- AI Review: Enabled / Disabled
|   `-- Back to Dashboard
|
|-- Provider Selector
|   |-- AWS    stale            account 123456789012
|   |-- Azure  fresh            public API
|   `-- GCP    review required  project thesis-demo
|
|-- Selected Provider Detail
|   |-- Credential Confirmation
|   |   |-- Use AWS pricing credential?
|   |   |-- Account: 123456789012
|   |   |-- Identity: t2mc-pricing-reader
|   |   `-- Fetch AWS Pricing
|   |
|   |-- Progress / SSE Log
|   |-- Candidate Summary
|   |-- Candidate Table
|   |-- Evidence Detail Drawer
|   `-- Approve Selection | Mark Unresolved
```

## Compact Web Layout

```text
Pricing Review
|-- Header
|-- Provider Selector Tabs
|-- Credential Confirmation
|-- Candidate Summary
|-- Candidate Table
`-- Bottom Action Bar
```

## Widget Tree

```text
PricingReviewScreen [NEW]
`-- PricingReviewBlocProvider [NEW]
    |-- PricingReviewHeader [NEW]
    |-- ProviderReviewSelector [NEW]
    |   `-- ProviderReviewTab [NEW]
    |-- ProviderCredentialConfirmation [NEW]
    |-- PricingRefreshProgressPanel [NEW]
    |-- CandidateReviewSummary [NEW]
    |-- PricingCandidateTable [NEW]
    |-- PricingEvidenceDrawer [NEW]
    `-- PricingReviewActionBar [NEW]
```

## Required State Flow

```text
Open screen
  -> PricingReviewLoadRequested
  -> GET /optimizer/pricing-health
  -> GET /cloud-access
  -> PricingReviewLoaded

Fetch provider
  -> User confirms credential context
  -> PricingRefreshRequested(provider, pricing_connection_id)
  -> POST /optimizer/pricing-refresh/{provider}
  -> await terminal pricing-refresh-run.v1 response
  -> reload pricing health and candidate report

Approve candidate
  -> PricingCandidateSelected(candidate_id)
  -> PricingDecisionApproveRequested
  -> POST /optimizer/pricing-review/decisions
  -> PricingDecisionAccepted
```

## Data Contracts

Management API endpoints:

- `GET /optimizer/pricing-health`
- `POST /optimizer/pricing-refresh/{provider}`
- `GET /optimizer/pricing-review/{provider}/candidate-reports`
- `GET /optimizer/pricing-review/candidate-reports/{report_id}/trace`
- `POST /optimizer/pricing-review/decisions`

All endpoints are Management API routes. Flutter must not call Optimizer
directly.

Approvals persist through Management API only using the Phase 5 reviewed
decision contract.

## Candidate Selection Rules

- AI may preselect a candidate in UI state.
- Preselection is not persistence.
- `Approve Selection` is disabled until backend marks the selected candidate as
  selectable and contract-valid.
- On AI/deterministic disagreement, both candidates are shown prominently.
- User may choose another candidate or mark unresolved.

## Long-Running Fetch Rule

Provider refreshes are independent. GCP/AWS may be long-running. The screen must
support one active provider refresh at a time initially. A later `Refresh all`
may only enqueue providers sequentially.

The current synchronous refresh contract exposes no trustworthy intermediate
progress. Flutter therefore shows provider-scoped indeterminate waiting until
the terminal response arrives; it does not fabricate SSE progress.

## Verification

- BLoC unit tests for provider selection, confirmation, fetch progress,
  candidate selection, approval, unresolved, and failed refresh.
- Widget tests for AI disabled/enabled, missing credential, Azure public API,
  disagreement, and blocked contract validation.
- Integration tests against Management API/SSE without live cloud E2E.

## Definition Of Done

- [x] Pricing Review Center route exists.
- [x] Provider refresh requires credential confirmation for AWS/GCP.
- [x] Azure shows public API/no credential required.
- [x] Provider-scoped waiting reflects the synchronous refresh contract.
- [x] Candidate review and collapsed evidence trace are implemented.
- [x] AI preselection is separate from approval.
- [x] Approvals persist through Management API only.
- [x] Tests cover happy/unhappy/edge states.
