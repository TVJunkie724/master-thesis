---
title: "Frontend Delta Roadmap"
description: "Cross-pillar roadmap for aligning Flutter with the credential, pricing, deployment, and configuration refactors."
tags: [flutter, roadmap, credentials, pricing, deployment, wizard]
lastUpdated: "2026-07-11"
version: "1.2"
---

<!-- SOURCES:
- FRONTEND_ARCHITECTURE.md sections "Architecture Overview", "Digital Twin States", "Dashboard", "Wizard Step 2", "Wizard Step 3"
- integration_vision.md sections "The Management Platform" and "User Workflow"
- docs/plans/provider_access_pricing_review/README.md
- docs/plans/provider_access_pricing_review/phase_01_credential_purpose_model.md
- docs/plans/provider_access_pricing_review/phase_03_profile_cloud_accounts_access_ui.md
- docs/plans/provider_access_pricing_review/phase_04_dashboard_pricing_health_row.md
- docs/plans/provider_access_pricing_review/phase_06_pricing_review_center_ui.md
- docs/plans/provider_access_pricing_review/phase_07_optimizer_step2_cleanup.md
- twin2multicloud_flutter/lib/screens/dashboard_screen.dart
- twin2multicloud_flutter/lib/screens/settings_screen.dart
- twin2multicloud_flutter/lib/screens/wizard/step2_optimizer.dart
- twin2multicloud_flutter/lib/screens/wizard/step3_deployer.dart
- twin2multicloud_flutter/lib/screens/twin_overview/twin_overview_screen.dart
- twin2multicloud_flutter/lib/models/wizard_config_requests.dart
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
EXTRACTED: 2026-06-18 | VERSION: 1.1
-->

# Frontend Delta Roadmap

This roadmap captures the Flutter work needed after the backend, credential
SSOT, pricing reliability, and deployment hardening refactors. The goal is a
coherent thesis-ready UI that exposes the final architecture instead of legacy
implementation details.

Before the feature-heavy phases in this roadmap continue, execute the
[Frontend Architecture Refactoring Roadmap](../frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md).
That prerequisite prevents the new Pricing Review, Profile Cloud Accounts,
Dashboard Pricing Health, Wizard cleanup, and Twin Overview work from expanding
the current god classes.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Flutter alignment with Management API contracts | Direct Flutter calls to Optimizer or Deployer |
| User-visible credential purpose and provider access state | Persisting admin/bootstrap credentials |
| Dashboard pricing readiness entry point | Live cloud deployment E2E in default verification |
| Dedicated Pricing Review Center | Full pricing registry editor |
| Wizard Step 1/2/3 cleanup | Rewriting optimizer formulas from Flutter |
| Twin Overview deployment/preflight hardening | Introducing RBAC before the platform has a role model |
| Cross-cutting error/loading/empty/accessibility gates | Mobile support |

## Target State

```text
Flutter App
|-- Settings / Profile
|   `-- Cloud Accounts & Access
|       |-- pricing credentials: user-scoped, minimal, visible metadata
|       `-- deployment credentials: twin/project-scoped, preflight-visible
|
|-- Dashboard
|   |-- Platform Stat Cards
|   |-- Pricing Data Health provider cards
|   `-- Twins Table
|
|-- Pricing Review Center
|   |-- provider-specific refresh
|   |-- credential confirmation
|   |-- candidate/evidence review
|   |-- collapsed intent-to-result trace details
|   `-- reviewed decision submission
|
|-- Wizard
|   |-- Step 1: twin name + deployment credential binding
|   |-- Step 2: calculation inputs + pricing readiness only
|   `-- Step 3: deployer configuration from typed DB-backed schema
|
`-- Twin Overview
    |-- deploy/destroy/preflight state
    |-- structured logs and outputs
    |-- simulator/test utility diagnostics
    `-- permission-set readiness visibility
