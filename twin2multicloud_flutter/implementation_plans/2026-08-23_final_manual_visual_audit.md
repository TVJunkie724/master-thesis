---
title: "Implementation Plan: Final Manual Flutter Visual Audit"
description: "Complete credential-free visual, interaction, accessibility, architecture, and release-gate audit for issue #111."
tags: [flutter, audit, accessibility, responsive, thesis]
lastUpdated: "2026-08-23"
version: "1.3"
status: "complete"
---

# Implementation Plan: Final Manual Flutter Visual Audit

**Approval:** Genehmigt by the user on 2026-08-23 after the mandatory
Architect/Builder plan review reached zero unresolved gaps.
The v1.2 baseline-token clarification was re-reviewed under the same approved
PoC boundary and introduced no product scope or unresolved plan gap.
Execution completed with a zero-finding full re-audit; issue #111 was closed
as completed on 2026-08-23.

## 0. Git Branch

- **Branch name:** `codex/post-phase8-finalization-concept`
- **Base branch:** `master` at `defb2042`
- **Merge strategy:** merge commit into `master`; no rebase of shared history.
- **Session ID:** `AI-0823-AUDT`
- **Mutation boundary:** Flutter source changes are allowed only for a recorded
  audit finding. No Optimizer, Deployer, Management API, credential, or live
  cloud mutation is authorized by this plan.
- **Push boundary:** keep commits local until the user requests publication.

The current `codex/` branch follows the active workspace convention and the
user-approved post-Phase-8 sequence. Historical `ai/dev` guidance does not
override the current branch policy or the already merged `master` baseline.

## 1. Summary

This plan executes the final whole-application quality gate from GitHub issue
#111 and the approved
[Post-Phase-8 Flutter Finalization](../docs/frontend_delta/concepts/CONCEPT_POST_PHASE_08_FINALIZATION.md)
concept. It audits the application as one coherent Thesis PoC after the
Configuration Workspace, pricing, operations, CloudConnection, architecture
profile, Five-layer v2, and Six-layer v1 work.

The audit has three outcomes only:

1. a finding is fixed and covered by regression evidence;
2. a finding is represented by an actionable issue and explicit limitation;
3. all eleven auditor phases pass with no unrecorded finding.

This plan adds no feature by itself. It defines the evidence matrix, safe
runtime boundary, viewport coverage, interactions, and completion criteria.
Real-provider E2E remains owned only by #107.

Every numbered section, test unit, audit phase, and Definition of Done item in
this plan is binding and must be completed. Nothing may be skipped because it
appears redundant with historical evidence.

## 2. Visual Layout (ASCII)

The audit covers the complete reachable route tree and its overlays.

```text
Application shell
|
|-- /login                         [production composition only]
|
`-- authenticated/demo shell
    |
    |-- /dashboard                 Dashboard summary and Twins table
    |   |-- navigation menu
    |   `-- destructive delete confirmation
    |
    |-- /settings                  Profile, theme, cloud access
    |   |-- connection create/validate/delete dialogs
    |   `-- guided bootstrap dialog and manual-prerequisite states
    |
    |-- /pricing-review            Provider freshness and reviewed evidence
    |   |-- provider selector
    |   |-- refresh/review states
    |   `-- collapsed trace/evidence panels
    |
    |-- /wizard                    New Configuration Workspace
    |-- /wizard/:twinId            Existing draft/configuration
    |   |-- Define Twin
    |   |-- Describe Workload
    |   |-- Choose Architecture
    |   |-- Prepare Deployment
    |   `-- Review Configuration
    |
    `-- /twins/:id/overview        Operational Twin Overview
        |-- readiness and deployment operations
        |-- resolved configuration and architecture
        |-- logs, outputs, trace, and simulator diagnostics
        |-- L4 Twin UI / L5 Grafana access cards
        `-- destroy, viewer-rotation, and one-time reveal dialogs
```

The same content hierarchy is inspected at three viewport classes:

```text
Wide desktop / Web >= 1440
+--------------------------------------------------------------+
| persistent navigation / header                               |
+----------------------+---------------------------------------+
| task/sidebar column  | primary content + evidence panels     |
| where applicable     |                                       |
+----------------------+---------------------------------------+

