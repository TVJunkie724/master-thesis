---
title: "Implementation Plan: Thesis Research Workflow Consolidation"
description: "Flutter implementation contract for the standalone Six-layer research workflow, portability, deployment credentials, and persisted evidence."
tags: [flutter, implementation-plan, thesis, six-layer, evidence]
lastUpdated: "2026-08-27"
version: "1.0"
---

<!-- SOURCES:
- docs/plans/2026-08-26_thesis_poc_target_concept.md
- docs/plans/2026-08-26_thesis_poc_execution_plan.md
- docs/research/research_questions_and_evaluation_design.md
- FRONTEND_ARCHITECTURE.md
- integration_vision.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_THESIS_RESEARCH_WORKFLOW.md
- twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_09_THESIS_RESEARCH_WORKFLOW_CONSOLIDATION.md
- twin2multicloud_flutter/lib/ and twin2multicloud_backend/src/ contract audit on 2026-08-27
EXTRACTED: 2026-08-27 | VERSION: 1.0
-->

# Implementation Plan: Thesis Research Workflow Consolidation

## 0. Git Branch

- **Branch name:** `codex/six-layer-clean`
- **Base branch:** the approved Thesis PoC cleanup branch after Phase 5 commit
  `9f37b1d5`
- **Merge strategy:** clean dependency-ordered commits; no rebase of shared
  history
- **Session ID:** `AI-0827-THES`
- **Authorization:** the user explicitly authorized all remaining phases and
  intermediate commits without another pause. This satisfies the implementation
  approval gate after a zero-finding plan review.
- **Safety boundary:** no live provider deployment, Destroy, validation,
  pricing refresh, or other cloud mutation is part of this plan.

Every step and Definition-of-Done checkbox in this document is mandatory. A
builder must not skip a step because an older test or screen still passes.

## 1. Summary

This phase implements
[`CONCEPT_THESIS_RESEARCH_WORKFLOW.md`](../docs/configuration_workspace/concepts/CONCEPT_THESIS_RESEARCH_WORKFLOW.md)
and Phase 6 of the repository-wide Thesis PoC execution plan. Flutter is
reduced to four research responsibilities: Scenario, Optimize, Prepare, and
Operate/Verify.

Those responsibilities span the application. Inside the Configuration
Workspace, the final responsibility is represented by the `Review` group;
actual operations and persisted verification evidence remain in Twin Overview.

The implementation must:

1. reduce Dashboard to Twin experiment inventory and bounded portability;
2. remove the Pricing Review route, pricing-health Dashboard row, aggregate
   stat cards, and their active Flutter state/API dependencies;
3. remove architecture-profile selection and pricing-maintenance tasks from
   the Configuration Workspace while retaining an internally validated,
   pinned `six-layer-eventing@1` contract;
4. reduce Settings to multiple deployment administrator CloudConnections with
   typed entry, allowlisted file import, validation, and deletion;
5. expose typed persisted telemetry and cleanup evidence in Twin Overview; and
6. preserve all current Deploy/Destroy idempotency, SSE reconnect/resume/replay,
   L4/L5 handoff, typed configuration, and immutable-result behavior.

The relevant current architecture is the Management-API-only Flutter boundary
in `FRONTEND_ARCHITECTURE.md`. No direct Optimizer, Deployer, Terraform, or
provider integration is introduced.

## 2. Visual Layout (ASCII)

### 2.1 Dashboard - wide desktop and Web

```text
+--------------------------------------------------------------------------+
| Twin2MultiCloud                                      [theme] [profile]    |
+--------------------------------------------------------------------------+
|                                                                          |
| Twin experiments                    [Import Twin] [New Twin]             |
| Reproducible Six-layer research scenarios                                |
|                                                                          |
| [All] [Draft] [Configured] [Deployed] [Destroyed] [Error]                |
| +----------------------------------------------------------------------+ |
| | Name | State | Updated | Last deploy | Actions                       | |
| | A    | draft | ...     | -           | [Edit][Duplicate][Export][X] | |
| | B    | deploy| ...     | ...         | [Open][Duplicate][Export][X] | |
| +----------------------------------------------------------------------+ |
|                                                                          |
| Empty: No Twin experiments yet. [Import Twin] [Create Twin]              |
+--------------------------------------------------------------------------+
```

The Dashboard must contain no aggregate stat cards, estimated fleet-cost card,
pricing-health row, or Pricing Review navigation.

### 2.2 Dashboard - compact supported Web

```text
+----------------------------------------------+
| Twin2MultiCloud              [theme][profile]|
+----------------------------------------------+
| Twin experiments                              |
| Reproducible Six-layer scenarios              |
| [Import Twin] [New Twin]                      |
| [All][Draft][Configured]...                   |
| +------------------------------------------+  |
| | internally scrollable exact table       |  |
| | row actions retain tooltips and order   |  |
| +------------------------------------------+  |
+----------------------------------------------+
```

The existing bounded horizontal table scroll remains. Actions must not be
hidden behind hover-only controls.

### 2.3 Configuration Workspace - wide

