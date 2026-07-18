# Phase 8: Flutter Read-Only Deployment Review

**Issue:** [#134](https://github.com/TVJunkie724/master-thesis/issues/134)  
**Status:** Reviewed and implementation-ready  
**Blocked by:** #130

This is Resolved Deployment Specification subphase 8, not repository
architecture Phase 8.

## 0. Git Branch

- **Branch:** `codex/pricing-tier-finalization`
- **Base branch:** `master`
- **Merge strategy:** merge commit, never rebase shared history.
- **Commit prefix:** `[AI-0717-rds8]`

## 1. Summary

Flutter must expose the exact immutable deployment decision used by the
Deployer without becoming a second configuration source. A successful
calculation therefore has two client-visible outcomes:

1. the cost result and resolved specification are persisted as one optimizer
   run;
2. Flutter immediately asks the Management API to select that whole run for
   deployment, invoking the existing pricing/account-context verification.

Provider values, SKUs, capacities, memory, storage classes, schedules, and
runtime profiles remain read-only. The user can recalculate the architecture
or retry run selection, but cannot edit individual resolved dimensions.

The selected specification is shown in two restrained places:

- a small status block on `Review recommendation`, close to the cost result;
- a compact `Resolved cloud resources` section in the existing final
  configuration summary.

No new wizard phase, long screen, direct Optimizer call, or direct Deployer
call is introduced.

### Trust And Consistency Rules

- `CostCalculationRunDetailResponse` is the source for the current run and
  specification.
- `select-for-deployment` is the only client operation that marks a run ready
  for deployment.
- The client validates run ID, twin ID, schema version, digest, compatibility
  state, selection timestamp, and specification identity across both
  responses.
- On edit, Flutter loads the newest run from the Management API. A newer
  unselected run cannot silently inherit the selection state of an older run.
- A legacy optimizer projection without a run specification remains readable
  but blocks deployment and directs the user to recalculate.
- Unknown future specification versions remain inspectable as unsupported
  metadata and never crash the screen or become deployable.
- A known v1 specification with malformed fields, mismatched run identity, or
  mismatched digest fails closed as an API-contract error.

## 2. Visual Layout

### Review Recommendation: Ready

```text
+------------------------------------------------------------------+
| Optimization results                                             |
| Total, trace summary, path, warnings, and cost comparison         |
|                                                                  |
| Deployment selection                                  [Ready]    |
| This optimizer run is verified and selected for deployment.      |
| 7 architecture slots | AWS + Azure + GCP | digest 7d63...91ac    |
+------------------------------------------------------------------+
```

The existing cost result remains unchanged. The status block is compact and
does not repeat every component.

### Review Recommendation: Selection Failed

```text
+------------------------------------------------------------------+
| Deployment selection                         [Needs attention]   |
| Pricing or account context could not be verified.                |
| The calculation is visible but deployment remains blocked.       |
|                                             [Retry verification] |
+------------------------------------------------------------------+
```

### Final Summary: Wide Desktop And Web

```text
+------------------------------------------------------------------+
| Configuration summary                                            |
|                                                                  |
| Twin                                                             |
| Workload                                                         |
| Architecture                                                     |
|                                                                  |
| Resolved cloud resources                              [Ready]     |
| 7 architecture slots | 3 providers | digest 7d63...91ac          |
| L1          Azure   Azure IoT Hub                  S1 x 1         |
| L2          AWS     Lambda processing bundle       256 MB         |
| L3 hot      GCP     Firestore Native               PAYG           |
| L3 cool     Azure   Blob Storage                   cool           |
| L3 archive  AWS     S3                             DEEP_ARCHIVE   |
| L4          Azure   Azure Digital Twins            standard       |
| L5          AWS     Managed Grafana                workspace      |
| Supporting runtime (only when present)                            |
| Transition  GCP     Cloud Functions + Scheduler   512 MB / 1h    |
| [v Show technical evidence]                                      |
|                                                                  |
| Deployment readiness                                             |
+------------------------------------------------------------------+
```

### Final Summary: Narrow Desktop Or Web Window

```text
+--------------------------------------+
| Resolved cloud resources     [Ready] |
| 7 slots | 3 providers                |
| digest 7d63...91ac                   |
|                                      |
| L1        Azure                      |
| Azure IoT Hub | S1 x 1               |
|                                      |
| L2        AWS                        |
| Lambda processing bundle | 256 MB    |
|                                      |
| [v Show technical evidence]          |
+--------------------------------------+
```

Rows wrap vertically and never introduce horizontal scrolling. Technical
evidence is collapsed on every initial render.

### Legacy, Unsupported, Invalid, And Empty States

```text
+------------------------------------------------------------------+
| Resolved cloud resources                         [Recalculate]    |
| This saved result predates deployable resource specifications.   |
|                                     [Recalculate architecture] |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| Resolved cloud resources                       [Unsupported]      |
| Specification version v2 is not supported by this app version.   |
|                                     [Recalculate architecture] |
+------------------------------------------------------------------+

+------------------------------------------------------------------+
| Resolved cloud resources                      [Not available]     |
| Calculate and verify an architecture to prepare deployment.      |
+------------------------------------------------------------------+
```

Malformed known-version payloads use the existing page-level error boundary;
the UI must not render partially trusted component rows.

## 3. Widget Tree

```text
WizardScreen [REUSE]
`-- BlocProvider<WizardBloc> [REUSE]
    `-- Step2Optimizer [MODIFY]
        `-- _buildResultsSection [MODIFY]
            `-- DeploymentSelectionStatus [NEW]

ConfigurationReviewTask [MODIFY]
`-- BlocBuilder<WizardBloc, WizardState> [REUSE]
    `-- _Summary [MODIFY]
        |-- _SummarySection [REUSE]
        |-- ResolvedDeploymentSummary [NEW]
        |   |-- ResolvedDeploymentStatusHeader [NEW]
        |   |-- LayoutBuilder [REUSE]
        |   |   `-- ResolvedDeploymentComponentRow[] [NEW]
        |   `-- ExpansionTile [REUSE]
        |       `-- ResolvedDeploymentEvidenceRow[] [NEW]
        `-- _SummarySection [REUSE]
```

`ResolvedDeploymentSummary` is new because `ServiceBreakdown` compares
provider alternatives, while this widget presents only the frozen deployment
winner and must distinguish deployable selections from evidence-only
dimensions. Existing summary sections, Material icons, `ExpansionTile`,
`AppSpacing`, and theme typography/colors are reused.

## 4. Component And Model Specifications

### Required File Boundaries

| Area | Required files |
| --- | --- |
| Models | new `lib/models/resolved_deployment_specification.dart`; modify `lib/models/optimizer_config.dart` |
| API abstraction | modify `lib/services/management_api.dart`, `lib/services/api_service.dart` |
| Wizard state | modify `lib/bloc/wizard/wizard_state.dart`, `wizard_event.dart`, `wizard_bloc.dart`, optimization and initialization handlers, and `services/wizard_init_service.dart` |
| Journey gate | modify `lib/features/configuration_workspace/domain/configuration_journey.dart` |
| Result review | modify `lib/screens/wizard/step2_optimizer.dart`; add `lib/widgets/results/deployment_selection_status.dart` |
| Final summary | modify `lib/features/configuration_workspace/presentation/configuration_review_task.dart`; add `lib/widgets/results/resolved_deployment_summary.dart` |
| Tokens | modify `lib/theme/spacing.dart` only for the three named layout constants |
| Demo | modify `lib/demo/demo_fixture_store.dart` and `lib/demo/demo_management_api.dart` |
| Tests | focused model, service, BLoC, journey, widget, demo, and integration files under the matching `test/` and `integration_test/` boundaries |
| Documentation | this plan, Configuration Workspace reference/roadmap, docs-site Flutter/runtime pages, and refactoring roadmap |

### Typed Models

Create `lib/models/resolved_deployment_specification.dart` with:

- a sealed supported/unsupported specification projection;
- immutable architecture-profile and optimization-context metadata;
- immutable component and dimension value objects;
- closed enums for component slots and dimension classifications;
- a stable slot order and human-readable labels;
- an immutable lightweight `OptimizerDeploymentRunData` that parses run and
  specification metadata without requiring a modern calculation result;
- an immutable `OptimizerRunSummaryData`;
- an immutable `OptimizerRunSelectionData`;
- a presentation-neutral `ResolvedDeploymentReview` projection.

Extend `OptimizerRunData` in `lib/models/optimizer_config.dart` with one
required `OptimizerDeploymentRunData deploymentRun`. The lightweight
projection contains:

| Field | Type | Required |
| --- | --- | --- |
| `id` | `String` | yes |
| `twinId` | `String` | yes |
| `deploymentCompatibility` | `DeploymentCompatibility` | yes |
| `deploymentSpecificationDigest` | `String?` | legacy only |
| `deploymentSpecificationVersion` | `String?` | legacy only |
| `deploymentSpecification` | `ResolvedDeploymentSpecificationData?` | legacy only |
| `selectedForDeploymentAt` | `DateTime?` | no |
| `createdAt` | `DateTime` | yes |

For a `ready` v1 run, all deployment fields are mandatory and mutually
consistent. Unknown versions produce an unsupported projection. Legacy runs
may omit the specification. Extra fields are ignored only for unknown future
versions; known v1 parsing validates every required field and scalar type.
Legacy list/detail hydration must use `OptimizerDeploymentRunData` and must
not require the modern `OptimizationResultData`/pricing-trace contract.

### `DeploymentSelectionStatus`

**File:** `lib/widgets/results/deployment_selection_status.dart`
**Widget:** `StatelessWidget`

| Parameter | Type | Required |
| --- | --- | --- |
| `review` | `ResolvedDeploymentReview` | yes |
| `isSelecting` | `bool` | yes |
| `onRetry` | `VoidCallback?` | no |

It renders one icon, title, one bounded explanatory sentence, and only for a
retryable selection failure a `TextButton.icon`. It never renders raw API
errors, provider payloads, or full digests.

### `ResolvedDeploymentSummary`

**File:** `lib/widgets/results/resolved_deployment_summary.dart`
**Widget:** `StatelessWidget`

| Parameter | Type | Required |
| --- | --- | --- |
| `review` | `ResolvedDeploymentReview` | yes |
| `isSelecting` | `bool` | yes |
| `onRetrySelection` | `VoidCallback?` | no |
| `onRecalculateArchitecture` | `VoidCallback` | yes |

The supported ready state renders all seven architecture components in stable
slot order. `transition_runtime` and `cross_cloud_glue` are rendered under a
small `Supporting runtime` subheading when present. No required component may
be hidden.

Primary row summaries include only `deployable_selection` dimensions.
`usage_tier`, `account_scope`, and `non_deployable_assumption` remain visible
inside technical evidence with their classification labels so they cannot be
mistaken for Terraform selections.

Expanded evidence contains:

- component ID, slot, provider, and service ID;
- each dimension ID, value, unit, and classification;
- formula and evidence references;
- Terraform target only when supplied;
- architecture profile/version, calculation strategy, formula set, workload
  contract, pricing registry version, catalog snapshot references, run ID, and
  full digest.

No credentials, raw pricing rows, unrestricted JSON, endpoints, or tokens are
rendered.

The summary file owns three private stateless leaf widgets:

| Widget | Parameters | Responsibility |
| --- | --- | --- |
| `_ResolvedDeploymentStatusHeader` | `review`, `isSelecting` | icon, state label, bounded summary |
| `_ResolvedDeploymentComponentRow` | `component`, `wide` | responsive slot/provider/service/deployable-dimension row |
| `_ResolvedDeploymentEvidenceRow` | `label`, `value` | wrapping, selectable technical key/value row |

`Step2Optimizer` only passes the derived review state and retry event to
`DeploymentSelectionStatus`. `ConfigurationReviewTask` only passes the same
review state plus retry/recalculation callbacks to
`ResolvedDeploymentSummary`; neither widget derives contract state itself.

## 5. Responsive Behavior

| Width | Behavior |
| --- | --- |
| `>= 1024` | Component rows use fixed slot/provider columns plus flexible service/dimension content. |
| `600-1023` | Slot/provider share the first line; service and dimensions wrap below. |
| `< 600` | Every row stacks slot, provider, service, then dimensions; actions remain full-width when needed. |

The existing content-width constraints remain authoritative. New breakpoints
must be named in `AppSpacing`; no inline breakpoint or row-width literal is
allowed. Web, macOS, Windows, and Linux share the same widget tree.

## 6. State Flow

`WizardBloc` owns current-run loading, selection, retry, and error state.
Widgets receive immutable review projections and emit events only.

### New State

- `OptimizerDeploymentRunData? deploymentRun`
- `OptimizerDeploymentRunData? savedDeploymentRun`
- `bool isSelectingDeploymentRun`
- `String? deploymentRunSelectionError`

`WizardState.deploymentReview` derives absent, selection-required, selecting,
ready, legacy, unsupported, or failed states from the lightweight deployment
run. `isConfigurationReadyForFinish` must require a selected, supported,
digest-consistent specification.

### New Event

`WizardDeploymentRunSelectionRequested` retries selection for the current run.
Duplicate requests while calculating, saving, or selecting are ignored.

### New Calculation

```text
Calculate
  -> WizardCalculateRequested
  -> WizardBloc
  -> ManagementApi.createOptimizerRun(twinId, params)
  -> typed calculation run + lightweight deployment run + immutable specification
  -> ManagementApi.selectOptimizerRunForDeployment(twinId, runId)
  -> verify run/specification/digest/selection response
  -> WizardState ready
  -> compact read-only UI
```

If creation succeeds but selection fails, the calculation remains visible,
the current run remains selection-required, downstream configuration tasks are
blocked, and the UI offers a retry. It never falls back to an older selected
run.

### Edit Initialization

```text
WizardInitEdit
  -> twin + twin config + deployer config + latest optimizer run
  -> validate latest run against optimizer projection
  -> compare the latest run's specification provider path with the optimizer
     projection and hydrate WizardState
  -> selected supported latest run: ready
  -> unselected latest run: selection required
  -> legacy projection without run/specification: recalculate
```

The service adapter may use the existing list and detail endpoints internally,
but the BLoC receives one typed `getLatestOptimizerRun` result. More than one
selected summary, inconsistent IDs, or inconsistent projection data is a
contract error.

`ConfigurationJourney` renames `Compare and select` to
`Review recommendation`, marks it as attention until the latest run is
selected, and blocks deployment preparation with
`Confirm the resolved architecture first`. Sidebar navigation cannot bypass
this gate.

## 7. Design Tokens

Reuse `AppSpacing.xs` through `xxl`, existing content widths, semantic
`ColorScheme`, text theme, divider theme, and Material status icons. Add only:

- `AppSpacing.resolvedDeploymentWideBreakpoint`;
- `AppSpacing.resolvedDeploymentSlotColumnWidth`;
- `AppSpacing.resolvedDeploymentProviderColumnWidth`.

No new literal colors, custom text styles, third-party icons, elevations, or
rounded card theme are introduced. The section remains unframed like existing
summary sections.

## 8. Interactions And States

- Technical evidence uses `ExpansionTile`, collapsed by default.
- Expansion uses the Material default transition; no custom animation.
- Retry dispatches one BLoC event and shows a bounded progress indicator.
- Recalculate opens `Calculate alternatives` through the existing task
  callback, where the calculation command already lives.
- Ready state has no command.
- Selection errors use the existing page alert plus a local retry affordance;
  raw backend details are normalized by `ApiErrorHandler`.
- Empty state contains no decorative card or illustration.
- Recalculation invalidation snapshots and restores `deploymentRun` together
  with the existing result so run identity cannot drift from the visible cost
  result.

## 9. Accessibility

- Focus order follows status header, component rows, evidence disclosure, then
  retry/recalculate action.
- Expansion and retry controls have explicit semantic labels.
- Status is communicated by icon plus text, never color alone.
- Full identifiers remain selectable text in expanded evidence.
- Long service IDs, formula references, and digest values wrap without
  clipping.
- Body and status text use theme colors meeting the existing Material contrast
  contract.
- Keyboard activation works through standard Material controls on all desktop
  platforms and Web.

## 10. Integration Points

Only the Management API origin is used.

| Method | Path | Result |
| --- | --- | --- |
| `POST` | `/twins/{twin_id}/optimizer-runs/` | typed current run detail and specification |
| `GET` | `/twins/{twin_id}/optimizer-runs/` | typed newest/selected run summaries |
| `GET` | `/twins/{twin_id}/optimizer-runs/{run_id}` | typed run detail for edit hydration |
| `POST` | `/twins/{twin_id}/optimizer-runs/{run_id}/select-for-deployment` | verified run selection and exact specification |

Extend `OptimizationApi` with:

```dart
Future<OptimizerDeploymentRunData?> getLatestOptimizerRun(String twinId);
Future<OptimizerRunSelectionData> selectOptimizerRunForDeployment(
  String twinId,
  String runId,
);
```

`ApiService` and `DemoManagementApi` must implement the same contract. No
widget calls HTTP. No Flutter code calls ports 5003 or 5004.

## 11. Test And Documentation Plan

### Model And Adapter Tests

Happy paths:

1. Parse a complete single-provider v1 specification.
2. Parse and select a multi-provider specification with transition/glue
   components.

Unhappy paths:

1. Reject a malformed known-v1 dimension or scalar type.
2. Reject selection response run/digest/specification mismatch.

Edge cases:

1. Preserve unknown future schema as unsupported metadata.
2. Read a legacy run without specification.
3. Reject duplicate selected summaries.
4. Reject detail twin/run context mismatch.
5. Preserve boolean, integer, and string dimension values without coercion.
6. Reject non-UTC/inconsistent selection timestamps.
7. Verify list-detail and selection calls use Management API paths only.

### BLoC And Journey Tests

Happy paths:

1. Calculation creates and selects exactly one run.
2. Edit hydration restores a selected latest run and ready review.

Unhappy paths:

1. Selection failure keeps the cost result visible and blocks downstream
   tasks.
2. Retry failure remains bounded and does not issue duplicate calls.

Edge cases:

1. Retry success transitions to ready.
2. Duplicate selection events are ignored.
3. Recalculation replaces the lightweight deployment run/specification
   atomically.
4. Restore-old-result restores the saved deployment-run identity as well.
5. Legacy projection recommends recalculation.
6. Latest unselected run cannot inherit an older selection.
7. Finish readiness cannot bypass unsupported or missing specifications.

### Widget And Responsive Tests

Happy paths:

1. Ready summary renders every required primary and supporting component.
2. Expansion renders exact technical evidence and full digest.

Unhappy paths:

1. Legacy and unsupported states provide architecture-review remediation.
2. Selection failure provides exactly one retry action.

Edge cases:

1. Evidence is collapsed by default.
2. Evidence-only dimensions are absent from the primary row.
3. Long identifiers wrap at 480 px without overflow.
4. Wide rows use stable slot/provider columns.
5. Empty state renders no component rows.
6. Status semantics include text independent of color.
7. Rapid expansion/retry interaction does not duplicate BLoC events.

### Demo And Docker Contract

- Demo fixtures cover selected single-cloud, selected multi-cloud, legacy,
  unsupported, and retryable failure projections.
- Demo calculation and selection use the same typed state transitions as live
  mode.
- The existing Docker-backed, non-cloud integration gate inspects the
  Management OpenAPI schemas and decodes list/detail data when a run exists.
- Integration tests do not select a run, deploy resources, or mutate cloud
  state.

### Repository Gates

- focused model, API, BLoC, journey, widget, demo, and integration tests;
- full `flutter analyze` and `flutter test`;
- `flutter build web --release` and host `flutter build macos`;
- static source checks for direct Optimizer/Deployer URLs and inline design
  tokens in new files;
- Management API focused contract/OpenAPI tests;
- strict MkDocs build and `git diff --check`;
- no provider credentials and no live cloud E2E.

### Documentation

- Add a concise implementation reference under
  `twin2multicloud_flutter/docs/configuration_workspace/`.
- Update the Configuration Workspace roadmap, Flutter component
  documentation, runtime/user guide, main refactoring roadmap, and this
  mini-roadmap.
- Documentation must explain the whole-run selection boundary and distinguish
  deployable dimensions from evidence-only pricing/account assumptions.

## 12. Definition Of Done

- [ ] Current and selected optimizer runs are typed end to end.
- [ ] Calculation invokes Management run selection and fails closed when
      verification cannot complete.
- [ ] Edit hydration cannot mix a newer run with an older selection.
- [ ] The latest supported selected specification gates deployment readiness.
- [ ] A user can confirm every exact frozen deployment component and dimension.
- [ ] Legacy and unsupported states provide a clear recalculation path.
- [ ] Technical evidence is collapsed by default and contains no secrets or
      unrestricted provider JSON.
- [ ] Widgets contain no HTTP, mutable domain state, inline design tokens, or
      direct Optimizer/Deployer calls.
- [ ] Model, API, BLoC, journey, widget, responsive, demo, and Docker contract
      gates pass.
- [ ] Analyzer, full Flutter tests, Web/macOS builds, Management contract
      tests, strict docs, and diff gates pass.
- [ ] Documentation and GitHub issue state match the implementation.
- [ ] #134 is closed with commit and verification evidence.