Narrow desktop / Web 1024-1439
+--------------------------------------------------------------+
| header / compact navigation                                  |
+--------------------------------------------------------------+
| stacked or constrained primary content                       |
| secondary evidence follows in reading order                  |
+--------------------------------------------------------------+

Compact supported Web 640-1023
+--------------------------------+
| compact header                 |
+--------------------------------+
| single-column scroll           |
| no horizontal page overflow    |
| actions wrap or stack          |
+--------------------------------+
```

Mobile widths below 640 px are outside the supported application contract.

## 3. Widget Tree

No new production widget is planned. Every node is `[REUSE]` and is an audit
target; a node may become `[MODIFY]` only after a concrete finding is recorded.

```text
ProviderScope                                      [REUSE]
`-- Twin2MultiCloudApp                             [REUSE] lib/app.dart
    `-- MaterialApp.router                         [REUSE]
        |-- DemoModeBanner                         [REUSE] lib/widgets/demo_mode_banner.dart
        `-- GoRouter                               [REUSE]
            |
            |-- LoginScreen                        [REUSE] lib/screens/login_screen.dart
            |   `-- LoginBody
            |       |-- DevelopmentLogin
            |       `-- ProductionProviderActions
            |           |-- ProviderAction
            |           `-- ExternalLoginPending / AuthProgress
            |
            |-- DashboardScreen                    [REUSE] lib/screens/dashboard_screen.dart
            |   `-- SelectableScaffold
            |       |-- BrandedAppBar
            |       |   |-- theme action
            |       |   `-- profile PopupMenuButton
            |       `-- scrollable constrained content
            |           |-- StatCard row
            |           |-- PricingHealthRow
            |           `-- Twins card
            |               |-- state FilterChip group
            |               |-- loading / error / empty branch
            |               `-- sortable Twins DataTable and delete dialogs
            |
            |-- SettingsScreen                     [REUSE] lib/screens/settings_screen.dart
            |   `-- SelectableScaffold
            |       |-- BrandedAppBar and profile menu
            |       `-- SettingsCloudAccessScope / CloudAccessBloc
            |           `-- SettingsContent
            |               |-- ProfileSection
            |               |-- LoginAccountsSection
            |               `-- CloudAccountsPanel
            |                   |-- create / validate / default / delete flows
            |                   `-- CloudBootstrapDialog
            |
            |-- PricingReviewScreen                [REUSE] lib/screens/pricing_review/pricing_review_screen.dart
            |   `-- PricingReviewBloc / PricingReviewView
            |       `-- SelectableScaffold
            |           |-- BrandedAppBar
            |           `-- constrained scroll content
            |               |-- PricingProviderSelector
            |               |-- InlineFeedback
            |               `-- PricingProviderWorkspace
            |                   |-- PricingRefreshRunSummary
            |                   `-- PricingCandidateReviewPanel
            |
            |-- WizardScreen                       [REUSE] lib/screens/wizard/wizard_screen.dart
            |   `-- WizardBloc / WizardView
            |       `-- ConfigurationWorkspaceScaffold
            |           |-- ConfigurationWorkspaceAppBar
            |           |-- ConfigurationWorkspaceHeader
            |           |-- ConfigurationAlertStack
            |           |-- ConfigurationWorkspaceShell
            |           |   |-- ConfigurationTaskSidebar >= 960 px
            |           |   |-- ConfigurationTaskSelector < 960 px
            |           |   `-- current task
            |           |       |-- ArchitectureProfileTask
            |           |       |   |-- ArchitectureProfileChoice
            |           |       |   `-- LogicalProfileFlow
            |           |       |-- CloudAccessTask
            |           |       |-- Step1Configuration
            |           |       |-- Step2Optimizer
            |           |       |-- Step3Deployer
            |           |       `-- ConfigurationReviewTask
            |           `-- ConfigurationNavigationBar
            |
            `-- TwinOverviewScreen                 [REUSE] lib/screens/twin_overview/twin_overview_screen.dart
                `-- TwinOverviewBloc / TwinOverviewView
                    |-- loading / error / loaded branch
                    `-- TwinOverviewContent        [REUSE] lib/widgets/twin_overview/
                        |-- TwinOverviewNavigationHeader
                        |-- TwinOverviewNameHeader
                        |-- DeploymentReadinessPanel
                        |-- LayerAccessPanel when deployed
                        |-- DeploymentOperationsPanel / DeploymentTerminal
                        |-- TestingUtilitiesPanel when deployed
                        |-- TerraformOutputsCard / DeploymentOutputsError
                        |-- DeploymentVerificationCard when deployed
                        |-- TwinOverviewConfigurationReview
                        `-- deploy / destroy / delete / simulator /
                            viewer-rotation / one-time-reveal dialogs
```