```text
+--------------------------------------------------------------------------+
| Configuration Workspace                              [theme] [profile] [X]|
+----------------------+---------------------------------------------------+
| Scenario             | Current task                                      |
|   Twin identity      |                                                   |
|   Workload           | Existing typed task content                       |
|   User logic         |                                                   |
|                      |                                                   |
| Optimize             | Existing calculation command, immutable result,   |
|   Calculate costs    | assumptions, exclusions, routes, graph evidence   |
|   Review result      |                                                   |
|                      |                                                   |
| Prepare              |                                                   |
|   Cloud access       |                                                   |
|   Data contracts     |                                                   |
|   Twin assets        |                                                   |
|                      |                                                   |
| Review               |                                                   |
|   Summary            |                                                   |
|   Readiness findings |                                                   |
|   Preflight          |                                                   |
+----------------------+---------------------------------------------------+
| [Back]                              [Save draft] [Calculate/Next/Finish]   |
+--------------------------------------------------------------------------+
```

There is no architecture-profile phase, selectable architecture card,
profile-change dialog, pricing-readiness task, or link to pricing maintenance.
The canonical Six-layer contract may be identified in secondary explanatory
text and in immutable result evidence.

### 2.4 Configuration Workspace - compact supported Web

```text
+----------------------------------------------+
| Configuration Workspace                       |
+----------------------------------------------+
| [Scenario > Workload                    v]    |
+----------------------------------------------+
| Existing typed task content                   |
|                                               |
+----------------------------------------------+
| [Back] [Save] [Calculate/Next/Finish]         |
+----------------------------------------------+
```

The selector groups exactly Scenario, Optimize, Prepare, and Review in this
order. It keeps the same navigability and blocked-reason semantics as the wide
sidebar.

### 2.5 Settings deployment connections - wide

```text
+--------------------------------------------------------------------------+
| <- Settings                                          [theme] [profile]    |
+--------------------------------------------------------------------------+
| Profile                                                                  |
|                                                                          |
| Deployment administrator connections                         [Refresh]   |
| Existing isolated thesis accounts only                                   |
|                                                                          |
| + AWS ----------------+ + Azure --------------+ + GCP ----------------+  |
| | 2 connections       | | 1 connection       | | 2 connections       |  |
| | aws-thesis valid    | | azure-lab untested | | gcp-demo valid      |  |
| | [Validate] [Delete] | | [Validate][Delete] | | [Validate][Delete]  |  |
| | [Enter] [Import CSV]| | [Enter][Import JSON]| |[Enter][Import JSON]|  |
| +---------------------+ +---------------------+ +----------------------+  |
+--------------------------------------------------------------------------+
```

### 2.6 Settings deployment connections - compact supported Web

```text
+----------------------------------------------+
| <- Settings                    [theme][profile]|
+----------------------------------------------+
| Profile                                       |
|                                               |
| Deployment administrator connections          |
| + AWS --------------------------------------+ |
| | connection rows and wrapped actions       | |
| | [Enter manually] [Import CSV]             | |
| +-------------------------------------------+ |
| + Azure ...                                 + |
| + GCP ...                                   + |
+----------------------------------------------+
```

No pricing connection, public-pricing pseudo-entry, default-pricing action, or
pricing status is rendered.

### 2.7 Twin Overview evidence - wide

```text
+--------------------------------------------------------------------------+
| Twin Overview                                                            |
| Readiness                                                                |
| L4 / L5 Access (deployed only)                                           |
| Operations + durable logs                                                |
|                                                                          |
| Telemetry verification (deployed only)                                   |
| [Run roundtrip]  Latest: PASS  Trace VERIFY-XXXXXXXX  3/3                |
| > Phase evidence                                                         |
| > Earlier persisted runs                                                 |
|                                                                          |
| Cleanup evidence (after Destroy or failed cleanup)                        |
| COMPLETE / INCOMPLETE                                                     |
| Terraform state: empty | AWS: empty | Azure: empty | GCP: empty          |
| > Retained shared prerequisites                                          |
| > Residual failures                                                      |
|                                                                          |
| Redacted outputs and configuration evidence                              |
+--------------------------------------------------------------------------+
```

### 2.8 Twin Overview evidence - compact supported Web

```text
+----------------------------------------------+
| Telemetry verification                        |
| PASS | VERIFY-XXXXXXXX | 3/3                  |
| [Run roundtrip]                               |
| > Phase evidence                              |
| > Earlier persisted runs                     |
|                                               |
| Cleanup evidence                              |
| COMPLETE                                      |
| Terraform: empty                              |
| AWS: empty                                    |
| > Shared prerequisites                        |
| > Residual failures                           |
+----------------------------------------------+
```

Evidence rows stack; no horizontal evidence table is introduced.

## 3. Widget Tree

