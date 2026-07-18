---
title: "Configuration Workspace Target"
description: "Enterprise-grade UX and architecture target for configuring a Twin2MultiCloud digital twin."
tags: [flutter, configuration, wizard, ux, architecture]
lastUpdated: "2026-07-12"
version: "1.0"
---

# Configuration Workspace Target

## Decision

Replace the fixed three-step wizard with an intent-driven, dependency-aware
configuration workspace. The workspace guides users through five business
phases without exposing backend file names, storage boundaries, or deployment
implementation details as navigation concepts.

The UI remains guided, but it is not strictly linear. Completed and available
tasks can be revisited directly. Tasks whose prerequisites are missing remain
visible with a concise reason. Tasks that do not apply to the selected
architecture are marked as not required rather than silently disappearing.

## User Journey

1. **Define twin**: name and execution mode.
2. **Describe workload**: device traffic, processing, retention, and twin
   capabilities.
3. **Choose architecture**: confirm pricing readiness, calculate alternatives,
   review the recommendation, and verify the immutable deployment selection.
4. **Prepare deployment**: bind deployment access for selected providers and
   supply data contracts, user logic, and required assets.
5. **Review configuration**: inspect the complete configuration, resolve
   readiness findings, run authoritative preflight validation, and finish.

Deployment itself remains an explicit Twin Overview operation. Finishing the
workspace creates a deployment-ready configuration; it does not deploy cloud
resources.

## Interaction Model

Wide layouts use a task sidebar and one focused content surface. Only the
active phase expands its subtasks. Compact layouts use a section chooser with
the same task state and ordering. A stable footer provides Back, draft status,
and Continue or Finish actions.

Task states are typed and deterministic:

| State | Meaning |
|---|---|
| `complete` | Required data is valid and persisted or represented in the draft. |
| `current` | The task currently shown in the content surface. |
| `attention` | User input exists but is invalid, stale, or invalidated. |
| `available` | Prerequisites are met and the task may be opened. |
| `blocked` | A prerequisite is missing; the UI states which one. |
| `notRequired` | The selected architecture does not require this task. |

Navigation state is presentation state. Readiness is derived from typed
configuration and backend contracts. The Management API's existing
`highest_step_reached` remains a compatibility field during migration and must
not become the new journey source of truth.

## Information Architecture

```text
Configuration workspace
|-- Define twin
|-- Describe workload
|   |-- Scenario and currency
|   |-- Device traffic
|   |-- Processing
|   |-- Retention
|   `-- Twin capabilities
|-- Choose architecture
|   |-- Pricing readiness
|   |-- Calculate alternatives
|   `-- Review recommendation
|-- Prepare deployment
|   |-- Cloud access
|   |-- Data contracts
|   |-- User logic
|   `-- Twin assets
`-- Review configuration
    |-- Summary
    |-- Readiness findings
    `-- Validation and preflight
```

## Architectural Boundaries

- A typed journey projector maps `WizardState` to phases, tasks, statuses,
  blockers, and the recommended next task.
- BLoC owns draft state and side effects. Widgets render projections and emit
  typed user intents.
- Existing optimizer and deployer request contracts remain authoritative; the
  redesign does not fork configuration data into a second UI-only model.
- Known schemas are form-first. Raw JSON or Python remains an advanced editing
  path with explicit validation.
- Pricing maintenance stays in the Pricing Review Center. The workspace shows
  pricing health and a dashboard-location hint, but does not fetch prices.
- Cloud access is requested only after architecture selection and only for
  providers used by that architecture.
- Generated deployment configuration is an artifact, not a navigation task.
- Provider resources and deployable dimensions are selected by the Optimizer,
  verified as one immutable run, and shown read-only; Flutter is not a second
  deployment-configuration source.
- Final completion requires server-side configuration validation and preflight;
  client readiness is guidance, not authority.

## Generation Flow

```text
Workload intent
  -> versioned calculation contract
  -> selected architecture
  -> versioned deployment templates/contracts
  -> generated deployment draft
  -> user-supplied domain exceptions and assets
  -> client readiness projection
  -> server validation and provider preflight
  -> deployment-ready manifest
```

Generation must be deterministic and provenance-aware. Until a backend contract
can generate a field, the UI continues to collect that field explicitly; it
must not simulate generation or introduce client-side placeholder artifacts.

## UX Quality Rules

- Show one coherent task at a time; avoid page-length collections of unrelated
  inputs.
- Ask only for fields needed by the current dependency state.
- Preserve entered values when moving between tasks.
- Validate form inputs continuously and code inputs explicitly.
- Keep architecture selection prominent in its phase and compact elsewhere.
- Summaries use domain language and reveal technical evidence progressively.
- Empty, loading, error, blocked, invalidated, and read-only states are first-
  class and testable.
- Keyboard navigation, focus order, semantics, and narrow-window behavior are
  release criteria.

## Non-Goals

- A generic schema-driven form engine.
- Separate beginner and expert modes.
- Direct Flutter communication with Optimizer or Deployer.
- Persisting the currently opened UI subtask in the backend.
- Triggering deployment when configuration is finished.
- Hiding missing backend capabilities behind mock generation or fallback data.

## Thesis Rationale

The target separates user intent, optimization, deployment preparation, and
runtime operation. This makes the five-layer research architecture visible
through business tasks while keeping provider-specific implementation detail
behind typed contracts. The dependency model also makes invalidation and
conditional requirements explainable, which is essential for reproducible
configuration and defensible deployment decisions.
