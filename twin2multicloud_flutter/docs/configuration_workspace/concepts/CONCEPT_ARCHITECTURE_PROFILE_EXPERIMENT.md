---
title: "Architecture Profile Experiment"
description: "A bounded Configuration Workspace experience for selecting, comparing, and deploying the Five-layer v2 and Six-layer v1 thesis profiles."
tags: [flutter, configuration-workspace, architecture-profiles, eventing, thesis]
lastUpdated: "2026-08-03"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/phase_08_architecture_profiles_eventing/README.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_service_bundle_closure.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md
- twin2multicloud_flutter/docs/configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md
- twin2multicloud_flutter/docs/configuration_workspace/RESOLVED_DEPLOYMENT_REVIEW.md
- FRONTEND_ARCHITECTURE.md
- User-approved Five-layer v2 and Six-layer v1 PoC boundaries from the 2026-08-03 planning conversation
EXTRACTED: 2026-08-03 | VERSION: 1.0
-->

# Architecture Profile Experiment

## Summary

The Configuration Workspace becomes the single UI for the Phase 8 experiment.
A researcher chooses one reviewed architecture profile, supplies one compatible
core workload and one fixed event scenario, compares only complete deployment
alternatives within that profile, prepares the exact cloud access required by
the selected result, and later opens the deployed L4 and L5 user surfaces.

The UI exposes two new selectable profiles:

- `five-layer-baseline@2`, where the agreed domain-event behavior is embedded
  in L1/L2 and no independent Event Layer is deployed;
- `six-layer-eventing@1`, which inherits the same L1-L5 behavior and adds an
  independently costed Eventing responsibility.

`five-layer-baseline@1` remains readable for historical Twins but is not
selectable for new calculations or deployments.

## Motivation

The current Configuration Workspace still presents legacy workload booleans,
fixed five-slot assumptions, and an optimizer recommendation without a visible
profile boundary. That would make the thesis experiment scientifically
ambiguous: a result could appear cheaper because it omits required behavior,
and Five-layer and Six-layer outcomes could be compared as if they were one
optimization space.

The target experience makes the experimental variable explicit while keeping
the infrastructure closed-world. It is a thesis demonstrator, not an
enterprise topology editor or cloud-governance product.

## Scope

| In scope | Out of scope |
|---|---|
| Architecture profile selection from an immutable Management API catalog | Free-form layers, graph editing, provider SKU editing, or inline service substitution |
| One shared core workload contract and one required immutable Small/Medium/Large event scenario | Event feature flags or user-authored event-rate combinations |
| Profile-local calculation and comparison with functional completeness before cost | Cross-profile winner, automatic recommendation of Five vs Six layers, or using price to replace a reviewed provider service bundle |
| Read-only logical profile flow and resolved provider/service assignments | Terraform values, raw resource identifiers, credentials, or direct cloud controls |
| All nine Five-layer v2 placements and the valid Six-layer provider combinations, including single-cloud | Assumptions that one provider always owns only the source or destination side |
| Guided request-scoped bootstrap after providers are known | Permanent storage of administrator credentials or an organization-wide IAM wizard |
| Exactly one usable L4 and one usable L5 access surface after deployment | Embedded provider consoles, scene/3D authoring, or a L4-to-L5 query dependency |
| Web and supported desktop platforms | Mobile targets and live paid cloud E2E in default verification |

## Experience Model

The existing five Configuration Workspace phases remain. Profile selection is
added at the beginning of **Describe workload**, because the selected profile
defines which workload fields are valid. The remaining journey stays familiar:

```text
Define Twin
    |
    v
Describe Workload
    |-- choose reviewed profile
    |-- choose core Small / Medium / Large preset or edit supported core fields
    `-- choose required immutable event Small / Medium / Large scenario
    |
    v
Choose Architecture
    |-- verify price/evidence readiness
    |-- calculate complete alternatives inside the selected profile
    `-- select one immutable resolved deployment run
    |
    v
Prepare Deployment
    |-- guided cloud bootstrap for missing selected-provider access
    |-- data contracts and user logic
    `-- profile-supported Twin assets only
    |
    v
Review Configuration
    |-- profile, workload, providers, services, edges, tiering, and readiness
    `-- Management API validation and deployment preflight
    |
    v
Twin Overview after deployment
    `-- one L4 card + one L5 card
