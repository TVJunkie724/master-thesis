# Implementation Plan: Architecture Profile Experiment

## 0. Git Branch

- **Branch name:** `codex/phase-8-profile-workflow`
- **Base branch:** the reviewed Phase 8.6 graph-resolver and immutable
  complete-service decision commit.
- **Merge strategy:** merge commit; no rebase. The user controls the later
  integration into the default branch.
- **Session/commit prefix:** `[AI-0803-PROF]`.
- **Authorization:** the user explicitly requested concept, planning, and
  implementation on 2026-08-03. This reviewed plan is the builder gate; no
  additional product-scope expansion is authorized.

## 1. Summary

This feature extends the implemented Configuration Workspace described in
`FRONTEND_ARCHITECTURE.md` and
`docs/configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md`. It makes the
thesis experiment explicit before workload entry:

- select the reviewed `five-layer-baseline@2` or
  `six-layer-eventing@1` profile;
- choose a compatible workload-v2 core preset and required immutable event
  scenario;
- calculate and compare only functionally complete alternatives inside that
  profile;
- review generic logical components, provider services, supporting resources,
  edges, tiering, evidence, and cost without a fixed-slot UI;
- retain historical `five-layer-baseline@1` as read-only compatibility.

Authority:

- `docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md`
- `docs/configuration_workspace/phases/PHASE_08_1_ARCHITECTURE_PROFILE_EXPERIMENT.md`
- `../../docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md`
- `../../docs/plans/phase_08_architecture_profiles_eventing/phase_08_service_bundle_closure.md`

The feature extends the existing Wizard BLoC and workspace shell. It does not
introduce a second wizard, graph editor, direct service call, cloud console, or
cross-profile winner.

## 2. Visual Layout (ASCII)

### Wide desktop/web: profile task, content width at least 960 px

```text
+ Configure Twin -----------------------------------------------------------+
| Define twin > Describe workload > Choose architecture > Prepare > Review |
|---------------------------------------------------------------------------|
| Tasks (280)            | Architecture profile                             |
| [*] Profile            | Choose the reviewed experiment boundary.         |
| [ ] Scenario           |                                                   |
| [ ] Device traffic     | + Five-layer v2 ------------------ [Selected] --+ |
| [ ] Processing         | | Events embedded in L1/L2; L3 hot = L5;       | |
| [ ] Retention          | | independent L4; 9 supported placements.       | |
| [ ] Twin activity      | | 5 responsibilities  View logical flow [v]     | |
| ...                    | +------------------------------------------------+ |
|                        | + Six-layer eventing v1 ------------------------+ |
|                        | | Same behavior plus independent Event Layer;    | |
|                        | | routing, replay, DLQ, bridge cost visible.      | |
|                        | | 6 responsibilities  View logical flow [v]      | |
|                        | +------------------------------------------------+ |
|                        | Historical profile (read only when loaded)       |
|---------------------------------------------------------------------------|
| Draft saved                               [Back] [Save draft] [Continue]   |
+----------------------------------------------------------------------------+
```

### Wide desktop/web: scenario task

```text
+ Describe workload --------------------------------------------------------+
| Profile: Six-layer eventing v1                                            |
|---------------------------------------------------------------------------|
| Core scenario                         | Event scenario                     |
| (o) Small  ( ) Medium  ( ) Large      | (o) Small  ( ) Medium  ( ) Large  |
| Device/twin/dashboard defaults         | Immutable rates, fan-out, payload |
| [Edit supported core fields]           | [Read scenario details]           |
|---------------------------------------------------------------------------|
| Events are required for both profiles. No event feature switches exist.   |
| Storage: hot [0,H), cool [H,C), archive [C,A), expire at A.               |
+----------------------------------------------------------------------------+
```

### Wide desktop/web: resolved architecture review

