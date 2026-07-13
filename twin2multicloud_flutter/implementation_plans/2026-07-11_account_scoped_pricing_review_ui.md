---
title: "Implementation Plan: Account-Scoped Pricing Review UI"
description: "Replace twin-bound pricing refresh UI with a compact account-scoped provider review workflow."
tags: [flutter, pricing, cloud-access, review]
lastUpdated: "2026-07-11"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/provider_access_pricing_review/phase_03_profile_cloud_accounts_access_ui.md
- docs/plans/provider_access_pricing_review/phase_04_dashboard_pricing_health_row.md
- docs/plans/provider_access_pricing_review/phase_05_reviewed_decisions_persistence.md
- docs/plans/provider_access_pricing_review/phase_06_pricing_review_center_ui.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_03_DASHBOARD_PRICING_HEALTH.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_04_PRICING_REVIEW_CENTER.md
- twin2multicloud_backend/src/schemas/cloud_access.py
- twin2multicloud_backend/src/schemas/pricing_health.py
- twin2multicloud_backend/src/schemas/pricing_refresh.py
- twin2multicloud_backend/src/schemas/pricing_review_contracts.py
- User decision on 2026-07-11: every screen must remain visually lean
EXTRACTED: 2026-07-11 | VERSION: 1.1
-->

# Implementation Plan: Account-Scoped Pricing Review UI

**Revision 1.1:** Audit hardening made the confirmed connection id explicit in
the refresh event, separated run/candidate presentation widgets, added inline
retry/dismiss behavior, and permits independent lazy trace loads per report.

**Review status:** Approved for implementation after architect and builder
review against all mandatory plan-review criteria. The user's instruction to
proceed on 2026-07-11 is the implementation approval for this corrective slice.

## 0. Git Branch

- **Branch name:** `codex/gcp-tiering-calculation-hardening`
- **Base branch:** current branch after merge commit `0b244c4` from `master`
- **Merge strategy:** merge commit; no rebase
- **Session ID:** `AI-0711-01ff`
- **Required:** only files listed in this plan may be staged. The existing
  user-owned `twin2multicloud_flutter/pubspec.lock` change must remain unstaged.

## 1. Summary

This slice replaces the legacy Twin selector and
`POST /optimizer/refresh-pricing/{provider}?twin_id=...` flow with the approved
user/account-scoped pricing contracts. Pricing state is global. A Twin is only
relevant for later cost calculation and optimizer-run evidence.

In scope:

| In scope | Out of scope |
|---|---|
| Typed pricing health and cloud access models | Cloud credential creation/editing |
| Provider-specific account confirmation | Pricing registry editor |
| Typed pricing refresh runs | OpenAI key management |
| Candidate reports, decisions, sanitized trace | Twin cost calculation run history |
| Compact Dashboard pricing status | Live cloud deployment E2E |

The visual rule is binding: every default screen state must show only status,
context, and the next action. Diagnostic and trace information must be collapsed
until explicitly opened.

## 2. Visual Layout (ASCII)

Wide desktop:

```text
Pricing Review                                            [reload]
Provider pricing is shared across your twins.

[ AWS: Review ]  [ Azure: Fresh ]  [ GCP: Missing ]

AWS pricing
Account 123456789012 - AWS Pricing Reader                 [Refresh]
Last update: 31 days - Review required

Refresh result (only after a run)
Succeeded - Account 123456789012 - completed 14:32

Review results (3)                                      [expand]
  collapsed by default
  expanded:
    [intent summary] [state] [selected value]
    [candidate choice when selectable]
    [Approve] [Mark unresolved]
    Technical evidence                                  [expand]
```

Compact web:

```text
Pricing Review                                  [reload]
Provider pricing is shared across your twins.

[ AWS ] [ Azure ] [ GCP ]

AWS pricing
Account 123456789012
Review required
[ Refresh ]

Refresh result
Review results (3)                              [expand]
```

Dashboard remains status-only:

```text
Pricing readiness                              [Review pricing]
[AWS Review - Account 123...] [Azure Fresh - Public API] [GCP Missing]
```

No Twin selector, raw log panel, raw JSON dump, or always-expanded evidence is
permitted in these default layouts.

## 3. Widget Tree

