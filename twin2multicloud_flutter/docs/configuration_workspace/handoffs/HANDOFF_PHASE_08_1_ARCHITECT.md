---
title: "Handoff: Phase 8.1 Architecture Profile Experiment to Architect"
description: "Self-contained handoff for the Flutter architecture-profile implementation plan."
tags: [flutter, handoff, architect, architecture-profiles]
lastUpdated: "2026-08-03"
version: "1.1"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md
- twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md
- .codex/skills/concept/references/handoff-protocol.md
EXTRACTED: 2026-08-03 | VERSION: 1.1
-->

# Handoff: Phase 8.1 Architecture Profile Experiment to Architect

## 1. Context

- Pillar: Configuration Workspace.
- Roadmap: `twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md`.
- Concept: `twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md`.
- Phase: `twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md`.
- The user has authorized concept, plan, and implementation of the bounded
  Phase 8 thesis PoC. This is not a request for a product-grade topology or
  cloud-governance UI.

## 2. Objective

Produce an executable Flutter implementation plan that extends the existing
Configuration Workspace with strict server-driven profile selection and
generic resolved review, while keeping the real/demo active catalog empty
until Five-layer v2 activation in Phase 8.9A. Populated Five-/Six-layer states
are contract and widget fixtures, not early runtime publication.

## 3. Required Reading

- `FRONTEND_ARCHITECTURE.md`
- `integration_vision.md`
- `.codex/skills/concept/references/flutter-guardrails.md`
- `twin2multicloud_flutter/README.md`
- `twin2multicloud_flutter/docs/configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md`
- `twin2multicloud_flutter/docs/configuration_workspace/RESOLVED_DEPLOYMENT_REVIEW.md`
- `twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md`
- `twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md`
- `twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md`
- `docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md`
- `docs/plans/phase_08_architecture_profiles_eventing/phase_08_service_bundle_closure.md`
- `docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md`
- `docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md`

## 4. Scope

In scope: the profile/review Configuration Workspace increment, strict
existing-API models, live/demo adapters, BLoC state, responsive and accessible
presentation, activation seams for later workload/calculation contracts, and
safe tests.

Out of scope: a graph editor, provider resource authoring, direct cloud calls,
direct Optimizer/Deployer calls, guided bootstrap implementation, deployed
layer-access implementation, mobile targets, and live cloud E2E. The latter
two UI capabilities already have separate concepts/phases and must integrate
without being folded into this plan.

## 5. Constraints And Decisions

- Extend the implemented Configuration Workspace and its Wizard BLoC; do not
  restore or create a second three-step wizard.
- Flutter talks only to the Management API.
- `five-layer-baseline@1` is historical read-only.
- Phase 8.7 exposes no selectable runtime/demo profile; Five v2 activates in
  8.9A and Six v1 only after its reviewed branch gate.
- Events are mandatory in both selectable profiles. No legacy event flags.
- Core workload and immutable event scenario are separate later inputs owned
  by the Phase 8.9A contract, not invented by the Phase 8.7 client.
- Calculations and rankings are profile-local. No cross-profile winner.
- The client never derives invalidation, functional completeness, resolved
  services, bridges, tiering jobs, or cost ownership.
- Five-layer v2 has L3 hot equal to L5 placement, independent L4, and no
  L4-to-L5 edge.
- New profile DTOs must be strict; raw nested maps are not an acceptable
  Flutter boundary.
- Reuse the current Riverpod runtime/dependency composition and BLoC feature
  workflow.

## 6. Acceptance Criteria

- `flutter analyze` is clean.
- The full Flutter test suite is green.
- Web, macOS, Windows, and Linux supported build gates pass.
- Loading, empty, error, stale, historical, unsupported, and retry paths are
  explicit.
- Compact and wide layouts remain usable at 200% text and by keyboard.
- Real integration tests use the Management API Docker stack without direct
  service calls or cloud deployment.

## 7. Dependencies

- Phase 8.6 generic graph resolver: implementation dependency, currently dark
  work in progress.
- Strict Management DTOs and workload-v2 contracts: must be implemented before
  their Flutter adapters.
- Complete-service decision and Six-layer Eventing manifest: determine catalog
  content; clients do not duplicate them.
- Guided bootstrap Phase 9 and Twin layer access remain separately planned.

## 8. Open Questions

None. Provider prices and catalog availability are evidence inputs and do not
change this UI contract.
