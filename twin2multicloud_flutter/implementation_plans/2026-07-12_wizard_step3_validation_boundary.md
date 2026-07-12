---
title: "Implementation Plan: Wizard Step 3 Validation Boundary"
description: "Move deployer artifact validation out of Step 3 widgets and into the Wizard BLoC as the first Step 3 cleanup subphase."
tags: [flutter, wizard, deployer, validation, clean-architecture]
lastUpdated: "2026-07-12"
version: "1.0"
---

# Implementation Plan: Wizard Step 3 Validation Boundary

## 0. Git Branch

- **Branch:** `codex/purpose-aware-cloud-access`
- **Base:** `master`
- **Merge strategy:** merge commit; no rebase of shared history.
- **Issue:** GitHub #38 remains the umbrella issue.
- This is Step 3 subphase 7A. It must be committed independently before 7B.

## 1. Summary

Wizard Step 3 currently calls `WizardDeployerValidationService` from the
screen and lets `FileEditorBlock` and `FunctionPackageBlock` maintain a second,
local validation state. This makes validation ownership ambiguous, complicates
error handling, and prevents the 1,045-line screen from being split safely.

This mandatory subphase establishes one event-driven validation boundary:

```text
Editor -> WizardArtifactValidationRequested -> WizardBloc
       -> WizardDeployerValidationService -> Management API
       -> controlled WizardState feedback -> Editor
```

It preserves every supported config, L2, L4, and L5 validation operation. It
does not change provider rules, backend schemas, file formats, uploads, save
semantics, or the visible Step 3 information architecture.

## 2. Visual Layout (ASCII)

The screen layout intentionally remains unchanged in 7A. Only validation
feedback ownership changes.

Wide desktop/Web:

```text
+------------------------------------------------------------------+
| Step 3 configuration                                             |
|                                                                  |
| [Artifact editor................................] [Upload]       |
| [...............................................] [Example]      |
| [...............................................] [Validate]     |
|                                        Validating... / Result    |
+------------------------------------------------------------------+
```

Compact Web:

```text
+----------------------------------------+
| Step 3 configuration                   |
| [Artifact editor.....................] |
| [....................................] |
| [Upload] [Example] [Validate]          |
| Validation result                     |
+----------------------------------------+
```

No new panel, card, dialog, animation, or navigation element is permitted.

## 3. Widget Tree

```text
Step3Deployer [MODIFY]
`-- artifact editor callbacks
    `-- WizardBloc.add(WizardArtifactValidationRequested)

FileEditorBlock [MODIFY]
|-- CodeField [REUSE]
|-- Upload / Example commands [REUSE]
|-- Validate command [MODIFY: event callback only]
`-- ArtifactValidationFeedbackView [NEW shared widget]