```text
Twin2MultiCloudApp [MODIFY lib/app.dart]
|-- GoRouter [MODIFY: remove /pricing-review]
|-- DashboardScreen [MODIFY lib/screens/dashboard_screen.dart]
|   |-- BrandedAppBar [REUSE]
|   |-- _ResearchInventoryHeader [NEW private]
|   |   |-- Import button [NEW]
|   |   `-- New Twin button [MOVED]
|   `-- TwinsTable/DataTable [MODIFY existing private composition]
|       `-- _TwinActions [NEW private extraction]
|           |-- Open/Edit [REUSE behavior]
|           |-- Duplicate [NEW]
|           |-- Export [NEW]
|           `-- Delete [REUSE behavior]
|
|-- SettingsScreen [MODIFY lib/screens/settings_screen.dart]
|   `-- CloudAccessBloc [MODIFY]
|       `-- DeploymentConnectionsPanel
|           [MODIFY lib/widgets/cloud_connections/cloud_accounts_panel.dart]
|           `-- _ProviderConnectionCard [MODIFY]
|               |-- connection rows [MODIFY]
|               |-- CloudConnectionCreateDialog [REUSE]
|               `-- CloudConnectionImportDialog [NEW]
|
|-- WizardScreen [MODIFY lib/screens/wizard/wizard_screen.dart]
|   `-- ConfigurationWorkspaceShell [REUSE]
|       |-- ConfigurationTaskSidebar [MODIFY projected groups only]
|       |-- ConfigurationTaskSelector [MODIFY projected groups only]
|       `-- existing task widgets [REUSE]
|
`-- TwinOverviewScreen [MODIFY]
    `-- TwinOverviewContent [MODIFY]
        |-- existing readiness/access/operations [REUSE]
        |-- DeploymentVerificationCard [MODIFY]
        |   |-- existing infrastructure section [REUSE]
        |   |-- telemetry command/log section [MODIFY]
        |   `-- TelemetryEvidencePanel [NEW]
        `-- CleanupEvidencePanel [NEW]
```

Deleted active presentation/state nodes:

```text
PricingReviewScreen [DELETE]
PricingReviewBloc/Event/State [DELETE]
PricingHealthRow and pricing maintenance widgets [DELETE]
StatCard and DashboardStats when no remaining caller exists [DELETE]
ArchitectureProfileChoice/Task/ChangeDialog [DELETE]
```

`pricing_catalog_evidence.dart`, calculation trace widgets, transfer evidence,
and immutable optimizer-result models are retained because they are research
evidence, not pricing administration.

## 4. Component Specifications

### 4.1 Twin portability boundary

Files:

- `lib/models/twin_transfer.dart` [NEW]
- `lib/services/management_api.dart` [MODIFY]
- `lib/services/api_service.dart` [MODIFY]
- `lib/demo/demo_management_api.dart` [MODIFY]
- `lib/providers/twins_provider.dart` [MODIFY]
- `lib/screens/dashboard_screen.dart` [MODIFY]

Typed contracts:

| Type | Required fields | Constraints |
|---|---|---|
| `TwinDuplicateRequest` | `name` | trimmed, 1-120 characters |
| `TwinImportRequest` | `newName`, `filename`, transient bytes | filename ends `.twin.zip`; bytes bounded by server; bytes excluded from equality/log output |
| `PortableTwinDownload` | safe filename, media type, transient bytes | `.twin.zip`, `application/zip`, no path traversal |

The Dashboard opens a name dialog before Duplicate or Import. Import then opens
the platform picker for one `.twin.zip`. Export receives the typed binary and
passes it to the existing `saveBinaryFile`. The screen never parses the archive.
Successful Duplicate/Import invalidates `twinsProvider` and navigates to the
new draft Workspace. Cancellation performs no API call.

No generic project ZIP widget is reused because the portable Twin contract has
a different filename, content, trust, and execution boundary. Existing file
picker/reader and binary-save utilities must be reused.

### 4.2 Dashboard inventory

File: `lib/screens/dashboard_screen.dart` [MODIFY]

The route remains a `ConsumerStatefulWidget`. It owns only sorting, lifecycle
filter selection, platform picker/dialog presentation, and navigation. Riverpod
continues to own list loading and mutation serialization.

The existing card/table, `TwinStateUtils`, confirmation dialog, and responsive
horizontal scroll are reused. Stat and pricing imports/providers are removed.
The filter adds `destroyed`, because cleanup evidence remains inspectable after
Destroy.

### 4.3 Deployment CloudConnection inventory and import

Files:

- `lib/models/cloud_connection.dart` [MODIFY]
- `lib/bloc/cloud_access/*` [MODIFY]
- `lib/widgets/cloud_connections/cloud_accounts_panel.dart` [MODIFY]
- `lib/widgets/cloud_connections/cloud_connection_import_dialog.dart` [NEW]
- `lib/services/management_api.dart` and adapters [MODIFY]

`CloudAccessState` changes from `CloudAccessInventory?` to an immutable
`List<CloudConnection>`. The BLoC filters fail-closed to
`purpose == deployment` before emitting UI state. Pricing-default events and
state disappear. Mutations reload `listCloudConnections()`.

`CloudConnectionImportRequest` contains metadata plus transient bytes:

| Parameter | Type | Required | Default |
|---|---|---:|---|
| `provider` | `CloudProvider` | yes | - |
| `displayName` | `String` | yes | - |
| `region` | `String` | yes | provider default |
| `targetScopeId` | `String?` | Azure/GCP | null |
| `accountId` | `String?` | no | null |
| `ssoRegion` | `String?` | no | null |
| `regionIotHub` | `String?` | no | null |
| `regionDigitalTwin` | `String?` | no | null |
| `filename` | `String` | yes | - |
| `bytes` | `Uint8List` | yes | - |

The dialog captures only non-secret metadata, then accepts exactly `.csv` for
AWS and `.json` for Azure/GCP. Parsing, allowlisting, and secret validation stay
server-side. File bytes live only in the request and are cleared when the
command completes or the dialog closes. The original filename is shown, but
file contents are never previewed.

The existing manual `CloudConnectionCreateDialog` and provider credential
forms are retained. This proves both typed and provider-export input without a
general credential editor.

### 4.4 Canonical architecture workflow projection

Files:

