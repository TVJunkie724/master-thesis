---
title: "Frontend Extension Points"
description: "Planned typed Flutter extension points without production-code TODO markers."
tags: [flutter, architecture, extension-points]
lastUpdated: "2026-08-05"
version: "1.2"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md
- twin2multicloud_flutter/docs/feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md
EXTRACTED: 2026-08-05 | VERSION: 1.2
-->

# Frontend Extension Points

This document records planned Flutter extension points without leaving TODO
markers in production code.

## Pricing Review

- `PricingReviewBloc` owns user command state for provider refreshes:
  selected credential context, active provider refresh, feedback, and refresh
  revision.
- Pricing readiness data continues to come from the Management API through the
  typed `PricingReviewStateResponse` model.
- Future reviewed decisions should be loaded from the Management API database,
  not edited directly in registry files from Flutter.
- AI-assisted candidate review remains disabled until the backend exposes an
  explicit capability and the runtime has an OpenAI API key configured.
- If AI assistance is enabled later, the UI should present contract-selected
  and AI-suggested candidates as review options; user confirmation remains the
  publishing boundary.

## Cloud Account And Credential Display

- CloudConnection selection remains the credential SSOT UI path.
- Profile-level cloud account visibility is the shared Settings entry point for
  provider, account/project/subscription metadata, validation status, and the
  implemented offline guided bootstrap. Prepare deployment uses the same Management-owned
  bootstrap feature after the selected architecture determines required
  provider scopes, then continues through the separate Twin deployment-
  preflight owner.
- Admin/bootstrap credentials are not a persistent app credential type. They
  are submitted only in the create-session request and are never restored.
- The UI distinguishes local secret release, successful provider-side
  revocation, required manual cleanup, and an existing user-owned credential
  remaining valid. It never labels local disposal as revocation.
- The binding concept and backend request are
  [Guided Cloud Access Bootstrap](../configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md)
  and [FR-002](../feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md).
- Deterministic provider adapters close the local PoC lifecycle without cloud
  mutation. Production remains disabled; live provider identity creation stays
  behind the reviewed external scripts and supervised validation.

## Optimization Strategies

- Optimization profile selection should be modeled as a typed backend contract
  before adding UI controls.
- Cost remains the active thesis strategy. Future metrics such as latency,
  sustainability, resilience, and compliance can be added as disabled/read-only
  strategy descriptors until backend support exists.
- A selected optimization strategy must match the calculation strategy and
  formula set exposed by the backend.

## Deployment Verification

- `DeploymentVerificationBloc` is the extension point for additional
  verification phases.
- Widgets must remain presentation-only; new verification operations should be
  added as BLoC events and typed model fields.

## Wizard Services

- Wizard use cases that call backend APIs or transform external files should
  live below `lib/bloc/wizard/services/`.
- Screens may coordinate local UI controls, but validation and cleanup logic
  should stay in injectable services with focused tests.
- Validation of uploaded `requirements.txt` files is tracked in GitHub Issue
  #36. Until that cross-service contract exists, the UI treats requirements as
  deployment input and does not claim that package resolution was validated.
