---
title: "Frontend Delta Roadmap"
description: "Cross-pillar roadmap for aligning Flutter with the credential, pricing, deployment, and configuration refactors."
tags: [flutter, roadmap, credentials, pricing, deployment, wizard]
lastUpdated: "2026-08-23"
version: "2.2"
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
- docs/plans/phase_08_architecture_profiles_eventing/README.md
- twin2multicloud_flutter/docs/frontend_delta/concepts/CONCEPT_POST_PHASE_08_FINALIZATION.md
- twin2multicloud_flutter/lib/screens/dashboard_screen.dart
- twin2multicloud_flutter/lib/screens/settings_screen.dart
- twin2multicloud_flutter/lib/screens/wizard/step2_optimizer.dart
- twin2multicloud_flutter/lib/screens/wizard/step3_deployer.dart
- twin2multicloud_flutter/lib/screens/twin_overview/twin_overview_screen.dart
- twin2multicloud_flutter/lib/models/wizard_config_requests.dart
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
EXTRACTED: 2026-08-23 | VERSION: 2.2
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
| User-visible credential purpose and provider access state | Creating credentials or deriving reduced permission sets |
| Dashboard pricing readiness entry point | Live cloud deployment E2E in default verification |
| Dedicated Pricing Review Center | Full pricing registry editor |
| Wizard Step 1/2/3 cleanup | Rewriting optimizer formulas from Flutter |
| Twin Overview deployment/preflight hardening | Introducing RBAC before the platform has a role model |
| Post-deployment L4/L5 Layer Access handoff | Embedding provider consoles or automating browser sessions |
| Cross-cutting error/loading/empty/accessibility gates | Mobile support |

## Concepts

- [Twin Layer Access Handoff](concepts/CONCEPT_TWIN_LAYER_ACCESS_HANDOFF.md)
  extends the existing Twin Overview with typed L4/L5 links, identity/readiness
  evidence, and one bounded GCP Viewer credential workflow.

## Target State

```text
Flutter App
|-- Settings / Profile
|   `-- Cloud Accounts & Access
|       |-- pricing credentials: user-scoped, minimal, visible metadata
|       |-- deployment credentials: user-owned, provider-target scoped,
|       |   reusable and bound to Twins by ID
|       `-- provider setup: external prerequisite -> stored admin connection
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
|-- Configuration Workspace
|   |-- Define twin
|   |-- Describe workload
|   |-- Choose architecture
|   |-- Prepare deployment
|   |   `-- select the externally provisioned admin connection
|   `-- Review configuration and preflight
|
`-- Twin Overview
    |-- deploy/destroy/preflight state
    |-- L4 semantic Twin and L5 raw/rollup access
    |-- structured logs and outputs
    |-- simulator/test utility diagnostics
    `-- credential validation readiness
```

## Cross-Phase Rules

- Flutter talks to the Management API only.
- Every async feature has loading, empty, error, and permission/blocked states.
- Cloud/deployment credentials, credential file paths, OpenAI keys, provider
  tokens, reader keys, and Admin credentials are never rendered. The only
  generated-secret exception is the explicit one-time GCP Grafana Viewer
  reveal defined by Frontend Delta 8.6; it is never persisted in Flutter state.
- Pricing refresh must identify the account/project/subscription used before a
  provider fetch starts.
- The configuration workspace does not own pricing refresh.
- Draft creation, workload description, calculation, and architecture review
  do not require cloud credentials. Deployment access is selected or generated
  only after the architecture fixes the required provider scopes.
- The PoC reuses externally provisioned, non-root administrator connections;
  credential creation and permission reduction remain outside the frontend.
- Reviewed pricing decisions are persisted through the Management API database.
- BLoC owns feature state and side effects; widgets render state.
- Each implementation phase must receive an architect implementation plan before
  code is written.

## Phase Index