- `lib/bloc/wizard/wizard_event.dart` [MODIFY]
- `lib/bloc/wizard/wizard_state.dart` [MODIFY]
- `lib/bloc/wizard/handlers/wizard_architecture_profile_handlers.dart`
  [MODIFY and rename only if needed]
- `lib/features/configuration_workspace/domain/configuration_journey.dart`
  [MODIFY]
- `lib/screens/wizard/wizard_screen.dart` [MODIFY]

Flutter retains the existing architecture detail and pinned Twin selection as
internal contract evidence, but it must remove:

- profile catalog lists from public state;
- profile-selected/change-preview/change-confirm/cancel events;
- change phases, invalidation fields, and change dialogs;
- selection/understanding tasks; and
- profile choice widgets.

One internal load event reads the exact `six-layer-eventing@1` detail and the
Twin's default pinned selection, validates their references and digests, and
marks the canonical contract ready. Any other profile is a visible incompatible
contract error, never a selectable fallback. Extension-slot loading still
follows the canonical detail revision.

The journey projection must expose exactly these groups and tasks:

| Group | Tasks |
|---|---|
| Scenario | Define Twin; Scenario and currency; Device traffic; Processing; Retention; Twin capabilities; User logic |
| Optimize | Calculate cost allocation; Review immutable result |
| Prepare | Cloud access; Data contracts; Twin assets |
| Review | Summary; Readiness findings; Validation and preflight |

The current three-step internal persistence compatibility mapping may remain
private until Phase 7 orphan cleanup, but no production label or control may
expose it.

### 4.5 Frozen-pricing calculation boundary

Files:

- `lib/bloc/wizard/wizard_event.dart`, `wizard_state.dart`, and optimizer
  handlers [MODIFY]
- `lib/screens/wizard/step2_optimizer.dart` [MODIFY]
- `lib/providers/twins_provider.dart` [MODIFY]
- pricing administration screen/BLoC/widgets/models [DELETE when unreferenced]

The Workspace must remove pricing-health loading, refresh readiness, and review
navigation. `canRequestCalculation` depends on canonical architecture,
workload, bounded extensions, command serialization, and form validity. The
durable optimizer-run Management endpoint remains authoritative and returns a
visible error if its frozen pricing evidence is unavailable or invalid.

Immutable pricing catalog references, assumptions, and calculation trace stay
visible inside the result. Flutter never recalculates or refreshes them.

### 4.6 Telemetry evidence contract

Files:

- `lib/models/deployment_verification.dart` [MODIFY]
- `lib/services/management_api.dart`, production, and demo adapters [MODIFY]
- `lib/bloc/deployment_verification/*` [MODIFY]
- `lib/widgets/deployment_verification_card.dart` [MODIFY]
- `lib/widgets/twin_overview/telemetry_evidence_panel.dart` [NEW]

Strict Dart types mirror:

- `telemetry-verification-session.v1`;
- `telemetry-verification.v1`;
- one record with status, trace, result, safe error, and timestamps; and
- `telemetry-verification-history.v1` with at most 25 newest-first records.

The phase-kind-provider and count/correlation invariants from the Pydantic
contract must be repeated at the Dart boundary. Unknown versions, duplicate
phases, mismatched L4 provider/kind, invalid counts, or secret-like extra data
fail visibly without echoing values.

`DeploymentVerificationBloc` loads persisted history on creation, starts one
typed verification session, retains the verification ID, displays live logs,
parses terminal evidence, and refreshes the persisted record after terminal or
stream failure. A dropped verification stream never starts another telemetry
message automatically. The user may retry only through a new explicit command.

`TelemetryEvidencePanel` is presentation-only. It shows latest status, trace,
phase evidence, elapsed time, failure phase, and collapsed earlier records.

### 4.7 Cleanup evidence contract

Files:

- `lib/models/cleanup_evidence.dart` [NEW]
- `lib/models/deployment_operations.dart` [MODIFY]
- `lib/bloc/twin_overview/twin_overview_state.dart` and BLoC [MODIFY]
- `lib/widgets/twin_overview/cleanup_evidence_panel.dart` [NEW]
- `lib/widgets/twin_overview/twin_overview_content.dart` [MODIFY]

`CleanupEvidence` mirrors the exact closed backend contract:

- schema `cleanup-evidence.v1`;
- status `complete`, `incomplete`, or `dry_run`;
- Terraform destroy and inventory evidence;
- unique AWS/Azure/GCP provider evidence;
- retained Azure resource-provider or GCP API prerequisites; and
- bounded residual failures.

The Dart parser must enforce terminal consistency, counts, provider uniqueness,
status combinations, and allowlisted enum values. It must reject unknown
fields rather than silently treating them as proof.

`DeploymentOperationSummary` gains `CleanupEvidence?`. Twin Overview loads it
from `DeploymentStatusSnapshot.latestDeployment` after refresh and parses it
from Destroy terminal `outputs.cleanup_evidence` before the canonical refresh.
Complete evidence uses success presentation. Incomplete evidence uses a visible
error state with residual scope/reason and must never be described as a
successful cleanup. Retained shared prerequisites are informational and remain
distinct from residual Twin resources.

### 4.8 Reuse decisions for new widgets

Every new widget is a private or evidence-specific extraction. The builder must
apply the reuse decision below and must not introduce another general-purpose
component for this phase.

