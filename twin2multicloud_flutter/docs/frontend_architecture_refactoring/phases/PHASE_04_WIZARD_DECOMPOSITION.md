---
title: "Phase 4: Wizard Decomposition"
description: "Split Wizard orchestration into smaller feature flows after repository and typed model boundaries exist."
tags: [flutter, wizard, bloc, refactoring]
lastUpdated: "2026-06-18"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
- twin2multicloud_flutter/docs/wizard/ROADMAP_WIZARD.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_05_WIZARD_STEP1_CREDENTIAL_BOUNDARY.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_06_WIZARD_STEP2_OPTIMIZER_CLEANUP.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_07_WIZARD_STEP3_CONFIG_SCHEMA.md
- twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart
- twin2multicloud_flutter/lib/screens/wizard/
EXTRACTED: 2026-06-18 | VERSION: 1.0
-->

# Phase 4: Wizard Decomposition

## Summary

Break the current Wizard orchestration into smaller responsibilities so that
Step 1 credential binding, Step 2 optimization inputs, and Step 3 deployer
configuration can evolve without one BLoC owning the whole platform workflow.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Split wizard state ownership by step and shared draft shell | Changing the three-step user journey without a separate UX concept |
| Move persistence/validation calls behind repositories | Pricing refresh review center implementation |
| Remove provider-specific parsing from widgets | Real cloud deployment from the wizard |
| Preserve create/edit draft behavior | Removing draft support |

## Prerequisites

- Phase 2 repository split is implemented.
- Phase 3 typed wizard and pricing/deployer models are available.

## Deliverables

- Wizard ownership map for shell, Step 1, Step 2, Step 3, and shared services.
- Event/state migration plan that preserves create/edit draft behavior.
- Validation and save-flow contract between each step and the repository layer.
- Backward-compatible fixture plan for existing wizard tests.
- Regression test matrix for initialization, navigation, validation, save,
  edit, and finish flows.

## Target Responsibilities

| Area | Owns |
|---|---|
| Wizard shell | Current step, navigation guard, draft identity, save/finish coordination. |
| Step 1 flow | Twin name, mode, deployment credential binding, credential validation state. |
| Step 2 flow | Calculation inputs, optimizer request/result, pricing readiness reference only. |
| Step 3 flow | Typed deployer config, file/package validation status, finish readiness. |
| Shared services | Draft load/save, request building, validation conversion, sanitized errors. |

## Acceptance Criteria

- Step-specific changes do not require editing a monolithic wizard event handler.
- Step 2 no longer owns global pricing maintenance or provider price refresh.
- Step 3 uses typed deployer config state rather than loosely shared maps.
- Create and edit flows remain behaviorally equivalent.
- Validation, loading, error, empty, and blocked states are explicit per step.
- Tests cover step initialization, draft save, validation failure, successful
  navigation, and finish gating.

## Verification

- BLoC tests prove each step can be exercised without constructing the entire
  old monolith behavior.
- Static review confirms service calls are behind repositories.
- UI smoke checks in later implementation verify create and edit still load the
  same data paths.

## Roadmap Anchor

Roadmap:
[Frontend Architecture Refactoring Roadmap](../ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md)
