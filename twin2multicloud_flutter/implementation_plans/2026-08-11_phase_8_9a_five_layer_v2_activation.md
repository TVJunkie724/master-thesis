# Implementation Plan: Phase 8.9A Five-layer v2 Activation

## 0. Git Branch

- **Branch name:** `codex/phase-8-9a-layer-access`
- **Base branch:** the reviewed Phase 8.9A provider/runtime foundation through
  `c72213c1`.
- **Merge strategy:** merge commit; no rebase. The user controls later
  integration into the default branch.
- **Session/commit prefix:** `[AI-0811-LACC]`.
- **Branch decision:** activation is the final atomic slice of the already
  isolated 8.9A branch. A nested UI-only branch would split one public
  Management contract across branches, so this reviewed corrective plan stays
  on the current branch. The Six-layer branch starts only after this branch is
  reviewed and committed.
- **Authorization:** the user requested complete Phase 8 planning,
  implementation, repeated review, and clean commits. No live cloud execution
  is authorized.

## 1. Summary

Activate `five-layer-baseline@2` as the first selectable runtime profile
without creating a false UI capability. The current Phase 8.7 Flutter boundary
correctly renders an empty catalog, but its optimizer input and resolved-result
parsers still understand only historical `@1`. Phase 8.9A therefore publishes
the following atomically:

- the exact immutable Small, Medium, and Large `five-layer-workload.v2`
  scenarios with mandatory embedded-event scenario IDs;
- selectable/default `five-layer-baseline@2` through the Management API;
- profile-aware optimizer-run creation through the existing Management
  endpoint;
- typed `resolved-twin-architecture.v2` and
  `resolved-deployment-specification.v2` Flutter review;
- an evaluation-only result state while the RDS v2 document still carries
  live-capacity blocking gates; calculation evidence remains reviewable but
  cannot be selected or packaged for a real deployment;
- live/demo adapter parity and real local Management integration;
- truthful readiness: offline profile publication may coexist with explicit
  live-capacity blocking gates and never claims a cloud deployment.

This is a bounded thesis-PoC activation, not a general workload editor. Users
select one frozen reproducible scenario and a display currency. They may
inspect the scenario fields across the existing Workload tasks, but cannot
author arbitrary values that the backend would reject. Historical `@1` remains
read-only, verifiable, destroyable, and not newly selectable.

Authority remains the current Configuration Workspace in
`FRONTEND_ARCHITECTURE.md`, the Phase 8.7 profile workflow, and
`docs/plans/phase_08_architecture_profiles_eventing/phase_08_9a_9b_execution_plan.md`.

## 2. Visual Layout (ASCII)

### Wide desktop/web: scenario task

```text
+ Configure Twin ---------------------------------------------------------+
| Define twin > Architecture > Workload > User Logic > Optimize > Deploy |
|-------------------------------------------------------------------------|
| Tasks (280)          | Scenario and currency                            |
| [*] Scenario         | Use one frozen thesis workload.                  |
| [ ] Device traffic   |                                                  |
| [ ] Processing       | + Small --------+ + Medium ------+ + Large -----+|
| [ ] Retention        | | 100 devices   | | 4,000        | | 30,000     ||
| [ ] Twin activity    | | Event Small   | | Event Medium | | Event Large||
|                      | | [Selected]     | | [Select]     | | [Select]   ||
|                      | +---------------+ +--------------+ +------------+|
|                      | Currency [ USD v ]                                |
|                      | Events are embedded and cannot be disabled.       |
|-------------------------------------------------------------------------|
| Draft saved                              [Back] [Save draft] [Continue] |
+--------------------------------------------------------------------------+
```

### Compact web: scenario task

```text
+ Configure Twin -------------------------+
| [Task: Scenario and currency          v] |
|------------------------------------------|
| Scenario and currency                    |
| + Small -------------------------------+ |
| | 100 devices · Event Small [Selected] | |
| +--------------------------------------+ |
| + Medium ------------------------------+ |
| +--------------------------------------+ |
| + Large -------------------------------+ |
| +--------------------------------------+ |
| Currency [ USD                       v]  |
| Events are embedded and always active.   |
|------------------------------------------|
| [Back] [Save draft] [Continue]           |
+------------------------------------------+
```

