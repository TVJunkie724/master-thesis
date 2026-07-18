---
title: "Phase 8.7: Flutter Architecture Profile Workflow"
description: "Implementation plan for compact profile selection and read-only resolved-architecture review across Web and desktop."
tags: [architecture, flutter, wizard, bloc, riverpod, accessibility, issue-138]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #138
- Phase 8.4 Management API DTO and profile-change preview contract
- Phase 8.6 resolved graph and deployment review contract
- FRONTEND_ARCHITECTURE.md
- twin2multicloud_flutter/README.md
- twin2multicloud_flutter/lib/services/management_api.dart
- twin2multicloud_flutter/lib/screens/wizard and twin2multicloud_flutter/lib/bloc/wizard
- User-approved compact task-sidebar workflow and Web/macOS/Windows/Linux support
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Phase 8.7: Flutter Architecture Profile Workflow

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#138 Implement the Flutter architecture profile workflow](https://github.com/TVJunkie724/master-thesis/issues/138) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-flutter-profile-workflow` |
| Base branch | `master` |
| Blocked by | Phase 8.6 / #152 |
| Targets | Web, macOS, Windows, Linux |
| Backend boundary | Management API only |
| Live cloud E2E | Forbidden |

All layouts, state transitions, API DTOs, accessibility behavior, demo parity,
tests, documentation, and Definition of Done items in this plan are mandatory.

## 1. Outcome

Replace fixed-slot architecture presentation with a compact profile-oriented
configuration and review workflow.

After the existing Twin identity prerequisite, the user follows five
profile-aware phases:

```text
Architecture
  -> Workload
  -> User Logic
  -> Optimize And Review
  -> Deployment Review
```

The user selects one reviewed profile, understands its responsibilities and
flow, enters only supported workload and extension-slot data, selects one
complete optimizer run, and reviews the immutable resolved components and
bindings. The UI is not an infrastructure editor.

Initially only implemented active profiles are returned. Do not render
`six-layer-eventing@1` as disabled or "coming soon" before Phase 8.9 makes it
real.

### Scope Boundary

| Included | Excluded |
|---|---|
| Typed Management API capability/models, Wizard BLoC transitions, compact profile/task workflow, data-driven graph/read-only evidence, server-derived invalidation confirmation, demo parity, accessibility, and Web/macOS/Windows/Linux gates | Direct Optimizer/Deployer access, backend architecture decisions, infrastructure editing, arbitrary graph/layer controls, Eventing UI before activation, mobile targets, and live provider execution |

## 2. Existing Architecture Boundary

Retain the current deliberate split:

- Riverpod owns runtime composition, environment/demo mode, authentication
  composition, and the `ManagementApi` adapter;
- `WizardBloc` owns the complex configuration workflow, async profile/run
  commands, invalidation, navigation readiness, and error state;
- presentation widgets receive typed state and emit typed events;
- `ApiService` is the only live HTTP implementation;
- `DemoManagementApi` implements the same interfaces with fixture repositories.

The older skill text that says Riverpod is not used is stale relative to the
implemented runtime composition and current project documentation. This plan
must not replace the working Riverpod/BLoC split with a third architecture.

## 3. Information Architecture

Update `ConfigurationJourney`:

```text
Define twin
`-- Define twin

Architecture
|-- Select profile
`-- Understand architecture

Workload
|-- Scenario and currency
|-- Device traffic
|-- Processing
|-- Retention
`-- Twin capabilities

User Logic
`-- Bind user logic

Optimize and review
|-- Pricing readiness
|-- Calculate alternatives
`-- Compare and select

Deployment review
|-- Cloud access
|-- Data contracts
|-- Twin assets
|-- Summary
|-- Readiness findings
`-- Validation and preflight
```

`Define twin` remains a prerequisite phase because a persisted Twin ID is
required by Management APIs. The five profile phases begin after identity.

Task readiness:

- profile selection is available after Twin identity;
- profile understanding is complete after profile detail loads and is
  acknowledged by navigation, not by a checkbox;
- workload is blocked until a profile is selected;
- user logic is blocked until profile extension slots load;
- optimization is blocked until workload and required extension bindings are
  valid;
- cloud access is blocked until one complete run is selected;
- deployment review is bound to the selected run's resolved architecture.