FunctionPackageBlock [MODIFY]
|-- FileEditorBlock [REUSE]
|-- requirements.txt editor [REUSE]
|-- Validate command [MODIFY: event callback only]
`-- ArtifactValidationFeedbackView [REUSE]

WizardBloc [MODIFY]
`-- WizardDeployerValidationService [REUSE]
```

The feedback view is shared only inside the file-input package so both editors
render the same controlled state without duplicating behavior.

## 4. Component Specifications

### `DeployerArtifactType` and `DeployerArtifactValidationRequest`

- **Path:** `lib/models/deployer_artifact_validation.dart`
- `DeployerArtifactType` is a closed enum for `config`, `events`,
  `iotDevices`, `payloads`, `processor`, `eventFeedback`, `eventAction`,
  `stateMachine`, `hierarchy`, `sceneConfig`, and `userConfig`.
- The enum owns each artifact's Management API validation type and boundary.
  Raw call-site strings are forbidden.
- The request is an immutable `Equatable` value object.
- Fields:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `type` | `DeployerArtifactType` | yes | Closed artifact/endpoint mapping |
| `content` | `String` | yes | Exact editor/upload content to validate |
| `provider` | `String?` | conditional | Layer provider captured when the event is created |
| `entityId` | `String?` | conditional | Processor/action/feedback identity |

`artifactId`, `boundary`, and `validationType` are derived. Processor and event
action requests require a non-empty `entityId`; provider-scoped requests
require a provider. Invalid combinations fail closed before an API call. The
request must not contain credentials, file paths, or raw API clients.

The request exposes a pure `validationError` getter. The BLoC converts a
non-null value into controlled invalid feedback and does not call the API;
constructor assertions are not an accepted runtime validation mechanism.

Mandatory mapping:

| Type | `artifactId` | Boundary / API type | Provider | Existing validity target |
|---|---|---|---|---|
| `config` | `config:core` | config / `config` | none | `configJsonValidated` |
| `events` | `config:events` | config / `events` | none | `configEventsValidated` |
| `iotDevices` | `config:iot-devices` | config / `iot` | none | `configIotDevicesValidated` |
| `payloads` | `payloads` | config / `payloads` | none | `payloadsValidated` |
| `processor` | `processor:<entityId>` | layer2 / `function-code` | L2 | `processorValidated[entityId]` |
| `eventFeedback` | `event-feedback` | layer2 / `function-code` | L2 | `eventFeedbackValidated` |
| `eventAction` | `event-action:<entityId>` | layer2 / `function-code` | L2 | `eventActionValidated[entityId]` |
| `stateMachine` | `state-machine` | layer2 / `state-machine` | L2 | `stateMachineValidated` |
| `hierarchy` | `hierarchy` | layer4Or5 / `hierarchy` | L4 | `hierarchyValidated` |
| `sceneConfig` | `scene-config` | layer4Or5 / `scene-config` | L4 | `sceneConfigValidated` |
| `userConfig` | `user-config` | layer4Or5 / `user-config` | L5 | `userConfigValidated` |

### `DeployerArtifactValidationFeedback`

- **Path:** same model file.
- Immutable `Equatable` value object with `valid` and normalized `message`.
- It is diagnostic UI state only; persisted validation booleans remain in the
  existing typed deployer config state.

### `WizardState`

- Add `Set<String> validatingArtifactIds`.
- Add `Map<String, DeployerArtifactValidationFeedback>
  artifactValidationFeedback`.
- Add pure getters `isArtifactValidating(id)` and
  `artifactFeedback(id)`.
- Both collections must participate in `copyWith` and `props`.
- Content-change handlers must clear feedback for their own artifact and keep
  existing persisted validation invalidation behavior.

### `WizardArtifactValidationRequested` and `WizardBloc`

`WizardArtifactValidationRequested` has exactly one required
`DeployerArtifactValidationRequest request` payload and includes it in
`Equatable.props`.

- Add one `WizardArtifactValidationRequested` handler.
- Ignore a duplicate request while the same `artifactId` is in flight.
- Set busy state before invoking the service.
- Select exactly one existing service method by the request's derived
  `boundary`.
- Apply a successful/failed validation result to the existing persisted
  boolean for that artifact in the same handler.
- Always store normalized feedback and clear busy state.
- A service exception must be normalized and represented as invalid feedback;
  it must not escape the event handler.
- Different artifact IDs may validate independently.

### `ArtifactValidationFeedbackView`

- **Path:** `lib/widgets/file_inputs/artifact_validation_feedback_view.dart`.
- Public, stateless, and presentation-only.
- Required `feedback`; optional `isValidating=false`.
- Renders bounded progress or icon-plus-message and owns no state or service.

### `FileEditorBlock`

Replace the async service-shaped callback with controlled parameters:

| Parameter | Type | Required | Default |
|---|---|---|---|
| `onValidate` | `ValueChanged<String>?` | no | `null` |
| `isValidating` | `bool` | no | `false` |
| `validationFeedback` | `DeployerArtifactValidationFeedback?` | no | `null` |
| `validationLabel` | `String?` | no | `filename` |

- The widget may own editor height, controller, file picker, and example-dialog
  state only.
- It must not own canonical validation state or catch API errors.
- Manual validation emits current controller content.
- Auto-validation after upload emits the uploaded content directly, preventing
  a stale-BLoC-state race.
- Feedback is rendered directly from constructor values; no
  `didUpdateWidget` synchronization or mirrored local validity is permitted.

### `FunctionPackageBlock`

- Replace `Future<Map<String, dynamic>> Function(String)? onValidate` with
  `ValueChanged<String>? onValidate`; add `isValidating=false` and optional
  `validationFeedback`.
- Use the same controlled callback/busy/feedback contract and shared feedback
  view.
- Requirements editing remains independent and is not validated in this
  subphase.
- The nested `FileEditorBlock` must not render duplicate validation feedback.

### `Step3Deployer`

- Delete `_validationService` and every direct validation helper call from the
  screen. `ProviderScope` remains temporarily only for GLB upload/delete and is
  removed in subphase 7D; it must not be used for validation.
- Build typed validation requests and dispatch events only.
- Preserve every existing artifact ID/provider mapping:
  config, events, IoT devices, payloads, processors, event feedback, event
  actions, state machine, hierarchy, scene config, and user config.

## 5. Responsive Behavior

| Width | Required behavior |
|---|---|
| `>= 900` | Existing Step 3 layout remains; controlled feedback must not resize the architecture column. |
| `< 900` | Existing stacked layout remains; validation text wraps to two lines and actions wrap without overflow. |

No new breakpoint is introduced. Long provider/API messages must ellipsize or
wrap within the editor boundary and never resize action buttons.

## 6. State Flow (BLoC)

```text
Validate press or uploaded content
  -> WizardArtifactValidationRequested(request)
  -> reject duplicate artifact request
  -> state.validatingArtifactIds += artifactId
  -> WizardDeployerValidationService
  -> Management API /twins/{id}/deployer/validate/{type}
  -> ValidationResult
  -> existing artifact validation boolean updated
  -> artifactValidationFeedback[artifactId] updated
  -> state.validatingArtifactIds -= artifactId
  -> controlled editor rebuild
