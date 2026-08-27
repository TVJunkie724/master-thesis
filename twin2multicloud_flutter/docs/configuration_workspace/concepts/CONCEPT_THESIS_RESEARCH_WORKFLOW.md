---
title: "Thesis Research Workflow Consolidation"
description: "Research-question-driven Flutter scope for the standalone Six-layer proof of concept."
tags: [flutter, thesis, research-workflow, six-layer, poc]
lastUpdated: "2026-08-27"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/2026-08-26_thesis_poc_target_concept.md sections 1-5 and 9-14
- docs/plans/2026-08-26_thesis_poc_execution_plan.md section 10
- docs/research/research_questions_and_evaluation_design.md
- FRONTEND_ARCHITECTURE.md sections "Architecture Overview", "Screens", and "Critical Architectural Review"
- twin2multicloud_flutter/docs/configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_08_TWIN_OVERVIEW_DEPLOYMENT_OPERATIONS.md
- twin2multicloud_flutter/lib/app.dart
- twin2multicloud_flutter/lib/screens/dashboard_screen.dart
- twin2multicloud_flutter/lib/screens/wizard/wizard_screen.dart
- twin2multicloud_flutter/lib/screens/twin_overview/twin_overview_screen.dart
EXTRACTED: 2026-08-27 | VERSION: 1.0
-->

# Thesis Research Workflow Consolidation

## Decision

Flutter becomes a focused research client for the standalone
`six-layer-eventing@1` proof of concept. It must expose the complete path from a
portable Twin scenario to calculation, provider preparation, deployment,
telemetry evidence, and cleanup evidence. It must not present dormant
architecture choices, pricing administration, or product-style fleet metrics.

The four responsibilities below are information responsibilities, not a
requirement to force the application into exactly four routes.

| Responsibility | Research or safety value | Primary surface |
|---|---|---|
| Scenario | Reproducible typed experiment input for RQ1 and RQ2 | Dashboard plus Configuration Workspace |
| Optimize | Immutable cost, assumptions, exclusions, and provider allocation for RQ3 | Configuration Workspace |
| Prepare | Explicit administrator-connection binding, graph readiness, confirmation, and repair for RQ1 | Settings plus Configuration Workspace |
| Operate and verify | Idempotent deployment, access handoff, telemetry proof, and cleanup proof for RQ1 and RQ3.2 | Twin Overview |

## Scope

| In scope | Out of scope |
|---|---|
| Multiple Twins and draft creation | Product fleet analytics and aggregate cost cards |
| Portable typed Twin import, export, and duplicate | Arbitrary executable project ZIPs |
| One fixed Six-layer architecture explanation | Architecture-profile selection or change workflows |
| One cost calculation command and immutable result review | Objective selection, weighted scoring, or pricing administration |
| Multiple named deployment CloudConnections per provider | Pricing credentials and default-pricing management |
| Typed entry and allowlisted provider credential-file import | Provider credential creation, rotation, or least-privilege derivation |
| Graph-derived readiness, preparation confirmation, and repair | Generic provider administration |
| Durable Deploy and Destroy with SSE reconnect/replay | Poll-only mutation UX or duplicate provider commands |
| Provider-accurate L4/L5 links | Embedded provider dashboards |
| Persisted telemetry and cleanup evidence | Unstructured log text as proof of success |

## Information Architecture

```text
Dashboard
|-- New Twin
|-- Import Twin archive
`-- Twin experiments
    |-- Open or edit
    |-- Duplicate to a new draft
    |-- Export portable archive
    `-- Delete only when lifecycle permits

Configuration Workspace
|-- Scenario
|   |-- Twin identity
|   |-- workload and behavior
|   `-- bounded user logic
|-- Optimize
|   |-- calculate
|   |-- review selected allocation and cost
|   `-- inspect assumptions, exclusions, and trace
|-- Prepare
|   |-- select one existing administrator connection per required provider
|   |-- configure bounded data contracts and assets
|   `-- review graph-derived readiness and repair
`-- Finish configuration

Settings
`-- Deployment CloudConnections
    |-- AWS, Azure, and GCP lists
    |-- typed entry or allowlisted credential-file import
    |-- validate
    `-- delete when unbound

Twin Overview
|-- deployment readiness and repair entry point
|-- L4 and L5 provider access
|-- Deploy or Destroy with durable operation progress
|-- persisted telemetry verification evidence
|-- post-Destroy cleanup evidence
`-- collapsed configuration and technical evidence
```

## Workflow Rules

1. A new Twin receives the canonical Six-layer contract automatically. The UI
   may explain that contract but must never offer a profile selector.
2. Frozen, referenced pricing snapshots are optimizer evidence. The user does
   not refresh, approve, or administer provider pricing from Flutter.
3. The optimizer remains the sole owner of monetary ranking. Flutter displays
   the immutable result and trace without recomputing it.
4. Settings stores multiple named deployment CloudConnections. The Workspace
   selects from those connections only after the resolved provider set is
   known.
5. Credential files are parsed by the Management API allowlist. Flutter never
   stores an uploaded file and never renders a secret after submission.
6. Deployed Twin definitions remain immutable. Duplicate or Import creates an
   independent draft with a unique name; no source Twin is destroyed
   implicitly.
7. Deploy and Destroy retain SSE reconnect, resume, and persisted replay. These
   behaviors protect cost-incurring mutations and are not product extras.
8. Verification presents typed persisted telemetry evidence. Destroy presents
   typed Terraform/provider inventory evidence, retained shared prerequisites,
   and residual failures.

## State And Error Contract

Every retained asynchronous surface must distinguish loading, data, empty,
blocked, and error states. Errors remain secret-safe and actionable:

- configuration failures point to the relevant task;
- readiness failures point to automatic preparation, manual action, or
  connection replacement;
- stream interruption shows reconnect/replay state and never starts a second
  provider operation;
- telemetry failure identifies the failed phase without claiming a successful
  roundtrip;
- cleanup failure keeps residual evidence visible and never reports a
  successful Destroy.

## Responsive And Accessibility Contract

The supported targets remain Web, macOS, Windows, and Linux. Wide layouts may
use a task sidebar and multi-column evidence rows. Compact supported layouts
stack the same information in the same semantic order. All commands require
text labels or tooltips, status is never color-only, dialogs restore focus, and
technical detail remains collapsed without becoming inaccessible.

## Acceptance

- A user can complete the supported journey without visiting a pricing,
  objective, profile-selection, generic-project, or operations-dashboard view.
- The Dashboard makes Twin portability available without introducing arbitrary
  project execution.
- The canonical Six-layer architecture is loaded and validated without a user
  selection step.
- Settings and the Workspace expose only deployment administrator connections.
- Telemetry and cleanup proof survive reload through typed Management API read
  models.
- Deploy and Destroy keep their current idempotent reconnect/replay safety.
- No Flutter code calls the Optimizer, Deployer, Terraform, or provider APIs
  directly.

## Roadmap Anchor

[Configuration Workspace Roadmap](../ROADMAP_CONFIGURATION_WORKSPACE.md),
Phase 9.