Changing profile atomically invalidates workload fields not supported by the
new contract, selected optimizer run, deployment readiness, and provider access
requirements. The UI must show a confirmation listing the categories that will
be invalidated before sending the revisioned request.

## 4. Typed Models

Add:

```text
twin2multicloud_flutter/lib/models/architecture_profile.dart
twin2multicloud_flutter/lib/models/resolved_twin_architecture.dart
```

### 4.1 Profile Models

- `ArchitectureProfileSummary`
- `ArchitectureProfileDetail`
- `ArchitectureProfileSelection`
- `ArchitectureResponsibility`
- `ArchitectureComponent`
- `ArchitectureEdge`
- `ArchitectureCapabilitySummary`
- `ArchitectureProviderAvailability`
- `ArchitectureExtensionSlotSummary`
- `ArchitectureVisualization`

Every `fromJson` must reject missing, wrong-type, additional contract-critical,
unknown-version, duplicate-ID, and unresolved-reference data through the
project's typed contract error boundary. UI code must not parse raw maps.

### 4.2 Resolved Models

- `ResolvedTwinArchitectureData` sealed by schema version;
- `ResolvedTwinArchitectureV1`;
- `ResolvedArchitectureAssignment`;
- `ResolvedArchitectureEdge`;
- `ResolvedFunctionalCompleteness`;
- `ResolvedArchitectureCostSummary`;
- `ResolvedArchitectureReview`.

The models preserve exact IDs/digests and canonical decimal strings. Display
formatting is separate.

### 4.3 Compatibility

Retain `ArchitecturePath`, fixed `CalcResult` fields, and
`ArchitectureServiceMap` only as isolated legacy parser/projection support.
New profile and review widgets must not import them. Remove their last generic
presentation use only after tests prove old baseline runs still display through
the Management compatibility DTO.

## 5. Management API Interface

Add `ArchitectureApi` as one capability interface in
`management_api.dart`, then include it in the existing composition:

```dart
abstract interface class ManagementApi
    implements
        SessionApi,
        AuthenticationApi,
        UserPreferencesApi,
        CloudAccessApi,
        TwinApi,
        PricingApi,
        PlatformCapabilityApi,
        OptimizationApi,
        DeploymentConfigurationApi,
        DeploymentLifecycleApi,
        VerificationApi,
        ArchitectureApi {}
```

`ApiService` and `DemoManagementApi` must implement the resulting
`ManagementApi` surface. Do not introduce a second transport client or bypass
the existing Riverpod-provided `ManagementApi` composition.

`ArchitectureApi` defines:

```text
listArchitectureProfiles()
getArchitectureProfile(profileId, profileVersion)
getTwinArchitectureSelection(twinId)
previewTwinArchitectureProfileChange(twinId, request)
selectTwinArchitectureProfile(twinId, request)
getSelectedResolvedArchitecture(twinId)
getRunResolvedArchitecture(runId)
```

Request:

```text
ArchitectureProfileChangePreviewRequest(
  profileId,
  profileVersion,
  expectedRevision
)

ArchitectureProfileSelectRequest(
  profileId,
  profileVersion,
  expectedRevision,
  invalidationDigest
)
```

Responses use the exact Phase 8.4 DTOs. `ApiService` calls only port 5005.
No widget/BLoC/repository calls Optimizer or Deployer directly.

`OptimizationApi.createOptimizerRun` remains workload-only from the widget
perspective; Management enriches profile/binding refs server-side.

`ArchitectureProfileChangePreviewResponse` is the only source for the
confirmation dialog. Flutter must not infer incompatible fields, bindings,
run selection, or readiness invalidation from local profile DTOs. After user
confirmation, the BLoC submits the returned digest. A stale digest reloads the
selection and preview before the user can confirm again.

## 6. BLoC Contract

Extend `WizardState` with:

- profile list load status and safe error;
- selected profile selection/revision;
- selected profile detail;
- profile-change invalidation preview;
- resolved architecture load status and safe error;
- selected run's resolved architecture;
- stale/incompatible/legacy resolution state;
- profile-derived required workload fields and extension slots.

Add events:

