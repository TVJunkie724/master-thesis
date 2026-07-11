# Provider Access And Pricing Review Roadmap

**Status:** in progress
**Scope:** Management API, Optimizer contracts, Flutter Dashboard/Profile/Pricing Review UI
**No real cloud E2E:** all live cloud checks remain manual/supervised only.

## Goal

Move pricing maintenance out of Wizard Step 2 and into a clear provider-access
workflow:

```text
Cloud admin credentials
  -> ephemeral bootstrap input only
  -> create least-privilege identities
  -> discarded

Pricing credentials
  -> user/profile-scoped
  -> minimal read-only provider access
  -> used by Dashboard/Pricing Review fetches

Deployment credentials
  -> twin/project-scoped
  -> least-privilege deployment access
  -> used by preflight/deploy/destroy
```

The Dashboard shows global pricing health as compact provider stat cards. The
Pricing Review Center performs provider-specific refresh, evidence review, and
reviewed-decision approval. Wizard Step 2 becomes a calculation screen only.

## Phase Index

| Phase | Plan | Status | Objective |
|---|---|---|---|
| 1 | `phase_01_credential_purpose_model.md` | planned | Add explicit credential purpose/scope model |
| 2 | `phase_02_bootstrap_output_split.md` | planned | Bootstrap separate pricing and deployment identities |
| 3 | `phase_03_profile_cloud_accounts_access_ui.md` | planned | Show/manage profile-level cloud access |
| 4 | `phase_04_dashboard_pricing_health_row.md` | done | Add Dashboard provider health stat cards |
| 5 | `phase_05_reviewed_decisions_persistence.md` | planned | Persist reviewed pricing choices in Management API DB |
| 6 | `phase_06_pricing_review_center_ui.md` | done | Add dedicated Pricing Review Center |
| 7 | `phase_07_optimizer_step2_cleanup.md` | planned | Remove pricing maintenance from Wizard Step 2 |
| 8 | `phase_08_tests_docs_thesis_evidence.md` | planned | Add final verification, docs, and thesis evidence |

## Cross-Phase Rules

- Flutter must call the Management API only.
- No Flutter screen may receive OpenAI keys, cloud secret values, admin
  credentials, or local credential file paths.
- Admin credentials are never persisted.
- Pricing fetch must show the provider account/project/subscription identity
  before a user starts a refresh.
- Provider fetches are independent. `Refresh all` may exist later only as a
  sequential/queued action over provider-specific refresh jobs.
- AI may preselect a candidate in the UI, but explicit user approval plus
  backend contract validation is required before persistence.
- Reviewed decisions are stored in the Management API database, not written from
  Flutter into source-controlled registry files.

## Target Dashboard Shape

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

## Readiness Review

The roadmap is split to keep each implementation slice small:

- backend schema first,
- bootstrap import second,
- profile UI before dashboard dependency,
- dashboard status before refresh/review workspace,
- reviewed-decision persistence before the review workspace can approve
  selections,
- Wizard Step 2 cleanup after the new workspace exists.

No phase depends on an unplanned roles/RBAC model. Until RBAC exists, access is
authenticated and user-owned.
