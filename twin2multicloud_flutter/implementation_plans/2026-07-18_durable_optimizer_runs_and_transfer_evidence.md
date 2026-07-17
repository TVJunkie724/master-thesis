# Durable Optimizer Runs and Transfer Evidence

**Status:** Approved for implementation  
**Issue:** [#116 Introduce route-aware cross-cloud transfer pricing contracts](https://github.com/TVJunkie724/master-thesis/issues/116)  
**Branch:** `codex/pricing-tier-finalization`  
**Base:** `master`

## 0. Delivery Contract

This slice completes the trusted calculation path from Flutter through the
Management API. It removes every client-authored optimizer-result write,
switches the configuration workspace to durable server-owned optimizer runs,
and exposes exact route evidence as optional, read-only detail.

The implementation targets Web, macOS, Windows, and Linux. It must not perform
live cloud deployments or provider mutations. Existing calculation results
without the additive transfer contract remain readable as historical data; no
missing evidence may be inferred or synthesized.

Planned commits:

1. `docs(flutter): plan durable optimizer runs`
2. `feat(flutter): use durable optimizer runs`
3. `feat(flutter): expose transfer route evidence`
4. `refactor(management): remove client-authored optimizer results`
5. `docs(pricing): finalize route evidence workflow`

## 1. Experience Summary

The user continues to calculate costs from the Optimization task in the
configuration workspace. The interaction stays compact:

- one calculation command;
- one authoritative result returned by a durable Management API run;
- a concise trace summary;
- collapsed exact-transfer evidence for technical inspection;
- no separate route editor, modal, or additional wizard page.

For a new twin, the first calculation creates the draft twin exactly once,
retains its ID even if calculation fails, and retries against that same twin.
The Management API performs calculation, contract validation, result
persistence, cheapest-path projection, and run-history persistence as one
server-owned workflow.

## 2. Responsive Layout

Wide desktop and web:

```text
+-----------------------------------------------------------------------+
| Calculation trace                                                     |
| [Publishable] [N records] [6 exact routes] [N field records]          |
|                                                                       |
| > Trace details                                                       |
| > Immutable pricing catalog evidence                                  |
| > Transfer route evidence                                             |
|   Solver: 486 paths | Winner: GCP -> ... -> AWS | deterministic tie   |
|   L1 -> L2   GCP europe-west1 -> Azure westeurope   EUR 0.42      [v] |
|   L2 -> L3   Azure westeurope -> AWS eu-central-1   EUR 0.31      [>] |
|   ... exactly six architecture edges ...                              |
|   > Shared billing pools                                              |
+-----------------------------------------------------------------------+
```

Compact desktop and narrow web:

```text
+--------------------------------------+
| Calculation trace                    |
| [Publishable] [6 exact routes]        |
| > Trace details                       |
| > Pricing catalog evidence            |
| > Transfer route evidence             |
|   486 evaluated paths                 |
|   L1 -> L2                            |
|   GCP europe-west1                    |
|   -> Azure westeurope                 |
|   EUR 0.42                        [v] |
|     Route class / network tier        |
|     Exact volume / evidence snapshot  |
|     > Tier contributions              |
|   ...                                 |
|   > Shared billing pools              |
+--------------------------------------+
```

All evidence sections are collapsed initially. Expanding a route must not
resize controls outside its own vertical flow or create horizontal scrolling.

## 3. Widget and Module Tree

```text
CalculationTraceSummary                         [MODIFY]
|-- _TraceHeader                                [EXTRACT]
|-- Wrap<_TraceChip>                            [REUSE]
|-- ExpansionTile "Trace details"               [REUSE]
|-- ExpansionTile "Pricing catalog evidence"    [REUSE]
`-- TransferRouteEvidence                       [NEW]
    |-- _SolverSummary                          [NEW]
    |-- List<TransferRouteEvidenceRow>           [NEW]
    |   `-- ExpansionTile
    |       |-- _RouteOverview                  [NEW]
    |       |-- _RouteTechnicalDetails          [NEW]
    |       `-- _TierContributionTable          [NEW]
    `-- ExpansionTile "Shared billing pools"    [NEW]

CalcResult                                      [MODIFY]
|-- TransferPricingContext                      [NEW TYPED MODEL]
`-- CompletePathOptimizationDiagnostics         [NEW TYPED MODEL]

OptimizationApi                                 [MODIFY]
`-- createOptimizerRun(twinId, params)           [NEW CANONICAL COMMAND]

WizardBloc optimization handlers                [MODIFY]
|-- ensure draft identity for create mode
|-- invoke one durable run command
|-- retain draft identity on retryable failure
`-- never write optimizer results from Flutter

Management API write contracts                  [MODIFY]
|-- TwinConfigUpdate                            [REMOVE optimizer_result]
|-- WizardConfigurationService                  [REMOVE result mutation]
`-- optimizer-config/result                     [REMOVE ENDPOINT]
```

## 4. Component Specifications

### Typed Transfer Contract

The client accepts only:

- `complete-path-transfer-pricing.v1`;
- exactly the six fixed baseline edge identifiers;
- unique routes and billing pools;
- known provider, route-class, and network-tier values;
- finite, non-negative numeric amounts;
- integral byte/count fields;
- exact endpoint, evidence, snapshot, and tier-contribution fields required by
  the server contract.

Unknown contract versions or malformed present evidence fail closed with a
field-oriented `FormatException`. Error text must never echo payload values.
When both transfer context and complete-path diagnostics are absent, the result
is treated as honest historical data. If only one is present, parsing fails.

### Durable Optimizer Run

`OptimizerRunData` requires:

- run ID and twin ID;
- `succeeded` status for the synchronous create response;
- result summary;
- total monthly cost and currency;
- created/completed timestamps.

The embedded result summary is parsed through `OptimizationResultData`.
Flutter does not calculate, alter, or submit a cheapest-path projection.

### Transfer Evidence

The top level shows route count and deterministic solver summary. Each route
shows:

- segment and endpoint layers;
- source/destination provider and region;
- route class and provider network tier;
- exact charged byte volume;
- egress, bridge/glue, and total cost;
- billing-pool identifier;
- evidence record and immutable catalog snapshot;
- cumulative tier intervals, units, unit prices, and contributions;
- explicit assumptions.

Same-provider zero-cost routes are labelled as such and never presented as
missing data. Billing pools expose aggregate bytes, billing unit, bytes per
unit, and pool total. Technical identifiers remain secondary text.

## 5. Responsive Rules

- `>= AppBreakpoints.desktop`: endpoint and cost information share one row.
- `< AppBreakpoints.desktop`: endpoint, route metadata, and cost stack
  vertically.
- No viewport-width font scaling.
- Route rows have stable icon and disclosure-control dimensions.
- Long evidence IDs wrap and remain selectable.
- No nested cards; expanded evidence uses unframed rows and dividers.
- Windows/Linux/macOS/web receive identical information architecture.

## 6. State and Workflow

```text
WizardCalculateRequested
    |
    +-- invalid params/readiness --> local actionable error
    |
    +-- create mode without twin_id
    |      |
    |      `-- validate trimmed name --> create draft --> emit retained twin_id
    |
    `-- POST /twins/{twin_id}/optimizer-runs
           |
           +-- success
           |     -> parse strict run/result/evidence
           |     -> calculate Step 3 invalidation
           |     -> update result + warnings
           |
           `-- failure
                 -> retain existing/new twin_id
                 -> clear calculating state
                 -> sanitized actionable error
```

The existing BLoC command serialization remains authoritative. Calculation is
ignored while save or another calculation is active. Save Draft persists
user-authored configuration and deployment preparation only; it never rewrites
the calculated result.

## 7. Design Tokens

- Spacing: `AppSpacing` only.
- Breakpoints: `AppBreakpoints`.
- Semantic colors: `Theme.colorScheme` and existing `AppColors` status colors.
- Provider identity: existing provider color mapping.
- Typography: existing theme text styles; no hard-coded font sizes.
- Motion: native `ExpansionTile`, honoring platform reduced-motion behavior.

## 8. Interaction and Error States

- **Initial:** no result; existing empty optimization state remains.
- **Calculating:** existing command is disabled and progress is visible.
- **Successful current result:** six exact routes are announced in summary.
- **Historical result:** trace remains available, with a concise statement that
  exact route evidence predates the contract.
- **Malformed current result:** calculation/load fails closed; no partial route
  table is shown.
- **Run failure after draft creation:** retry uses the retained twin ID.
- **Unsupported pricing route:** backend structured error is surfaced without
  exposing raw response or secrets.
- **Concurrent click:** no duplicate twin and no duplicate run.

## 9. Accessibility

- Native disclosure controls provide keyboard and screen-reader semantics.
- Each route title includes segment, source, destination, and total cost.
- Status is conveyed by icon and text, never color alone.
- Expansion labels identify their content and item count.
- Evidence IDs and assumptions remain selectable text.
- Focus order follows summary, route list, then billing pools.
- All content works without hover interactions.

## 10. API and Trust-Boundary Changes

Canonical write:

```http
POST /twins/{twin_id}/optimizer-runs
Content-Type: application/json

{"params": {...}}
```

Removed writes:

```text
PUT /twins/{twin_id}/optimizer-config/result
TwinConfigUpdate.optimizer_result
Flutter OptimizationApi.saveOptimizerResult
Flutter generic twin-config optimizer_result field
```

Read-only compatibility remains:

```text
GET /twins/{twin_id}/optimizer-config
TwinConfigResponse.optimizer_result
```

The direct `/optimizer/calculate` endpoint can remain as a non-persisting
diagnostic API, but Flutter no longer uses it. Management API documentation and
OpenAPI tests must identify durable runs as the canonical application path.

## 11. Verification Matrix

### Flutter Models

- current contract parses all six routes, pools, tier contributions, and
  diagnostics;
- historical result without both additive fields parses;
- only one additive field fails;
- wrong version, duplicate/missing route, duplicate pool, unknown provider or
  route class, boolean/numeric string, negative/non-finite amount, invalid
  count, and dangling pool reference fail;
- parsing errors contain field names but no supplied values.

### Flutter API Adapter

- durable run uses `POST`, correct twin path, and params envelope;
- strict response decoding returns `OptimizerRunData`;
- old result-write request is absent;
- transport and contract failures use the existing sanitized error boundary.

### Wizard BLoC

- edit mode creates one run and updates state;
- create mode creates one draft, then one run;
- run failure after draft creation retains the ID;
- retry does not create another draft;
- invalid name blocks network calls;
- repeated calculate clicks are serialized;
- save draft never writes optimizer result;
- architecture-change and missing-cloud-access warnings remain intact.

### Widgets

- wide and compact layouts render without overflow;
- evidence is collapsed initially;
- expanding displays six routes and nested tier detail;
- billing pool and solver diagnostics are discoverable;
- same-provider zero route is explicit;
- historical result shows no fabricated evidence;
- semantics include route and disclosure context.

### Demo Mode

- demo calculation uses the durable run API;
- newly calculated demo data contains deterministic six-edge evidence;
- demo result persists in memory and can be restored;
- historical showcase data remains explicitly historical when evidence is
  absent.

### Management API

- generic twin update rejects/ignores no optimizer-result write because the
  field is absent from the request contract;
- removed result endpoint is absent from OpenAPI and returns 404/405;
- durable run remains atomic and updates optimizer config/history once;
- read projections and deployment continue to consume server-owned results;
- ownership, malformed result, pricing-catalog mismatch, and rollback tests
  remain green.

### Gates

- `flutter analyze`
- full `flutter test`
- `flutter build web`
- `flutter build macos`
- focused and full Management API test suites in Docker
- Ruff, Bandit, compileall, and `pip check`
- strict MkDocs build
- Compose config validation
- real local HTTP smoke test against Management and Optimizer containers
- no live cloud deployment or provider mutation

## 12. Definition of Done

- Flutter has exactly one optimizer calculation command: durable server-owned
  run creation.
- No client-authored optimizer result can enter Management persistence.
- New successful runs expose exact six-edge transfer evidence and complete-path
  diagnostics through strict typed models.
- The configuration UI remains compact, with technical detail collapsed.
- New-twin calculation is retry-safe and duplicate-safe.
- Historical results remain readable without invented evidence.
- Tests cover contract, workflow, UX, accessibility, demo, and trust boundary.
- Developer, component, contract, and roadmap documentation describe the
  canonical workflow only.
- Issue #116 is closed only after all gates pass and the Flutter slice is
  committed.

## Plan Review

The plan was reviewed against implementation readiness, separation of
concerns, enterprise trust boundaries, desktop/web UX, accessibility,
historical compatibility, error handling, and test breadth.

Review corrections included:

- removing both client-authored persistence paths, not only the dedicated
  result endpoint;
- retaining a draft twin ID after a failed first calculation;
- requiring paired transfer context and diagnostics;
- preserving honest historical reads without synthesizing evidence;
- keeping route evidence collapsed instead of introducing another screen;
- covering all supported desktop platforms and web;
- separating user-authored parameters from server-owned calculation results.

No unresolved implementation ambiguity remains for this slice.
