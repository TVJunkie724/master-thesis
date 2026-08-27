---
title: "Thesis Research Workflow Implementation"
description: "Durable Flutter boundary and verified evidence for the standalone Six-layer research workflow."
tags: [flutter, implementation, thesis, six-layer, evidence]
lastUpdated: "2026-08-27"
version: "1.0"
---

# Thesis Research Workflow Implementation

**Status:** Implemented and audited.

## Final Boundary

Flutter is the Management-API client for one fixed
`six-layer-eventing@1` research workflow:

| Surface | Responsibility |
|---|---|
| Dashboard | Manage multiple Twin experiments and bounded `.twin.zip` portability. |
| Configuration Workspace | Execute Scenario, Optimize, Prepare, and Review in that exact order. |
| Settings | Store, import, validate, select, and delete named deployment-administrator connections for AWS, Azure, and GCP. |
| Twin Overview | Run durable deployment operations, expose L4/L5 handoff, and present persisted telemetry and cleanup evidence. |

The router contains only login, Dashboard, Settings, create/edit Workspace, and
Twin Overview routes. Flutter does not call an Optimizer, Deployer, Terraform,
or provider API directly.

## Typed Contracts

- `TwinDuplicateRequest`, `TwinImportRequest`, and `PortableTwinDownload`
  enforce bounded names, safe `.twin.zip` filenames, exact ZIP media type, and
  transient defensive byte copies.
- `CloudConnectionImportRequest` accepts only AWS CSV or Azure/GCP JSON input,
  bounds file size, keeps bytes outside equality and rendered state, and sends
  them to the Management API for allowlisted parsing.
- `WizardBloc` loads the exact canonical architecture detail and, for a saved
  Twin, its pinned selection. ID, version, and digest must match before the
  workflow becomes ready.
- Optimizer results retain immutable catalog references, sources, timestamps,
  assumptions, exclusions, allocation, and calculation trace.
- `TelemetryVerificationRecord` and history types enforce the three-phase
  provider/kind/correlation/count contract and recover authoritative persisted
  evidence by verification ID after a stream interruption.
- `CleanupEvidence` enforces schema, Terraform and provider inventories,
  provider uniqueness, retained shared prerequisites, residual failures, and
  terminal status consistency.

## State Ownership

| Owner | State and commands |
|---|---|
| `TwinCommandController` | Serialized Twin duplicate/import/export/delete and inventory invalidation. |
| `CloudAccessBloc` | Deployment-connection list and create/import/validate/delete commands. |
| `WizardBloc` | Canonical contract, scenario, calculation, selected allocation, provider binding, validation, and finish gates. |
| `DeploymentVerificationBloc` | Persisted telemetry history, one active verification, SSE logs, and terminal recovery without a second automatic message. |
| `TwinOverviewBloc` | Deploy/Destroy idempotency, SSE catch-up/replay, access/readiness, and persisted cleanup evidence. |

Widgets render typed state and emit events or callbacks. Uploaded credentials,
portable archives, and downloaded bytes are never placed in durable UI state.

## Verified Evidence

| Gate | Evidence |
|---|---|
| Focused tests | 43 passed across route, inventory, portability, Workspace, deployment connections, telemetry, cleanup, compact layouts, keyboard, and focus behavior. |
| Full tests | 812 passed. |
| Analyzer | Zero issues. |
| Architecture checker | Passed; presentation remains behind the Management API. |
| Web | Release build succeeded with `config/dev.example.json`. |
| Desktop | macOS release build succeeded with `config/dev.example.json`. |
| Docker integration | Docker daemon unavailable; no mocked success was substituted. |
| Cloud safety | No live validation, preparation, Deploy, Destroy, telemetry command, or provider mutation was executed. |

## AUDIT PASSED

**Feature:** Thesis Research Workflow Consolidation  
**Date:** 2026-08-27  
**Plan:** `implementation_plans/2026-08-27_thesis_research_workflow_consolidation.md`  
**Session:** `AI-0827-THES`  
**Branch:** `codex/six-layer-clean`

| Audit phase | Result |
|---|---|
| Plan integrity | Reviewed twelve-section implementation plan and recorded approval gate. |
| Structure | Required models, widgets, state owners, adapters, and tests exist in their planned layers; orphan presentation nodes are absent. |
| Widget tree | Private inventory header/actions and dedicated connection, telemetry, and cleanup widgets match the plan. |
| Visual and layout | New surfaces use theme and spacing tokens; Workspace dimensions are centralized. |
| Responsive | Wide and compact projections pass at 640 px with 150 and 200 percent text scaling. |
| State | Riverpod/BLoC ownership, serialization, loading, empty, blocked, error, cancellation, and recovery paths are hard-asserted. |
| Interactions | Enter submission, Escape focus restoration, confirmations, collapsed evidence, and duplicate-command suppression pass. |
| Accessibility | Named tooltips, text status, semantics, focus recovery, and non-color-only evidence pass. |
| Integration | Typed Management API routes match the plan; no direct backend/provider boundary exists. |
| Code quality | Analyzer, 812 tests, architecture checker, Web release, macOS release, and diff hygiene pass. |
| Plan cross-check | Definition of Done and removal regressions are covered; commits carry `AI-0827-THES`. |

**APPROVED FOR HANDOFF**
