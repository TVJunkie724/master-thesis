---
title: "Configuration Workspace Roadmap"
description: "Incremental migration from the legacy three-step wizard to the dependency-aware configuration workspace."
tags: [flutter, roadmap, configuration, wizard]
lastUpdated: "2026-07-12"
version: "1.0"
---

# Configuration Workspace Roadmap

The [target concept](CONCEPT_CONFIGURATION_WORKSPACE.md) is implemented in
small vertical phases. Every phase preserves persisted configuration contracts,
adds focused tests, receives two code reviews, and is committed independently.

| Phase | Status | Scope | Completion gate |
|---|---|---|---|
| 1 | Done | Typed journey projection and responsive workspace shell | 378 Flutter tests and analyzer pass; wide/compact navigation and state projection are covered. |
| 2 | Done | Define twin and access timing | Identity is focused; selected-path deployment access is purpose-filtered and gated after architecture selection; 382 tests pass. |
| 3 | Done | Describe workload | The 26 optimizer inputs are split into five focused tasks without changing `CalcParams`; aggregate hidden-field validation and 384 tests pass. |
| 4 | Planned | Choose architecture | Pricing health, calculation, comparison, invalidation, and selection form a coherent task flow. |
| 5 | Planned | Prepare deployment | Step 3 sections become requirement-driven tasks for access, contracts, logic, and assets. |
| 6 | Planned | Review and preflight | Summary, readiness findings, server validation, and Finish provide one authoritative completion path. |
| 7 | Planned | Quality and migration gate | Legacy navigation is removed, docs are aligned, and full static/test/build evidence passes. |

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

## Compatibility Strategy

During phases 1-6, new journey phases map to the legacy persistence level:

| Journey phase | Legacy level |
|---|---|
| Define twin | 0 |
| Describe workload | 1 |
| Choose architecture | 1 |
| Prepare deployment | 2 |
| Review configuration | 2 |

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
| Deployment preparation | Requirement-matrix tests across provider paths and optional 3D assets. |
| Completion | Tests proving client readiness cannot bypass server validation or preflight. |
| Accessibility | Semantic labels, keyboard traversal, focus recovery, and no overflow at supported desktop widths. |