- `WizardArchitectureProfilesLoadRequested`;
- `WizardArchitectureProfileSelected`;
- `WizardArchitectureProfileChangePreviewLoaded`;
- `WizardArchitectureProfileChangeConfirmed`;
- `WizardArchitectureProfileDetailLoadRequested`;
- `WizardResolvedArchitectureLoadRequested`;
- `WizardArchitectureEvidenceToggled`;
- `WizardArchitectureViewModeChanged`.

Presentation-only graph view mode/disclosure state may remain local widget
state when it has no workflow effect. Network commands, selection, invalidation,
readiness, and errors remain in BLoC.

Required state transitions:

```text
initial
  -> profilesLoading
  -> profileReady | profileEmpty | profileError
  -> selectingProfile
  -> profileSelected | selectionConflict | selectionError
  -> workload/logic ready
  -> optimizing
  -> resolutionLoading
  -> resolutionReady | resolutionIncompatible | resolutionError
```

A stale selection revision reloads current selection and presents a conflict
message. A stale invalidation digest reloads both selection and preview and
requires a new explicit confirmation. Neither case overwrites server state
automatically.

## 7. Wide Layout

Workspace width at or above `1200` logical pixels:

```text
+----------------------+------------------------------------------------------+
| Configuration        | Architecture                                         |
|                      |                                                      |
| Define twin        o | Profile                                              |
|                      | +-------------------+--------------------------------+ |
| Architecture       * | | Five-layer       | Five-layer baseline            | |
|   Select profile   * | | baseline       o | Responsibilities  5            | |
|   Understand       o | |                   | Components        7+           | |
|                      | |                   | Providers         AWS Azure... | |
| Workload           l | +-------------------+--------------------------------+ |
| User Logic         l |                                                      |
| Optimize...        l | [Overview] [Components]                Active v1     |
| Deployment...      l |                                                      |
|                      |  Ingestion --> Processing --> Storage                 |
|                      |                         |       |                      |
|                      |                         +--> Twin --> Visualization    |
|                      |                                                      |
|                      | Functional coverage                                  |
|                      | Required capabilities complete                        |
|                      | Technical details                              [v]     |
+----------------------+------------------------------------------------------+
| Back                       Draft saved                         Continue       |
+-----------------------------------------------------------------------------+
```

The profile list and detail are unframed columns separated by a divider. Do not
place cards inside a containing card. The active profile row is a radio
selection row with concise status, not a marketing card.

## 8. Medium And Compact Layouts

From `960` through `1199`, keep the task sidebar and stack profile selector,
summary, graph, and functional coverage.

Below `960`, reuse `ConfigurationTaskSelector` above the content:

```text
+------------------------------------------+
| Architecture / Select profile        [v] |
+------------------------------------------+
| Five-layer baseline                (o)   |
| Active v1                                |
|------------------------------------------|
| 5 responsibilities | 7+ components      |
| AWS | Azure | Mixed supported            |
|                                          |
| [Overview] [Components]                  |
|                                          |
| Ingestion                                |
|    |                                     |
| Processing                               |
|    |                                     |
| Storage ----> Twin ----> Visualization   |
|                                          |
| Functional coverage                      |
| Required capabilities complete           |
| Technical details                  [v]    |
+------------------------------------------+
| Back                         Continue     |
+------------------------------------------+
```

Below `720`, graph layout changes to a vertical Sugiyama orientation. It does
not shrink node text with viewport width. Nodes use bounded width, wrap labels,
and allow vertical scrolling. The full screen never requires horizontal page
scrolling.

## 9. Resolved Architecture Review

The `Compare and select` task shows:

```text
+--------------------------------------------------------------------------+
| Recommendation                                                           |
| Five-layer baseline v1 | Mixed providers | USD 42.17 / month             |
| Functional completeness: Complete      Deployment contract: Ready        |
|                                                                          |
| Responsibilities                                                         |
| Ingestion       AWS      IoT Core                                         |
| Processing      Azure    Functions                                        |
| Storage hot     AWS      DynamoDB                                         |
| ...                                                                      |
|                                                                          |
| Architecture flow                                             [Open]     |
| Cost and pricing evidence                                      [Open]     |
| Deployment dimensions                                         [Open]     |
| Rejected candidates (12 by reason)                             [Open]     |
|                                                                          |
| [Select complete run]                                                    |
+--------------------------------------------------------------------------+
```

