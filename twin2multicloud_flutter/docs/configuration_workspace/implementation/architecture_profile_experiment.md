---
title: "Architecture Profile Workflow Implementation"
description: "Implemented Flutter state, API, presentation, and Five-/Six-layer activation boundaries for Phase 8.7, Phase 8.9A, and Phase 8.9B."
tags: [flutter, architecture-profiles, wizard, bloc, phase-8]
lastUpdated: "2026-08-14"
version: "1.7"
---

<!-- SOURCES:
- twin2multicloud_flutter/implementation_plans/2026-08-03_architecture_profile_experiment.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md
- docs/plans/phase_08_architecture_profiles_eventing/README.md
- twin2multicloud_flutter/lib/bloc/wizard/
- twin2multicloud_flutter/lib/features/configuration_workspace/
- twin2multicloud_flutter/lib/widgets/results/resolved_architecture_review.dart
- Credential-free OrbStack integration verification on 2026-08-03
EXTRACTED: 2026-08-14 | VERSION: 1.7
-->

# Architecture Profile Workflow Implementation

## Implemented Boundary

Phase 8.7 installed the reusable Flutter workflow before activation.
`ApiService` and `DemoManagementApi` implement the same
seven-operation `ArchitectureApi`; `WizardBloc` owns all network commands and
workflow state; Riverpod continues to inject the runtime adapter. No widget
calls Optimizer, Deployer, or a cloud provider.

The real and demo catalogs now expose active standalone Six-layer v1
for offline selection. `six-layer-eventing@1` remains visible only as
historical evidence for audit, verification, and destroy compatibility. The
connected local stack calculates both active profiles and persists their exact
RTA/RDS v2 evidence. Demo Small/Medium/Large calculations deliberately remain
canonical Six-layer fixtures; selecting Six-layer in Demo allows profile
inspection but calculation returns `DEMO_PROFILE_CALCULATION_UNAVAILABLE`
rather than fabricating or relabeling a resolved result.

| In scope | Out of scope |
|---|---|
| Typed profile/resolution reads, BLoC-owned selection state, active Six-layer-v2 and Six-layer-v1 Workload/RTA/RDS evidence, fixture-driven generic review, responsive/accessibility behavior, and credential-free Management integration | Arbitrary workload or topology editing, provider execution, live-capacity claims, infrastructure editing, and real cloud deployment |

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
cloud-console embedding, L4-to-L5/3D behavior, arbitrary workload editing, or
fabricated live-capacity evidence. Phase 8.9A atomically activated the frozen
Workload v2 scenarios and Six-layer for offline evaluation. Phase 8.9B
activates the strict Six-layer Eventing delta through the same workflow.
Provider credential provisioning and deployed L4/L5 access remain outside
this offline architecture experiment.

## Verification

Unit and widget coverage includes empty/historical catalogs, exact active
selection hydration, detail races, server-owned invalidation, revision and
digest conflicts, incompatible Twin/run/profile resolutions, declared-edge
rendering, dialog locking, generic tiering/bridge review, all responsive
boundaries, keyboard selection/cancellation, explicit light/dark status cues,
and the pricing/navigation regression suite.

The credential-free desktop integration tests create and remove local Twins,
verify the Management-owned active/historical profile boundary, and exercise
the single active profile. The Six-layer workflow calculates and persists one
local Six-layer resolution, verifies the independent
`component.eventing` assignment, and confirms that live deployment remains
blocked without capacity evidence. The repository entrypoint
runs the tests after Management readiness through OrbStack-compatible Compose.
It does not refresh prices, contact a provider, deploy, destroy infrastructure,
or execute Terraform.

The reusable Phase 8.7 implementation commit is `a0f6fb7b`; the Six-layer UI
activation is recorded by `e977982b` and `a661d789`. Phase 8.7's two review
perspectives closed all state, UI, and verification findings. The latest 8.9B
Flutter rerun passed 893 tests, static analysis, Web release, and macOS debug
builds. The complete OrbStack integration passed readiness, active-profile,
extension, and Layer Access checks in an isolated
Compose project. Linux and Windows remain the existing host-CI build gates
when this branch is integrated; the local macOS run does not claim those host
builds. Two final 8.9B reviews of the complete profile workflow and its
cross-stack contract reached zero unresolved findings; the offline result is
frozen for Phase 8.10 evaluation, while live-capacity gates remain fail-closed.

Phase 8.10 now generates the thesis evaluation as a deterministic repository
evidence package. That package evaluates the historical v1 reconstruction and
the standalone Six-layer profile, but it does not add another Flutter flow, turn the UI
into an evaluation dashboard, or authorize a cross-profile winner claim.

Authoritative sources:

- [Architecture Profile Experiment concept](../concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md)
- [Architecture Profile Experiment phase](../phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md)
- [Configuration Workspace roadmap](../ROADMAP_CONFIGURATION_WORKSPACE.md)
- `docs/plans/phase_08_architecture_profiles_eventing/README.md`