```

Changing the profile after calculation is destructive only through the
existing server-owned invalidation preview and digest confirmation. The client
never guesses what is invalidated.

## Workload Semantics

Both selectable profiles use the same functional workload. Events are always
present, so the legacy event-check, notification, feedback, error-handling,
scene, and self-hosting feature switches are not shown.

The editable core workload contains device traffic, retention boundaries,
Twin state/graph activity, and aggregate dashboard usage. The event workload
is selected by immutable scenario ID. Core and event scenarios are paired by
size for the frozen thesis evaluation, but they remain separate versioned
inputs so that Event Layer cost can be attributed without letting users invent
unsupported combinations.

Storage tiering remains visible as retention behavior, not as optional
enterprise machinery. The UI explains that raw data moves through hot, cool,
and archive windows while rollups remain in hot storage. It does not expose
scheduler, job, shard, checkpoint, or provider-lifecycle implementation knobs.

## Architecture Comparison Semantics

The optimizer produces alternatives only after the selected profile's required
capabilities have been satisfied. Results are grouped by that profile and may
be compared by total estimated cost only within the group. Five-layer v2 and
Six-layer v1 are separate experimental runs; neither is labeled the universal
winner.

The resolved review distinguishes:

- primary logical responsibilities and their provider services;
- supporting resources that make a selected responsibility usable;
- same-provider direct paths and cross-cloud bridge edges;
- finite tiering jobs and transfer ownership;
- cost dimensions, evidence status, limitations, and unsupported candidates.

For Five-layer v2, L3 hot and L5 are deliberately co-located while L4 remains
independent. The UI therefore supports all nine L3/L5-to-L4 placements and
does not imply that L4 feeds Grafana. For GCP, one named Firestore database may
serve separately owned L3 and L4 collections when both responsibilities are on
GCP; this is shown as a resource-sharing fact, not as a merged logical layer.

## Cloud Access And Manual Actions

Draft creation, profile selection, workload entry, calculation, and review are
credential-free. Once a deployment result is selected, the UI derives the
required provider set and offers the shared guided bootstrap flow.

The researcher may supply a short-lived or deliberately disposable
administrator/bootstrap credential. The backend uses it only for the current
request/session to create and validate a bounded deployment identity, stores
only that bounded CloudConnection, and reports the truthful disposal or
revocation result. Provider prerequisites that cannot be created safely by the
PoC pause with exact instructions and resume through the normal deployment
preflight. The administrator credential is never required again after a valid
bounded CloudConnection exists.

## Post-Deployment Result

Twin Overview exposes exactly two sibling access cards:

- L4 opens the provider Twin surface or the bounded GCP Twin Explorer;
- L5 opens the provisioned Grafana dashboard for raw history and hourly
  rollups.

These cards are independent. An L4 access problem does not hide a ready L5
surface, and Grafana does not require L4. Generic Terraform outputs remain a
separate technical-evidence section.

## Dependencies

| Dependency | Required outcome |
|---|---|
| Phase 8.6 graph resolver | Deterministic generic deployment graph and binding preflight |
| Management architecture APIs | Strict profile summaries/details, server invalidation preview, selection revision, and resolved architecture |
| Workload v2 and event scenario contracts | Profile-supported fields, fixed scenario IDs, validation, and deterministic digests |
| Guided bootstrap APIs | Provider guides and request-scoped sessions that produce bounded CloudConnections |
| Deployment access API | Typed `deployment-access.v1` L4/L5 read model and GCP Viewer rotation |
| Five-layer v2 implementation | Complete service bundles, storage tiering, readers, projection, permissions, Terraform, and cost formulas |
| Six-layer v1 delta | Event Layer bundles and source-owned bridge across every directed provider pair |

Flutter consumes all of these only through the Management API.

## Open Questions

There are no unresolved product decisions. Exact provider prices, service
catalog availability, and supervised browser sign-in remain evidence or
runtime-preflight facts; they do not change the bounded UX.

## Related Concepts

- [Configuration Workspace](../CONCEPT_CONFIGURATION_WORKSPACE.md)
- [Cloud Access Bootstrap](CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md)
- [Resolved Deployment Review](../RESOLVED_DEPLOYMENT_REVIEW.md)
- [Twin Layer Access Handoff](../../frontend_delta/concepts/CONCEPT_TWIN_LAYER_ACCESS_HANDOFF.md)

## Roadmap Anchor

This concept is delivered by
[Phase 8.1: Architecture Profile Experiment](../phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md)
in the [Configuration Workspace Roadmap](../ROADMAP_CONFIGURATION_WORKSPACE.md).
