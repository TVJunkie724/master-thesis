---
title: "Phase 1: Architecture Baseline"
description: "Freeze frontend dependency rules, migration inventory, and state ownership before further UI delta implementation."
tags: [flutter, architecture, baseline, refactoring]
lastUpdated: "2026-07-15"
version: "1.1"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/concepts/CONCEPT_FRONTEND_ARCHITECTURE_TARGET.md
- .codex/skills/concept/references/flutter-guardrails.md
- FRONTEND_ARCHITECTURE.md sections "Flutter Tech Stack Explained" and "Critical Architectural Review"
- twin2multicloud_flutter/lib/app.dart
- twin2multicloud_flutter/lib/services/api_service.dart
- twin2multicloud_flutter/lib/providers/
- twin2multicloud_flutter/lib/bloc/
EXTRACTED: 2026-07-15 | VERSION: 1.1
-->

# Phase 1: Architecture Baseline

**Status:** Completed

## Summary

Create the architecture baseline that future implementation plans must follow.
This phase resolves the current ambiguity between historical Riverpod references
and the current `flutter_bloc` feature-flow rule, and it records the migration
inventory for large files and raw-map boundaries.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Document dependency direction and allowed imports | Moving code before an implementation plan exists |
| Decide the BLoC/provider boundary | Removing all provider usage in one step |
| Inventory raw-map and side-effect hotspots | Creating new UI screens |
| Define migration safety gates | Running live cloud E2E tests |

## Prerequisites

- Backend contract baseline work has produced typed Management API responses
  for the currently planned UI deltas.
- The existing Frontend Delta Roadmap remains linked as downstream feature work.

## Deliverables

- Architecture baseline section or document defining:
  - allowed layer dependencies,
  - feature BLoC ownership,
  - app-level provider boundary,
  - repository/API-client responsibilities,
  - where raw maps are still explicitly tolerated.
- Migration inventory for the known hotspots:
  - `lib/services/api_service.dart`,
  - `lib/bloc/wizard/wizard_bloc.dart`,
  - `lib/bloc/twin_overview/twin_overview_bloc.dart`,
  - `lib/screens/twin_overview/twin_overview_screen.dart`,
  - `lib/widgets/deployment_verification_card.dart`,
  - `lib/screens/wizard/step3_deployer.dart`.
- Test strategy per migration area.

## Binding State Ownership

Twin2MultiCloud deliberately uses Riverpod and BLoC at different architectural
levels. They are complementary; a feature must not mirror the same mutable
state in both systems.

| Owner | Allowed responsibilities | Not allowed |
|---|---|---|
| Riverpod | Runtime profile, dependency composition, Management API and stream adapter injection, session/auth shell, theme, router, fixture identity | Multi-step feature state machines, provider-specific wizard rules, deployment reconnect orchestration |
| BLoC | Wizard workflows, pricing review, cloud-account commands, deployment operations, logs/reconnect, Twin Overview feature state | Reading Dart defines, constructing HTTP clients, owning app theme/router/session |
| Repositories and API ports | Typed Management API use cases, transport mechanics, DTO decoding, normalized failures | Widget state, navigation, direct Optimizer/Deployer access |
| Widgets and screens | Render typed state and emit callbacks/events | HTTP calls, response parsing, credential handling, duplicated feature state |

Composition flows in one direction:

```text
AppRuntimeConfig
  -> RuntimeComposition / Riverpod adapter providers
  -> route-level BLoC construction
  -> typed BLoC state
  -> presentation
```

The runtime profile is a single immutable value. `development` requires an
explicit Management API origin and local token, `production` requires HTTPS
and starts token-free, and `demo` has fixture adapters with no network config.
Production authentication remains fail-closed until GitHub issue #10 provides
the real OAuth/SAML session lifecycle.

## Acceptance Criteria

- The implementation architect can determine where a new API method, DTO,
  repository call, event, state, and widget belongs without interpretation.
- The plan states how existing provider usage is treated during migration.
- Every major hotspot has a target owner and a migration phase.
- No phase depends on real cloud E2E tests.
- The downstream Frontend Delta phases explicitly treat this phase as a
  prerequisite.

## Verification

- Concept review against this roadmap.
- Static inventory review for direct Optimizer/Deployer calls, raw maps, and
  side effects in widgets.
- Runtime ownership is enforced by the Flutter architecture checker and its
  tests; feature behavior remains covered by BLoC and widget tests.

## Roadmap Anchor

Roadmap:
[Frontend Architecture Refactoring Roadmap](../ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md)