```text
PricingReviewScreen [MODIFY]
`-- BlocProvider<PricingReviewBloc> [REUSE/MODIFY]
    `-- _PricingReviewView [MODIFY, smart]
        |-- BrandedAppBar [REUSE]
        |-- PricingProviderSelector [NEW, dumb]
        |   `-- PricingProviderSelectorItem x3 [private]
        |-- PricingProviderWorkspace [NEW, dumb]
        |   |-- account/status summary
        |   `-- refresh command
        |-- PricingRefreshRunSummary [NEW, dumb, conditional]
        `-- PricingCandidateReviewPanel [NEW, dumb, conditional]
            |-- report ExpansionTile list
            |-- candidate RadioGroup
            |-- decision actions
            `-- PricingTraceDetails [NEW, dumb, collapsed]

DashboardScreen [MODIFY]
`-- PricingHealthRow [MODIFY, REUSE]
    `-- compact provider status items
```

Layer changes:

```text
models/   cloud_access_inventory.dart [NEW]
          pricing_health.dart [NEW]
          pricing_refresh_run.dart [NEW]
          pricing_candidate_review.dart [NEW]
services/ api_service.dart [MODIFY]
bloc/     pricing_review_event.dart [MODIFY]
          pricing_review_state.dart [MODIFY]
          pricing_review_bloc.dart [MODIFY]
widgets/  pricing/pricing_provider_selector.dart [NEW]
          pricing/pricing_provider_workspace.dart [NEW]
          pricing/pricing_refresh_run_summary.dart [NEW]
          pricing/pricing_candidate_review_panel.dart [NEW]
          pricing/pricing_review_strings.dart [NEW]
screens/  pricing_review/pricing_review_screen.dart [MODIFY]
providers/twins_provider.dart [MODIFY: global pricing health provider]
widgets/  pricing/pricing_health_row.dart [MODIFY]
app.dart [MODIFY: remove twin query parameter]
```

## 4. Component Specifications

### PricingProviderSelector

| Parameter | Type | Required | Default |
|---|---|---:|---|
| pricingHealth | `PricingHealthResponse?` | yes | - |
| selectedProvider | `String` | yes | - |
| enabled | `bool` | no | `true` |
| onSelected | `ValueChanged<String>` | yes | - |

Stateless and presentation-only. It uses three stable-width provider items on
wide layouts and a three-option segmented control on compact layouts. Each item
shows provider, status, and a single short source label.

### PricingProviderWorkspace

| Parameter | Type | Required | Default |
|---|---|---:|---|
| provider | `String` | yes | - |
| health | `ProviderPricingHealth?` | yes | - |
| access | `CloudAccessEntry?` | yes | - |
| isLoading | `bool` | yes | - |
| isRefreshing | `bool` | yes | - |
| canRefresh | `bool` | yes | - |
| error / reportError | `String?` | yes | - |
| onRefresh / onRetry | `VoidCallback` | yes | - |

Stateless. AWS/GCP refresh is enabled only when `connectionId` exists and the
access status is `active` or `stale`. `missing`, `needs_validation`, `invalid`,
and `disabled` are blocked with the backend-provided explanation. Azure uses
public access and no connection id. The
screen opens a confirmation dialog before dispatching the refresh event. The
dialog repeats the exact identity/account/project used.

### PricingRefreshRunSummary

Shows only provider, terminal status, credential identity, completion time, and
safe error text. `resultSummary` stays out of the default UI.

| Parameter | Type | Required | Default |
|---|---|---:|---|
| run | `PricingRefreshRun` | yes | - |

### PricingCandidateReviewPanel

Receives reports, selected candidate ids, selected report/trace state, and
callbacks. The panel is absent before a successful run. It is one collapsed
section by default. Individual reports are also collapsed. Trace is loaded only
when requested and remains collapsed by default.

Candidate actions:

- `Approve` is enabled only for a candidate contained in the report and when
  `deterministicSelection.selectable` is true.
- `Mark unresolved` submits `decision=defer` with no candidate id.
- AI suggestion is a diagnostic label only and never persists automatically.

