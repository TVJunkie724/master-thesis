---
title: "Flutter Quality Audit Remediation"
date: "2026-07-15"
branch: "codex/cross-project-quality-audit"
base: "master"
issues: [38, 39]
status: "in_progress"
---

# Flutter Quality Audit Remediation

## Goal

Close the remaining Flutter architecture and quality findings before Phase 9.
The implementation must preserve the current configuration workspace, offline
demo, pricing review, and deployment workflows while restoring clear ownership
between application composition, feature state, presentation, and external
side effects.

## Approved Architecture

Riverpod remains the application-composition mechanism for authentication,
theme, runtime adapters, and lightweight dashboard queries. Feature workflows
with multi-step state transitions use BLoC. This is the approved hybrid from
the completed Flutter refactor plans; this audit does not migrate state
management frameworks.

```
Composition root (Riverpod)
        |
        v
Feature BLoC
        |
        v
Smart screen coordinator
        |
        v
Focused presentation widgets
        |
        v
Management API port / file-system adapter
```

Flutter continues to call only the Management API. No real-cloud E2E is part
of this audit.

## Audit Findings

1. `Step2Optimizer` performs a redundant Management API read and owns loading
   state even though `WizardBloc` already hydrates optimizer parameters.
2. `Step3Deployer` reads the API provider directly for GLB upload and deletion.
3. Wizard shell, deployment-task presentation, and Wizard event orchestration
   have grown back into broad files after later workspace features.
4. Production error paths emit downstream messages through `debugPrint`.
5. Credential setup links still target legacy service-local HTML instead of
   the canonical MkDocs site.
6. Production TODO comments and the stale infrastructure TODO document compete
   with GitHub Issues as the work-tracking source of truth.
7. Dashboard twin deletion bypasses its feature command boundary and performs
   API I/O directly from presentation code.

## Subphase 1 - Boundary And Hygiene Corrections

### Scope

- Remove the redundant optimizer read from `Step2Optimizer`; edit-mode data is
  hydrated only by `WizardBloc` and `WizardInitService`.
- Route GLB upload and delete commands through typed Wizard events and BLoC
  handlers. File selection remains a presentation/platform side effect; bytes
  are transient and are never added to `WizardState` or equality properties.
- Add explicit busy/error/success state for GLB commands and reject commands
  before API I/O when no saved twin exists.
- Replace raw debug output with fixed, secret-free structured event identifiers.
- Point credential help to a runtime-configurable canonical MkDocs base URL.
- Remove stale TODO comments and the superseded Flutter infrastructure tracker;
  retain future work in Issues #36 and #39.

### Exact Contracts

- `WizardSceneGlbUploadRequested` carries `Uint8List bytes` and a sanitized
  basename. It never participates in state equality and is released after the
  handler returns.
- `WizardSceneGlbDeleteRequested` carries no payload. Both GLB commands require
  `state.twinId`; missing identity fails locally without calling the API.
- `WizardState` adds one immutable `SceneGlbCommandState` with `idle`,
  `uploading`, and `deleting` phases plus a nullable public message. A new
  command clears the prior message. Completion never retains bytes.
- `AppLogger` accepts a closed `AppLogEvent` enum only. Callers cannot attach
  exception text, response bodies, credentials, filenames, or free-form maps.
- `DocsConfig.baseUrl` reads `DOCS_BASE_URL`, defaults to
  `http://localhost:5010`, removes trailing slashes, and exposes canonical
  `/cloud-setup/` and `/cloud-setup/provider-links/` targets. Provider names
  are encoded as fragments only after closed enum/string normalization.

### Tests

- Widget test proving Step 2 performs no direct API request.
- BLoC tests for GLB upload/delete success, missing twin, transport failure,
  command serialization, and transient-byte ownership.
- Logger tests proving arbitrary exception/downstream text is not emitted.
- Docs configuration tests for normalized base URLs and provider anchors.

## Subphase 2 - Deployment Task Presentation Split

### Scope

- Reduce `step3_deployer.dart` to the smart coordinator and platform file
  picker.
- Extract generated-config presentation, L2 user-logic editors, layer-aligned
  task content, and twin-asset editors into focused dumb widgets under
  `features/configuration_workspace/presentation/deployment/`.
- Child widgets receive immutable `WizardState` projections and callbacks only;
  they do not read Riverpod, BLoC, Dio, or Management API services.