### Remaining Workload tasks

```text
+ Processing -------------------------------------------------------------+
| Frozen scenario: Small                         [Change scenario]          |
|-------------------------------------------------------------------------|
| Embedded domain events                                                  |
| Event scenario     eventing-small-v1                                    |
| Rule/action check  mandatory                                             |
| Workflow           four fixed synthetic actions                          |
| Device feedback    mandatory                                             |
|                                                                          |
| Values are fixed for the reproducible thesis comparison.                 |
+--------------------------------------------------------------------------+
```

Device traffic, Retention, and Twin activity use the same read-only
label/value surface for their applicable fields. The existing Optimization
review remains generic and adds no Five-layer slot editor.

## 3. Widget Tree

```text
ConfigurationWorkspaceShell [REUSE]
`-- Step2Optimizer [MODIFY]
    |-- workload task header [REUSE]
    |-- CalcForm [MODIFY]
    |   |-- legacy @1 form projection [REUSE, historical only]
    |   `-- FiveLayerV2WorkloadForm [NEW, private in calc_form.dart]
    |       |-- scenarioAndCurrency
    |       |   |-- SegmentedButton/focusable scenario cards [NEW]
    |       |   |-- DropdownButtonFormField<String> [REUSE]
    |       |   `-- embedded-event notice [NEW]
    |       `-- selected-task read-only DefinitionList rows [NEW]
    `-- ResolvedDeploymentSummary [MODIFY]
        |-- ResolvedArchitectureReview [MODIFY type boundary]
        `-- generic RDS component/evidence rows [MODIFY]
```

There is no new screen, route, state-management owner, package, graph editor,
or cloud-service call.

## 4. Component Specifications

### `lib/models/calc_params.dart` [MODIFY]

`CalcParams` remains the Wizard/API value type so historical persistence and
existing widgets do not require an unsafe untyped union. It gains a strict
wire-variant discriminator and exact Five-layer-v2 factories:

| Member | Type | Rule |
|---|---|---|
| `schemaVersion` | `String?` | `null` means historical v1; v2 must equal `five-layer-workload.v2` |
| `scenario` | `FiveLayerWorkloadScenario?` | required for v2; `small`, `medium`, or `large` |
| `eventingScenarioId` | `String?` | derived from the selected core scenario; never independently editable |
| `isFiveLayerV2` | `bool` | true only for the exact v2 variant |
| `fiveLayerV2(...)` | factory | emits one canonical S/M/L fixture with selected USD/EUR currency |
| `fromJson(...)` | factory | strict exact-key parsing for v2; retains historical compatibility parsing for v1 |
| `toJson()` | map | emits either the exact v1 shape or exact v2 shape, never a merged payload |

Common getters continue to project devices, retention, dashboard use, and
Twin entities so existing read-only review widgets remain typed. V2 exposes
no legacy event flags, 3D flags, GCP feature toggles, or error-handling flag on
the wire.

Currency is not part of the S/M/L scenario identity. The scenario matcher in
Management, Optimizer, and the persisted cost-ledger validator compares every
frozen Core field except `currency`, then validates currency independently as
USD/EUR. This closes the current contradiction where the schema advertises
EUR but fixture equality accepts only USD; it does not make any workload
dimension editable.

### `lib/widgets/calc_form/calc_form.dart` [MODIFY]

| Parameter | Type | Required | Default |
|---|---|---:|---|
| `profileId` | `String?` | no | `null` |
| `profileVersion` | `String?` | no | `null` |
| existing parameters | unchanged | as today | unchanged |

When the exact profile ref is `five-layer-baseline@2`, the form initializes to
Small only when no persisted v2 value exists. Scenario changes emit one full
canonical `CalcParams`; currency changes preserve the scenario. Device,
Processing, Retention, and Twin activity tasks are read-only projections.
When a historical `@1` Twin is loaded, the legacy form remains reviewable and
cannot create a new optimizer run because the profile is non-selectable.