The `Deployment review` summary shows:

- profile ID/version/digest;
- calculation run and architecture digest;
- resolved components, providers, services, regions, tiers/capacities;
- resolved logical edges and cross-cloud boundaries;
- extension artifact status;
- credential/readiness status by selected provider;
- graph/deployment specification compatibility;
- collapsed technical bindings/evidence.

Physical cloud names, secrets, raw pricing payloads, tfvars, and editable
provider SKUs are never shown.

## 10. Graph Component

Add:

```text
twin2multicloud_flutter/lib/widgets/architecture_profiles/
  architecture_profile_graph.dart
  architecture_profile_node.dart
  architecture_profile_edge_legend.dart
  architecture_profile_summary.dart
  resolved_architecture_summary.dart
  architecture_evidence_disclosure.dart
```

Use the existing `graphview` package with a deterministic Sugiyama layout.
Data comes from typed profile/resolution nodes and edges. Do not hardcode L1-L5
or service names in graph code.

Controls:

- `SegmentedButton`: Overview / Components;
- icon-only zoom in, zoom out, reset buttons with tooltips and semantics;
- keyboard focus and activation;
- `InteractiveViewer` only within the graph surface on wide/medium layouts;
- vertical static graph on compact layout;
- collapsed technical legend/evidence.

Stable dimensions:

- node min/max width and padding from theme tokens;
- node height content-driven within bounded lines;
- graph viewport uses constrained min/max height;
- layout changes never resize the sidebar/footer;
- long provider/service/profile names wrap and are tested.

## 11. Widget Tree

```text
WizardScreen [MODIFY]
`-- WizardView [MODIFY]
    `-- ConfigurationWorkspaceScaffold [REUSE]
        `-- ConfigurationWorkspaceShell [MODIFY]
            |-- ConfigurationTaskSidebar [MODIFY]
            |-- ConfigurationTaskSelector [MODIFY]
            `-- selected task child from WizardView [MODIFY]
                |-- ArchitectureProfileTask [NEW]
                |   |-- ArchitectureProfileSelector [NEW]
                |   |   `-- ArchitectureProfileRow [NEW]
                |   |-- ArchitectureProfileSummaryPanel [NEW]
                |   |-- ArchitectureProfileGraph [NEW]
                |   |   |-- ArchitectureProfileNode [NEW]
                |   |   `-- ArchitectureProfileEdgeLegend [NEW]
                |   |-- FunctionalCoverageSummary [NEW]
                |   `-- ArchitectureEvidenceDisclosure [NEW]
                |-- WorkloadTasks [REUSE/MODIFY profile field visibility]
                |-- DeploymentTaskContent [MODIFY]
                |   `-- DeploymentUserLogicSection [MODIFY #113 slots]
                |-- OptimizerReviewTask [MODIFY]
                |   `-- ResolvedArchitectureSummary [NEW]
                `-- ConfigurationReviewTask [MODIFY]
                    `-- ResolvedArchitectureSummary [REUSE]