The audit also inventories every `showDialog`, `showModalBottomSheet`, menu,
expansion panel, file picker entry, external-link action, and transient
notification reachable from these roots.

## 4. Component Specifications

Because the plan adds no component, this section specifies audit inputs and
required evidence rather than new constructors.

| Component | Required inputs | States to inspect | Evidence |
|---|---|---|---|
| Application/router shell | runtime mode, auth state, theme | redirect, authenticated, demo, unknown/deep route | route test, code trace, visual smoke |
| Dashboard | typed stats, Twins, pricing health | showcase, empty, degraded, loading/error where deterministic | compact/wide screenshots and interaction notes |
| Settings / Cloud Access | profile and connection inventory | populated, empty, validation failure, delete blocked, bootstrap manual prerequisite | dialog/focus/secret-boundary evidence |
| Pricing Review | health, refresh run, candidate/evidence | ready, stale/review-required, degraded, provider switch, failure | state and collapsed evidence inspection |
| Configuration Workspace | draft, workload, profile, run, access, readiness | new/edit, unsaved, invalidated, blocked, loading/error/empty/data | journey matrix and navigation evidence |
| Twin Overview | lifecycle, readiness, operation, logs, outputs, layer access | configured/deployed/error/destroyed, reconnect/degraded, unavailable access | operation and responsive matrix |

Production files remain unchanged if the audit passes. A finding-specific
change must cite the violated approved plan, exact file/line, severity, fix,
and regression test before implementation.

## 5. Responsive Behavior

| Breakpoint | Exact audit width | Required behavior |
|---|---:|---|
| Wide desktop/Web | 1440 px | Multi-column layouts use available width without excessive empty space; navigation and evidence remain visible. |
| Narrow desktop/Web | 1024 px | Secondary columns collapse or constrain without truncating actions or changing task order. |
| Compact supported Web | 640 px | Single-column or explicitly compact layout; no RenderFlex/page overflow; actions remain reachable by keyboard and scrolling. |

Each width is inspected in light and dark themes on Web. The host-native macOS
application is inspected at wide and compact-supported window sizes. Windows
and Linux receive existing platform build/test evidence plus the shared Flutter
layout evidence; the report must state that platform-native manual interaction
was not available on the macOS host rather than claiming otherwise.

Text scaling is checked at 100 %, 150 %, and 200 % for representative dense
surfaces: Settings Cloud Access, Configuration Review, and Twin Overview.

## 6. State Flow (BLoC And Runtime Composition)

The current authoritative state boundary is preserved:

- Riverpod owns runtime mode, authentication, theme, router, and
  `ManagementApi` composition.
- `CloudAccessBloc`, `PricingReviewBloc`, `WizardBloc`, and
  `TwinOverviewBloc` own complex feature workflows.
- presentation widgets receive typed state/callbacks and do not perform HTTP.

No new event or state is introduced by this plan. The audit traces representative
flows end to end:

```text
User interaction
    -> Riverpod command or feature BLoC event
    -> typed ManagementApi port
    -> DemoManagementApi (manual audit) / ApiService (contract audit)
    -> typed response or normalized safe error
    -> provider/BLoC state
    -> visible loading / empty / blocked / error / data branch
```

Subscriptions, timers, controllers, and router instances must be disposed by
their current owners. SSE is inspected through the typed `LogStreamClient`
boundary and never through a direct provider or Deployer URL.

## 7. Design Tokens

No new token is planned. The audit checks current use of:

- `ThemeData.colorScheme` and text styles;
- `lib/theme/colors.dart` provider/status tokens;
- `lib/theme/spacing.dart` shared spacing tokens;
- Material icons already present in the project.

Any new or modified production UI color, spacing, or text style introduced by
an audit remediation must use the current shared theme/token boundary unless
the finding-specific change documents an exact framework-required exception.
The visual audit also treats an existing value as a finding when it causes an
observable contrast, consistency, responsive, or accessibility defect.

The already approved PoC baseline contains historical component-specific
Material palette values and exact editor/terminal geometry. Their mere
syntactic presence is not a new visual-audit finding: a mechanical whole-app
token rewrite would be a separate refactor without a user-facing audit target.
This clarification was added after the baseline scan and re-reviewed against
the Thesis PoC boundary. It does not permit new one-off values, and it does not
excuse any observed visual or accessibility defect.

## 8. Interactions And Animations

The audit verifies existing planned behavior; it adds no decorative animation.

| Interaction | Required result |
|---|---|
| Route/menu navigation | One deterministic destination, correct browser history, no use-after-dispose navigation. |
| Primary/secondary actions | Immediate busy/disabled feedback; repeated commands fail closed. |
| Dialogs and one-time reveals | Focus enters the dialog; Escape/cancel is safe; destructive/sensitive confirmation is explicit. |
| Expansion/evidence panels | Collapsed-by-default details remain keyboard reachable and preserve scroll position where specified. |
| Provider/task selection | Visible selected/focus state and no stale result from the previous selection. |
| Loading | Bounded progress indicator or explicit loading state, never a blank surface. |
| Error/degraded | Safe actionable message with retry/remediation where supported. |
| Empty | Truthful explanation and next action; no fabricated data. |

Material-default hover, focus, press, duration, and curve behavior is accepted
where no approved plan specifies a custom value. Any custom animation is
checked against its owning implementation plan and `pump`/visual behavior.

## 9. Accessibility

The audit requires:

1. logical Tab traversal following visual/read order;
2. visible focus on every interactive control;
3. semantic name, role, state, and disabled reason for non-obvious controls;
4. Escape for dismissible dialogs and Enter/Space activation where Material
   semantics apply;
5. no color-only status or provider distinction;
6. body-text contrast of at least 4.5:1 and large text/UI indicators of at
   least 3:1 for audited token pairs;
7. usable 200 % text scaling without clipped essential content;
8. destructive and secret-reveal actions that are not accidentally triggered
   by traversal.

Automated semantics/widget evidence complements but does not replace manual
keyboard and focus inspection on Web and macOS.

## 10. Integration Points

The manual audit uses `DemoManagementApi` and `DemoLogStreamClient`, so it makes
no HTTP request. The static/automated contract audit covers the production
adapter groups below through the single Management API origin:

| Boundary | Representative methods/paths | Audit requirement |
|---|---|---|
| Authentication/profile | `/auth/*`, `/users/me` | Router guards and safe errors; demo never starts external auth. |
| Twins/configuration | `/twins`, `/twins/{id}`, `/twins/{id}/config` | Typed create/edit/hydration and ownership-safe errors. |
| Cloud access/bootstrap | `/cloud-connections/*`, `/cloud-bootstrap/*` | No secret response rendering or persistence in Flutter. |
| Pricing/optimization | `/optimizer/pricing-health`, refresh/review/run endpoints | Typed freshness/evidence and no client-authored trusted pricing. |
| Architecture profiles | `/architecture-profiles/*`, Twin selection/resolution | Complete read-only profiles and revision-safe invalidation. |
| Deployment operations | Twin readiness/preflight/deploy/destroy/log/output endpoints | Typed operations, redaction, and bounded SSE recovery. |
| Layer access | Twin deployment access and GCP viewer rotation endpoints | Exact L4/L5 handoff and one-time credential handling. |

Registered routes are `/login`, `/dashboard`, `/settings`, `/pricing-review`,
`/wizard`, `/wizard/:twinId`, and `/twins/:id/overview`. No Flutter source may
call ports 5003/5004 or provider endpoints directly.

## 11. Test Plan

Existing tests are reused first. A new test is added only to reproduce a
finding that is not already protected.