```text
+ Review recommendation ----------------------------------------------------+
| Six-layer eventing v1 | Large | EUR | Complete | estimated 123.45/month  |
|---------------------------------------------------------------------------|
| Logical flow                                                               |
| [L1 AWS] -> [L2 AWS] -> [Event Azure] -> [L3 hot/L5 GCP] -> [L4 Azure]   |
|                 bridge ^             raw query | twin projection           |
|---------------------------------------------------------------------------|
| Primary responsibilities               | Supporting resources              |
| L1 AWS  IoT Core                       | GCP scheduled tiering job          |
| L2 AWS  Lambda / Step Functions        | AWS->Azure source bridge           |
| EV Azure Event Hubs / Service Bus      | failure store / logs               |
| L3 GCP  Firestore / Storage tiers      | typed L3 reader                     |
| L4 Azure Digital Twins                 | Twin projection adapter             |
| L5 GCP  Grafana OSS                    | ...                                 |
|---------------------------------------------------------------------------|
| [Cost and evidence v] [Edges and limitations v]       [Select this run]   |
+----------------------------------------------------------------------------+
```

### Compact web: below 800 px

```text
+ Configure Twin --------------------------+
| Describe workload / Profile        [v]   |
|-------------------------------------------|
| Architecture profile                      |
| + Five-layer v2 ------------------------+ |
| | Events embedded | 5 responsibilities | |
| | [Selected] [Logical flow v]           | |
| +---------------------------------------+ |
| + Six-layer eventing v1 ---------------+ |
| | Independent Event Layer              | |
| | [Select] [Logical flow v]             | |
| +---------------------------------------+ |
|-------------------------------------------|
| [Back]                    [Continue]      |
+-------------------------------------------+
```

The compact resolved review stacks profile/run summary, logical flow, primary
components, supporting resources, and disclosures. Logical nodes wrap into a
vertical ordered list with labeled edges; no horizontal canvas or scrolling is
used. The existing supported lower bound of 640 px remains.

### Profile-change confirmation

```text
+ Change architecture profile --------------------------+
| The server reports these invalidations:                |
| - current calculation run                              |
| - selected deployment run                             |
| - incompatible user-function binding                  |
|                                                        |
| Preserved: Twin name, compatible workload fields       |
|                             [Cancel] [Change profile]   |
+--------------------------------------------------------+
```

## 3. Widget Tree

```text
WizardScreen [MODIFY]
`-- ConfigurationWorkspaceShell [REUSE]
    |-- ConfigurationTaskSidebar / Selector [MODIFY: new profile task]
    `-- task content switch [MODIFY]
        |-- ArchitectureProfileTask [NEW]
        |   |-- ProfileCatalogStatus [NEW, private]
        |   |-- ArchitectureProfileChoice [NEW]
        |   |   `-- LogicalProfileFlow [NEW]
        |   `-- ArchitectureProfileChangeDialog [NEW]
        |-- Step2Optimizer [MODIFY]
        |   |-- WorkloadScenarioPanel [NEW]
        |   |-- CalcForm [MODIFY: workload-v2 fields only]
        |   `-- Pricing/Calculate controls [REUSE, profile-gated]
        |-- ResolvedDeploymentSummary [MODIFY]
        |   |-- ResolvedProfileSummary [NEW]
        |   |-- LogicalResolvedFlow [NEW]
        |   |-- PrimaryComponentList [MODIFY: generic assignments]
        |   |-- SupportingResourceList [REUSE/MODIFY]
        |   `-- EdgeAndEvidenceDisclosure [NEW]
        `-- ConfigurationReviewTask [MODIFY: profile/workload summary]
```

State/service tree:

```text
management_api.dart
|-- ArchitectureApi [NEW]
`-- OptimizationApi [MODIFY request type]
api_service.dart [MODIFY]
demo_management_api.dart [MODIFY]
architecture_profile.dart [NEW]
architecture_workload.dart [NEW]
resolved_architecture.dart [NEW]
calc_params.dart [MODIFY]
wizard_event.dart [MODIFY]
wizard_state.dart [MODIFY]
wizard_bloc.dart + handlers [MODIFY]
configuration_journey.dart [MODIFY]
```

Reuse decisions are binding:

- Reuse the workspace shell, task navigation, footer, alert stack, Card,
  ExpansionTile, ChoiceChip/Radio patterns, pricing health surface, and run
  selection flow.
