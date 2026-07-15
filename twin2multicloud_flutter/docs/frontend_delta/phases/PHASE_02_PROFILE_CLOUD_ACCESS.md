---
title: "Phase 2: Profile Cloud Access"
description: "Plan the Settings/Profile UI for user-owned cloud account and credential visibility."
tags: [flutter, frontend-delta, settings, credentials]
lastUpdated: "2026-07-15"
version: "1.1"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- docs/plans/provider_access_pricing_review/phase_03_profile_cloud_accounts_access_ui.md
- twin2multicloud_flutter/lib/screens/settings_screen.dart
- twin2multicloud_flutter/lib/widgets/cloud_connections/cloud_connection_section.dart
EXTRACTED: 2026-06-13 | VERSION: 1.0
-->

# Phase 2: Profile Cloud Access

**Status:** Done. Settings exposes the purpose-aware Cloud Access inventory,
provider/account metadata, validation and deletion handling, pricing-default
selection, creation flows, and compact/wide states through the feature BLoC.

## Summary

Extend Settings/Profile with a Cloud Accounts & Access section so users can see
which provider accounts are configured, which credentials are used for pricing
or deployment, and which access can be validated or deleted.

| In scope ✅ | Out of scope ❌ |
|---|---|
| User-owned provider access inventory | Credential rotation |
| Pricing vs deployment purpose visibility | Admin credential persistence |
| Validate/delete/blocked states | Editing secret payloads in-place |
| Azure public pricing capability display | RBAC/admin-only screens |

## Prerequisites

- Phase 1 contract baseline.
- `GET /cloud-access` exists or has an approved backend implementation plan and
  returns secret-free provider access inventory.
- CloudConnection delete behavior blocks active twin-bound deployment use.

## Deliverables

- Settings-level concept for Cloud Accounts & Access.
- Account/project/subscription identity display requirements.
- Purpose rows for pricing and deployment access.
- Delete and validate behavior rules.
- Empty/error/loading states.
- Default pricing credential rules when a user has multiple credentials for one
  provider.
- Desktop and compact Web layout requirements.

## UI Shape

```text
Settings
`-- Cloud Accounts & Access
    |-- Provider filter / Refresh
    |-- AWS Account 123456789012
    |   |-- Pricing read access      Active      Default
    |   |-- Deployment access        Used by Twin A
    |   `-- Validate | Delete
    |-- GCP Project thesis-demo
    |   |-- Pricing read access      Needs validation
    |   |-- Deployment access        Used by Twin B
    |   `-- Validate | Delete
    `-- Azure
        |-- Pricing                  Public API
        `-- Deployment SP            Used by Twin C
```

## Architecture Guardrails

- The screen owns state through a Settings/Profile feature BLoC or an approved
  equivalent feature state object; widgets do not call `ApiService` directly.
- The service layer calls the Management API only.
- Reuse or extend existing CloudConnection display primitives before creating
  new credential cards.
- Use existing theme spacing/color tokens.
- The architect implementation plan must include desktop and compact Web ASCII
  layouts before build work starts.

## Acceptance Criteria

- Users can answer: which cloud account/project/subscription is this app using?
- Users can distinguish pricing read access from deployment access.
- Users can discard pricing credentials after confirmation.
- Deleting deployment credentials that are in use is blocked or explained.
- Users can see which pricing credential is the default for each provider.
- After deleting the default pricing credential, provider pricing refresh is
  disabled until another valid default is selected or created.
- No secrets, file paths, or admin credentials are displayed.

## Verification

- Widget tests for loaded, empty, error, validate, delete-blocked, and
  delete-confirmed states in the later implementation phase.
- Integration smoke against Management API only.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