Every automated test must assert an exact value, exact state, or exact widget
count. Integration tests must use the real local Management API; HTTP clients
are not mocked at integration level.

### Unit A: Route And Shell Inventory

| # | Type | Test description | Expected outcome |
|---:|---|---|---|
| 1 | Happy | Demo starts at Dashboard | Authenticated demo shell and banner render once. |
| 2 | Happy | Authenticated production route navigation | Every registered route resolves to its intended screen. |
| 3 | Unhappy | Unauthenticated protected deep link | Redirects to Login without loop. |
| 4 | Unhappy | Disposed/recomposed router during login | No navigation through a disposed router; safe error is visible on failure. |
| 5 | Edge | Unknown route | Truthful router error/no blank screen. |
| 6 | Edge | Browser back/forward | Matched route and selected navigation remain consistent. |
| 7 | Edge | Theme switch | Route and feature state survive theme recomposition. |
| 8 | Edge | Demo scenario switch at process start | Exact fixture loads once without network dependency. |
| 9 | Edge | Rapid navigation | No duplicate route action or post-dispose callback. |

### Unit B: Scenario And Async-State Coverage

| # | Type | Test description | Expected outcome |
|---:|---|---|---|
| 1 | Happy | Showcase scenario across all routes | Populated typed surfaces render and primary navigation remains usable. |
| 2 | Happy | Complete create/edit Configuration Workspace paths | Correct task order, save/finish gates, and selected architecture evidence. |
| 3 | Unhappy | Degraded scenario | Provider/operation failures are explicit, redacted, and recoverable where supported. |
| 4 | Unhappy | Contract/parser failure in a representative feature | Safe error state replaces stale data. |
| 5 | Edge | Empty scenario | Every route has a truthful empty state and next action. |
| 6 | Edge | Review-required pricing | Calculation gating follows server health evidence. |
| 7 | Edge | Architecture change invalidates a selected run | Stale run and deployment readiness fail closed. |
| 8 | Edge | Deployment log reconnect/catch-up | No gap, duplicate, or unbounded buffer. |
| 9 | Edge | Historical/unsupported access surface | No fabricated L4/L5 link or credential. |

### Unit C: Responsive And Accessibility Coverage

| # | Type | Test description | Expected outcome |
|---:|---|---|---|
| 1 | Happy | 1440 px light/dark walkthrough | Intended wide hierarchy and readable contrast. |
| 2 | Happy | 640 px light/dark walkthrough | Single-column/compact behavior without overflow. |
| 3 | Unhappy | 200 % text scale on dense review panels | Essential text/actions remain visible and scrollable. |
| 4 | Unhappy | Keyboard-only destructive/sensitive workflow | Confirmation cannot be bypassed or accidentally accepted. |
| 5 | Edge | 1024 px breakpoint transition | No duplicated, lost, or reordered action. |
| 6 | Edge | Long names, regions, IDs, and errors | Wrap/truncate with accessible full meaning; no page overflow. |
| 7 | Edge | Empty and one-item lists | Stable alignment and meaningful semantics. |
| 8 | Edge | Focus after dialog close | Returns to the invoking control or a deterministic safe target. |
| 9 | Edge | Expansion panel traversal | Header and children follow logical Tab order. |

### Unit D: Quality, Security, And Platform Gates

| # | Type | Test description | Expected outcome |
|---:|---|---|---|
| 1 | Happy | Architecture checker and self-tests | No direct-service, diagnostic, secret-literal, or runtime-config finding. |
| 2 | Happy | Analyzer, full Flutter suite, Web/macOS builds | All commands pass from a clean worktree. |
| 3 | Unhappy | Secret-shaped fixture/response | Raw/typed guards reject or redact it before presentation. |
| 4 | Unhappy | Direct port/service literal fixture in checker self-test | Checker fails with sanitized diagnostics. |
| 5 | Edge | Windows/Linux platform workflows | Tracked platform gates remain configured and last run is recorded. |
| 6 | Edge | Web release build with demo config | Build contains no service URL, token, or credential. |
| 7 | Edge | macOS host build/run | Native window launches in demo mode with no cloud access. |
| 8 | Edge | Dirty worktree after evidence capture | Only planned audit report/finding fixes are present. |
| 9 | Edge | Deadline/aborted audit | Report remains explicitly incomplete; issue #111 is not closed. |

