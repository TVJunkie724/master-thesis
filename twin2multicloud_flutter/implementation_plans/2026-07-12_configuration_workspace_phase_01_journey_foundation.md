# Configuration Workspace Phase 1: Journey Foundation

## Objective

Introduce the typed, dependency-aware journey projection and responsive
workspace shell while preserving every existing form, calculation, persistence,
and finish workflow. This phase changes navigation semantics, not data
contracts.

## Preconditions

- The typed `WizardState`, pricing readiness, and deployer readiness projections
  are the current domain inputs.
- Flutter communicates only with the Management API.
- Existing drafts and `highest_step_reached` values must remain readable.
- The old Step 1/2/3 content widgets remain available during this phase.

## Files

### Add

- `lib/features/configuration_workspace/domain/configuration_journey.dart`
- `lib/features/configuration_workspace/presentation/configuration_task_sidebar.dart`
- `lib/features/configuration_workspace/presentation/configuration_task_selector.dart`
- `lib/features/configuration_workspace/presentation/configuration_workspace_shell.dart`
- `test/features/configuration_workspace/configuration_journey_test.dart`
- `test/features/configuration_workspace/configuration_workspace_shell_test.dart`

### Modify

- `lib/screens/wizard/wizard_screen.dart`
- `test/screens/wizard_pricing_gate_test.dart` only if its navigation harness
  requires adaptation.

## Domain Contract

Define stable enums:

- `ConfigurationPhaseId`: `defineTwin`, `describeWorkload`,
  `chooseArchitecture`, `prepareDeployment`, `reviewConfiguration`.
- `ConfigurationTaskId`: all task IDs from the approved concept.
- `ConfigurationTaskStatus`: `complete`, `current`, `attention`, `available`,
  `blocked`, `notRequired`.

`ConfigurationJourney.fromWizardState(state, currentTask)` returns immutable
phase/task view models, a canonical current task, a recommended next task, and
navigation permissions. It performs no network calls and mutates no state.

### Readiness Rules In Phase 1

- Define twin is complete when the trimmed name is non-empty.
- Workload tasks are collectively complete when `calcParams` exists and the
  calculation form is valid. Detailed task-level completeness is added in
  Phase 3; all workload subtasks share this aggregate status temporarily.
- Pricing readiness is complete when the supported pricing contract can
  calculate; stale/error state produces attention.
- Calculate alternatives is complete when `calcResult` exists and not
  invalidated.
- Compare and select is complete when `calcResult` exists.
- Prepare deployment is blocked until an architecture result exists.
- Cloud access is complete when every provider required by the selected path
  has a bound/valid connection.
- Deployment artifact task status is projected from `deployerReadiness`.
- Review is available only after architecture selection; Finish remains gated
  by existing authoritative readiness and BLoC behavior.

Any phase-1 aggregate that cannot distinguish sibling tasks must be visibly
treated as transitional in code structure, not by TODO comments in the UI.

## Compatibility Adapter

Map each task to the legacy content owner:

- `defineTwin` -> Step 1
- workload and architecture tasks -> Step 2
- deployment and review tasks -> Step 3

When a task is selected, issue `WizardGoToStep` only if the mapped legacy step
differs. Keep the task selection in the screen's presentation state. On initial
load, choose the journey's recommended task derived from persisted data.

Do not modify request models, database fields, or API endpoints.

## Responsive Shell

- At widths >= 960 logical pixels: fixed-width task sidebar plus expanded
  content.
- Below 960: a compact task selector above content.
- Show only the active phase's subtasks in expanded form.
- Every status has icon, semantic label, selected/focus state, and blocked
  reason tooltip or supporting text.
- The shell must not nest decorative cards or constrain existing content into a
  narrow panel.
- Header and footer remain stable; the legacy horizontal step indicator is
  removed.

## Navigation Behavior

- Selecting complete/current/attention/available tasks navigates immediately.
- Blocked tasks are non-interactive and expose their reason.
- Not-required tasks are non-interactive.
- Back selects the previous navigable task, or exits on the first task.
- Continue selects the next recommended task; calculation and Finish retain
  their existing explicit command behavior.
- Save remains available independently of task navigation and respects
  read-only twin state.

## Error And State Handling

- Preserve BLoC alert banners and save/exit confirmations.
- A missing/unknown current task falls back deterministically to the recommended
  task.
- A state change that blocks the current task relocates to the earliest
  attention/available task after the current frame; it must not trigger during
  build.
- Read-only twins allow inspection and navigation but disable mutations.

## Tests

### Unit

- Table-driven projection for empty create, named draft, workload configured,
  stale pricing, calculated result, missing selected-provider access, complete
  deployer config, invalidated config, and read-only state.
- Stable phase/task ordering and unique IDs.
- Compatibility mapping for every task.
- Recommended-task selection and fallback.

### Widget

- Wide sidebar and compact selector breakpoints.
- Only active phase exposes subtasks.
- Blocked/not-required tasks cannot navigate and expose semantics.
- Available/completed tasks navigate and preserve child content state.
- No legacy `Step 1 / 3` indicator remains.
- Existing pricing calculation gate remains effective.

### Regression

- Existing wizard BLoC, pricing, deployer artifact, and request-builder tests.
- `flutter analyze`.
- Full `flutter test` at phase gate.

## Review Gates

1. Architecture review: no duplicated persistence model, no backend current-task
   field, no readiness decisions hidden in widgets.
2. UX/code review: keyboard/semantics, compact layout, invalidation behavior,
   and legacy workflow preservation.

## Definition Of Done

- The UI presents the approved five-phase journey.
- The old horizontal three-step indicator is absent.
- Every task has deterministic state and dependency behavior.
- Existing configuration content and commands remain functional.
- New and existing tests pass with no analyzer findings.
- Roadmap phase 1 is marked complete with verification evidence.