| Parameter | Type | Required | Default |
|---|---|---:|---|
| reports | `List<PricingCandidateReport>` | yes | - |
| selectedCandidateIds | `Map<String, String>` | yes | - |
| traces | `Map<String, PricingTrace>` | yes | - |
| traceErrors | `Map<String, String>` | yes | - |
| loadingTraceReportIds | `Set<String>` | yes | - |
| submittingReportIds | `Set<String>` | yes | - |
| onCandidateSelected | callback `(reportId, candidateId)` | yes | - |
| onTraceRequested | `ValueChanged<String>` | yes | - |
| onDecisionRequested | callback `(reportId, decision, candidateId?)` | yes | - |

### PricingHealthRow

The Dashboard row switches from `PricingReviewStateResponse` to
`PricingHealthResponse`. It keeps one action, `Review pricing`, and adds the
backend-provided source/account label without adding controls to provider cards.

All components must use `AppSpacing`, `AppColors`, and `ThemeData.textTheme`.
All new user-facing strings must be grouped in
`pricing_review_strings.dart`. No new package is allowed. Material icons only.

## 5. Responsive Behavior

| Breakpoint | Width | Required behavior |
|---|---:|---|
| Wide Desktop | >= 1440 | provider items in one row; workspace action aligned right |
| Narrow Desktop/Web | 900-1439 | provider items remain in one row; workspace wraps metadata before action |
| Compact Web | < 900 | segmented provider selector; workspace and actions stack; buttons full width |

Long source labels must ellipsize in selector items and wrap in the workspace.
No horizontal page scrolling is permitted.

## 6. State Flow (BLoC)

`PricingReviewBloc` is the only state owner for the Pricing Review screen.

Required events:

- `PricingReviewStarted`
- `PricingReviewReloadRequested`
- `PricingReviewProviderSelected(provider)`
- `PricingReviewProviderRefreshRequested(provider, connectionId)`
- `PricingReviewReportsReloadRequested(provider)`
- `PricingReviewReportExpanded(reportId)`
- `PricingReviewCandidateSelected(reportId, candidateId)`
- `PricingReviewDecisionRequested(reportId, decision, candidateId?)`
- `PricingReviewFeedbackCleared`

Required state:

- `PricingHealthResponse? pricingHealth` and `String? pricingHealthError`
- `CloudAccessInventory? cloudAccess` and `String? cloudAccessError`
- `String selectedProvider`, default `aws`
- independent loading flags for health and access so partial data stays visible
- `String? refreshingProvider`
- `Map<String, PricingRefreshRun> latestRunsByProvider`
- `Map<String, List<PricingCandidateReport>> reportsByProvider`
- `Map<String, String> reportsErrorsByProvider`
- `Map<String, String> selectedCandidateIds`
- `Set<String> loadingTraceReportIds`
- `Map<String, PricingTrace> traces`
- `Map<String, String> traceErrors`
- `Set<String> submittingDecisionReportIds`
- `PricingReviewFeedback? feedback`

Required data flow:

```text
UI -> event -> PricingReviewBloc -> ApiService -> Management API :5005
   <- state <- typed model parsing <- response ------------------|
```

Initial load requests `/optimizer/pricing-health` and `/cloud-access`. Refresh
posts the provider and explicitly confirmed connection id. On a successful run,
the BLoC loads candidate reports and then reloads health/access. Trace requests
are lazy. A private in-flight guard prevents duplicate refresh POSTs even when
events arrive before a state rebuild. No Twin list is loaded.

The current Management API completes the fetch inside the refresh POST and
returns a terminal run. Its SSE route repeats that terminal state and exposes no
intermediate progress. This slice must show an honest indeterminate provider
loading state while awaiting the POST and must not fabricate progress events.
The service method must use `Duration(minutes: 20)` as its receive timeout for
the existing long-running GCP request.

## 7. Design Tokens

Reuse:

- `AppSpacing.xs/sm/md/lg/xl`
- `AppSpacing.maxContentWidthLarge`
- `AppSpacing.pricingReviewCardBreakpoint`
- `AppSpacing.borderRadiusSm`
- `AppSpacing.actionButtonHeight`
- provider colors and semantic colors from `AppColors`

No new color or spacing token is required. Any newly discovered layout value
must be added to the token files before widget use.

## 8. Interactions & Animations

- Provider selection is immediate and keyboard-focusable.
- Refresh opens a confirmation dialog. Enter confirms; Escape cancels.
- While refreshing, only provider selection and refresh commands are disabled;
  existing content remains readable.