### Unit E: Credential-Free Management API Integration

| # | Type | Test description | Expected outcome |
|---:|---|---|---|
| 1 | Happy | Run the canonical frontend integration entrypoint | Real Management API readiness, architecture, user-function, bootstrap, and layer-access contracts pass on the host desktop. |
| 2 | Happy | Existing local services predate the gate | They remain running after the gate; only the temporary isolated fixture is removed. |
| 3 | Unhappy | Credential overlay is requested | Entrypoint rejects the run before starting tests. |
| 4 | Unhappy | A submitted/revealed sentinel reaches logs or SQLite | Gate fails with a redacted diagnostic. |
| 5 | Edge | Required services are initially stopped | Gate starts only missing credential-free services and stops only those it started. |
| 6 | Edge | Optimizer was already running | Gate restores its normal catalog-age policy after the fixture-only run. |
| 7 | Edge | Layer Access fixture test runs | Isolated container/database is used and removed after success or failure. |
| 8 | Edge | Management API is unavailable | Readiness wait fails boundedly; no Flutter test silently passes. |
| 9 | Edge | Integration command exits non-zero | Audit verdict remains REJECTED and #111 stays open. |

Required command from the repository root:

```bash
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
```

The entrypoint enforces no credential overlay, starts only missing local
services, stops only services it started, restores a pre-existing Optimizer,
and always removes the isolated Layer Access fixture. Do not replace it with a
blanket `docker compose down`, because that would destroy unrelated local
state.

All five units meet or exceed the minimum two happy, two unhappy, and five edge
cases because this audit covers routing, asynchronous state machines,
responsive/accessibility behavior, real local integration, and cross-platform
release evidence rather than one isolated widget.

### Documentation Output

The final phase must create
`twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_10_FINAL_MANUAL_VISUAL_AUDIT.md`.
It records the route/state/viewport matrix, all eleven auditor phases, exact
commands/results, manual Web/macOS observations, Windows/Linux evidence limits,
findings and their disposition, cloud-safety statement, and APPROVED/REJECTED
verdict. Screenshots are committed only when needed to prove a concrete visual
finding; otherwise the report references reproducible scenario/route/viewport
coordinates and avoids binary repository noise.

## 12. Definition Of Done

- [x] The plan is approved by `plan-review` before audit execution.
- [x] Every registered route, reachable overlay, menu, and external-access
      action appears in the audit matrix.
- [x] Showcase, empty, and degraded demo scenarios are inspected without
      network or cloud access.
- [x] Wide, narrow, compact-supported, light, dark, and representative text
      scale states are inspected.
- [x] Web and macOS receive manual visual/interaction evidence; Windows and
      Linux platform-native limitations and automated gates are recorded.
- [x] Keyboard, focus, semantics, contrast, scrolling, overflow, truncation,
      destructive confirmation, and secret disclosure boundaries are checked.
- [x] Every finding is fixed with regression evidence or tracked as an explicit
      issue/Thesis limitation.
- [x] `python3 -m unittest scripts.tests.test_check_flutter_architecture` passes.
- [x] `python3 scripts/check_flutter_architecture.py` passes.
- [x] `flutter analyze --no-pub` reports zero issues.
- [x] The full `flutter test --no-pub` suite passes.
- [x] Web release and macOS debug/release audit builds succeed with tracked,
      secret-free configuration.
- [x] The supported-platform CI definition and latest evidence for Windows and
      Linux are recorded honestly.
- [x] No Flutter call to Optimizer, Deployer, or a cloud provider exists.
- [x] No live pricing refresh, bootstrap execution, provider validation,
      deployment, destroy, simulator cloud execution, or billing mutation ran.
- [x] A canonical audit report records phase-by-phase evidence, findings,
      residual risks, and the final APPROVED/REJECTED verdict.
- [x] Commits follow `[AI-0823-AUDT] type(scope): description` and remain
      reviewable as plan, finding fixes, and final evidence slices.
- [x] Issue #111 closes only after a zero-finding full re-audit.
