---
title: "Configuration Workspace Roadmap"
description: "Incremental migration from the legacy three-step wizard to the dependency-aware configuration workspace."
tags: [flutter, roadmap, configuration, wizard]
lastUpdated: "2026-08-27"
version: "2.4"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md
- twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_THESIS_RESEARCH_WORKFLOW.md
- twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_09_THESIS_RESEARCH_WORKFLOW_CONSOLIDATION.md
- docs/plans/phase_08_architecture_profiles_eventing/README.md
EXTRACTED: 2026-08-27 | VERSION: 2.3
-->

# Configuration Workspace Roadmap

The [target concept](CONCEPT_CONFIGURATION_WORKSPACE.md) is implemented in
small vertical phases. Every phase preserves persisted configuration contracts,
adds focused tests, receives two code reviews, and is committed independently.

## Concepts

- [Configuration Workspace](CONCEPT_CONFIGURATION_WORKSPACE.md) defines the
  shared task-oriented shell and dependency-aware journey.
- [Architecture Profile Experiment](concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md)
  defines the standalone Six-layer v1 thesis workflow.
- [Thesis Research Workflow Consolidation](concepts/CONCEPT_THESIS_RESEARCH_WORKFLOW.md)
  supersedes the selectable-profile product workflow with the fixed
  `six-layer-eventing@1` research path.

| Phase | Status | Scope | Completion gate |
|---|---|---|---|
| 1 | Done | Typed journey projection and responsive workspace shell | 378 Flutter tests and analyzer pass; wide/compact navigation and state projection are covered. |
| 2 | Done | Define twin and access timing | Identity is focused; selected-path deployment access is purpose-filtered and gated after architecture selection; 382 tests pass. |
| 3 | Done | Describe workload | Optimizer inputs are split into five focused tasks while retaining one canonical `CalcParams` contract; aggregate hidden-field validation remains covered. |
| 4 | Done | Choose architecture | Pricing health, compact calculation review, recommendation evidence, and invalidation form a focused task flow; 384 tests pass. |
| 5 | Done | Prepare deployment | Existing validated editors are composed into focused access, contract, logic, and asset tasks; all 384 tests pass. |
| 6 | Done | Review and preflight | Summary, actionable findings, centralized fail-closed readiness, and distributed server validation provide one completion path; 387 tests pass. |
| 7 | Done | Quality and migration gate | Legacy navigation and visible step terminology are removed; analyzer, 380 tests, web release build, and macOS release build pass. |
| 8 | Done | Immutable deployment selection review | Whole-run Management API selection, latest-run hydration, atomic invalidation/restore, fail-closed navigation, read-only primary/supporting resource summary, collapsed technical evidence, isolated demo parity, 706 tests, analyzer, architecture, Web/macOS, backend-contract, and docs gates pass. |
| 8.1 | Re-scoped; offline verification pending | [Architecture profile experiment](phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md) | [Implementation](implementation/architecture_profile_experiment.md) exposes standalone Six-layer v1 through one Management-owned workflow. Previous two-profile evidence is historical; the reduced profile requires fresh offline verification and later supervised live-capacity evidence. |
| 9 | Done | [Thesis research workflow consolidation](phases/PHASE_09_THESIS_RESEARCH_WORKFLOW_CONSOLIDATION.md) | Fixed Six-layer workflow, bounded Twin portability, deployment-administrator imports, persisted telemetry/cleanup evidence, analyzer, architecture gate, 812 tests, and Web/macOS release builds pass. |

## Cross-Phase Definition Of Done

- No persisted field or supported workflow is lost.
- UI navigation has one source of truth and does not duplicate readiness rules.
- Management API remains the only Flutter backend boundary.
- Existing drafts open on the first incomplete or attention task.
- Invalidated downstream configuration is visible and recoverable.
- Widget, projector, BLoC, repository/contract, and regression tests scale with
  the phase's risk.
- `flutter analyze`, the full Flutter test suite, and web/macOS builds pass at
  the final gate.
- No credentials, generated artifacts, or provider responses are logged or
  rendered outside their approved evidence surfaces.
- The visible optimizer result, selected run, and resolved deployment
  specification retain one identity; a newer unselected run cannot inherit an
  older deployment selection.
- Draft creation, workload entry, calculation, and architecture review remain
  credential-free; the selected architecture determines which provider scopes
  require deployment access.
- The PoC reuses externally provisioned, non-root administrator connections for
  all required provider scopes. Credential creation and permission reduction
  remain outside the implemented workflow.

## Compatibility Strategy

During phases 1-6, new journey phases map to the legacy persistence level:

| Journey phase | Legacy level |
|---|---|
| Define twin | 0 |
| Architecture | 0 |
| Workload | 1 |
| User Logic | 1 |
| Optimize and review | 1 |
| Deployment review | 2 |

The mapping is isolated in one adapter and removed only when the Management API
contract is deliberately migrated. Existing `currentStep` UI coupling must not
spread into new widgets.

## Verification Matrix

| Boundary | Required evidence |
|---|---|
| Journey projector | Table-driven tests for create/edit, complete, blocked, invalidated, optional, and read-only states. |
| Navigation | Widget tests for direct revisit, prerequisite blocking, recommended next task, and compact layout. |
| Workload | Round-trip tests proving every `CalcParams` field survives task navigation and presets. |
| Architecture | Tests for stale pricing, calculation errors, recalculation invalidation, and selected result restoration. |
| Deployment selection | Strict specification parsing/digest tests, latest-run list/detail consistency, bounded selection retry, navigation gates, and responsive read-only summary coverage. |
| Deployment preparation | Requirement-matrix tests across provider paths; scene/3D assets remain historical-profile compatibility only and are absent from Six-layer v1. |
| Guided cloud access | Strict provider-guide/session models; GCP existing-project/API-baseline ownership and organization-mode rejection; request-secret non-persistence; duplicate suppression; restart/recheck; exact disposal/revocation outcomes; shared Settings/workspace result. |
| Completion | Tests proving client readiness cannot bypass server validation or preflight. |
| Accessibility | Semantic labels, keyboard traversal, focus recovery, and no overflow at supported desktop widths. |