- Feedback appears as one compact inline banner and can be dismissed.
- Candidate and trace disclosure uses Material `ExpansionTile`; no custom
  animation is introduced.
- Loading uses bounded inline indicators, never a full-screen blocker.
- Errors are inline with a retry action. Empty reports show one sentence and no
  decorative container.

## 9. Accessibility

- Focus order: back, reload, providers AWS/Azure/GCP, refresh, review expansion,
  candidate choices, decision actions, trace expansion.
- Provider selectors expose semantic labels containing provider and status.
- Disabled refresh actions expose the backend reason in visible helper text.
- Color is never the only state indicator; every state has text.
- Body and action text must use theme colors meeting WCAG AA contrast.

## 10. Integration Points

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/optimizer/pricing-health` | none | `pricing-health.v1` |
| GET | `/cloud-access` | none | `cloud-access-inventory.v1` |
| POST | `/optimizer/pricing-refresh/{provider}` | `{pricing_connection_id, force}` | `pricing-refresh-run.v1` |
| GET | `/optimizer/pricing-review/{provider}/candidate-reports?refresh_run_id=...` | none | report list v1 |
| GET | `/optimizer/pricing-review/candidate-reports/{report_id}/trace` | none | `pricing-trace.v1` |
| POST | `/optimizer/pricing-review/decisions` | report, decision, candidate | decision v1 |

Route `/pricing-review` has no `twin_id` query parameter. All calls go through
the Management API. Ports 5003 and 5004 are forbidden.

The terminal-only refresh SSE route is intentionally not consumed. A future
asynchronous backend run contract may add reconnectable progress without
changing the typed run/report models introduced here.

## 11. Test Plan

Model tests must cover complete payloads, missing optional metadata, empty
provider maps, unknown status strings, numeric candidate values, null values,
date parsing, and bounded trace parsing.

BLoC tests:

| Type | Case | Required assertion |
|---|---|---|
| Happy | initial load | health/access stored; no Twin API call |
| Happy | Azure refresh | POST has null connection; reports reload |
| Happy | AWS refresh | confirmed connection id is forwarded exactly |
| Happy | approve candidate | exact report/candidate submitted once |
| Unhappy | health load fails | inline error state, retry remains available |
| Unhappy | refresh run fails | safe backend error shown; no reports loaded |
| Unhappy | trace load fails | report remains usable; trace error is scoped |
| Unhappy | decision rejected | candidate selection remains; error shown |
| Edge | AWS missing connection | refresh event is ignored/blocked |
| Edge | provider switched during refresh | active run stays associated with original provider |
| Edge | duplicate refresh click | one API call only |
| Edge | empty reports | explicit empty review result |
| Edge | report has no candidates | only defer is available |
| Edge | AI suggestion differs | suggestion displayed but not persisted |
| Edge | stale response after reload | current selected provider is preserved |

Widget tests must verify wide/compact selector behavior, missing credential,
Azure public source, collapsed default details, expansion, candidate choice,
decision loading, and long-label overflow safety.

Commands:

```text
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/dev.json
flutter build macos --dart-define-from-file=config/dev.json
```

An optional integration smoke may read health/access from local Docker. It must
not start AWS/GCP refresh or deploy cloud resources. Real cloud E2E is forbidden.

## 12. Definition of Done

- [x] Twin selector and twin-bound pricing refresh API usage are removed.
- [x] Dashboard consumes typed global pricing health.
- [x] Pricing Review consumes typed health and cloud access inventory.
- [x] AWS/GCP refresh requires explicit account confirmation.
- [x] Azure refresh clearly uses the public API.
- [x] Typed refresh run status and safe errors are visible.
- [x] Candidate reports and sanitized traces are collapsed by default.
- [x] Decisions persist only through Management API.
- [x] Loading, error, empty, partial, and success states are implemented.
- [x] Main views remain visually lean at all breakpoints.
- [x] No direct Optimizer/Deployer call exists.
- [x] No hardcoded color/spacing additions exist.
- [x] `flutter analyze` passes with zero issues.
- [x] `flutter test` passes.
- [x] Web and macOS builds pass.
- [x] Frontend delta roadmap records completion of this account-scoped slice.
- [x] Only task files are committed; `pubspec.lock` remains untouched.
- [x] Implementation is ready for auditor verification.
