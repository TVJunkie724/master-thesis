# GCP Credentials And Pricing Evidence

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

Depends on:

- `2026-06-08_pricing_evidence_registry_foundation.md`
- `2026-06-08_pricing_registry_contract_api.md`

## Goal

Fix GCP pricing credential and permission handling before treating GCP Catalog
data as live evidence. Then apply the evidence model to GCP.

## Problem

Current credential-backed checks returned `401` against the GCP Cloud Billing
Catalog API. That means generated GCP pricing is currently schema-valid only
through emergency fallback values and must remain review-required.

GCP cannot be considered live-valid until authentication and required
permissions are proven.

## Scope

This phase includes GCP pricing credentials, permission validation, and evidence
capture.

It must not:

- change Azure or AWS behavior
- change GCP calculation formulas before evidence exists
- accept fallback-backed GCP pricing as publishable
- require real cloud deployment E2E

## Credential Requirements

The phase must identify the minimum credentials required for:

- listing Cloud Billing Catalog services
- listing SKUs for relevant services
- reading project/billing metadata only where needed

The permission checker must validate these operations before pricing refresh.

Credential files or uploaded service-account JSON must never be copied into
pricing evidence, generated snapshots, logs, or review reports. Auth failures
must include operation names and permission context, not secret material.

## Evidence Sources

Expected sources:

- Google Cloud Billing Catalog API
- official Google Cloud pricing documentation only as reproducible official
  cloud evidence

## GCP Services In Scope

- Cloud Pub/Sub / IoT equivalent
- Cloud Run Functions / Cloud Functions
- Firestore / hot storage
- Cloud Storage nearline/archive
- Compute Engine for self-hosted digital twin/grafana equivalents
- API Gateway / Service Control
- Workflows
- Cloud Scheduler
- Network egress

## Implementation Steps

1. Diagnose current 401 without logging secrets.
2. Update credential/preflight validation for Billing Catalog operations.
3. Document minimum GCP roles/permissions.
4. Add GCP raw snapshot writer for sanitized Catalog rows.
5. Add GCP candidate extraction preserving service, SKU, category, region, unit,
   and tiered rates.
6. Add selected/rejected evidence output.
7. Access intents, mappings, and normalization rules through
   `PricingRegistryService`, not direct YAML reads.
8. Add a developer-readable evidence report showing selected SKU/rate,
   alternatives, and rejection reasons per intent.
9. Keep GCP pricing output review-required until live evidence is complete.

## Test Strategy

Required tests:

- invalid GCP credential returns structured permission/auth failure
- permission checker covers Catalog list services/list SKUs operations
- GCP candidate extraction preserves tiered rates
- failed GCP refresh does not publish fallback as fresh
- GCP fallback remains calculation-possible only as review-required emergency
- auth and evidence error responses redact service-account secrets
- selected/candidate/rejected GCP evidence is persisted outside logs
- GCP evidence code uses `PricingRegistryService` for registry metadata

No real GCP deployment E2E is required.

## Definition Of Done

- [ ] GCP pricing credential failure is structured and actionable.
- [ ] Required GCP pricing permissions are documented and checked.
- [ ] GCP raw Catalog evidence can be captured when credentials are valid.
- [ ] GCP selected/rejected evidence is inspectable.
- [ ] GCP evidence reports expose the exact Catalog SKU/rate selected per
  intent.
- [ ] GCP fallback pricing is never publishable.
- [ ] GCP credential/auth failures are structured and secret-redacted.
- [ ] GCP provider evidence code does not add scattered direct registry-file
  reads.

## Self Review

### Architect Review

- Auth/permission repair comes before evidence claims.
- GCP remains review-required until evidence is proven.
- No deployment E2E is introduced.

### Builder Review

- The 401 failure is the first concrete target.
- Permission and evidence tasks are separated.
- Tests are clear and do not need live deployments.

### Review Findings

- Fixed: GCP evidence is blocked by auth until proven otherwise.
- Fixed: permission checker is included before live evidence publication.
- Fixed: GCP credential material is explicitly excluded from evidence/logs.
- Fixed: selected GCP Catalog SKU/rate evidence must be inspectable outside
  logs.
- Fixed: GCP evidence implementation depends on the registry service/API
  boundary.

No open findings after review.