- A new profile choice is required because existing provider/pricing cards
  represent calculated results and cannot own revisioned profile selection.
- Extend existing resolved deployment review; do not create another result
  screen.
- Use Material `Icons` only and add no state-management, graph, or design
  package.

## 4. Component Specifications

### 4.1 Strict architecture models

**Files:**

- `lib/models/architecture_profile.dart` [NEW]
- `lib/models/architecture_workload.dart` [NEW]
- `lib/models/resolved_architecture.dart` [NEW]

Required immutable Equatable types:

| Type | Required fields |
|---|---|
| `ArchitectureProfileRef` | `profileId`, positive `profileVersion`, nonblank `displayName` |
| `ArchitectureProfileSummary` | ref, lifecycle, selectable, implemented, responsibility count, concise purpose/limitations, `contentDigest` |
| `ArchitectureProfileDetail` | summary, typed logical components, typed logical edges, supported workload field IDs, extension slot IDs, `contentDigest` |
| `LogicalProfileComponent` | unique ID, responsibility ID/label, kind, required capabilities |
| `LogicalProfileEdge` | unique ID, source/target IDs, contract ID, channel/purpose |
| `ArchitectureWorkloadOptions` | schema version, profile ref/digest, core presets, immutable event scenarios, editable field definitions |
| `CoreWorkloadPreset` | ID `core-small-v2`/`core-medium-v2`/`core-large-v2`, size, typed values |
| `EventingScenarioSummary` | immutable ID/version, size, event/publish/payload/fan-out/retry/DLQ/replay/ordering summary, digest |
| `ProfileChangePreview` | twin ID, current/target refs, expected revision, server invalidations/preservations, preview digest |
| `TwinArchitectureSelection` | twin ID, profile ref, selection revision, lifecycle/compatibility, selected/updated timestamps |
| `ResolvedArchitecture` | schema/profile/provider/catalog refs, resolution ID/digest, typed assignments, typed edges, supporting components, dimensions/evidence |
| `ResolvedComponentAssignment` | logical/component/provider/service IDs, display labels, primary/supporting role, capacity/evidence status |
| `ResolvedArchitectureEdge` | logical edge/contract/source/target IDs, transport kind, bridge/transfer/cost ownership and safe limitations |

Every parser must reject missing, wrong-type, and unexpected fields; unknown
schema versions; duplicate IDs; unresolved edge/component refs; noncanonical
provider values; blank labels; nonfinite/negative cost values; invalid digests;
and secret-like keys. Nested untyped `Map<String,dynamic>` is not retained
after parsing.

### 4.2 Workload v2

**File:** `lib/models/calc_params.dart` [MODIFY]

Replace new-profile serialization with a strict `WorkloadV2` value owned by
`CalcParams` during migration. It must contain:

- device count/type count, interval, message size;
- hot/cool/archive/expiry boundaries satisfying `1 <= H < C < A`;
- `twinEntityCount`;
- `aggregateDashboardRefreshesPerHour`;
- `apiCallsPerAggregateDashboardRefresh`;
- `dashboardActiveHoursPerDay`;
- `monthlyEditorSeats` and `monthlyViewerSeats`;
- `twinStateMaterializationsPerSecond`;
- `twinGraphUpdatesPerSecond`;
- currency, `corePresetId`, and required `eventingScenarioId`.

Legacy `useEventChecking`, notification, feedback, error-handling, 3D/scene,
and self-hosting fields remain parseable only through a separate historical
adapter. They must never be emitted for a v2 calculation.

### 4.3 Management API capability

**Files:**

- `lib/services/management_api.dart` [MODIFY]
- `lib/services/api_service.dart` [MODIFY]
- `lib/demo/demo_management_api.dart` [MODIFY]

Add `ArchitectureApi` with exact methods:

```dart
Future<List<ArchitectureProfileSummary>> listArchitectureProfiles();
Future<ArchitectureProfileDetail> getArchitectureProfile(
  ArchitectureProfileRef ref,
);
Future<ArchitectureWorkloadOptions> getArchitectureWorkloadOptions(
  ArchitectureProfileRef ref,
);
Future<TwinArchitectureSelection> getTwinArchitectureProfile(String twinId);
Future<ProfileChangePreview> previewTwinArchitectureProfileChange(
  String twinId,
  ArchitectureProfileRef target,
);
Future<TwinArchitectureSelection> changeTwinArchitectureProfile(
  String twinId,
  ProfileChangePreview preview,
);
Future<ResolvedArchitecture> getTwinResolvedArchitecture(String twinId);
Future<ResolvedArchitecture> getOptimizerRunResolvedArchitecture(String runId);
```

`OptimizationApi.createOptimizerRun` must accept a typed request carrying the
profile ref/revision, workload v2, event scenario ID/digest, and optional exact
pricing-evidence version. Live and demo implementations must expose identical
semantics. The mutating profile change is never automatically retried.

### 4.4 Wizard state and journey

**Files:**

- `lib/bloc/wizard/wizard_state.dart` [MODIFY]
- `lib/bloc/wizard/wizard_event.dart` [MODIFY]
- `lib/bloc/wizard/wizard_bloc.dart` and focused handlers [MODIFY]
- `lib/features/configuration_workspace/domain/configuration_journey.dart` [MODIFY]

Add `ConfigurationTaskId.architectureProfile` before
`scenarioAndCurrency`; replace the new-profile `processing` and
`twinCapabilities` task projection with `twinActivity` and `dashboardUsage`.
The historical adapter may still route legacy drafts to their old read-only
summary. `WizardState` must own typed catalog/detail/options,
persisted selection/revision, profile-change phase/preview, selected core/event
scenario IDs, resolved architecture phase/value/error, and historical mode.

The new-profile workload order is Profile, Scenario and currency, Device
traffic, Retention, Twin activity, and Dashboard usage. The journey marks those
tasks blocked until an implemented active profile and compatible scenario are
selected. Calculation/recommendation are blocked
until pricing and all profile/workload readiness are complete. Cloud access is
derived from the selected resolved architecture, never `cheapestPath`.

### 4.5 Presentation components

| Component/file | Constructor inputs | State form | Visual rules |
|---|---|---|---|
| `presentation/architecture_profile_task.dart` [NEW] | catalog/detail/options/selection phases; callbacks | Stateless BLoC consumer from parent | Existing content max width, `AppSpacing.lg/md/sm`, ThemeData text, provider-neutral surface colors |
| `presentation/architecture_profile_choice.dart` [NEW] | summary, selected, disabled, onSelect/onExpand | Stateless | Card with radio semantics, status Chip, max two-line purpose, no marketing art |
| `presentation/logical_profile_flow.dart` [NEW] | typed nodes/edges, optional resolved providers | Stateless | Wrap/Column layout; Material icons; labeled edges; no CustomPainter/canvas dependency |
| `presentation/architecture_profile_change_dialog.dart` [NEW] | server preview, busy/error, confirm/cancel | Stateful only for focus; BLoC state remains external | Existing dialog spacing/actions; scrollable invalidation list; destructive confirmation color from theme |
| `presentation/workload_scenario_panel.dart` [NEW] | typed presets/scenarios/selection callbacks | Stateless | Two grouped selections wide, stacked compact; disclosure details |
| `lib/widgets/results/resolved_deployment_summary.dart` [MODIFY] | typed resolution review and run selection | Stateless | Generic component/edge lists, progressive disclosures, no five-slot assumptions |

No component owns HTTP, persistence, provider logic, or raw JSON.

## 5. Responsive Behavior

| Breakpoint | Width | Behavior |
|---|---|---|
| Wide Desktop | >= 1440 px | Existing sidebar plus content; scenario groups two columns; resolved primary/supporting lists two columns |
| Narrow Desktop / Web | 800-1439 px | Sidebar retained where current shell allows; cards one column when content below 960 px; logical flow wraps |
| Compact Web | < 800 px, supported to 640 px | Existing task selector replaces sidebar; all cards/buttons stack; logical edges become labeled vertical rows; dialogs constrain and scroll |

