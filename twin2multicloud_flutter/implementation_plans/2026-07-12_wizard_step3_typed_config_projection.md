---
title: "Implementation Plan: Wizard Step 3 Typed Config Projection"
description: "Centralize Step 3 hydration, persistence data, requiredness, and readiness in typed domain models."
tags: [flutter, wizard, deployer, config, domain-model]
lastUpdated: "2026-07-12"
version: "1.0"
---

# Implementation Plan: Wizard Step 3 Typed Config Projection

## 0. Git Branch

- **Branch:** `codex/purpose-aware-cloud-access`
- **Base:** `master`
- **Issue:** GitHub #38.
- **Subphase:** 7B; must be committed independently before 7C.

## 1. Summary

Step 3 configuration is currently duplicated across `WizardState`, a DTO
declared inside `WizardInitService`, request-building helpers, and two separate
validity implementations. This subphase creates a typed domain SSOT for:

- API hydration and update payload construction;
- provider/workload-dependent artifact requirements;
- section and overall readiness;
- generated versus user-authored ownership metadata.

It preserves the existing editor UI and API wire format. It also fixes the
existing gate that permits a 3D deployment without the required managed GLB.

## 2. Visual Layout (ASCII)

No visual restructuring occurs in 7B. The typed projection prepares 7C:

```text
Step 3
|-- Configuration Files          <- readiness.configuration
`-- User Functions & Assets      <- readiness.artifacts
```

Wide and compact layouts remain unchanged.

## 3. Widget Tree

```text
Step3Deployer [UNCHANGED composition]
`-- WizardState.deployerReadiness [NEW typed projection]

WizardBloc [MODIFY hydration import]
`-- DeployerConfigData [NEW model-layer location]

WizardInitService [MODIFY]
`-- DeployerConfigData [REUSE model]

DeployerHelper [MODIFY]
`-- WizardState.deployerConfigData.toUpdateRequest()
```

## 4. Component Specifications

### `DeployerConfigData`

- **Path:** `lib/models/deployer_config.dart`.
- Immutable `Equatable` model containing every existing Step 3 field.
- `fromJson` tolerates absent/null legacy map fields; incompatible non-map
  values raise `FormatException` instead of being silently cast or discarded.
- `toUpdateRequest()` is the only Flutter mapping to
  `DeployerConfigUpdateRequest`.
- The class is removed from `wizard_init_service.dart`.

### `DeployerConfigRequirements`

Immutable value object derived from calculation/provider context:

| Requirement | Rule |
|---|---|
| Core config, events, IoT devices | always required |
| Payload definitions | always required |
| Processor | one per validated device ID |
| Event feedback | `returnFeedbackToDevice=true` |
| Event action | each parsed action when `useEventChecking=true` |
| State machine | `triggerNotificationWorkflow=true` |
| Hierarchy | L4 is AWS or Azure |
| Scene config and GLB | `needs3DModel=true` and L4 is AWS or Azure |
| User config | L5 is AWS or Azure |

Provider matching is case-insensitive. GCP/other L4/L5 does not inherit
AWS/Azure-only artifacts.

### `DeployerArtifactReadiness` / `DeployerSectionReadiness`

- Artifact fields: stable ID, label, source (`generated` or `userAuthored`),
  required, hasContent, validated, optional dependency.
- `ready` means not required, or required with content and validation.
- GLB uses `sceneGlbUploaded` as both content and validation evidence.
- Section fields: ID, label, artifacts, derived `ready`, missing IDs, invalid
  IDs.
- Sections are `configuration`, `payloads`, `userLogic`, and
  `digitalTwinAssets`.

### `DeployerConfigReadiness`

- Combines data and requirements into the four sections.
- `configurationReady` replaces `isSection2Valid`.
- `deploymentArtifactsReady` replaces `isSection3Valid`.
- `ready` requires both.
- Projection is pure and performs no parsing beyond already typed inputs.

### `WizardState`

- Add pure getters `deployerConfigData`, `deployerRequirements`, and
  `deployerReadiness`.
- Existing public `isSection2Valid` and `isSection3Valid` remain as temporary
  compatibility aliases delegating to the projection; 7C removes section
  numbering from presentation.
- Device/action parsing stays in state for this slice and is moved only if 7C
  proves a separate parser boundary is needed.

### `DeployerHelper`

- Request building delegates to `state.deployerConfigData.toUpdateRequest()`.
- Remove unused duplicate hydration, validity, and data-presence methods.
- Keep only the compatibility payload/request facade used by persistence.

## 5. Responsive Behavior

No breakpoint or layout changes. Typed readiness must be independent of
viewport width.

## 6. State Flow

```text
Management API flat deployer response
  -> DeployerConfigData.fromJson
  -> WizardInitService hydrates WizardState
  -> WizardState.deployerConfigData
  + provider/calc context
  -> DeployerConfigRequirements
  -> DeployerConfigReadiness
  -> finish/save/section gates

WizardState.deployerConfigData
  -> toUpdateRequest
  -> Management API update
```

No HTTP call is added and Flutter continues to use Management API only.

## 7. Design Tokens

No design tokens are added or changed.

## 8. Interactions And States

- Existing editing, validation, save, ZIP, and GLB interactions remain.
- Readiness changes synchronously after each controlled BLoC state update.
- Missing required artifacts fail closed.
- Optional artifacts never block finish.
- A required 3D GLB now blocks finish until uploaded.

## 9. Accessibility

No visual controls change. 7C consumes source/requiredness labels in accessible
section summaries.

## 10. Integration Points

Wire compatibility must remain exact for:

- `GET /twins/{id}/deployer/config`
- `PUT /twins/{id}/deployer/config`

All snake_case fields in `DeployerConfigUpdateRequest` remain unchanged. No
direct Optimizer/Deployer service calls are introduced.

## 11. Test Plan

### Domain tests

- Full/empty/partial JSON hydration and wrong map shapes.
- Exact update request round trip for all fields.
- Requiredness for AWS, Azure, GCP, and mixed-provider paths.
- Optional event feedback/actions/state machine permutations.
- 3D on/off with AWS/Azure/GCP L4, including missing GLB.
- Dynamic processor/action completeness and invalid content.
- Generated/user-authored source metadata.

### Regression tests

- Wizard init hydration remains exact.
- Save request payload remains byte-for-field compatible.
- ZIP-derived state uses the same readiness projection.
- Existing Step 2/Step 3 finish gating remains green except the intentional
  missing-GLB hardening.

### Gates

- `flutter analyze`
- `flutter test -r compact`
- Web and macOS release builds with `config/dev.json`
- No cloud deployment E2E.

## 12. Definition Of Done

- [ ] Deployer config DTO lives in the model layer.
- [ ] Hydration and update mapping have one typed implementation each.
- [ ] Requiredness is centralized and provider/workload aware.
- [ ] Section/overall readiness has one pure projection.
- [ ] Missing required GLB blocks 3D configuration completion.
- [ ] Duplicate dead helper logic is removed.
- [ ] Full tests, analyzer, Web, and macOS builds pass.
- [ ] Phase 7 roadmap and GitHub #38 are updated.
