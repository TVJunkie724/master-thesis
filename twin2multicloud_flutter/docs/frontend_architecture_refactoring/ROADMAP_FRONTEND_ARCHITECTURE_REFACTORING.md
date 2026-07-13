---
title: "Frontend Architecture Refactoring Roadmap"
description: "Roadmap for decomposing the Flutter app into stable Management API, state, domain, and presentation boundaries before feature-heavy UI delta work continues."
tags: [flutter, architecture, refactoring, roadmap, thesis]
lastUpdated: "2026-06-18"
version: "1.0"
---

<!-- SOURCES:
- FRONTEND_ARCHITECTURE.md sections "Architecture Overview", "Flutter Tech Stack Explained", "Screens", "Critical Architectural Review"
- integration_vision.md sections "The Core Vision", "System Architecture", "The Management Platform"
- ONBOARDING.md sections "Source Of Truth", "Project Map", "Tests"
- twin2multicloud_flutter/README.md sections "Local Runtime", "Quality Checks"
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- twin2multicloud_flutter/lib/services/api_service.dart
- twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart
- twin2multicloud_flutter/lib/bloc/twin_overview/twin_overview_bloc.dart
- twin2multicloud_flutter/lib/screens/twin_overview/twin_overview_screen.dart
- twin2multicloud_flutter/lib/widgets/deployment_verification_card.dart
- twin2multicloud_flutter/lib/screens/wizard/step3_deployer.dart
EXTRACTED: 2026-06-18 | VERSION: 1.0
-->

# Frontend Architecture Refactoring Roadmap

This roadmap is the prerequisite architecture track for the Flutter app. It
exists because the backend and pricing/deployment contracts have become more
structured, while the Flutter app still concentrates too many responsibilities
in a few large files.

The goal is not a redesign. The goal is to make future UI work implementable
without expanding god classes, raw maps, duplicated parsing, direct provider
knowledge, or inconsistent error handling.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Decompose API access behind feature repositories | Visual redesign of the application |
| Replace raw response maps at feature boundaries with typed models | Mobile support |
| Reduce Wizard and Twin Overview orchestration complexity | Real cloud E2E tests |
| Establish consistent loading, empty, error, and blocked states | New backend endpoints beyond already approved gaps |
| Define the state-management boundary for BLoC and app-level providers | Introducing role-based access control |
| Prepare the app for pricing review, cloud access, and deployment operation UI phases | Rewriting Optimizer or Deployer internals |

## Why This Comes Next

This track should start before the remaining Frontend Delta UI phases. The
current code can still be made to work, but it is not a stable foundation for
Pricing Review Center, Profile Cloud Accounts, Dashboard Pricing Health, and
Twin Overview deployment hardening.

The critical current hotspots are:

| Area | Current risk |
|---|---|
| `lib/services/api_service.dart` | One service owns auth, twins, config, pricing, deployer, deployment, verification, simulator, and mixed response parsing. |
| `lib/bloc/wizard/wizard_bloc.dart` | One BLoC owns navigation, persistence, validation, pricing snapshots, deployer config, ZIP upload, and cleanup. |
| `lib/bloc/twin_overview/twin_overview_bloc.dart` | One BLoC owns read model loading, deployment actions, SSE, log parsing, simulator flows, and outputs. |
| `lib/screens/twin_overview/twin_overview_screen.dart` | Presentation contains formatting and domain interpretation logic. |
| `lib/widgets/deployment_verification_card.dart` | A large stateful widget performs API calls, SSE handling, parsing, and rendering. |
| `lib/screens/wizard/step3_deployer.dart` | A large screen mixes form state, validation calls, provider-specific logic, and rendering. |

## Target Architecture

```text
Flutter UI
|
|-- Presentation
|   |-- screens: route-level smart entry points only
|   `-- widgets: dumb, reusable, token-based rendering
|
|-- Feature State
|   |-- BLoCs: one responsibility per feature flow
|   `-- state models: typed loading/data/error/empty/blocked branches
|
|-- Feature Repositories
|   |-- CloudAccessRepository
|   |-- PricingRepository
|   |-- TwinRepository
|   |-- WizardRepository
|   |-- DeploymentRepository
|   `-- DeployerConfigRepository
|
|-- Management API Client
|   |-- typed request/response decode
|   |-- auth header and runtime config
|   `-- consistent error normalization
|
`-- Core
    |-- Result / AppFailure
    |-- runtime config
    |-- logging/redaction helpers
    `-- design tokens
```

