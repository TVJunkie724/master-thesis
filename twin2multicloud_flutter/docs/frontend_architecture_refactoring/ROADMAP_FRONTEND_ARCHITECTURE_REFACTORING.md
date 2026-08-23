---
title: "Frontend Architecture Refactoring Roadmap"
description: "Roadmap for decomposing the Flutter app into stable Management API, state, domain, and presentation boundaries before feature-heavy UI delta work continues."
tags: [flutter, architecture, refactoring, roadmap, thesis]
lastUpdated: "2026-08-23"
version: "1.2"
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
EXTRACTED: 2026-08-23 | VERSION: 1.2
-->

# Frontend Architecture Refactoring Roadmap

This roadmap records the completed prerequisite architecture track for the
Flutter app. The implementation deliberately used a narrower architecture than
the first draft: `ManagementApi` is the application port, `ApiService` is its
production adapter, Riverpod composes runtime/auth/API dependencies, and
feature BLoCs own complex workflows. A mandatory repository class per feature
was not added merely to satisfy the original diagram.

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
| 1 | Completed | [PHASE_01_ARCHITECTURE_BASELINE.md](phases/PHASE_01_ARCHITECTURE_BASELINE.md) | Dependency rules, state ownership, and explicit runtime/auth profiles are enforced. |
| 2 | Superseded by narrower port boundary | [PHASE_02_API_REPOSITORY_SPLIT.md](phases/PHASE_02_API_REPOSITORY_SPLIT.md) | The stable `ManagementApi` port and typed models provide the required test seam; feature repository wrappers are not required for this PoC. |
| 3 | Completed | [PHASE_03_TYPED_FEATURE_MODELS.md](phases/PHASE_03_TYPED_FEATURE_MODELS.md) | Typed DTO/read models replace raw maps at stable twin, configuration, optimizer, pricing-export, and deployer feature boundaries (#72). |
| 4 | Completed | [PHASE_04_WIZARD_DECOMPOSITION.md](phases/PHASE_04_WIZARD_DECOMPOSITION.md) | #38 splits handler, request-builder, service, and presentation responsibilities while preserving one public workflow BLoC. |
| 5 | Completed | [PHASE_05_TWIN_OVERVIEW_DECOMPOSITION.md](phases/PHASE_05_TWIN_OVERVIEW_DECOMPOSITION.md) | #73 separates typed operations, readiness, logs, outputs, simulator/trace state, and presentation. |
| 6 | Completed for PoC | [PHASE_06_PRESENTATION_AND_DESIGN_SYSTEM_CLEANUP.md](phases/PHASE_06_PRESENTATION_AND_DESIGN_SYSTEM_CLEANUP.md) | #38, #73, and #108 establish focused presentation widgets and shared architecture/design checks; the final human visual review under #111 passed in Frontend Delta Phase 10. |
| 7 | Completed | [PHASE_07_ARCHITECTURE_QUALITY_GATE.md](phases/PHASE_07_ARCHITECTURE_QUALITY_GATE.md) | #108 and #109 enforce architecture, tests, demo behavior, and Web/all-desktop build gates. |

## Execution Order

1. Preserve the completed Phase 1 and typed-model boundaries.
2. Add a feature repository only when it creates a real use-case boundary that
   `ManagementApi` plus a feature BLoC cannot express cleanly.
3. Keep the completed Configuration Workspace and Twin Overview ownership
   splits stable while addressing audit findings.
4. Keep the architecture and supported-platform checks green for every future
   Flutter change.
5. Run the final human audit from the Frontend Delta roadmap before supervised
   provider E2E.

## Relationship To Frontend Delta

This roadmap does not replace the
[Frontend Delta Roadmap](../frontend_delta/ROADMAP_FRONTEND_DELTA.md). Its
completed boundaries are the foundation for the remaining final manual audit.

## Readiness For Implementation Planning

The architecture track is complete for the Thesis PoC. New feature work still
requires a dedicated concept and architect implementation plan before Dart code
changes. Findings inside the already approved final audit may use a focused
finding-specific plan proportional to their risk.