The Five-layer form is private because there is no second public workflow. It
uses existing `AppSpacing.sm/md/lg`, the current card theme/color scheme, and
`ThemeData` typography. No new design token is necessary.

### `lib/screens/wizard/step2_optimizer.dart` [MODIFY]

Pass the server-owned selected profile ref into `CalcForm`. The summary uses
v2 terminology (`Embedded`, event scenario, Twin entities, aggregate refresh)
when appropriate and retains historical labels for `@1`. The calculate event
and scroll behavior remain BLoC-owned and unchanged.

### `lib/models/resolved_twin_architecture.dart` [MODIFY]

Replace the v1-named public value with one typed model that records
`schemaVersion` and accepts only v1/v2. V2 accepts only the contract statuses
`offline_contract_fixture` and `publishable`, requires `native_v2`, pairs the
first status with an RDS-v2 offline readiness document and the second with an
RDS-v2 deployment-ready document, and preserves the otherwise shared
assignment/edge/cost/completeness invariants. V1 retains its current strict
rules. Unknown versions still fail closed.

### `lib/models/resolved_deployment_specification.dart` [MODIFY]

Add strict `ResolvedDeploymentSpecificationV2`, typed v2 component
selections, dimensions, bindings, pinned references, fixed dimensions, and
readiness. Both supported versions expose typed presentation data without
flattening the different contracts: v1 retains architecture/support component
groups; v2 exposes profile ref, providers, all exact component selections,
optimization evidence, readiness, run ID, and digest. V2 must validate exact
keys, unique/resolved IDs, provider values, digest, Five-layer L3-hot/L5
co-location, and profile/schema pairing. Secret-like fields fail closed.

### `lib/widgets/results/resolved_deployment_summary.dart` [MODIFY]

Consume the schema-specific typed presentation projection rather than casting
to v1. Rows show responsibility/assignment, provider, every exact
implementation component, region, capacity/usage dimensions, readiness
status/blocking gates, and exact digests. V1 keeps its current labels. V2
groups every service selection under its logical responsibility and never
invents additional architecture layers or a primary/supporting distinction
absent from the contract.

`ResolvedDeploymentReview` adds an `evaluationOnly` state. It is derived from
the v2 readiness object even though the outer compatibility value confirms
that the specification schema itself is supported. The Wizard does not call
the deployment-selection endpoint for this state; it loads the run's resolved
architecture directly for review and keeps Prepare deployment/Finish blocked.

### `lib/demo/demo_management_api.dart` [MODIFY]

The demo catalog contains exactly active `five-layer-baseline@2`, new demo
Twins pin `@2`, and calculation accepts the same three scenarios. The demo
returns deterministic v2 RTA/RDS evidence using the same parsers as live
responses. It performs no network or cloud operation.

### Optimizer activation boundary [MODIFY]

`2-twin2clouds/api/calculation.py` requests
`offline_contract_fixture` for the normal unsupervised Five-layer-v2
calculation path. The repository already knows how to calculate and rank these
complete candidates with their live-capacity blockers; it must not request
`publishable` and then silently pretend those gates were satisfied. The
architecture-resolution environment default becomes enabled only in the same
activation commit as the profile definitions.

`five_layer_v2_workload.py` matches the immutable scenario independently of
USD/EUR and still requires the exact same-size event scenario. All other
differences remain `ARCH_WORKLOAD_INCOMPATIBLE`.

The same boundary publishes one immutable Five-layer v2 rate card per provider
from a strict source manifest. Every registered implementation component and
cross-cloud route role is either billed exactly once or explicitly classified
as non-billable. USD is the base currency; EUR uses one pinned conversion
shared by all three provider snapshots. Azure IoT Hub uses exact frozen
Small/Medium/Large tier outcomes. Azure Large Cosmos cost evaluation uses its
108,000-RU/s rounded storage/operation proxy rather than an unresolved zero;
the separate request-charge and autoscale live gates still prevent
deployment until a supervised measured value is supplied.

### Management activation and persistence boundary [MODIFY]

