---
title: "Phase 8.1: Architecture Profile Experiment"
description: "Expose Five-layer v2 and Six-layer v1 as bounded, profile-local thesis experiments in the Configuration Workspace."
tags: [flutter, phase, architecture-profiles, optimizer, eventing]
lastUpdated: "2026-08-11"
version: "1.4"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md
- twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_service_bundle_closure.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_9_six_layer_eventing_implementation.md
EXTRACTED: 2026-08-11 | VERSION: 1.4
-->

# Phase 8.1: Architecture Profile Experiment

**Implementation status:** Phase 8.7 is implemented and zero-finding reviewed
locally. The runtime/demo catalog now exposes Five-layer v2 for offline
selection and evaluation; live-capacity gates still block deployment. See the
[implementation reference](../implementation/architecture_profile_experiment.md).

## Summary

Deliver the Architecture Profile Experiment in activation-safe increments.
Phase 8.7 extends the Configuration Workspace with strict profile and resolved
architecture DTOs, server-driven selection/review state, generic single-cloud
and multicloud presentation fixtures, and historical read-only compatibility.
It truthfully blocks new-profile work while the active catalog is empty.
Phase 8.9A publishes Workload v2 and Five-layer v2; Phase 8.9B adds the
Six-layer delta. Guided bootstrap and deployed L4/L5 access retain their own
phases and integrate through the same selected architecture.

## Prerequisites

- The Phase 8.6 graph resolver and staged binding preflight are committed and
  pass their offline gates.
- The immutable complete-service decision package approves
  `five-layer-baseline@2` and pins its provider/component manifests.
- The reviewed Phase 8.8 package pins the shared event scenarios and the
  `six-layer-eventing@1` Event Layer delta for later activation.
- Management API profile and resolved-architecture endpoints expose strict,
  profile-neutral DTOs.
- The current Configuration Workspace Phase 8 immutable deployment selection
  remains green and is extended rather than replaced.

## Deliverables

1. Strict Dart profile summary/detail, resolved architecture, and
   profile-change preview models matching the existing Phase 8.4 API.
2. A typed Management API capability shared by live and demo adapters.
3. Wizard/Configuration Workspace state for catalog loading, profile
   selection, server preview confirmation, stale revision recovery, compatible
   workload fields, and resolved profile review.
4. A profile task before workload entry and a read-only logical-flow summary.
5. An explicit activation seam: the Phase 8.7 empty-catalog state blocks
   unsupported work, while Phase 8.9A atomically publishes the canonical
   Workload v2/profile evidence without fabricating live-capacity readiness.
6. Profile-local calculation and recommendation presentation fixtures with no
   cross-profile winner, ready for the Phase 8.9A request contract.
7. Generic assignment/edge/support-component review for all valid
   single-cloud and multicloud results.
8. Documentation, demo parity, unit/widget tests, and credential-free real
   Management API integration coverage.

## Acceptance Criteria

- Only profiles returned by the Management active catalog are selectable;
  it now contains exactly Five-layer v2, while `five-layer-baseline@1` is
  historical and read-only.
- Phase 8.7 does not submit a new-profile calculation. The mandatory event
  scenario and exact Workload v2 mapping activate atomically in Phase 8.9A.
- Populated fixtures prove that visible workload-field IDs and extension slots
  derive from the selected profile rather than fixed UI layer assumptions.
- A profile change uses only the server preview/digest, invalidates downstream
  state atomically, and requires a fresh preview after a stale conflict.
- After the 8.9A activation, calculation is impossible when profile, workload,
  scenario, pricing, or functional-completeness readiness is absent; before
  activation the empty catalog blocks it earlier.
- Result review represents arbitrary registered components and edges without
  assuming five fixed slots.
- Five-layer v2 review shows L3-hot/L5 co-location and independent L4 without a
  L4-to-L5 edge.
- Six-layer review adds the Eventing responsibility and bridge only where the
  resolved providers require it.
- Single-cloud results show local Eventing/tiering and no bridge or cross-cloud
  transfer.
- Flutter calls only the Management API and renders no credentials, raw
  Terraform values, or physical destination identifiers.
- Web, macOS, Windows, and Linux supported gates remain green; default tests
  create no cloud resource.

## Roadmap Anchor

[Configuration Workspace Roadmap](../ROADMAP_CONFIGURATION_WORKSPACE.md),
inserted as Phase 8.1 without renumbering the existing Phase 9 bootstrap.
