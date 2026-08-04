---
title: "Architecture Profile Workflow Implementation"
description: "Implemented Flutter state, API, presentation, activation, and verification boundaries for Phase 8.7."
tags: [flutter, architecture-profiles, wizard, bloc, phase-8]
lastUpdated: "2026-08-03"
version: "1.1"
---

<!-- SOURCES:
- twin2multicloud_flutter/implementation_plans/2026-08-03_architecture_profile_experiment.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md
- twin2multicloud_flutter/lib/bloc/wizard/
- twin2multicloud_flutter/lib/features/configuration_workspace/
- twin2multicloud_flutter/lib/widgets/results/resolved_architecture_review.dart
- Credential-free OrbStack integration verification on 2026-08-03
EXTRACTED: 2026-08-03 | VERSION: 1.1
-->

# Architecture Profile Workflow Implementation

## Implemented Boundary

Phase 8.7 installs the reusable Flutter workflow without activating a new
runtime architecture. `ApiService` and `DemoManagementApi` implement the same
seven-operation `ArchitectureApi`; `WizardBloc` owns all network commands and
workflow state; Riverpod continues to inject the runtime adapter. No widget
calls Optimizer, Deployer, or a cloud provider.

The real and demo catalogs are empty until Five-layer v2 is published.
`five-layer-baseline@1` remains visible only as a historical selection for
audit, verification, and destroy compatibility. Populated profiles and
resolved architectures used by tests are contract fixtures, not advertised
runtime capabilities.

| In scope | Out of scope |
|---|---|
| Typed profile/resolution reads, BLoC-owned selection state, fixture-driven generic review, responsive/accessibility behavior, and credential-free Management integration | Workload v2 publication, a selectable runtime profile, guided cloud bootstrap, provider execution, infrastructure editing, and deployed L4/L5 access |

## Journey And State

```text
Define twin
  -> Architecture: Select profile -> Understand architecture
  -> Workload
  -> User Logic
  -> Optimize and review
  -> Deployment review
```

The Twin must first be saved because profile selection is revisioned against a
persisted selection. A matching profile detail must load and the researcher
must visit **Understand architecture** before workload and user logic unlock.
Calculation additionally requires valid workload, all profile-required
extension bindings, and pricing readiness.

`WizardState` keeps separate phases for catalog, detail, profile change, and
resolved architecture. Request generations prevent late catalog/detail/run
responses from replacing newer state. Profile mutations follow this sequence:

```text
target profile
  -> Management change preview (current revision)
  -> dialog renders only returned invalidations
  -> explicit confirmation submits revision + preview digest
  -> Management result clears only returned fields/bindings/run/readiness
```

A revision or invalidation-digest conflict clears the preview, reloads the
current selection, and requires another explicit confirmation. There is no
automatic mutating retry.

## Presentation

- `ArchitectureProfileTask` renders loading, empty, error, historical,
  selection, detail, and conflict states.
- `ArchitectureProfileChoice` exposes mutually exclusive selection semantics
  with version, responsibility count, provider availability, and limitations.
- `LogicalProfileFlow` projects either responsibilities or components from the
  typed graph. At widths of 720 and above it uses a bounded Sugiyama canvas
  with zoom/reset controls. Below 720 it renders a labeled vertical projection
  containing only declared edges; it never infers a sequential connection.
- `ArchitectureProfileChangeDialog` displays only server-returned workload,
  extension, run, and readiness effects and prevents duplicate submission.
- `ResolvedArchitectureReview` renders required and supporting assignments,
  provider services, regions, tiering/support resources, local and cross-cloud
  edges, costs, extension bindings, and pinned evidence. Its
  `LogicalResolvedFlow` uses the same bounded-wide/exact-compact projection
  rule and shows only resolved assignments and declared edges. It contains no
  editable infrastructure field.

Workspace layout breakpoints remain 1200 for wide sidebar composition, 960 for
compact task selection, 720 for graph projection, and 640 as the supported
lower width. Widget tests cover 640, 719, 720, 959, 960, 1199, and 1200 plus
200% text scaling.

## Activation And PoC Limits

This is a Master-thesis PoC boundary, not a general architecture product. It
does not add free-form layers, provider SKU controls, an Event feature flag,
cloud-console embedding, L4-to-L5/3D behavior, Workload v2, or a fake active
demo profile. Phase 8.9A owns the atomic Workload v2 and Five-layer v2
activation; Phase 8.9B owns the Six-layer delta. Guided bootstrap and deployed
L4/L5 access remain separate reviewed slices.

## Verification

Unit and widget coverage includes empty/historical catalogs, exact active
selection hydration, detail races, server-owned invalidation, revision and
digest conflicts, incompatible Twin/run/profile resolutions, declared-edge
rendering, dialog locking, generic tiering/bridge review, all responsive
boundaries, keyboard selection/cancellation, explicit light/dark status cues,
and the pricing/navigation regression suite.

The credential-free desktop integration test creates and removes one local
Twin, verifies the empty active catalog and historical selection, and proves
that historical detail/change targets are rejected. The repository entrypoint
runs it after Management readiness through OrbStack-compatible Compose. It
does not refresh prices, contact a provider, deploy, destroy infrastructure,
or execute Terraform.

Authoritative sources:

- [Architecture Profile Experiment concept](../concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md)
- [Architecture Profile Experiment phase](../phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md)
- [Configuration Workspace roadmap](../ROADMAP_CONFIGURATION_WORKSPACE.md)
- `docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md`
