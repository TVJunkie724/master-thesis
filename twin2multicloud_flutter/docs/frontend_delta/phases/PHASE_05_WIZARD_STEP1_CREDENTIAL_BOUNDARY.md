---
title: "Phase 5: Wizard Step 1 Credential Boundary"
description: "Plan the Wizard Step 1 cleanup so it binds deployment credentials without owning pricing access."
tags: [flutter, frontend-delta, wizard, credentials]
lastUpdated: "2026-06-13"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- twin2multicloud_flutter/docs/wizard/phases/PHASE_CREDENTIAL_SSOT.md
- docs/plans/provider_access_pricing_review/phase_01_credential_purpose_model.md
- twin2multicloud_flutter/lib/screens/wizard/step1_configuration.dart
- twin2multicloud_flutter/lib/models/wizard_config_requests.dart
EXTRACTED: 2026-06-13 | VERSION: 1.0
-->

# Phase 5: Wizard Step 1 Credential Boundary

## Summary

Clean up Wizard Step 1 so it captures twin identity and binds deployment-scoped
CloudConnections. Pricing credentials are profile-level provider access and are
not configured inside the twin wizard.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Deployment credential binding per provider | Pricing credential refresh |
| Purpose-aware CloudConnection selection | Admin credential bootstrap UI |
| Secret-free summaries and validation state | Secret editing after creation |
| Legacy fallback compatibility messaging | Pricing Review Center behavior |

## Prerequisites

- Phase 1 contract baseline.
- Purpose-aware CloudConnections exist.
- Profile Cloud Access concept is approved.

## Deliverables

- Wizard Step 1 target responsibility statement.
- Rule that selected credentials are deployment-scoped for the twin.
- Migration/compatibility behavior for existing drafts that still have legacy
  credential fields.
- Validation and delete/unbind behavior boundaries.
- CloudConnection filtering rules based on `purpose=deployment` and compatible
  provider.
- User-facing messaging for pricing access being managed in Profile/Dashboard,
  not inside the Wizard.

## UI Shape

```text
Wizard Step 1
|-- Digital Twin Name
|-- Mode
|-- Deployment Cloud Connections
|   |-- AWS deployment credential
|   |-- Azure deployment credential
|   `-- GCP deployment credential
`-- Note: Pricing access is managed outside the Wizard.
```

## Architecture Guardrails

- Step 1 binds deployment-scoped CloudConnections only.
- Pricing-scoped CloudConnections must not appear in Step 1 provider selectors.
- The Wizard BLoC owns selection, validation, unbind, and delete state.
- Widgets do not call `ApiService` directly.
- Persisted wizard config writes CloudConnection IDs and non-secret settings
  only.
- The architect implementation plan must include desktop and compact Web ASCII
  layouts before build work starts.

## Acceptance Criteria

- Step 1 no longer suggests that pricing access is configured there.
- Provider selection cannot accidentally bind pricing-only credentials as
  deployment credentials.
- Existing drafts remain understandable and recoverable.
- Legacy inline credentials are displayed only as compatibility/recovery state
  and are not re-saved as new secret payloads.
- Pricing credentials are not created, selected, deleted, or validated in Step 1.
- The persisted wizard config references CloudConnection IDs, not secret
  payloads.

## Verification

- Later implementation requires unit tests for credential filtering and
  selected-connection persistence.
- Widget tests cover empty, selected, validation failed, unknown selected ID,
  and legacy draft compatibility states.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