- Preserve all filenames, validation requests, task filtering, layout
  breakpoints, generated JSON, examples, and explicit clear semantics.

### Tests

- Existing Step 3 validation, ZIP, GLB, and configuration workspace tests.
- Focused widget tests for data-contract, user-logic, and twin-assets task
  composition, including compact width and validation callbacks.

### Preserved Layouts

Wide desktop:

```text
+-----------------------------------------------------------------------+
| Configuration workspace                                               |
+----------------------+------------------------------------------------+
| Phase/task sidebar   | Selected deployment task                       |
|                      |                                                |
| Cloud access         | [Quick ZIP upload when data-contract task]     |
| Data contracts       | [Configuration / payload editors]              |
| User logic           | [Processor / event / state-machine editors]    |
| Twin assets          | [Hierarchy / scene / GLB / user config]        |
| Review               |                                                |
+----------------------+------------------------------------------------+
| Back                                      Save / Continue / Finish     |
+-----------------------------------------------------------------------+
```

Compact Web and narrow desktop:

```text
+------------------------------------------+
| Configuration workspace                  |
| [Current phase/task selector]             |
+------------------------------------------+
| Selected task                            |
| editors stacked at full available width  |
| validation feedback below each editor    |
+------------------------------------------+
| Back                                     |
| Save / Continue / Finish                 |
+------------------------------------------+
```

The refactor must not change labels, task order, breakpoints, or visibility.
New or moved dimensions must use `AppSpacing`; provider colors use `AppColors`
or the active `ThemeData`. Material icons remain the only icon source.

### Widget Tree

```text
WizardScreen [MODIFY, composition only]
`-- BlocProvider<WizardBloc> [REUSE]
    `-- WizardView [MODIFY, smart boundary]
        `-- ConfigurationWorkspaceScaffold [NEW, dumb]
            |-- BrandedAppBar [REUSE]
            |-- ConfigurationWorkspaceHeader [NEW, dumb]
            |-- ConfigurationAlertStack [NEW, dumb]
            |-- ConfigurationWorkspaceShell [REUSE]
            |   |-- ConfigurationTaskSidebar [REUSE]
            |   `-- selected task content
            |       `-- Step3Deployer [MODIFY, smart coordinator]
            |           `-- DeploymentTaskContent [NEW, dumb]
            |               |-- DeploymentDataContractsTask [NEW]
            |               |-- DeploymentUserLogicTask [NEW]
            |               |-- DeploymentTwinAssetsTask [NEW]
            |               `-- DeploymentLayerOverview [NEW]
            `-- ConfigurationNavigationBar [NEW, dumb]
```

New widgets are justified because existing Step 3 widgets model editor blocks
and layer rows, not task-level composition. They must reuse
`Step3QuickUploadSection`, `CollapsibleBlockWrapper`, `FileEditorBlock`,
`FunctionPackageBlock`, `Step3LayerRow`, `Step3GlbUploadCard`, and
`ConfigurationWorkspaceShell`; duplicating those primitives is forbidden.

All new task widgets receive `WizardState` plus typed callbacks such as
`ValueChanged<WizardEvent> onEvent`, `VoidCallback onUploadGlb`, and
`VoidCallback onDeleteGlb`. They must not receive API clients, provider refs,
or mutable maps owned by the widget.

## Subphase 3 - Wizard Shell And Event-Orchestration Split

### Scope

- Extract workspace header, alert stack, task navigation, and confirmation
  presentation from `wizard_screen.dart` into dumb workspace widgets.
- Group `WizardBloc` handlers by cohesive concern: initialization/cloud access,
  optimization/persistence, artifact validation/content, and ZIP/GLB commands.
- Keep one public `WizardBloc` and one state machine. Handler modules may share
  the BLoC library but may not introduce global mutable state or duplicate API
  clients.
- Preserve every existing event, state transition, route, and save/finish
  contract unless Subphase 1 replaces an unsafe GLB event explicitly.

### Tests

- Full Wizard BLoC suite, save/finish/reload/clear tests, and configuration
  journey tests.
- Focused shell tests for loading, error, warning, invalidation, save, back,
  next, and finish actions.

### State And Interaction Rules

- `WizardView` remains the sole owner of route changes, confirmation dialogs,
  file picking, snackbars, and Riverpod invalidation.