```

New widgets are necessary because existing architecture widgets parse fixed
`cheapestPath` slots and hardcode service labels. Existing shared status,
segmented control, disclosure, alert, button, dialog, loading, and empty-state
primitives must be reused.

## 12. Visual Tokens And Interaction

- Reuse `AppSpacing`, theme `ColorScheme`, and existing text styles.
- Add tokens only if an existing semantic token cannot express graph node,
  selected row, edge, focus, or provider status.
- No inline color literals, spacing magic numbers, or standalone `TextStyle`.
- Use Material `Icons` only.
- Profile selection uses radio semantics; graph mode uses segmented control.
- Profile change confirmation is a dialog only because it is destructive to
  downstream draft state.
- Async action buttons show bounded progress without changing dimensions.
- Focus returns to the initiating control after dialog cancellation/error.
- No decorative gradients, oversized hero, nested cards, or explanatory
  feature prose.

## 13. Loading, Empty, Error, And Compatibility States

Required states:

- initial profile loading skeleton;
- no active profile: blocking empty state with support/error code;
- profile list error with retry;
- profile detail missing/stale/incompatible;
- selection conflict;
- profile change invalidation confirmation;
- no required extension slots;
- required extension binding invalid;
- optimizer run in progress;
- no result;
- rejected/no admissible candidate;
- legacy run readable but not profile-resolvable;
- resolution digest mismatch;
- selected run invalidated;
- Management API unavailable;
- demo fixture contract mismatch.

No state may render a blank graph or silently fall back to fixed service maps.

## 14. Accessibility

- WCAG 2.1 AA contrast in light and dark themes.
- Logical traversal: task selector/sidebar, profile rows, graph controls,
  summary, evidence disclosures, footer.
- Every profile row announces name, version, lifecycle, selection, and
  availability.
- Graph nodes expose responsibility, component, provider, service, and status
  through semantics independent of visual position/color.
- Edges have an ordered semantic summary outside the canvas.
- Color is never the only provider/status signal.
- Escape closes dialogs/disclosures where platform convention applies.
- Enter/Space activate focused rows and controls.
- At 200% text scaling, controls do not overlap and long words fit.

### 14.1 Security And Privacy

- Flutter receives only owner-authorized Management API projections.
- Profile IDs, component IDs, safe evidence references, and readiness states
  may be displayed; credentials, secret references, physical provider
  resource names, raw provider responses, source code, tfvars, and stack traces
  must never enter widget state, analytics, screenshots, or UI errors.
- The BLoC must retain only the latest safe preview/result and clear
  profile-dependent state on logout, Twin change, or invalidation.
- Error presentation uses stable Management API codes plus correlation IDs and
  never parses raw downstream messages.
- Demo fixtures must pass the same secret-like-field scan as live DTO fixtures.
- Cross-user and stale-revision responses fail closed and cannot reveal whether
  another user's resource exists.

## 15. Demo Contract

Add versioned fixture assets:

```text
twin2multicloud_flutter/assets/demo/v1/
  architecture-profiles.json
  architecture-profile-five-layer-baseline.json
  resolved-twin-architecture-mixed.json