| New widget | Existing reuse first | Why a small extraction is still required |
|---|---|---|
| `_ResearchInventoryHeader` | Existing buttons, typography, spacing, and `BrandedAppBar` | No existing header owns the paired portable-Twin actions; keeping it private avoids a speculative shared abstraction. |
| `_TwinActions` | Existing open/delete behavior, confirmation dialog, icons, and tooltips | The existing table composes row actions inline; the private extraction is needed only to serialize the new Duplicate/Export actions and keep row semantics testable. |
| `CloudConnectionImportDialog` | Existing credential metadata fields, provider labels, file-picker reader, dialog shell, and action controls | Manual secret-entry dialogs cannot safely accept transient provider-export bytes. The import dialog owns only non-secret metadata plus one allowlisted file handoff. |
| `TelemetryEvidencePanel` | Existing card, status, expansion, color, and typography primitives | Persisted three-phase evidence has a strict typed hierarchy that no generic log or result widget represents. It remains presentation-only. |
| `CleanupEvidencePanel` | Existing card, status, expansion, provider-label, color, and typography primitives | Cleanup proof must distinguish Terraform, provider inventory, retained shared prerequisites, and residual failure; reusing a success/log card would blur that safety boundary. |

### 4.9 Documentation deliverable

After code and verification are complete, the builder must:

1. update
   `twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_09_THESIS_RESEARCH_WORKFLOW_CONSOLIDATION.md`
   with exact focused/full test, analyzer, architecture-checker, and Web-build
   evidence;
2. create the short durable implementation reference
   `twin2multicloud_flutter/docs/configuration_workspace/implementation/thesis_research_workflow.md`
   describing only the final boundary, typed contracts, state ownership, and
   verified evidence; and
3. mark Phase 9 complete in
   `twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md`
   only after every safe gate passes.

No temporary handoff, product roadmap, or implementation diary is created.
Repository-wide stale-document removal remains the separately committed Phase
7 cleanup.

## 5. Responsive Behavior

| Breakpoint | Width | Mandatory behavior |
|---|---:|---|
| Wide desktop | `>= AppSpacing.workspaceSidebarBreakpoint` | Workspace sidebar visible; Dashboard header actions inline; provider connection cards wrap up to three columns; evidence summary rows may use `Wrap`. |
| Narrow desktop / Web | `AppSpacing.compactSupportedWidth` to sidebar breakpoint | Workspace task selector replaces sidebar; Dashboard table remains internally scrollable; provider cards and evidence sections stack as width requires. |
| Compact supported Web | minimum `AppSpacing.compactSupportedWidth` | One content column; actions wrap below labels; exact task/evidence order retained; dialogs use constrained scrolling; no viewport overflow. |

The implementation must move the current Workspace `960` and sidebar `300`
values into `lib/theme/spacing.dart` before touched layout code uses them.
Existing semantic breakpoints may be renamed from pricing-specific names when
their remaining use is general. No new literal spacing, radius, color, or text
size is allowed in touched widgets.

## 6. State Flow (BLoC and Riverpod)

### 6.1 Ownership

| Owner | State and side effects |
|---|---|
| Riverpod `twinsProvider` / command controller | Twin list, serialized duplicate/import/export/delete API calls, list invalidation |
| `CloudAccessBloc` | deployment connection loading, import/create/validate/delete commands, busy IDs, safe feedback |
| `WizardBloc` | canonical architecture evidence, typed scenario, calculation, provider binding, validation and finish gates |
| `TwinOverviewBloc` | deployment status, cleanup evidence, Deploy/Destroy stream reconnect/replay, access/readiness state |
| `DeploymentVerificationBloc` | persisted verification history, one active telemetry session, live logs, terminal evidence recovery |
| Widgets | render typed state, present platform picker/dialog/save handoffs, emit events/callbacks |

### 6.2 Twin portability

```text
Dashboard action
  -> picker/name dialog
  -> TwinCommandController
  -> ManagementApi
  -> POST /twins/{id}/duplicate OR POST /twins/import OR GET /twins/{id}/export
  -> typed Twin or PortableTwinDownload
  -> invalidate Twin list / save file / navigate
```

### 6.3 Deployment connection import

```text
Settings dialog
  -> CloudAccessImportRequested(metadata + transient bytes)
  -> CloudAccessBloc
  -> ManagementApi multipart POST /cloud-connections/import
  -> typed redacted CloudConnection
  -> reload deployment connection list
  -> clear transient request and show safe feedback
```

### 6.4 Canonical Workspace

```text
Workspace initializes
  -> WizardCanonicalArchitectureLoadRequested
  -> WizardBloc
  -> ManagementApi canonical detail + Twin pinned selection
  -> exact reference/digest validation
  -> canonical architecture state
  -> Scenario -> Optimize -> Prepare -> Review task projection
```

### 6.5 Telemetry verification

```text
Twin Overview creates verification scope
  -> VerificationHistoryLoadRequested
  -> GET persisted history
  -> typed history state

Run roundtrip
  -> explicit event
  -> POST typed start
  -> SSE live log stream
  -> typed terminal evidence OR stream failure
  -> GET persisted verification by ID
  -> authoritative latest evidence state
```

### 6.6 Cleanup evidence

```text
Destroy command
  -> existing idempotent Management operation
  -> existing catch-up + SSE replay
  -> terminal outputs.cleanup_evidence
  -> strict CleanupEvidence parse
  -> TwinOverview state
  -> canonical deployment-status refresh
  -> persisted latest cleanup evidence
```