- Extracted shell widgets emit callbacks only. They do not read BLoC or
  Riverpod and contain no timers or delayed navigation.
- `WizardBloc` remains the sole owner of API commands and state transitions.
- Existing keyboard focus, semantic button labels, disabled reasons, and
  confirmation cancellation behavior must remain available. New busy states
  expose a live-region status and disable duplicate GLB commands.
- The existing 900 px task-layout breakpoint and 640 px supported minimum
  viewport remain authoritative. No page-level horizontal overflow is allowed.

## Subphase 4 - Verification And Audit Closure

### Required Gates

```bash
flutter analyze
flutter test
flutter build web --release --dart-define-from-file=config/dev.example.json
flutter build macos --debug --dart-define-from-file=config/dev.example.json
dart format --output=none --set-exit-if-changed lib test
git diff --check
```

Static audit checks must confirm:

- no production `print` or `debugPrint`;
- no TODO/FIXME/HACK comments in production Dart;
- no direct Optimizer or Deployer service URLs;
- no screen/widget imports Dio;
- no screen/widget directly calls `ManagementApi` or `ApiService` for a
  feature command;
- no secret or binary credential payload is logged, rendered, or retained in
  feature state;
- all approved demo scenarios still render every route.

### Test Matrix

Every changed unit requires hard assertions:

- Step 2: existing params, absent params, edit hydration, no twin, pricing
  loading/error, and no direct service invocation.
- GLB commands: upload success, delete success, missing twin, duplicate command,
  transport failure, stale message clearing, binary non-retention, and command
  recovery after failure.
- Deployment tasks: all four focus modes, disabled dependencies, dynamic device
  processors, event actions, state machine, AWS/Azure scene files, no-3D path,
  unsupported L4/L5 info, compact layout, and exact validation events.
- Wizard shell: loading, ready, warning, error, invalidation confirmation,
  save, back, next, finish, Escape cancellation, and disabled action semantics.
- Logger/docs: every closed event serializes without free-form data; default,
  custom, trailing-slash, unknown-provider, and fragment URL cases are exact.

Mocks are allowed only for unit/widget isolation. No integration contract is
changed, so this remediation does not add a mocked-HTTP integration test or a
live-cloud E2E. Existing real-stack integration coverage remains unchanged.

## Documentation Phase

- Mark this plan complete with exact evidence and residual external tool
  warnings.
- Update `docs/frontend/FRONTEND_EXTENSION_POINTS.md` only where ownership or
  Issue #36 references need correction.
- Update Issues #38 and #39 with commits and verification. GitHub remains the
  future-work SSOT; no replacement TODO document is created.

## Implementation Progress

### Subphase 1 - Complete

- Removed direct API ownership from optimizer and deployer task screens.
- Routed dashboard twin deletion through a serialized Riverpod command
  controller that owns API I/O and cache invalidation.
- Added typed, serialized GLB commands with transient binary ownership.
- Replaced free-form diagnostic output with a closed, secret-free event log.
- Moved credential help to the runtime-configured canonical MkDocs site.
- Removed stale production TODOs and the superseded Flutter TODO tracker.
- Verification: `flutter analyze` passed; the full suite passed with 510 tests;
  the post-review focused boundary suite passed with 17 tests; `git diff
  --check` passed.
- Review: two manual passes completed with no unresolved finding.

## Definition Of Done

- [ ] All four subphases pass their focused and full gates.
- [ ] Step 2 and every Step 3 command obey the BLoC boundary.
- [ ] Wizard shell and deployment task widgets are presentation-only.
- [ ] `WizardBloc` handlers are grouped by cohesive responsibility without
      changing its public state machine.
- [ ] No free-form error/secret data reaches application logs.
- [ ] All credential help opens the canonical runtime-configured MkDocs site.
- [ ] No production TODO/FIXME/HACK comments or stale Flutter TODO tracker remain.
- [ ] Loading, error, empty, blocked, disabled, success, wide, and compact states
      are covered with hard assertions.
- [ ] Web and macOS builds succeed from `config/dev.example.json`.
- [ ] Two code-review passes find no unresolved Critical, Major, or Minor findings.
- [ ] Issue #38 is closed only when its remaining file-level decomposition and
      acceptance criteria are complete.
- [ ] Issue #39 remains open until the complete lifecycle has integration evidence.
- [ ] No live-cloud resources are created and no live-cloud E2E is executed.