```

`DemoManagementApi` must implement every `ArchitectureApi` method and mutate
selection/revision/invalidation exactly like the live contract. It may show only
implemented profiles. Tests must fail if demo/live interface methods or
contract versions drift.

## 16. Implementation Slices

### Slice A: Models And API Adapter

Must add typed DTOs, strict parsing, `ArchitectureApi`, `ApiService`, demo
fixtures/adapter, and contract tests.

### Slice B: Journey And BLoC

Must reorder tasks, add profile/resolution state/events, dependency readiness,
server-derived profile invalidation preview, digest-bound confirmation,
conflict recovery, and legacy compatibility.

### Slice C: Profile Selection And Visualization

Must implement wide/medium/compact layouts, deterministic graph, controls,
semantics, loading/empty/error states, and visual tests.

### Slice D: Workload And User Logic Integration

Must derive supported workload fields/extension slots from profile DTOs,
preserve current values, require #113 bindings, and reject hidden unsupported
fields rather than silently submitting them.

### Slice E: Optimizer And Deployment Review

Must replace generic fixed-slot rendering with resolved component/edge
summaries and collapsed evidence while preserving current run selection and
deployment readiness.

### Slice F: Migration And Platform Gate

Must isolate legacy models/widgets, prove demo parity, run all-platform builds,
strict docs, and architecture dependency gates.

## 17. Test Plan

### Models/API

Happy:

- parse baseline profile/detail and mixed resolution;
- round-trip selection request/response and exact revision.

Unhappy:

- unknown schema/profile version;
- missing/duplicate/unresolved component/edge/port.

Edge:

- long names;
- empty extension slots;
- unsupported provider;
- exact decimal cost;
- legacy run;
- additional contract-critical field;
- digest mismatch.

### BLoC/Journey

Happy:

- load/select profile then unlock workload;
- complete profile/workload/logic, calculate, select run, unlock deployment.

Unhappy:

- selection 409 reloads without overwrite;
- stale invalidation digest reloads preview and never submits a blind retry;
- invalid resolution blocks deployment.

Edge:

- idempotent same-profile selection;
- destructive profile change cancelled/confirmed;
- preview contents match cleared fields, unbound slots, selected run, and
  readiness categories returned by the real Management API;
- compatible CloudConnections and artifacts remain visible after a profile
  change;
- selected run invalidated;
- profile API retry;
- no active profile;
- extension binding becomes stale;
- edit existing legacy Twin.

### Widget/Visual

Happy:

- wide profile selector/detail/graph;
- compact selector/vertical graph.

Unhappy:

- error/empty/incompatible views;
- graph with invalid DTO never reaches widget and shows safe BLoC error.

Edge:

- 960, 1200, and 720 breakpoint boundaries;
- 200% text scale;
- longest profile/provider/service names;
- keyboard-only flow;
- light/dark contrast and focus;
- single profile;
- multiple active profiles after Phase 8.9;
- no graph overlap/blank pixels at supported sizes.

### Integration

Use the real Docker Management API:

- create/load a Twin with default baseline selection;
- change/reload selection revision;
- preview and confirm a destructive profile change using the exact
  `invalidation_digest`;
- create a fixture-backed optimizer run and read resolution;
- select complete run and verify deployment task unlocks;
- cross-user resource access remains hidden;
- no direct Optimizer/Deployer request occurs.

Unit tests may mock `ArchitectureApi`; integration tests may not mock HTTP.
Extend `run_frontend_integration_tests()` in `thesis.sh` so the resolved host
device runs `integration_test/architecture_profile_workflow_test.dart` after
the existing Management readiness test. The script remains credential-free.

## 18. Verification Commands

```bash
./thesis.sh test frontend
./thesis.sh test frontend-integration
```

Windows build runs in the existing GitHub Actions Windows job. Web, Linux,
macOS, and Windows gates are all mandatory. Local unavailability of one host
target does not waive its CI gate.

Before the integration entrypoint starts services, it must record which named
services are already running. After verification, it must stop only services
that this invocation started. It must never run `docker compose down` against a
shared developer stack as test cleanup.

No integration path may trigger provider pricing refresh, Terraform, deploy,
destroy, or live cloud resources.

## 19. Documentation

Update:

- configuration workspace concept/roadmap with the profile-aware task order;
- Flutter component docs with actual Riverpod/BLoC ownership;
- user guide for profile selection, workload, user logic, optimization, and
  deployment review;
- contract/data-flow docs for Flutter-to-Management profile APIs;
- demo handbook/scenario docs;
- architecture roadmap and #138 with named platform/test evidence.

Do not put Eventing evaluation conclusions in user docs. Do not edit LaTeX.

## 20. Rollout And Rollback

- Feature availability is server-driven by active profile DTOs.
- Existing Twins receive baseline selection through Phase 8.4 migration.
- Existing valid runs use the typed compatibility projection.
- Legacy unresolvable runs remain readable with a blocking explanation.
- Rollback disables the profile workflow route and new run creation; it does
  not silently restore direct fixed-field deployment.
- Manual visual audit #111 remains a later user-led gate.

## 21. Definition Of Done

- [ ] After Twin identity, the workspace presents the five profile-aware phases
      in the specified order.
- [ ] Profile selection is compact, revisioned, keyboard accessible, and
      Management-API-only.
- [ ] Only implemented active profiles are visible.
- [ ] Workload and User Logic fields derive from the selected profile.
- [ ] Profile change invalidation is explicit and atomic.
- [ ] The confirmation dialog renders only the server-derived invalidation
      preview and submits its digest; stale previews require reconfirmation.
- [ ] Graphs are typed, data-driven, read-only, responsive, nonblank, and free
      of overlap at all supported breakpoints/text scales.
- [ ] Resolved assignments, edges, costs, evidence, and deployment dimensions
      are progressively reviewable without editable infrastructure fields.
- [ ] Fixed-slot models/widgets are isolated to tested legacy compatibility.
- [ ] Riverpod/BLoC/runtime/API ownership remains clean.
- [ ] Loading, empty, error, stale, incompatible, legacy, and conflict states
      are complete.
- [ ] Demo/live adapters implement identical architecture interfaces.
- [ ] Model, API, BLoC, journey, widget, visual, accessibility, navigation,
      demo, and real-Management integration tests pass.
- [ ] Analyzer, full Flutter tests, Web, macOS, Linux, and Windows gates pass.
- [ ] No direct Optimizer/Deployer, live cloud, Terraform, or paid operation
      occurs.
- [ ] User/developer/demo docs, roadmap, and #138 are updated.
- [ ] Two reviews find no unresolved issue.
- [ ] The structured commit references #138.
