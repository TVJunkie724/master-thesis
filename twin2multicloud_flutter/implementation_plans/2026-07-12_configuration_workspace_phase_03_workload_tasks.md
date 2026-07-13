# Configuration Workspace Phase 3: Workload Tasks

## Objective

Split the optimizer's 26-field monolith into focused workload tasks while
preserving the `CalcParams` wire contract, presets, dependencies, validation,
and calculation semantics.

## Task Mapping

- Scenario and currency: scenario presets and output currency.
- Device traffic: devices, sending interval, message size, device types.
- Processing: event checking, workflows, feedback, actions, error-handling
  capability state.
- Retention: hot, cool, and archive durations with ordering validation.
- Twin capabilities: 3D requirements and dashboard/editor/viewer workload.

## Architecture

- `CalcForm` receives a typed section ID and remains the only editor of
  `CalcParams`.
- Every change emits a complete immutable `CalcParams`; BLoC remains draft SSOT.
- Hidden sections must remain part of aggregate validation so task navigation
  cannot accidentally mark an invalid full model valid.
- Re-entering a task hydrates from the latest BLoC state.
- Presets remain deterministic full-model updates, not partial UI defaults.
- Task headings and instructions are owned by the workspace, not cloud-layer
  terminology.

## Verification

- Round-trip every `CalcParams` field across all five task views.
- Apply each preset and verify values survive task navigation.
- Verify processing dependent-field reset behavior.
- Verify retention ordering blocks aggregate validity from every task.
- Verify no task renders fields assigned to a sibling task.
- Full analyzer and Flutter tests pass.

## Non-Goals

- Changing optimizer formulas or API payloads.
- Adding new workload fields.
- Persisting visited-task state.