```

The service remains the sole normalizer for missing twin/provider, empty
content, API rejection, and transport errors. Flutter never calls Deployer
port 5004 directly.

GLB upload/delete is explicitly unchanged in 7A and remains the only direct
service interaction in `Step3Deployer` until subphase 7D.

## 7. Design Tokens

- Reuse `AppSpacing`, `AppColors`, and `ThemeData` only.
- Replace touched hardcoded validation colors/spacings in
  `FileEditorBlock`/`FunctionPackageBlock` with existing tokens.
- Adding a token is allowed only when no semantically equivalent token exists.
- Material `Icons` remain the only icon source.

## 8. Interactions And States

- Validate is disabled for empty content or while the same artifact is busy.
- Busy state uses the existing bounded progress indicator.
- Success and invalid results show icon plus text; color is supplementary.
- Content change immediately clears persisted validity and stale feedback.
- Upload cancellation changes nothing.
- File read failure remains local file-I/O feedback and never enters BLoC.
- No automatic retry. The user may validate again explicitly.
- No animation beyond existing Material state transitions.

## 9. Accessibility

- Existing tab order remains editor, upload, example, validate.
- Validate controls expose `Validate <artifact label>` tooltips/semantics.
- Busy and result states are readable as text, not color only.
- Feedback supports text scaling and keyboard operation without overflow.
- Focus is not moved after validation completes.

## 10. Integration Points

All calls remain through Management API port 5005:

| Method | Path | Body |
|---|---|---|
| POST | `/twins/{id}/deployer/validate/{configType}` | `{content}` |
| POST | `/twins/{id}/deployer/validate/{l2Type}` | `{content, provider}` |
| POST | `/twins/{id}/deployer/validate/{l4OrL5Type}` | `{content, provider}` |

No route changes, SSE channels, storage writes, or cloud calls are introduced.

## 11. Test Plan

### Model/state unit tests

1. Requests and feedback have stable equality.
2. Busy and feedback lookups return controlled values.
3. Content changes clear only the matching artifact feedback.
4. Missing required entity/provider combinations fail closed and never invoke
   the service.

### BLoC tests

Happy paths:

1. Config validation updates busy, feedback, and config validity.
2. L2 processor validation preserves entity mapping.
3. L4/L5 validation captures the provider from the event.

Unhappy paths:

1. Missing twin/provider returns controlled invalid feedback.
2. API failure is normalized and busy state is cleared.
3. Invalid result resets persisted validity.

Edge cases:

1. Duplicate same-artifact request is ignored.
2. Different artifact requests remain independent.
3. Uploaded content is the exact validated content.
4. Editing after success clears only that feedback.
5. Empty content never calls Management API.
6. GCP provider mapping continues to `google` in the service boundary.

### Widget tests

1. Controlled success/invalid/busy feedback renders.
2. Validate emits the exact current content.
3. Empty content disables validate.
4. Compact width has no overflow.
5. Function package renders feedback only once.

### Gates

- `flutter analyze`
- `flutter test -r compact`
- `flutter build web --dart-define-from-file=config/dev.json`
- `flutter build macos --dart-define-from-file=config/dev.json`
- No live Management API integration test is required in 7A because the
  endpoint contracts and already-tested validation service are unchanged.
  BLoC tests mock only `ApiService`; final live persistence/reload coverage is
  mandatory in 7D.
- No live provider fetch or deployment E2E.

## 12. Definition Of Done

- [ ] Every Step 3 validation is represented by a typed request.
- [ ] Wizard BLoC is the single owner of validation progress and feedback.
- [ ] Step 3 widgets perform no validation service or validation API calls.
- [ ] File editors own presentation/file-picker state only.
- [ ] Existing config/L2/L4/L5 validation mappings remain functional.
- [ ] Duplicate and error paths clear busy state deterministically.
- [ ] Touched UI uses theme/spacing tokens and remains overflow-safe.
- [ ] Unit, BLoC, widget, regression, analyzer, Web, and macOS gates pass.
- [ ] Phase 7 roadmap records subphase 7A completion evidence.
- [ ] GitHub #38 is updated; it remains open for 7B-7D.
