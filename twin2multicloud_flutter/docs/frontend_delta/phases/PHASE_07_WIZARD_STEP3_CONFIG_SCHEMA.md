---
title: "Phase 7: Wizard Step 3 Config Schema"
description: "Plan the Wizard Step 3 deployer configuration cleanup around typed DB-backed configuration state."
tags: [flutter, frontend-delta, wizard, deployer, config-schema]
lastUpdated: "2026-06-13"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- FRONTEND_ARCHITECTURE.md Wizard Step 3 section
- docs/plans/project_storage_abstraction.md
- docs/plans/deployment-verification-architecture-v4.md
- twin2multicloud_flutter/lib/screens/wizard/step3_deployer.dart
- twin2multicloud_flutter/lib/models/wizard_config_requests.dart
EXTRACTED: 2026-06-13 | VERSION: 1.0
-->

# Phase 7: Wizard Step 3 Config Schema

## Summary

Review and clean up Wizard Step 3 so deployer configuration is represented as
typed, DB-backed state instead of a large monolithic file-editing surface with
implicit schema rules.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Step 3 responsibility and schema concept | Removing zip upload if still needed |
| Typed deployer configuration field inventory | Direct Deployer file writes |
| Section-level validation and persistence rules | Changing deployed cloud architecture |
| Component split requirements for the monolithic screen | Live cloud E2E |

## Prerequisites

- Phase 6 Step 2 cleanup has stable calculation output.
- Management API exposes typed deployer config read/write behavior.
- Project storage/runtime workspace boundaries are understood.

## Deliverables

- Step 3 field inventory mapped to DB/API fields.
- Required/optional field matrix by selected provider and layer.
- Validation ownership rules: Flutter UX vs Management API vs Deployer.
- Monolith reduction concept for splitting Step 3 into maintainable sections.
- Compatibility behavior for uploaded project zips.

## Implementation Subphases

| Subphase | Scope | Status |
|---|---|---|
| 7A | Move all artifact validation into the Wizard BLoC and make editors controlled | done |
| 7B | Move flat deployer hydration DTOs into the model layer and define the typed field/requiredness projection | planned |
| 7C | Split the monolithic screen into core config, user logic, assets, and architecture presentation components | planned |
| 7D | Isolate ZIP/GLB import orchestration, add replacement confirmation, and run the final Step 3 integration gate | planned |

Subphases are ordered. Visual restructuring must not begin before 7A removes
widget-owned API orchestration, and import hardening must not be mixed into the
editor/component split.

### 7A Evidence

- Typed artifact, endpoint, provider, and entity mapping is centralized in
  `DeployerArtifactType`.
- Wizard BLoC owns busy, feedback, stale-response rejection, and persisted
  validation state.
- Editors are controlled; no completed-event bypass remains.
- Analyzer, 360 tests, and Web/macOS release builds pass.

## Field Groups To Inventory

| Group | Examples | Required decision |
|---|---|---|
| Core deployer config | digital twin name, generated `config.json` values | Which values are generated from Step 2 vs user-editable? |
| Events/devices | `config_events.json`, `config_iot_devices.json` | Which schema validates each file and where is it persisted? |
| L1 assets | payload definitions and simulator inputs | Which provider/layer requires which files? |
| L2 functions | processors, feedback, event actions, state machines | Which functions are generated from device/event config? |
| L4/L5 assets | hierarchy, scene, user config, GLB upload state | Which fields are provider-specific and which are optional? |
| Zip import | uploaded template/project zip | Which extracted values overwrite existing draft state? |

## Architecture Guardrails

- Step 3 must be split into maintainable feature components during
  implementation planning; the existing monolith is not the target state.
- Flutter stores and reloads typed state through the Management API.
- Flutter may provide local UX validation but final validation/persistence
  belongs to Management API and Deployer contracts.
- File upload/import remains an explicit user action with confirmation before
  replacing current Step 3 state.
- The architect implementation plan must include desktop and compact Web ASCII
  layouts before build work starts.

## Acceptance Criteria

- Every Step 3 field has a clear owner, persistence field, validation state, and
  provider/layer condition.
- Flutter stores config through Management API, not local files or Deployer
  direct writes.
- Step 3 can be implemented in smaller feature components.
- Existing saved drafts and uploaded zip workflows remain recoverable.
- No new Step 3 work may add more responsibilities to a single monolithic
  screen file.
- Generated values from Step 2 are visually distinguishable from user-authored
  values.

## Verification

- Later implementation requires unit tests for config request building and
  hydration.
- Widget tests cover provider-dependent required fields and validation gating.
- Integration tests verify Management API persistence and reload behavior.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