At 200% text, cards grow vertically, labels wrap, and no status or action is
clipped. No screen adds horizontal page scrolling.

## 6. State Flow (BLoC)

The existing `WizardBloc` owns this feature because profile, workload,
calculation, deployment selection, and invalidation form one draft state
machine. Riverpod continues to provide the runtime `ManagementApi`; widgets do
not read it directly.

Required events:

| Event | Payload | Side effect |
|---|---|---|
| `WizardArchitectureCatalogRequested` | none | list profiles; hydrate current selection in edit mode |
| `WizardArchitectureProfileOpened` | profile ref | load strict detail and workload options |
| `WizardArchitectureProfileSelected` | target ref | request server preview or select directly only for a new unpersisted draft |
| `WizardArchitectureProfileChangeConfirmed` | preview digest/revision | PUT exact preview; reload selection/options; clear invalidated state from response |
| `WizardArchitectureProfileChangeCancelled` | none | discard transient preview |
| `WizardCoreScenarioSelected` | preset ID | project typed defaults into workload draft |
| `WizardEventScenarioSelected` | scenario ID | bind immutable scenario ref/digest |
| `WizardWorkloadV2Changed` | typed field/value | validate only profile-supported fields |
| existing calculate event [MODIFY] | typed calculation request | create profile-scoped run through Management |
| existing run selected [MODIFY] | run ID | hydrate matching resolved architecture and readiness |
| `WizardResolvedArchitectureRetried` | run/twin context | retry only the read |

```text
Widget
  -> WizardEvent
  -> WizardBloc
  -> ArchitectureApi / OptimizationApi
  -> Management API :5005
  -> strict DTO parser
  -> WizardState.copyWith
  -> ConfigurationJourney projection
  -> Widget
```

Loading generations/tokens must prevent a late detail/options response from a
previous profile overwriting the current selection. A stale preview conflict
clears the preview, reloads current selection, and requires explicit
reconfirmation.

## 7. Design Tokens

Reuse `AppSpacing`, `AppColors.getProviderColor`, ThemeData color scheme,
typography, button, card, chip, focus, and dialog themes. Add only named tokens
that are proven missing during implementation:

- `AppSpacing.profileChoiceMinHeight` if current minimum-interactive/card
  tokens cannot express the accessible card layout;
- no new literal colors, TextStyles, radii, durations, or breakpoints inside
  widgets.

Any new token must be committed before its first widget use and receive
light/dark tests. Profile identity must not use provider colors.

## 8. Interactions & Animations

- Profile cards use standard Material hover/focus/pressed states and radio
  semantics; selecting the current row is a no-op.
- Logical-flow disclosure uses the existing ExpansionTile animation; no custom
  motion is added.
- Catalog/detail/options loading uses one inline progress indicator in the
  content header while preserving already loaded content on refresh.
- Catalog empty/error and detail/option errors are inline with one Retry
  action. Mutating profile-change errors stay in the dialog; calculation
  errors use the existing workspace alert stack.
- The confirmation dialog traps focus, closes on Escape only when not busy,
  and restores focus to the initiating profile row.
- A stale response closes its invalid preview and announces that a fresh
  confirmation is required.
- Empty resolved architecture is a bounded “calculate/select a run first”
  state, not a blank graph.

## 9. Accessibility

- Tab order follows task navigation, heading, profile rows, disclosures,
  scenario groups, fields, then footer actions.
- Every profile row announces display name, version, selection/availability,
  responsibility count, and concise limitation.
- Every logical node announces responsibility, provider/service when resolved,
  and status. Every edge announces source, target, contract purpose, and local
  or bridge transport.
- Radio groups expose one selected item; invalidation dialog lists are
  announced under a descriptive heading.
- Enter/Space selects focused rows; Escape closes disclosures/dialog when safe.
- Focus is visible in light/dark themes. Body text meets 4.5:1 and large/status
  text 3:1; color is never the only provider or readiness cue.
- At 200% text and 640 px width there is no clipped control or horizontal page
  scroll.

## 10. Integration Points

Management API endpoints consumed:

| Method | Path | Request body | Response shape | Notes |
|---|---|---|---|---|
| GET | `/architecture-profiles` | - | strict list of profile summaries | Returns historical plus active profiles; UI filters selection by server flags |
| GET | `/architecture-profiles/{id}/versions/{version}` | - | strict profile detail | Typed logical nodes/edges |
| GET | `/architecture-profiles/{id}/versions/{version}/workload-options` | - | `architecture-workload-options.v1` | New Management projection of frozen presets/scenarios |
| GET | `/twins/{id}/architecture-profile` | - | selection/revision | Current draft selection |
| POST | `/twins/{id}/architecture-profile/change-preview` | target ref and expected revision | server invalidation preview/digest | No client inference |
| PUT | `/twins/{id}/architecture-profile` | target ref, expected revision, preview digest | updated selection plus invalidation result | No automatic retry |
| POST | `/twins/{id}/optimizer-runs/` | profile ref/revision, workload v2, scenario ref/digest, pricing version | typed run detail | Replaces legacy params for new profiles |
| GET | `/optimizer-runs/{run_id}/resolved-architecture` | - | strict resolved architecture | Must match run/profile/digest |
| GET | `/twins/{id}/resolved-architecture` | - | selected/latest resolved architecture | Edit/review hydration |

Existing route registrations remain:

| Route | Screen | Guards |
|---|---|---|
| `/twins/new` | `WizardScreen` / Configuration Workspace | authenticated |
| `/twins/{id}/edit` | same screen | authenticated, owned Twin, editable state |

No direct request to ports 5003 or 5004 is permitted.

## 11. Test Plan

### Strict models and API adapter

| # | Type | Test | Expected hard assertion |
|---|---|---|---|
| 1 | Happy | Parse Five-layer detail/options fixture | Exact nodes, edges, presets, scenarios, digest |
| 2 | Happy | Parse Six-layer resolved mixed-provider fixture | Exact Event Layer, bridge, supporting resources and costs |
| 3 | Unhappy | Unknown schema/version or wrong field type | `FormatException`, no partial value |
| 4 | Unhappy | Duplicate IDs/unresolved edge/secret-like field | Fail closed with exact contract error |
| 5 | Edge | Historical @1 summary | Parsed read-only and never selectable |
| 6 | Edge | Empty catalog | Exact empty state, no default selection |
| 7 | Edge | Nonfinite/negative cost | Rejected |
| 8 | Edge | Unknown provider/service status | Rejected |
| 9 | Edge | API returns target Twin/run mismatch | Rejected |
| 10 | Edge | Demo/live fixtures | Same typed interface and identity invariants |

### Wizard BLoC and journey

| # | Type | Test | Expected hard assertion |
|---|---|---|---|
| 1 | Happy | New draft selects Five v2 then scenarios | Workload tasks available; calculation request has exact refs |
| 2 | Happy | Six-layer run selected | Resolved Event Layer/bridge and provider-derived cloud access visible |
| 3 | Unhappy | Catalog/detail/options API failure | Exact retryable phase; existing draft preserved |
| 4 | Unhappy | Stale preview conflict | Preview cleared, selection reloaded, confirmation required again |
| 5 | Edge | Rapid profile A then B loads | Late A response cannot overwrite B |
| 6 | Edge | Profile change invalidates run/binding | Only server-listed state cleared |
| 7 | Edge | Missing event scenario | Calculation blocked with exact journey reason |
| 8 | Edge | Single-cloud resolution | No bridge/egress; cloud access requires one provider |
| 9 | Edge | Remote L4 | L3/L5 remain co-located; projection edge shown; no L4-to-L5 |
| 10 | Edge | Historical edit | Read-only review, no new calculation/deployment |

### Widgets/accessibility