Flutter continues to call the Management API only. Repositories are Flutter-side
facades for Management API use cases; they do not call Optimizer or Deployer.

## Architectural Decisions

| Decision | Final state | Rationale |
|---|---|---|
| Management API boundary | Flutter uses only the Management API base URL from runtime config. | Preserves the Orchestrator boundary from the project vision. |
| State management | Feature flows use BLoC. App-level provider usage is limited to dependency/theme/auth shell concerns until explicitly migrated. | The current project guardrail and existing feature BLoCs already define this direction. |
| API access | A small API client owns HTTP mechanics; repositories own feature use cases. | Prevents `ApiService` from growing with every new screen. |
| Response shape | Feature boundaries use typed models for stable contracts; raw maps are allowed only inside model decoders or explicitly unstructured payload containers. | Makes pricing, deployment, and wizard behavior testable. |
| Error handling | All repositories return normalized failures; screens render consistent state branches. | Prevents silent catches, ad-hoc `debugPrint`, and duplicated UI error decisions. |
| Presentation | Widgets render typed state and emit callbacks; they do not call services or parse API responses. | Keeps UI components reusable and auditable. |
| Design system | Existing theme and spacing tokens are the source of truth. | Avoids visual drift while the app is being refactored. |

## Phase Index

| Phase | Status | Document | Primary outcome |
|---|---|---|---|
| 1 | Planned | [PHASE_01_ARCHITECTURE_BASELINE.md](phases/PHASE_01_ARCHITECTURE_BASELINE.md) | Dependency rules, state ownership, and migration inventory are frozen. |
| 2 | Planned | [PHASE_02_API_REPOSITORY_SPLIT.md](phases/PHASE_02_API_REPOSITORY_SPLIT.md) | API access is split into a core client and feature repositories. |
| 3 | Planned | [PHASE_03_TYPED_FEATURE_MODELS.md](phases/PHASE_03_TYPED_FEATURE_MODELS.md) | Typed DTO/read models replace raw maps at feature boundaries. |
| 4 | Planned | [PHASE_04_WIZARD_DECOMPOSITION.md](phases/PHASE_04_WIZARD_DECOMPOSITION.md) | Wizard responsibilities are split into smaller feature flows. |
| 5 | Planned | [PHASE_05_TWIN_OVERVIEW_DECOMPOSITION.md](phases/PHASE_05_TWIN_OVERVIEW_DECOMPOSITION.md) | Twin Overview separates read model, deployment operations, outputs, logs, and deferred simulator work. |
| 6 | Planned | [PHASE_06_PRESENTATION_AND_DESIGN_SYSTEM_CLEANUP.md](phases/PHASE_06_PRESENTATION_AND_DESIGN_SYSTEM_CLEANUP.md) | Screens/widgets become presentation-only and token-aligned. |
| 7 | Planned | [PHASE_07_ARCHITECTURE_QUALITY_GATE.md](phases/PHASE_07_ARCHITECTURE_QUALITY_GATE.md) | Architecture regression checks prove readiness for remaining UI delta implementation. |

## Execution Order

1. Run Phase 1 before creating new Pricing Review, Profile Cloud Accounts, or
   Dashboard Pricing Health implementation plans.
2. Run Phase 2 and Phase 3 before wiring any new backend read models into UI.
3. Run Phase 4 before touching Wizard Step 1, Step 2, or Step 3 feature work.
4. Run Phase 5 before simulator/log-trace and deployment operation UI work.
5. Run Phase 6 after the major feature boundaries are stable, so visual cleanup
   does not fight still-moving state boundaries.
6. Run Phase 7 before resuming the feature-heavy Frontend Delta sequence.

## Relationship To Frontend Delta

This roadmap does not replace the
[Frontend Delta Roadmap](../frontend_delta/ROADMAP_FRONTEND_DELTA.md). It is
the foundation that should be executed first. After Phase 7 passes, the existing
Frontend Delta phases can continue with lower architectural risk.

## Readiness For Implementation Planning

This roadmap is ready for concept review. Each phase still requires a dedicated
architect implementation plan before Dart code changes are allowed.