Management publishes only `five-layer-baseline@2`, makes it the new-Twin
default, and enables profile resolution in the same commit. Its v2
architecture validator accepts an internally consistent
`offline_contract_fixture` RTA/RDS pair for immutable cost evidence. The
existing outer `deployment_compatibility_status == ready` continues to mean
that the RDS schema/digest is supported; actual selection eligibility is the
nested RDS readiness contract. `select_for_deployment` and the deployment
package builder require `readiness.status == deployment_ready` and an empty
blocking-gate list. An offline pair returns the stable
`DEPLOYMENT_CAPACITY_EVIDENCE_PENDING` conflict and is never selected.

No database status migration is introduced merely to duplicate the immutable
RDS readiness field. Historical rows and compatibility values remain intact.

## 5. Responsive Behavior

| Breakpoint | Width | Behavior |
|---|---:|---|
| Wide desktop | `>= 1200` | existing sidebar; three scenario cards in one row; evidence rows use their existing fixed columns |
| Medium desktop/web | `960-1199` | existing sidebar; scenario cards wrap as two plus one; resolved rows retain generic wide form when text scale permits |
| Compact web | `< 960`, supported to `640` | existing task selector; scenario cards stack; label/value rows stack below the existing `720` evidence breakpoint |

At 200% text, scenario cards grow vertically, labels wrap, and no fixed-height
text container or horizontal page scroll is introduced.

## 6. State Flow (BLoC)

`WizardBloc` remains the single owner. No new BLoC or Riverpod feature state is
introduced.

| Event | Payload | Effect |
|---|---|---|
| existing `WizardArchitectureProfileSelected` | server profile ref | server preview/select; invalidated workload is cleared exactly as returned |
| existing `WizardCalcParamsChanged` | canonical `CalcParams` v1/v2 | update draft input and invalidate a nonmatching saved run |
| existing `WizardCalculationRequested` | none | POST exact variant to Management; never call Optimizer directly |
| existing run selection/read events | run ID | parse RTA/RDS v1 or v2 and update review/readiness |

```text
Scenario/currency widget
  -> WizardCalcParamsChanged(canonical Workload v2)
  -> WizardBloc
  -> state.calcParams
  -> WizardCalculationRequested
  -> ManagementApi.createOptimizerRun
  -> POST /twins/{id}/optimizer-runs/
  -> Management -> Optimizer
  -> typed run + offline RTA v2 + RDS v2 with exact blockers
  -> WizardState.copyWith
  -> generic evaluation review; no deployment selection while blocked
```

Loading, API error, empty profile, historical profile, invalidated workload,
unknown schema, evaluation-only readiness, unsupported readiness, and
stale-run states retain explicit state branches. Profile changes never
silently translate an old workload. The Optimizer produces
`offline_contract_fixture` for this unsupervised local path; Management accepts
and persists the immutable calculation evidence, but its selection boundary
rejects any RDS v2 whose readiness is not `deployment_ready` with a stable
capacity-evidence-pending error. No live gate is marked satisfied by local
tests.

## 7. Design Tokens

No new colors or typography tokens are required. Reuse the existing spacing
scale and add the single workspace-specific `960` scenario-card breakpoint so
the documented one/two/three-column transitions are named rather than
hardcoded. The implementation uses:

- `AppSpacing.xs/sm/md/lg/xl`;
- `AppSpacing.configurationWorkloadCompactBreakpoint`;
- existing Configuration Workspace max widths and responsive breakpoints;
- `ThemeData.colorScheme` for selected/focus/error surfaces;
- `ThemeData.textTheme` for headings, labels, body, and evidence;
- Material `Icons.event_available`, `Icons.devices`, and existing cloud icons.

## 8. Interactions & Animations

- Tab order is Small, Medium, Large, currency, workspace navigation.
- Enter/Space selects the focused scenario; selecting the already selected
  scenario is idempotent.
- The existing Material selected/focus/hover state is used; no custom
  animation or package is added.
- Changing scenario or currency immediately emits canonical local state; the
  user still explicitly invokes Calculate.
- API calculation loading/error behavior remains the existing button/banner
  state. A v2 contract failure preserves the chosen scenario and shows the
  bounded Management error.
- An evaluation-only result shows its exact blocking gates and does not render
  Verify/Retry as though local interaction could satisfy live evidence.
