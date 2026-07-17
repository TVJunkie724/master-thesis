# Phase 8: Flutter Read-Only Deployment Review

**Issue:** [#134](https://github.com/TVJunkie724/master-thesis/issues/134)  
**Status:** Reviewed and implementation-ready  
**Blocked by:** #130

This is RDS subphase 8, not repository architecture Phase 8.

## UX Decision

Do not add another long wizard page. Extend the existing deployment review with
a compact "Resolved cloud resources" summary:

```text
Resolved cloud resources                         Ready
7 architecture slots | 3 providers | verified digest

L1  Azure  IoT Hub S1 x 1
L2  AWS    Lambda processing bundle, 256 MB
...

[Show technical evidence]
```

The collapsed disclosure shows service IDs, deployable dimensions, region,
model/evidence references, compatibility state, and shortened digest. It never
shows credentials, raw pricing rows, or unrestricted provider JSON.

### Desktop and Wide Web

```text
+---------------------------------------------------------------+
| Configuration summary                                         |
|                                                               |
| Twin                                                          |
| Workload                                                      |
| Architecture                                                  |
|                                                               |
| Resolved cloud resources                         [Ready icon]  |
| L1  Azure   IoT Hub                  S1 x 1                    |
| L2  AWS     Lambda processing bundle 256 MB                    |
| L3  GCP     Firestore Native         PAYG                      |
| ...                                                           |
| [v Show technical evidence]                                   |
|                                                               |
| Deployment readiness                                          |
+---------------------------------------------------------------+
```

### Narrow Web and Desktop Window

```text
+----------------------------------+
| Resolved cloud resources   Ready |
|                                  |
| L1  Azure                        |
| IoT Hub | S1 x 1                 |
|                                  |
| L2  AWS                          |
| Lambda bundle | 256 MB           |
|                                  |
| [v Show technical evidence]      |
+----------------------------------+
```

Rows wrap; they never become horizontally scrollable cards.

### Widget Tree

```text
ConfigurationReviewTask [MODIFY]
`-- BlocBuilder<WizardBloc, WizardState> [REUSE]
    `-- _Summary [MODIFY]
        |-- _SummarySection [REUSE]
        |-- ResolvedDeploymentSummary [NEW]
        |   |-- ResolvedDeploymentStatusHeader [NEW]
        |   |-- LayoutBuilder [REUSE]
        |   |   `-- ResolvedComponentRow[] [NEW]
        |   `-- ExpansionTile [REUSE]
        |       `-- ResolvedDimensionDetails[] [NEW]
        `-- _SummarySection [REUSE]
```

`ExpansionTile`, existing summary rows, Material icons, `AppSpacing`, and theme
text/color tokens are reused. A new widget is justified because cost
`ServiceBreakdown` compares all providers, while this panel shows only the
frozen deployable winner and its compatibility state.

## Implementation

- Add immutable typed Dart models for the v1 read projection.
- Parse unknown versions into an explicit unsupported state, not a crash.
- Add repository/API adapter methods without raw map access in widgets.
- Render ready, legacy/recalculate, stale, and invalid states.
- Keep selection values read-only.
- Add complete demo-mode fixtures for single-cloud, multi-cloud, legacy, and
  invalid states.
- Preserve responsive behavior on Web, macOS, Windows, and Linux.

## Required File Boundaries

| Area | Files |
| --- | --- |
| Models | new focused model plus `lib/models/optimizer_config.dart` |
| API | `lib/services/management_api.dart`, `lib/services/api_service.dart` |
| State | `lib/bloc/wizard/wizard_state.dart` and optimization/init handlers |
| Screen | `lib/features/configuration_workspace/presentation/configuration_review_task.dart` |
| Widgets | new files under `lib/widgets/results/` |
| Theme | existing `lib/theme/spacing.dart`, color scheme, and text theme; no inline design tokens |
| Demo | `lib/demo/demo_management_api.dart` and typed fixtures |
| Tests | model, service contract, BLoC, screen/widget, demo, and responsive suites |

Widgets do not call HTTP. The Wizard BLoC owns loading/state transitions and
uses only the Management API abstraction on port 5005. No direct Optimizer or
Deployer call is allowed.

## Tests and Gates

- model parsing and unknown-field/version tests;
- repository and API contract fixtures;
- compact widget and expansion tests;
- legacy recalculation action test;
- no-overflow tests at narrow and desktop widths;
- demo navigation test;
- analyze, unit/widget tests, and all-desktop/web build gates.

## Definition of Done

- [ ] A user can confirm the exact frozen deployment selection.
- [ ] Legacy/unsupported states offer a clear recalculation path.
- [ ] Technical evidence is collapsed by default.
- [ ] No widget calls HTTP or owns mutable domain state.
- [ ] No inline color, spacing, text-style, or third-party icon token is added.
- [ ] Model, service, BLoC, widget, demo, analyze, and platform build gates pass.
- [ ] A Docker-backed non-cloud contract check verifies the Management API shape.
- [ ] #134 is closed with commit and verification evidence.