```

## Cross-Phase Rules

- Flutter talks to the Management API only.
- Every async feature has loading, empty, error, and permission/blocked states.
- Secret values, credential file paths, OpenAI keys, and admin credentials are
  never rendered or accepted by Flutter outside explicit user upload forms.
- Pricing refresh must identify the account/project/subscription used before a
  provider fetch starts.
- Wizard Step 2 does not own pricing refresh.
- Reviewed pricing decisions are persisted through the Management API database.
- BLoC owns feature state and side effects; widgets render state.
- Each implementation phase must receive an architect implementation plan before
  code is written.

## Phase Index

| Phase | Status | Document | Primary Area | Management API Dependency |
|---|---|---|---|---|
| 1 | Planned | [PHASE_01_CONTRACT_BASELINE.md](phases/PHASE_01_CONTRACT_BASELINE.md) + [implementation plan](../../implementation_plans/2026-06-17_frontend_delta_phase_01_contract_baseline.md) | API contracts and DTO readiness | Required |
| 2 | Planned | [PHASE_02_PROFILE_CLOUD_ACCESS.md](phases/PHASE_02_PROFILE_CLOUD_ACCESS.md) | Settings/Profile | `GET /cloud-access` or approved backend plan |
| 3 | Done | [PHASE_03_DASHBOARD_PRICING_HEALTH.md](phases/PHASE_03_DASHBOARD_PRICING_HEALTH.md) | Dashboard | `GET /optimizer/pricing-health` |
| 4 | Done | [PHASE_04_PRICING_REVIEW_CENTER.md](phases/PHASE_04_PRICING_REVIEW_CENTER.md) | Pricing Review | Pricing refresh/review contracts |
| 5 | Planned | [PHASE_05_WIZARD_STEP1_CREDENTIAL_BOUNDARY.md](phases/PHASE_05_WIZARD_STEP1_CREDENTIAL_BOUNDARY.md) | Wizard Step 1 | Purpose-aware CloudConnections |
| 6 | Done | [PHASE_06_WIZARD_STEP2_OPTIMIZER_CLEANUP.md](phases/PHASE_06_WIZARD_STEP2_OPTIMIZER_CLEANUP.md) | Wizard Step 2 | Pricing readiness contract |
| 7 | Planned | [PHASE_07_WIZARD_STEP3_CONFIG_SCHEMA.md](phases/PHASE_07_WIZARD_STEP3_CONFIG_SCHEMA.md) | Wizard Step 3 | Typed deployer config schema |
| 8 | Planned | [PHASE_08_TWIN_OVERVIEW_DEPLOYMENT_OPERATIONS.md](phases/PHASE_08_TWIN_OVERVIEW_DEPLOYMENT_OPERATIONS.md) | Twin Overview | Preflight/log/output contracts and simulator/test contracts or approved backend plans |
| 9 | Planned | [PHASE_09_CROSS_CUTTING_QUALITY_GATE.md](phases/PHASE_09_CROSS_CUTTING_QUALITY_GATE.md) | Cross-cutting | All prior contracts |

## Execution Order

The order is intentional:

0. Complete the frontend architecture refactoring foundation before adding new
   feature-heavy UI surfaces.
1. Establish backend/read-model contracts before UI work.
2. Give users a profile-level place to understand provider access.
3. Add Dashboard pricing readiness after the access inventory exists.
4. Add Pricing Review Center after dashboard entry point and review persistence.
5. Clean Wizard Step 1 so it no longer mixes pricing and deployment access.
6. Remove pricing maintenance from Wizard Step 2 after replacement surfaces
   exist.
7. Refactor Step 3 once Step 2 produces a stable typed calculation result.
8. Harden Twin Overview deployment operations after credential/preflight state
   is visible.
9. Run cross-cutting quality and thesis-evidence gates.

## Readiness For Implementation Planning

This roadmap is ready for the architect step. Each phase still requires a
dedicated implementation plan before Flutter code changes are allowed.