- An empty catalog retains the existing blocking empty state. A historical
  profile renders read-only evidence and no enabled calculation action.

## 9. Accessibility

- Each scenario control has one semantic label containing size, device count,
  event scenario, and selected state.
- Exactly one scenario is selected; selection is not conveyed by color alone.
- Read-only fields use semantic label/value pairs and remain selectable text
  where technical IDs are shown.
- Existing focus traversal and visible Material focus rings are preserved.
- Body text targets at least 4.5:1 contrast; large/status text at least 3:1
  through the existing color scheme.
- At 200% text and every supported breakpoint, actions remain reachable and
  text is not clipped.

## 10. Integration Points

| Method | Path | Request | Response | Rule |
|---|---|---|---|---|
| GET | `/architecture-profiles` | none | active summaries | contains only `five-layer-baseline@2` after activation |
| GET | `/architecture-profiles/five-layer-baseline/2` | none | strict detail | includes Workload v2 field IDs and pinned digest |
| GET | `/twins/{id}/architecture-profile` | none | pinned selection | new Twin defaults to `@2`; historical Twin remains `@1` |
| POST | `/twins/{id}/optimizer-runs/` | `{params: five-layer-workload.v2}` | succeeded run + RDS v2 | Flutter calls Management only |
| GET | `/twins/{id}/resolved-architecture` | none | RTA v2 read | owner-scoped |
| GET | `/optimizer-runs/{id}/resolved-architecture` | none | RTA v2 read | run identity must match |

No SSE or route registration changes are required. Ports 5003/5004 remain
absent from Flutter source.

The activation commit also changes the repository/Compose defaults for
`ARCHITECTURE_PROFILE_RESOLUTION_ENABLED` to true. An explicit false override
remains a fail-closed operational rollback and never re-enables new `@1`
selection.

## 11. Test Plan

### Workload model/form/BLoC

| # | Type | Case | Hard assertion |
|---:|---|---|---|
| 1 | Happy | Small/USD initializes after `@2` selection | exact canonical fixture JSON including `eventing-small-v1` |
| 2 | Happy | Large/EUR is selected | exact Large fields and EUR; one BLoC event |
| 3 | Unhappy | unknown v2 field or wrong schema | `FormatException`; no partial model |
| 4 | Unhappy | mismatched core/event scenario | rejected; calculation API not called |
| 5 | Edge | Medium values round-trip persistence | exact JSON equality |
| 6 | Edge | historical v1 JSON loads | legacy projection unchanged |
| 7 | Edge | profile changes v1 -> v2 | old workload cleared; canonical v2 initialized only after selection |
| 8 | Edge | rapid Small -> Large | last selection wins; no auto-calculation |
| 9 | Edge | currency changes | scenario/event ID unchanged |
| 10 | Edge | 640/719/720/959/960/1199/1200 and 200% text | exact layout transition; zero overflow |

### RTA/RDS parsing and review

| # | Type | Case | Hard assertion |
|---:|---|---|---|
| 1 | Happy | canonical single-cloud Small v2 | exact profile/run/digest/providers/components/readiness |
| 2 | Happy | canonical three-cloud Large v2 | exact assignments, bridges, and blocking gates |
| 3 | Unhappy | digest or profile/schema pairing tampered | `FormatException` |
| 4 | Unhappy | unresolved binding/component/edge ID | `FormatException` |
| 5 | Edge | v1 historical fixture | unchanged supported review |
| 6 | Edge | unknown v3 | unsupported/fail-closed state, never deployable |
| 7 | Edge | single cloud | one provider and no cross-cloud evidence inferred |
| 8 | Edge | remote L4 | L3/L5 co-located, L4 independent, projection edge visible |
| 9 | Edge | live capacity blockers | explicit blocked readiness rows; no deployed claim |
| 10 | Edge | service-selection count > responsibility count | every selection renders without fake layers or invented roles |

### Real Management and demo integration