No widget calls Dio, HTTP, SSE, Optimizer, Deployer, Terraform, or a provider
API.

## 7. Design Tokens

The phase must reuse:

- `Theme.of(context).colorScheme` for semantic surface/status colors;
- existing `AppColors.success`, warning, error, and provider mapping;
- `AppSpacing` content widths, paddings, icon sizes, action height, radii,
  elevation, and terminal dimensions; and
- `ThemeData.textTheme` for all typography.

Required token cleanup before widgets:

| Token | Value source | Purpose |
|---|---|---|
| `AppSpacing.workspaceSidebarBreakpoint` | move existing `960.0` | Workspace wide/compact boundary |
| `AppSpacing.workspaceSidebarWidth` | move existing `300.0` | Workspace sidebar width |
| `AppSpacing.compactSupportedWidth` | existing supported 640-pixel contract | Minimum audited layout width |

No new color is required. Material `Icons` is the only icon source.

## 8. Interactions and Animations

- Duplicate and Import require a non-empty unique-name submission; backend
  conflict remains inline in the dialog or a safe SnackBar and no optimistic
  row is added.
- Export shows save success, cancellation, or safe failure without modifying
  Twin state.
- Credential Import disables repeat submission while active. File picker
  cancellation keeps the dialog open and performs no call.
- Credential deletion retains the current confirmation and remains blocked by
  the backend while bound to a Twin.
- Removed pricing/profile routes must resolve as no-match through `go_router`;
  no redirect or hidden menu remains.
- Workspace navigation keeps current task status, blocked reason, Save,
  Discard, Cancel, and command serialization behavior.
- Telemetry phase evidence and older runs use native `ExpansionTile`, collapsed
  by default. A stream drop shows recovery progress, then persisted evidence or
  a Retry control; it never auto-sends another message.
- Cleanup detail uses collapsed shared-prerequisite and residual sections.
  Incomplete cleanup expands the residual section by default.
- Deploy/Destroy confirmation dialogs and SSE reconnect animation/state remain
  unchanged.
- Loading is local to the owning surface. A failure in telemetry-history load
  must not disable Destroy; a cleanup evidence parse failure must remain visible
  without hiding operation logs.

## 9. Accessibility

- Focus order follows visual order: page heading, primary actions, filters,
  Twin rows; Workspace selector/sidebar then task content then navigation;
  evidence command then latest summary then detail/history.
- Every icon-only row action keeps a provider- and Twin-specific tooltip.
- Dialog Cancel and Escape return focus to the invoking button.
- Duplicate/Import name fields submit on Enter only when valid.
- Status uses icon plus text. `PASS`, `FAIL`, `COMPLETE`, `INCOMPLETE`, and
  blocked reasons are announced as text and not inferred from color.
- Telemetry phase semantics announce phase, provider, evidence kind, and result.
- Cleanup semantics distinguish Terraform state, each provider inventory,
  retained shared prerequisites, and residual failures.
- Live operation/log state remains a semantic live region without announcing
  every replayed line twice.
- At 150 and 200 percent text scale at the supported compact width, actions,
  dialogs, cards, and evidence must remain reachable without overflow.
- Body and large-text contrast continue to derive from Material theme colors;
  touched code must not introduce direct palette values.

## 10. Integration Points

All routes below are relative to the configured Management API origin.

| Method | Path | Request | Typed response | Notes |
|---|---|---|---|---|
| GET | `/twins/` | - | `List<Twin>` | Dashboard inventory |
| POST | `/twins/{id}/duplicate` | `{name}` | `Twin` | Creates independent draft |
| POST multipart | `/twins/import` | `new_name`, `.twin.zip` archive | `Twin` | Archive parsed server-side |
| GET | `/twins/{id}/export` | - | `application/zip` | Strict portable archive |
| GET | `/cloud-connections/` | optional provider | `List<CloudConnection>` | UI filters deployment purpose |
| POST | `/cloud-connections/` | typed provider payload | `CloudConnection` | Manual entry |
| POST multipart | `/cloud-connections/import` | JSON metadata and provider file | `CloudConnection` | Server allowlist; original file not retained |
| POST | `/cloud-connections/{id}/validate` | - | validation result | Identity validation |
| DELETE | `/cloud-connections/{id}` | - | no secret response | Backend blocks bound delete |
| GET | `/architecture-profiles/six-layer-eventing/versions/1` | - | canonical detail | No catalog selection UI |
| GET | `/twins/{id}/architecture-profile` | - | pinned reference | Must equal canonical contract |
| POST | `/twins/{id}/optimizer-runs` | typed `CalcParams` | immutable run/result | Frozen pricing evidence owned by Optimizer |
| POST | `/twins/{id}/verify/dataflow` | bounded payload | verification session | Starts exactly one explicit telemetry message |
| GET | `/twins/{id}/verify/dataflow` | `limit <= 25` | verification history | Persisted evidence |
| GET | `/twins/{id}/verify/dataflow/{verification_id}` | - | verification record | Terminal recovery |
| GET | `/twins/{id}/deployment-status` | - | status with cleanup evidence | Exact adapter path stays the existing one |
| Existing POST/SSE | Deploy and Destroy routes | idempotency/cursor contracts | existing typed operation state | Must not regress |

Routes after implementation:

| Route | Screen | Guard |
|---|---|---|
| `/login` | `LoginScreen` | unauthenticated entry |
| `/dashboard` | `DashboardScreen` | authenticated/demo |
| `/settings` | `SettingsScreen` | authenticated/demo |
| `/wizard` | `WizardScreen` create | authenticated/demo |
| `/wizard/:twinId` | `WizardScreen` edit | authenticated/demo; backend immutability authoritative |
| `/twins/:id/overview` | `TwinOverviewScreen` | authenticated/demo; owner-scoped reads |

`/pricing-review` must be removed. No direct port 5003 or 5004 call is allowed.

## 11. Test Plan

Every test below must make exact assertions and verify relevant mock call
counts. Unit mocks isolate BLoCs and API adapters only. Integration tests use a
real local Management API and never mock HTTP.

### 11.1 Twin portability model, adapter, provider, and Dashboard

| # | Type | Case | Exact outcome |
|---:|---|---|---|
| 1 | Happy | Duplicate a draft | one POST, returned ID, list invalidated, edit route receives new ID |
| 2 | Happy | Export a configured Twin | safe `.twin.zip` filename and exact bytes reach save utility |
| 3 | Unhappy | Duplicate name conflict | no optimistic Twin, safe conflict visible, source unchanged |
| 4 | Unhappy | Import malformed archive | backend error visible; list and route unchanged |
| 5 | Edge | Import picker cancelled | zero API calls |
| 6 | Edge | Export save cancelled | zero Twin mutation and no error claim |
| 7 | Edge | Duplicate command clicked twice | exactly one POST |
| 8 | Edge | Unsafe export filename | typed parser fails before save |
| 9 | Edge | Empty Dashboard | exact two primary actions and no stats/pricing content |
| 10 | Edge | Destroyed Twin row | Open, Duplicate, Export, and lifecycle-safe Delete states are exact |

### 11.2 Deployment CloudConnections

| # | Type | Case | Exact outcome |
|---:|---|---|---|
| 1 | Happy | Load multiple deployment connections | exact provider grouping and count; pricing entries absent |
| 2 | Happy | Import each AWS/Azure/GCP supported file | exact multipart metadata, filename, bytes, and one reload per command |
| 3 | Unhappy | Import wrong extension | local validation message; zero API calls |
| 4 | Unhappy | Backend rejects unsupported column/key | safe error; file content never rendered |
| 5 | Edge | File picker cancelled | dialog state retained; zero API calls |
| 6 | Edge | Duplicate import click while busy | exactly one request |
| 7 | Edge | Bound delete returns conflict | row remains and bound reason is visible |
| 8 | Edge | List includes legacy pricing connection | BLoC output contains zero pricing entries |
| 9 | Edge | Reload fails after successful import | success plus explicit refresh warning; no secret data |
| 10 | Edge | Compact 640 at 200 percent text | controls remain reachable with zero overflow exception |

### 11.3 Canonical Workspace

| # | Type | Case | Exact outcome |
|---:|---|---|---|
| 1 | Happy | New draft receives canonical selection | exact `six-layer-eventing@1` detail and four groups load |
| 2 | Happy | Existing compatible draft resumes | current task derived from retained typed state |
| 3 | Unhappy | Twin selection is not canonical | visible incompatible error; calculation disabled |
| 4 | Unhappy | Canonical detail contract is malformed | fail closed; no task silently marked complete |
| 5 | Edge | Production widget tree | zero profile selectors/change dialogs/pricing readiness controls |
| 6 | Edge | Four group order | exact Scenario, Optimize, Prepare, Review order |
| 7 | Edge | Calculation command while active | exactly one durable optimizer run |
| 8 | Edge | Frozen pricing failure from optimizer | safe calculation error without refresh CTA |
| 9 | Edge | Compact selector | same task IDs, labels, blocked reasons, and navigation order as sidebar |
| 10 | Edge | Existing extension bindings | canonical slots remain loaded and validated |

### 11.4 Telemetry evidence

| # | Type | Case | Exact outcome |
|---:|---|---|---|
| 1 | Happy | Parse three-phase pass evidence | trace, counts, three unique phases, provider/kind/correlation exact |
| 2 | Happy | Load persisted history then complete a live run | latest record replaced by exact authoritative fetched record |
| 3 | Unhappy | Fail evidence at phase 2 | status fail, failed phase visible, no phase 3 success fabricated |
| 4 | Unhappy | Unknown schema or invalid phase/provider pair | secret-safe contract failure; no partial success card |
| 5 | Edge | Empty history | explicit no-evidence state and enabled Run action |
| 6 | Edge | Stream drops after POST | GET by retained verification ID; no second POST |
| 7 | Edge | Duplicate terminal evidence | one authoritative record and no duplicate card |
| 8 | Edge | 25-record boundary | exact newest-first count and collapsed history |
| 9 | Edge | Concurrent Run click | one POST only |
| 10 | Edge | Compact/text scale | phase details readable without overflow |

### 11.5 Cleanup evidence

