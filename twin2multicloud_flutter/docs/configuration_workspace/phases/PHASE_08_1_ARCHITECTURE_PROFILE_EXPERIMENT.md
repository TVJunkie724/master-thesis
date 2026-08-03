---
title: "Phase 8.1: Architecture Profile Experiment"
description: "Expose Five-layer v2 and Six-layer v1 as bounded, profile-local thesis experiments in the Configuration Workspace."
tags: [flutter, phase, architecture-profiles, optimizer, eventing]
lastUpdated: "2026-08-03"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md
- twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_service_bundle_closure.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_9_six_layer_eventing_implementation.md
EXTRACTED: 2026-08-03 | VERSION: 1.0
-->

# Phase 8.1: Architecture Profile Experiment

## Summary

Extend the implemented Configuration Workspace with a strict architecture
profile and workload-v2 workflow. The increment covers selection, calculation,
resolved review, single-cloud and multicloud presentation, and historical
read-only compatibility. Guided bootstrap and deployed L4/L5 access retain
their own phases and integrate through the same selected architecture.

## Prerequisites

- The Phase 8.6 graph resolver and staged binding preflight are committed and
  pass their offline gates.
- The immutable complete-service decision package approves
  `five-layer-baseline@2` and pins its provider/component manifests.
- The reviewed Phase 8.8 package pins the shared event scenarios and the
  `six-layer-eventing@1` Event Layer delta.
- Management API profile and resolved-architecture endpoints expose strict,
  profile-neutral DTOs.
- The current Configuration Workspace Phase 8 immutable deployment selection
  remains green and is extended rather than replaced.

## Deliverables

1. Strict Dart profile summary/detail, workload-v2, event-scenario, resolved
   architecture, and profile-change preview models.
2. A typed Management API capability shared by live and demo adapters.
3. Wizard/Configuration Workspace state for catalog loading, profile
   selection, server preview confirmation, stale revision recovery, compatible
   workload fields, and resolved profile review.
4. A profile task before workload entry and a read-only logical-flow summary.
5. Removal of legacy event/scene/self-hosting switches from new-profile input
   while retaining historical read-only parsing.
6. Profile-local calculation and recommendation presentation with no
   cross-profile winner.
7. Generic assignment/edge/support-component review for all valid
   single-cloud and multicloud results.
8. Documentation, demo parity, unit/widget tests, and credential-free real
   Management API integration coverage.

## Acceptance Criteria

- Only active and implemented `five-layer-baseline@2` and
  `six-layer-eventing@1` are selectable; `five-layer-baseline@1` is clearly
  historical and read-only.
- The event scenario is mandatory and comes from the immutable catalog; no
  event feature flag or inline event workload is submitted.
- The visible/editable workload fields come from the selected profile and map
  exactly to workload v2.
- A profile change uses only the server preview/digest, invalidates downstream
  state atomically, and requires a fresh preview after a stale conflict.
- Calculation is impossible when profile, workload, scenario, pricing, or
  functional-completeness readiness is absent.
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