| # | Type | Case | Hard assertion |
|---:|---|---|---|
| 1 | Happy | new real local Twin | catalog/detail/selection are exact `@2` |
| 2 | Happy | Small calculation | Management persists v2 params, offline RTA v2, RDS v2, and exact live blockers; UI parses all |
| 3 | Unhappy | legacy params submitted for new `@2` Twin | stable Management validation error |
| 4 | Unhappy | owner B reads owner A run/profile | forbidden/not found with no leaked body |
| 5 | Edge | all nine L3/L5-to-L4 placements | remain resolvable locally and readiness is truthful |
| 6 | Edge | historical `@1` Twin | readable but detail target/calculation/redeploy fail closed |
| 7 | Edge | demo reset | returns deterministic `@2` catalog/selection/run |
| 8 | Edge | direct downstream-port scan | zero Flutter references to 5003/5004 |
| 9 | Edge | no CloudConnections/live evidence | calculation succeeds; automatic selection is skipped and deployment stays blocked |
| 10 | Edge | integration cleanup | only services started by the test are stopped |
| 11 | Edge | AWS TwinMaker account plan unavailable offline | successful result persists with explicit live-pricing gate; deployment selection fails closed |
| 12 | Edge | Azure Large Cosmos without measured RU fixture | non-zero 108,000-RU/s evaluation proxy is costed; request-charge/autoscale gates remain deployment-blocking |

The credential-free integration entrypoint keeps the normal seven-day pricing
freshness policy unchanged for ordinary runtime. For this deterministic
fixture-only gate it passes an explicit large `PRICING_CATALOG_MAX_AGE_DAYS`
to containers started by the test, so advancing wall-clock time cannot force a
provider pricing refresh. The calculation still pins and verifies the exact
repository-owned catalog digests; no price or live-capacity evidence is
fabricated.

The complex cross-contract state machine requires all listed edge cases; five
would not cover schema evolution, historical compatibility, profile
invalidation, responsiveness, and ownership independently.

## 12. Definition of Done

- [ ] Exact Workload v2 S/M/L variants are implemented in Flutter and no
      legacy event feature flag is emitted for `@2`.
- [ ] `five-layer-baseline@2` is the only new selectable/default profile;
      historical `@1` is unchanged and nonselectable.
- [ ] Flutter creates new-profile runs only through Management and parses both
      RTA v2 and RDS v2 strictly.
- [ ] Unsupervised v2 calculations persist as evaluation-only evidence; open
      live-capacity gates prevent selection/deployment with no fabricated
      success.
- [ ] Generic result review renders v1 and v2 without fixed Five-layer slot
      inference or fake Event-layer presentation.
- [ ] Demo/live adapters expose the same active profile and typed schemas.
- [ ] Offline readiness blockers remain visible and no cloud deployment,
      capacity measurement, or browser-sign-in claim is introduced.
- [ ] Unit/widget/integration hard assertions cover the cases in Section 11.
- [ ] `flutter analyze`, full Flutter tests, Web and macOS builds pass.
- [ ] Backend, deployment-contract, strict MkDocs, link, drift, security, and
      local OrbStack integration gates pass without live E2E.
- [ ] Concept, plan, and implementation reviews are repeated until zero
      unresolved findings.
- [ ] Clean `[AI-0811-LACC]` commits preserve generated copies with their
      canonical contract change.
- [ ] Six-layer work starts only from the reviewed, committed Five-layer v2
      activation digest.

### Plan review record

| Pass | Perspective | Result |
|---:|---|---|
| 1 | Architect + builder | Two findings: the proposed runtime path falsely required `publishable` while no live gate can be satisfied locally, and USD fixture equality contradicted the advertised USD/EUR currency contract. |
| 2 | Architect + builder | Zero unresolved findings after specifying the offline-evidence/deployment-blocked state end to end, prohibiting fabricated live evidence, and separating immutable scenario identity from validated display currency. |
| 3 | Concept + plan + audit | Two implementation findings: generated v2 schemas reverted EUR pricing evidence to USD-only, and Azure Large entered ranking with a zero autoscale quantity. |
| 4 | Concept + plan + audit | Zero unresolved findings after fixing the generator-owned EUR contract, publishing immutable provider cards, and replacing zero with the bounded storage/operation evaluation proxy while retaining all supervised deployment gates. |