| # | Type | Case | Exact outcome |
|---:|---|---|---|
| 1 | Happy | Complete one-provider cleanup | Terraform/provider empty, zero residual, COMPLETE |
| 2 | Happy | Complete multi-provider cleanup with shared prerequisites | retained items shown separately, still COMPLETE |
| 3 | Unhappy | Incomplete provider inventory | residual failure visible and INCOMPLETE |
| 4 | Unhappy | Malformed evidence or duplicate provider | typed contract error; never displayed as cleanup success |
| 5 | Edge | Destroy terminal carries evidence | visible before canonical refresh and identical after refresh |
| 6 | Edge | Reload destroyed Twin | persisted latest cleanup evidence restored |
| 7 | Edge | Failed cleanup with logs | residual panel and logs both remain accessible |
| 8 | Edge | Dry run | labelled DRY RUN and never treated as Destroy success |
| 9 | Edge | Retained prerequisite without residual | informational, not error-colored |
| 10 | Edge | Empty/absent historical evidence | honest unavailable state; no fabricated proof |

### 11.6 Removed-surface and architecture regression

- Router/widget tests must assert `/pricing-review`, Pricing Review screen,
  Pricing Health row, Dashboard stats, profile selector, and profile-change
  dialog are absent.
- Static architecture tests must assert no presentation HTTP/SSE imports, no
  ports 5003/5004, no credential-secret rendering, and no new TODO/FIXME/HACK.
- Existing Deploy/Destroy reconnect, cursor gap, replay, duplicate command,
  Layer Access, redacted outputs, configuration, archive, and immutability tests
  must remain green.

### 11.7 Commands

Run focused tests first, then the complete safe gate:

```bash
cd twin2multicloud_flutter
dart format --output=none --set-exit-if-changed lib test integration_test
flutter analyze
flutter test test/models test/bloc test/widgets test/screens test/demo
flutter test
flutter build web --release --dart-define-from-file=config/dev.example.json
```

Run the repository architecture checker from the root:

```bash
python3 scripts/check_flutter_architecture.py
git diff --check
```

When a local Docker runtime is available, run the real Management API contract
integration without credentials or cloud mutation:

```bash
docker compose up -d db management-api optimizer
cd twin2multicloud_flutter
flutter test integration_test/management_api_readiness_test.dart \
  --dart-define-from-file=config/dev.example.json
flutter test integration_test/research_workflow_contract_test.dart \
  --dart-define-from-file=config/dev.example.json
cd ..
docker compose stop management-api optimizer db
```

The integration test must use the real `ApiService`, create only disposable
local database records, delete its own records, and hard-assert route schemas,
portable archive headers, deployment-only connections, telemetry history, and
cleanup evidence fixtures. It must not enable credential overlays or call
provider validation, preparation, pricing refresh, Deploy, Destroy, simulator,
or live telemetry commands.

## 12. Definition of Done

- [ ] Every component marked `[NEW]`, `[MODIFY]`, or `[DELETE]` is implemented
      exactly as specified; no mandatory step is skipped.
- [ ] Dashboard contains only research inventory and bounded Twin portability;
      aggregate stats, pricing health, and product language are absent.
- [ ] Duplicate, Import, and Export use strict typed Management API contracts,
      unique names, transient bytes, and no arbitrary project execution.
- [ ] Settings shows multiple deployment administrator CloudConnections only.
- [ ] AWS CSV, Azure JSON, and GCP JSON import use the allowlisted multipart
      Management API route and never render or retain file content.
- [ ] Configuration Workspace exposes exactly Scenario, Optimize, Prepare, and
      Review; no profile selection/change or pricing-maintenance UI remains.
- [ ] The internal canonical architecture contract fails closed unless the Twin
      is pinned to `six-layer-eventing@1` with matching detail/digest.
- [ ] Cost calculation remains one durable server-owned command with immutable
      pricing/catalog/assumption evidence and no Flutter refresh path.
- [ ] Persisted telemetry evidence is strict, reloadable, trace-correlated, and
      recoverable after stream failure without an automatic second message.
- [ ] Persisted cleanup evidence is strict, reloadable, and distinguishes
      complete cleanup, retained shared prerequisites, and residual failure.
- [ ] Existing Deploy/Destroy idempotency and SSE reconnect/resume/replay tests
      remain green without weakened assertions.
- [ ] Existing L4/L5 access, readiness/repair, redaction, configuration,
      immutable lifecycle, and demo behavior remain green.
- [ ] Loading, data, empty, blocked, error, cancellation, and race branches in
      Sections 8 and 11 are implemented and hard-asserted.
- [ ] Compact 640-pixel layout at 150 and 200 percent text scale passes for all
      modified dense surfaces; focus, semantics, and Escape behavior pass.
- [ ] All touched widgets use `AppSpacing`, `AppColors`/`ColorScheme`,
      `ThemeData.textTheme`, and Material `Icons`; no magic visual literals or
      inline `TextStyle` constructors are introduced.
- [ ] Flutter still calls only the Management API; no direct Optimizer,
      Deployer, Terraform, or provider call exists.
- [ ] `dart format`, `flutter analyze`, complete `flutter test`, architecture
      checker, Web release build, and `git diff --check` pass.
- [ ] Real local Management API integration passes when Docker is available;
      an unavailable runtime is reported honestly and is not replaced by mocked
      integration success.
- [ ] No live provider mutation or cost-incurring E2E is executed.
- [ ] Phase 9 and its short implementation reference record exact test/build
      evidence; stale implementation-only docs are left for the Phase 7
      repository cleanup rather than mixed into Dart changes.
- [ ] Commits use the `AI-0827-THES` prefix for this Flutter phase and leave a
      clean worktree ready for the `auditor` quality gate.