| Phase | Status | Document | Primary Area | Management API Dependency |
|---|---|---|---|---|
| 1 | Done | [PHASE_01_CONTRACT_BASELINE.md](phases/PHASE_01_CONTRACT_BASELINE.md) | API contracts and DTO readiness | Implemented and typed for current workflows |
| 2 | Done | [PHASE_02_PROFILE_CLOUD_ACCESS.md](phases/PHASE_02_PROFILE_CLOUD_ACCESS.md) | Settings/Profile | `GET /cloud-access` |
| 3 | Done | [PHASE_03_DASHBOARD_PRICING_HEALTH.md](phases/PHASE_03_DASHBOARD_PRICING_HEALTH.md) | Dashboard | `GET /optimizer/pricing-health` |
| 4 | Done | [PHASE_04_PRICING_REVIEW_CENTER.md](phases/PHASE_04_PRICING_REVIEW_CENTER.md) | Pricing Review | Pricing refresh/review contracts |
| 6 | Done | [PHASE_06_WIZARD_STEP2_OPTIMIZER_CLEANUP.md](phases/PHASE_06_WIZARD_STEP2_OPTIMIZER_CLEANUP.md) | Wizard Step 2 | Pricing readiness contract |
| 7 | Done | [Configuration Workspace Roadmap](../configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md) | End-to-end configuration journey | Typed configuration, preflight, and deployment contracts |
| 8 | Done offline; live sign-in pending | [PHASE_08_TWIN_OVERVIEW_DEPLOYMENT_OPERATIONS.md](phases/PHASE_08_TWIN_OVERVIEW_DEPLOYMENT_OPERATIONS.md) + [Layer Access plan](../../implementation_plans/2026-07-31_twin_layer_access_handoff.md) | Twin Overview | Existing operation contracts plus implemented [FR-001](../feature-requests/FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md) |
| 9 | Done | [PHASE_09_CROSS_CUTTING_QUALITY_GATE.md](phases/PHASE_09_CROSS_CUTTING_QUALITY_GATE.md) | Cross-cutting | All delivered contracts; residual issues tracked |
| 9.1 | Local gates complete; platform CI pending | [Immutable Region-Scoped Pricing Catalogs](../../../2-twin2clouds/implementation_plans/2026-07-17_immutable_region_pricing_catalogs.md) | Pricing Review, calculation evidence, Twin Overview | Strict immutable references replace full pricing exports; compact evidence, honest legacy state, Web/macOS builds, and live local integration are verified |
| 10 | Done | [PHASE_10_FINAL_MANUAL_VISUAL_AUDIT.md](phases/PHASE_10_FINAL_MANUAL_VISUAL_AUDIT.md) | Complete manual visual, interaction, accessibility, and release audit | No new Management API contract; deterministic demo/local data only |

## Execution Order

The order is intentional:

0. Complete the frontend architecture refactoring foundation before adding new
   feature-heavy UI surfaces.
1. Establish backend/read-model contracts before UI work.
2. Give users a profile-level place to understand provider access.
3. Add Dashboard pricing readiness after the access inventory exists.
4. Add Pricing Review Center after dashboard entry point and review persistence.
5. Replace the technical three-step wizard with the dependency-aware
   [Configuration Workspace](../configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md).
6. Keep pricing maintenance in its dedicated replacement surfaces.
7. Preserve the typed optimizer and deployment contracts while reorganizing
   their inputs around user tasks.
8. Keep the shared Settings/workspace CloudConnection selection stable while
   Six-layer uses externally provisioned administrator credentials.
9. Harden Twin Overview deployment operations after credential/preflight state
   is visible.
10. Run cross-cutting quality and thesis-evidence gates.
11. Replace client-authored full pricing artifacts with compact, immutable,
    Management-owned catalog references after the backend catalog boundary is
    implemented.
12. Reconcile superseded backlog ideas with the closed-world architecture, then
    run the complete manual visual and interaction audit under #111 without
    cloud mutations.

## Current Boundary

The planned frontend delta is implemented for Web and all supported desktop
platforms: macOS, Windows, and Linux. Stable twin, configuration, optimizer, and
deployer response boundaries are typed under #72; dynamic payloads remain only
in the documented open-payload containers. The pricing delta under #119 now
replaces the legacy full pricing-export contract with strict immutable catalog
references. Flutter never supplies trusted pricing evidence and no longer
exposes provider-wide pricing JSON artifacts. Production authentication code is
implemented; live UIBK activation remains externally gated by federation
registration and configuration. Deployment lifecycle integration is complete
through #39 and #73. The explicit dev-auth runtime boundary from #71 is
complete. New product work still requires a dedicated implementation plan
before Flutter code changes.

Frontend Delta 8.6 is implemented and verified against a credential-free local
Management API for every L4/L5 provider pair. Standalone Six-layer v1
are now active for offline calculation; Phase 8.10 generates research evidence
without adding frontend behavior. Provider-console browser sign-in remains a
separate supervised-live boundary.

The final human audit is complete in
[Phase 10](phases/PHASE_10_FINAL_MANUAL_VISUAL_AUDIT.md). General
region-catalog administration, arbitrary provider-binding overrides,
product-grade runtime monitoring, and a second centralized error bus remain
outside the approved Thesis PoC boundary. Any live-provider evidence remains a
separate supervised activity under #107.