| # | Type | Test | Expected hard assertion |
|---|---|---|---|
| 1 | Happy | Select profile/scenarios by keyboard | Exactly one selected semantics node per group |
| 2 | Happy | Expand resolved flow/evidence | Exact nodes/edge labels visible |
| 3 | Unhappy | Empty/error catalog | Exact message and one Retry action |
| 4 | Unhappy | Confirmation mutation fails | Dialog remains; safe error visible; no local selection change |
| 5 | Edge | 640/799/800/959/960/1440 widths | No overflow and expected stack/column layout |
| 6 | Edge | 200% text and long labels | No clipped action or horizontal page scroll |
| 7 | Edge | Light/dark | Status readable without color-only meaning |
| 8 | Edge | Dialog Escape/busy | Closes only when safe and restores focus |
| 9 | Edge | Resolved many supporting resources | Disclosure scrolls/wraps without blank graph |
| 10 | Edge | L4 and L5 same/different provider labels | Correct service and edge semantics |

### Real Management integration and commands

Integration tests must start the Docker stack through the repository wrapper,
use authenticated Management API :5005, create no cloud resource, and assert:
catalog/detail/options; selection preview/digest/change; stale revision;
Five-layer and Six-layer optimizer runs; single/mixed resolved architecture;
run selection/readiness; ownership isolation; and absence of direct ports
5003/5004 in the Flutter client.

Mandatory command sequence from the repository root:

```bash
./thesis.sh test backend
./thesis.sh test deployment-contract
./thesis.sh test frontend
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
docker --context orbstack compose --profile docs run --rm docs mkdocs build --strict
```

Then run release builds for Web and the available macOS/Linux host targets;
Windows runs in CI. Record running services before the integration run and stop
only services started by that run, including on failure; do not issue a blanket
prune or stop user-owned containers. No real cloud E2E is scheduled.

### Documentation phase

After tests and before final review, update the Configuration Workspace
roadmap/phase, FR tracker and #138 status, `FRONTEND_ARCHITECTURE.md`, Flutter
README, Phase 8 mini-roadmap/handoff, and current docs-site profile/workload/
deployment-review pages with exact implemented behavior and verification.
Create
`twin2multicloud_flutter/docs/configuration_workspace/implementation/architecture_profile_experiment.md`
as the component/state/API reference. Strict MkDocs and link checks are
mandatory. Research interpretation stays in `docs/research/`; LaTeX remains
untouched.

## 12. Definition of Done

- [ ] Every model, API method, event, state, component, and journey rule in
      Sections 3-6 is implemented; none is optional.
- [ ] New-profile requests contain workload v2 and one immutable event scenario
      and contain none of the retired feature flags.
- [ ] Only active/implemented Five-layer v2 and Six-layer v1 are selectable;
      historical @1 remains read-only.
- [ ] Functional completeness precedes profile-local cost ranking.
- [ ] Generic resolved review covers primary/supporting components, edges,
      tiering, bridges, evidence, limitations, and single-cloud absence rules.
- [ ] Flutter uses Management API only; live and demo adapters have strict
      parity.
- [ ] Loading, empty, error, stale, historical, unsupported, conflict, and
      retry states are explicit.
- [ ] `flutter analyze` and full Flutter tests pass with hard assertions.
- [ ] Credential-free real Management integration passes and creates no cloud
      resources.
- [ ] Web/macOS/Linux build gates and Windows CI pass.
- [ ] Accessibility, keyboard, light/dark, responsive, and 200% text checks
      pass.
- [ ] Current frontend documentation and implementation reference are updated;
      no LaTeX file is changed.
- [ ] Commit history uses clean `[AI-0803-PROF]` scoped commits.
- [ ] Two implementation reviews reach zero unresolved findings before the
      final profile-workflow commit.

### Plan review record

| Pass | Perspective | Result |
|---|---|---|
| 1 | Architect | Zero unresolved findings on 2026-08-03 after aligning the plan with the implemented Configuration Workspace, replacing legacy processing/3D tasks for new profiles, separating profile-local ranking from service-bundle selection, using strict nested DTOs, and correcting the actual `ResolvedDeploymentSummary` reuse boundary |
| 2 | Builder | All 20 plan-review criteria pass on 2026-08-03 with zero unresolved findings after pinning API datatypes, race/stale behavior, exact BLoC ownership, responsive layouts, hard test assertions, OrbStack real-Management commands, documentation phase, and clean commit gates |
