# Implementation Plan: Twin Overview Operations Hardening

**Status:** Approved scope; implementation in progress.

## 0. Git Branch

- **Branch name:** `codex/twin-overview-operations-hardening`
- **Base branch:** `master` at merge commit `32effe7`
- **Merge strategy:** Merge commit; no rebase.
- **Session ID:** `AI-0714-operations`
- **GitHub issue:** [#73](https://github.com/TVJunkie724/master-thesis/issues/73)
- **Related architecture debt:** [#72](https://github.com/TVJunkie724/master-thesis/issues/72)

Every subphase below is mandatory and receives its own implementation review,
verification evidence, roadmap update, and structured commit before the next
subphase starts.

## 1. Summary

Phase 8 completes the operational Twin Overview defined by the Frontend Delta
Roadmap. It replaces loosely typed deployment maps and coupled boolean flags
with explicit Management API contracts and operation state, makes deploy and
destroy recovery resilient, exposes twin-scoped deployment readiness, and
turns simulator and trace utilities into understandable long-running workflows.

The slice preserves the existing configuration-review and deployment-
verification features. Flutter continues to call only the Management API.
No verification step provisions or destroys real cloud resources.

### Required subphases

| Subphase | Scope | Commit gate |
|---|---|---|
| 8.1 | Typed deployment status, outputs, history, log-page, operation-session, trace-start, and binary-download contracts; correct nullable state transitions | Model, parser, API-adapter, demo-adapter, and BLoC tests pass |
| 8.2 | Twin-scoped cached readiness read model plus explicit provider preflight command in Management API and Flutter | Backend service/route tests and Flutter readiness tests pass |
| 8.3 | Persisted log catch-up, cursor-based SSE reconnect, bounded terminal state, and explicit connection phases | Reconnect, duplicate, gap, cancellation, and failure tests pass |
| 8.4 | Testing Utilities panel for trace and simulator workflows, collapsed diagnostics, and provider-specific least-privilege archive policy | Deployer packaging, Management API proxy, BLoC, and widget state matrices pass |
| 8.5 | Responsive Twin Overview composition, token cleanup, accessibility, documentation, and release gate | Full backend/Flutter suites and Web/macOS builds pass |

### Implementation progress

| Subphase | Status | Verification evidence |
|---|---|---|
| 8.1 | Done | Typed parser/API/demo/BLoC tests: 55 passed; complete Flutter suite: 451 passed; `flutter analyze --no-pub`: no issues |
| 8.2 | Done | Backend readiness matrix: 25 passed; complete backend suite: 582 passed; complete Flutter suite: 463 passed; Bandit and analyzer clean; Web/macOS release builds pass |
| 8.3 | Done | Focused backend stream/route matrix: 51 passed; complete backend suite: 592 passed; complete Flutter suite: 466 passed; Bandit/analyzer clean; Web/macOS release builds pass |
| 8.4 | Done | Deployer archive/security matrix: 34 passed; complete offline Deployer suite: 1,131 passed, 1 skipped; Management API contract matrix: 53 passed; complete Management API suite: 601 passed; complete Flutter suite: 480 passed; scoped Bandit and analyzer clean; Terraform validates; Web/macOS release builds pass |
| 8.5 | Next | Responsive/accessibility quality gate pending |

Subphase 8.1 also verified defensive copies for nested outputs and binary
downloads, fail-fast pagination bounds, session-scoped demo cursors, safe server
filenames, and explicit clearing of stale operation artifacts. No cloud E2E was
executed.

Subphase 8.2 added a persisted, secret-free, owner-scoped readiness cache keyed
by twin, provider, Cloud Connection identity, credential fingerprint, permission-
set version, and TTL. Cached reads never contact providers; only the explicit
preflight command performs Optimizer and Deployer validation. Deployment now
fails closed at both the Flutter command boundary and the Management API until
the current provider architecture has a successful preflight. Response models
and Flutter parsers enforce matching provider order, non-empty bounded evidence,
permission-set consistency, timestamps, and aggregate readiness. Downstream
messages are redacted before persistence or rendering. No cloud E2E or resource
creation was executed.

Subphase 8.3 consolidated all deployment producers and the authenticated SSE
route onto one canonical session registry. Server replay and live-delivery
buffers are bounded, stale consumer generations cannot reset newer streams,
pending expiry follows real activity, and replay gaps explicitly require
persisted catch-up. Flutter now loads all persisted session pages before opening
SSE with the last accepted cursor, suppresses duplicates, rejects gaps, limits
visible history to 500 entries, and performs cancellable bounded reconnects
followed by a typed status check. The SSE adapter has deterministic cancellation,
strict event/URL/size validation, and reads the current Management API session
token for every new connection. No live-cloud E2E was executed.

Subphase 8.4 separates trace and simulator state from deployment operation
state, adds bounded diagnostics and stale-response guards, and keeps simulator
bytes transient through an explicit request/save lifecycle. The compact Testing
Utilities panel keeps diagnostics collapsed and requires acknowledgement before
downloading credential-bearing archives. The Deployer now assembles archives
from strict provider allowlists, rejects unsafe paths, symlinks, broad secret
file permissions, invalid identities, malformed metadata, and oversized input,
and emits exact provider/credential-class headers. AWS device policies allow
only the exact client and telemetry topic, Azure packages contain only the
device identity, and GCP uses a dedicated topic-publisher service account rather
than deployment/bootstrap credentials. The Management API revalidates the full
binary contract and sends no-store/nosniff headers. Tests use synthetic secrets
and archives only; no live-cloud E2E was executed.

## 2. Visual Layout (ASCII)

### Wide desktop, at least 1200 px content width

```text
+----------------------------------------------------------------------------+
| Back to Dashboard                                      Theme               |
+----------------------------------------------------------------------------+
| Project name                                              [STATE]           |
| Cloud resource name                                                         |
+----------------------------------------------------------------------------+
| DEPLOYMENT READINESS                                                        |
| Ready / Review required                 Last checked timestamp              |
| AWS [matched]  Azure [matched]  GCP [outdated]          [Run preflight]     |
| > GCP: expected permission-set v2, stored v1             [Open account]     |
+----------------------------------------------------------------------------+
| OPERATIONS                                                                 |
| [Deploy / Retry]                          [Destroy / Cleanup]                |
| Current operation: Deploying | Connected | elapsed                          |
| v Live and persisted logs (collapsed when idle)                            |
|   [level] [timestamp] message                              [Copy] [Download]|
+----------------------------------------------------------------------------+
| TESTING UTILITIES                                                           |
| Send one traceable test message                 [Run trace]                 |
| Trace status / providers / duration                                          |
| > Diagnostics (collapsed by default)                                        |
| Download local simulator package                 [Download simulator]       |
| Sensitive archive notice and selected L1 provider                           |
+----------------------------------------------------------------------------+
| DEPLOYMENT OUTPUTS                                                          |
| Stable output rows, source operation, deployed timestamp                    |
+----------------------------------------------------------------------------+
| INFRASTRUCTURE / DATAFLOW VERIFICATION                                      |
+----------------------------------------------------------------------------+
| CONFIGURATION REVIEW                                                        |
+----------------------------------------------------------------------------+
```

### Narrow desktop and compact Web, below 900 px

```text
+------------------------------------------+
| Back                         Theme       |
+------------------------------------------+
| Project name                             |
| Cloud resource name            [STATE]  |
+------------------------------------------+
| DEPLOYMENT READINESS                     |
| status + timestamp                       |
| provider rows                            |
| [Run preflight]                          |
+------------------------------------------+
| OPERATIONS                               |
| [Deploy / Retry]                         |
| [Destroy / Cleanup]                      |
| operation status                         |
| > Logs                                   |
+------------------------------------------+
| TESTING UTILITIES                        |
| [Run trace]                              |
| > Diagnostics                            |
| [Download simulator]                     |
| sensitive archive notice                 |
+------------------------------------------+
| OUTPUTS / VERIFICATION / CONFIGURATION   |
| stacked, each section unframed or one    |
| genuine tool card; no nested cards       |
+------------------------------------------+
```

## 3. Widget Tree

```text
TwinOverviewScreen [MODIFY]
`-- BlocProvider<TwinOverviewBloc> [REUSE]
    `-- TwinOverviewView [MODIFY]
        `-- SelectableScaffold [REUSE]
            |-- BrandedAppBar [REUSE]
            `-- TwinOverviewContent [NEW]
                |-- TwinOverviewNavigationHeader [NEW]
                |-- InlineOperationNotice [NEW]
                |-- TwinOverviewNameHeader [REUSE]
                |-- DeploymentReadinessPanel [NEW]
                |-- DeploymentOperationsPanel [NEW]
                |   |-- DeploymentActionBar [NEW]
                |   `-- DeploymentLogPanel [NEW]
                |       `-- DeploymentTerminal [REUSE, extend typed rows]
                |-- TestingUtilitiesPanel [NEW]
                |   |-- TraceUtilitySection [NEW]
                |   |   `-- DiagnosticDisclosure [NEW]
                |   `-- SimulatorDownloadSection [NEW]
                |-- TerraformOutputsCard [REUSE, typed input]
                |-- DeploymentVerificationCard [REUSE]
                `-- TwinOverviewConfigurationReview [REUSE]
```

`TwinOverviewCommandCenter` is decomposed and removed after the final callers
and tests migrate. New panels are siblings, not nested cards.

## 4. Component Specifications

### Typed contracts

Location: `lib/models/deployment_operations.dart`.

Required immutable value objects:

- `OperationSession` with `sessionId` and `sseUrl`.
- `ActiveDeploymentSession` adds `operationType`.
- `DeploymentOperationSummary` with typed operation/status enums and timestamps.
- `DeploymentStatusSnapshot` validating `deployment-status.v1`.
- `DeploymentOutputsSnapshot` validating `deployment-outputs.v1`, redaction flag,
  source operation, and nullable outputs.
- `DeploymentLogEntry` and `DeploymentLogPage` validating
  `deployment-log-page.v1` and cursor invariants.
- `LogTraceStartResult` with trace ID, provider set, optional session/SSE URL,
  sent timestamp, and public message.
- `BinaryDownload` with bytes, sanitized filename, and media type.

All parsers must reject missing required fields, unsupported schema versions,
unknown enum values, invalid timestamps, descending event IDs, unsafe filenames,
and cursor regressions with a public `AppException`. No dynamic map crosses from
an operation-specific `ManagementApi` method into the deployment state after
subphase 8.1. Legacy optimizer/deployer configuration maps remain isolated in
the existing configuration-review projection and are not expanded by this phase.

### State ownership

Location: `lib/bloc/twin_overview/`.

`TwinOverviewLoaded` must own immutable value objects instead of parallel
operation booleans:

- `DeploymentOperationViewState`: idle, starting, connecting, streaming,
  reconnecting, completed, failed; operation type; session; logs; last event ID.
- `DeploymentReadinessViewState`: initial/loading/ready/reviewRequired/failed;
  provider checks and checked timestamp.
- `TraceViewState`: idle/starting/streaming/completed/failed/cancelled; trace
  metadata and bounded diagnostics.
- `SimulatorDownloadViewState`: idle/requesting/readyToSave/saving/saved/failed.

Nullable domain fields must support explicit clearing. The implementation must
use either a private copy sentinel or dedicated clear parameters consistently;
passing `null` may not silently preserve stale errors, outputs, timestamps,
trace IDs, bytes, or messages.

### DeploymentReadinessPanel

Location: `lib/widgets/twin_overview/deployment_readiness_panel.dart`.

Parameters:

| Name | Type | Required | Default |
|---|---|---:|---|
| `state` | `DeploymentReadinessViewState` | yes | - |
| `onRunPreflight` | `VoidCallback` | yes | - |
| `onOpenCloudAccounts` | `VoidCallback` | yes | - |

The panel renders cached readiness immediately. Remote preflight runs only after
an explicit click and never automatically during screen load. Provider checks
are concise by default; details disclose expected/supplied permission versions,
safe messages, and remediation actions.

### DeploymentOperationsPanel

Location: `lib/widgets/twin_overview/deployment_operations_panel.dart`.

It receives the twin lifecycle, readiness, operation state, and callbacks. It
must disable deploy when cached readiness is not deployable, explain why in the
same focus context, and preserve destroy/cleanup access for error-state twins.
The log region is collapsed when idle and automatically opens for active or
failed operations.

### TestingUtilitiesPanel

Location: `lib/widgets/twin_overview/testing_utilities_panel.dart`.

Trace and simulator are independent tools. Trace diagnostics are collapsed by
default and contain status, trace ID, provider path, sanitized events, completion
summary, and actionable error. The simulator section shows the selected L1
provider and requires acknowledgement that the archive contains narrowly scoped
device/runtime authentication material before requesting it. Flutter must never
inspect, unpack, log, cache, or render archive contents.

The Deployer must enforce an explicit ZIP allowlist and provider credential
policy before streaming any archive:

- AWS: only per-device certificate/private key and the public root CA.
- Azure: only per-device identity material required by the simulator.
- GCP: only a dedicated simulator service-account key restricted to publishing
  to the twin telemetry topic; never the deployment, bootstrap, function, or
  user CloudConnection service-account key.

If the required runtime identity cannot be proven, package generation fails
closed with a redacted actionable error. Archive entries must reject absolute
paths, traversal, symlinks, unexpected credential filenames, and duplicates.
The Management API forwards safe filename/content metadata but never persists
or logs the binary body.

### Screen composition

`TwinOverviewView` remains the single smart presentation boundary. It dispatches
BLoC events, owns navigation/dialog/file-save effects, and passes immutable data
and callbacks to dumb widgets. Dialog widgets and alert presentation move out of
the screen file. No child widget calls `ManagementApi`, `dio`, or SSE directly.

## 5. Responsive Behavior

| Breakpoint | Width | Required behavior |
|---|---:|---|
| Wide desktop | at least 1200 px | Provider readiness in one row; primary actions side by side; utility sections in two columns when both fit |
| Narrow desktop/Web | 900-1199 px | Provider rows wrap; operations stay side by side when labels fit; utilities stack |
| Compact Web | below 900 px | All actions and sections stack; labels wrap; log controls remain horizontally scrollable without clipping terminal content |

The supported minimum viewport is 640 px. Fixed-format terminal content scrolls
horizontally; the page itself must not overflow horizontally.

## 6. State Flow (BLoC)

### Load and readiness

```text
TwinOverviewView
  -> TwinOverviewLoad
  -> TwinOverviewBloc
  -> typed ManagementApi operation methods
  -> Management API deployment/readiness services
  -> typed snapshots
  -> TwinOverviewLoaded
  -> readiness + operations + utilities panels
```

### Deploy/destroy and resilient logs

```text
Action confirmation
  -> DeployRequested / DestroyRequested
  -> ManagementApi command
  -> OperationSession
  -> persisted log catch-up(afterEventId)
  -> SSE(lastEventId)
  -> deduplicate by event ID
  -> bounded operation state
  -> terminal panel
  -> terminal event OR connection loss
     |-- terminal event -> refresh typed status + outputs
     `-- connection loss -> catch-up -> reconnect or typed status terminal state
```

At most one deployment stream and one trace stream may exist. Starting a new
operation must cancel and dispose the previous client/subscription. Delayed
callbacks must be cancellable and may not emit after `close()`.

### Trace and simulator

```text
Run trace -> start result -> trace SSE -> bounded diagnostic events -> summary
Download simulator -> acknowledgement -> binary response metadata -> save dialog
                   -> clear bytes immediately after save/cancel/failure
```

File-save dialogs remain presentation effects. Binary bytes are transient and
must never enter Equatable props, logs, persisted preferences, or demo fixtures.

## 7. Design Tokens

The implementation must reuse `AppSpacing`, `AppColors`, and `ThemeData`. It may
add named tokens only for stable tool dimensions such as log viewport height,
action minimum height, and status icon size. Existing hardcoded values in the
modified Twin Overview files must be migrated. No inline `Colors.*`, spacing
literal, radius literal, or standalone `TextStyle` remains in touched widgets.

## 8. Interactions & Animations

- Primary actions use explicit confirmation dialogs; destructive confirmation
  remains mandatory.
- Readiness and diagnostics use `ExpansionTile`/disclosure semantics and are
  collapsed by default except on blocking failure.
- Running actions show a stable-size progress indicator and preserve button
  dimensions.
- Errors appear inline in their owning section. A dismissible global notice is
  reserved for cross-section save/delete feedback.
- Reconnect state is visible, non-blocking, and never represented as success.
- Motion uses existing Material transitions only; no decorative animation is
  introduced.

## 9. Accessibility

- Focus order follows page order: navigation, readiness, operations, logs,
  trace, simulator, outputs, verification, configuration.
- Disabled actions expose the blocking reason in adjacent semantic text, not a
  tooltip alone.
- Every icon-only control has a tooltip and semantic label.
- Status is communicated by icon and text, never color alone.
- Disclosure controls announce expanded/collapsed state.
- Dialogs return focus to their triggering action; Escape cancels without side
  effects and Enter confirms only when the destructive acknowledgement passes.
- Text and controls satisfy WCAG AA contrast through theme color roles.

## 10. Integration Points

### Existing Management API contracts to type and preserve

| Method | Path | Response |
|---|---|---|
| POST | `/twins/{id}/deploy` | `OperationSession` |
| POST | `/twins/{id}/destroy` | `OperationSession` |
| GET | `/twins/{id}/deployment-status` | `deployment-status.v1` |
| GET | `/twins/{id}/outputs` | `deployment-outputs.v1` |
| GET | `/twins/{id}/deployments` | `deployment-history.v1` |
| GET | `/twins/{id}/logs` | `deployment-log-page.v1` |
| POST | `/twins/{id}/log-trace/start` | `LogTraceStartResult` |
| GET/SSE | returned trace/deployment `sse_url` | typed SSE events |
| GET | `/twins/{id}/simulator/download` | `BinaryDownload` with safe filename and sensitivity metadata |

### New Management API contracts

| Method | Path | Response | Side effects |
|---|---|---|---|
| GET | `/twins/{id}/deployment-readiness` | `deployment-readiness.v1` cached twin/provider readiness | none; no provider calls |
| POST | `/twins/{id}/deployment-preflight` | `deployment-preflight.v1` provider checks and aggregate readiness | explicit provider validation only; no resource creation |

The backend owns required-provider derivation from the selected architecture,
connection ownership, purpose checks, permission-set comparison, and aggregate
deployability. Flutter never reconstructs those rules.

The Deployer owns simulator package content and least-privilege credential
selection. The Management API owns authorization and safe proxy metadata;
Flutter owns only explicit user acknowledgement and local file-save effects.

Routes remain `/twins/:id/overview`; no new top-level route is required. Cloud
account remediation navigates to `/settings`.

## 11. Test Plan

### Contract and parser tests

- Happy: parse every complete v1 contract and nullable empty outputs/log pages.
- Unhappy: reject wrong schema version and malformed required field.
- Edge: unknown operation enum, invalid timestamp, unsafe filename, descending
  log IDs, cursor regression, empty provider set, redacted output marker.

### Backend readiness tests

- Happy: one-provider and three-provider twins return deterministic cached
  readiness; explicit preflight aggregates successful checks.
- Unhappy: missing binding, wrong-purpose connection, outdated permission set,
  owner mismatch, downstream validation failure.
- Edge: duplicate provider path, destroyed/error/deploying twin, connection
  deleted concurrently, no optimizer result, stale prior validation, secret-like
  downstream text. Responses and logs must be redacted.

### Deployer simulator-package security tests

- Happy: AWS, Azure, and GCP archives contain only the provider allowlist and
  exact expected runtime credential class.
- Unhappy: GCP deployment/admin key offered as simulator identity, missing
  dedicated runtime key, unexpected credential file, path traversal, symlink,
  duplicate archive entry, or unsafe project/device filename.
- Edge: multiple devices, empty payload list, Unicode display name mapped to a
  safe archive name, oversized file/total archive bound, and concurrent package
  requests. Tests inspect synthetic ZIPs only and never use live credentials.

### BLoC tests

- Happy: load; deploy; destroy clearing outputs; reconnect with catch-up; trace
  completion; simulator download/save acknowledgement.
- Unhappy: command failure; SSE failure; catch-up failure; status refresh
  failure; trace rate limit; simulator 404/timeout/save cancellation.
- Edge: duplicate SSE event, out-of-order event, 500-entry bound, operation
  replaced, event after close, explicit null clearing, failed refresh preserving
  useful prior state, active session absent despite deploying state.

### Widget tests

- Readiness ready/review/loading/error and provider detail disclosure.
- Deploy blocked explanation, destroy cleanup availability, operation progress,
  reconnect and failure log visibility.
- Trace idle/running/completed/failed and collapsed diagnostics.
- Simulator acknowledgement, busy, cancelled, saved, and failed states.
- Wide, narrow, and 640 px compact layouts with no overflow.
- Keyboard focus, semantics, tooltip, and theme tests.

### Integration and release verification

- Management API tests run locally with downstream provider calls replaced at
  the client boundary; no real cloud E2E.
- Flutter integration smoke may use Management API `TEST_MODE`, not mocked HTTP.
- `flutter analyze --no-pub`
- `flutter test --no-pub`
- `flutter build web --no-pub`
- `flutter build macos --no-pub`
- Backend unit/integration suite excluding `tests/e2e`.

## 12. Definition of Done

- [ ] All five mandatory subphases are implemented and independently committed.
- [ ] Operation-specific deployment contracts expose no dynamic map beyond the
  API adapter; legacy configuration projection remains contained.
- [ ] Nullable errors, outputs, timestamps, trace IDs, and bytes clear correctly.
- [ ] Backend owns twin-scoped readiness and required-provider rules.
- [ ] Preflight is explicit, redacted, owner-scoped, and creates no resources.
- [ ] SSE reconnect catches up persisted logs without duplicates or gaps.
- [ ] Operation and trace logs are bounded and subscriptions are disposed.
- [ ] Simulator archives contain only allowlisted, provider-specific runtime
  credentials; GCP never exports deployment/bootstrap/CloudConnection keys.
- [ ] Simulator archives are handled as transient sensitive binary downloads.
- [ ] Existing deploy, destroy, verification, configuration review, and demo
  workflows remain functional.
- [ ] Loading, empty, blocked, running, reconnecting, completed, failed, cancel,
  and stale states have deterministic UI.
- [ ] Touched UI uses theme and spacing tokens without nested cards.
- [ ] Wide desktop, narrow desktop/Web, and compact Web layouts do not overflow.
- [ ] Accessibility requirements in Section 9 are covered by hard assertions.
- [ ] Backend suite excluding cloud E2E passes.
- [ ] `flutter analyze` and the complete Flutter suite pass.
- [ ] Web and macOS release builds pass.
- [ ] Phase 8 roadmap and GitHub #73 contain final evidence.
- [ ] No credentials, generated artifacts, provider secrets, or real-cloud test
  output are committed.
