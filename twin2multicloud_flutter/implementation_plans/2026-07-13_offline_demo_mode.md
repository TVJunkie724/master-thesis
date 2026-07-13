# Implementation Plan: Offline Demo Mode

## 0. Git Branch

- **Branch name:** `codex/flutter-offline-demo-mode`
- **Base branch:** `master` at `1556409`
- **Merge strategy:** Merge commit; no rebase.
- **Commit prefix:** `[AI-0713-demo]`
- **Approval:** The user approved the ports/adapters plus provider-composition
  target and explicitly requested implementation on 2026-07-13.

## 1. Summary

Twin2MultiCloud must provide a deterministic, credential-free showcase mode
that can display and exercise every Flutter screen without Docker, cloud
accounts, OpenAI, or network access. The mode must use the production widgets,
routes, BLoCs, validation code, and domain models. Only infrastructure adapters
are replaced at the application composition root.

Required implementation slices:

1. Define explicit Management API and log-stream ports and make the existing
   HTTP/SSE clients production adapters.
2. Add validated, versioned fixture scenarios and a mutable in-memory demo
   store.
3. Implement a deterministic demo Management API adapter covering every method
   in the production contract.
4. Compose demo authentication, repositories, and log streams centrally and
   mark the runtime visibly as demo data.
5. Add `./thesis.sh demo`, documentation, contract tests, full user-flow tests,
   route smoke tests, and Desktop/Web build gates.

Non-goals:

- No separate demo screens or duplicated widget tree.
- No live cloud calls, real deployment, real credential validation, or Docker
  dependency.
- No persistence after application restart.
- No random failures or timing-dependent fixtures.
- No production backend changes.

## 2. Visual Layout (ASCII)

Every existing screen remains unchanged below a narrow, persistent runtime
marker. The marker is the only new global visual element.

Wide Desktop and Web:

```text
+--------------------------------------------------------------------------+
| DEMO  Local sample data | Offline | Changes reset when the app restarts  |
+--------------------------------------------------------------------------+
| Existing Login/Dashboard/Settings/Pricing/Wizard/Twin Overview screen    |
|                                                                          |
| The exact production widget tree is rendered here.                       |
+--------------------------------------------------------------------------+
```

Compact Web:

```text
+------------------------------------------------+
| DEMO | Offline sample data | Resets on restart |
+------------------------------------------------+
| Existing responsive production screen          |
+------------------------------------------------+
```

The demo starts authenticated on `/dashboard`. All remaining routes are
reached through existing production navigation and fixture twins.

## 3. Widget Tree

```text
[MODIFY] main.dart
`-- [REUSE] ProviderScope
    `-- [MODIFY] Twin2MultiCloudApp
        `-- [REUSE] MaterialApp.router
            `-- builder
                `-- [NEW] DemoModeBanner
                    `-- [REUSE] existing routed screen child

[REUSE] DashboardScreen
[REUSE] SettingsScreen
[REUSE] PricingReviewScreen
[REUSE] WizardScreen
[REUSE] TwinOverviewScreen
```

`DemoModeBanner` is necessary because no existing widget communicates a
runtime trust boundary. It must not become a navigation control or feature
description.

## 4. Component Specifications

### 4.1 Runtime configuration

- **File:** `lib/config/app_runtime.dart`
- Define `AppMode { development, production, demo }`.
- Parse `APP_MODE`; unsupported values must fail fast with an actionable
  `StateError`.
- Parse `DEMO_SCENARIO`; supported values are `showcase`, `empty`, and
  `degraded`.
- Expose immutable `AppRuntimeConfig` through a Riverpod provider.
- `demo` must never depend on `API_BASE_URL` or `DEV_AUTH_TOKEN`.
- `main()` must initialize Flutter bindings, parse runtime configuration, and
  await `RuntimeComposition.bootstrap(...)` before `runApp`. The resulting
  immutable dependency graph is supplied through provider overrides. This
  guarantees that fixture validation and the initial demo user exist before
  auth and router providers build.

### 4.2 Infrastructure ports

- **File:** `lib/services/management_api.dart`
- Define narrow repository interfaces for user preferences, twins, cloud
  access, pricing, optimization, deployment configuration, deployment
  lifecycle, and verification.
- Define a composite `ManagementApi` implemented by both infrastructure
  adapters.
- **File:** `lib/services/api_service.dart`
- `ApiService` must implement `ManagementApi` without changing endpoint,
  timeout, token, or error behavior.
- BLoCs/helpers must depend on the narrowest compatible port or on the
  composite contract where a feature crosses several boundaries.

### 4.3 Log-stream port

- **File:** `lib/services/log_stream_client.dart`
- Define `LogStreamClient.streamDeploymentLogs(...)` and `cancel()`.
- Define an injected `LogStreamClientFactory`.
- `SseService` must implement this port.
- Twin overview and deployment verification BLoCs must receive the factory;
  neither may construct `SseService` directly.

### 4.4 Demo fixture catalog and store

- **Files:**
  - `assets/demo/v1/showcase.json`
  - `assets/demo/v1/empty.json`
  - `assets/demo/v1/degraded.json`
  - `lib/demo/demo_fixture_store.dart`
- Fixture root must contain `schema_version`, `scenario`, `user`, and the
  required domain collections.
- The loader must reject unsupported versions, duplicate twin/connection IDs,
  dangling references, unknown providers, and missing required collections.
- All returned maps/lists must be defensive copies so callers cannot mutate the
  catalog outside the store transaction methods.
- Store mutations must be in-memory and deterministic. IDs use a monotonic
  scenario-local sequence; timestamps use an injected clock.

Required fixture collections:

| Key | Required type | Ownership and references |
|---|---|---|
| `schema_version` | integer | Must equal `1`. |
| `scenario` | string | Must match the selected fixture name. |
| `user` | object | Demo identity and theme preference. No secret fields. |
| `twins` | array | Unique twin IDs and valid lifecycle states. |
| `twin_configs` | object | Keyed by existing twin ID; connection IDs must exist. |
| `optimizer_configs` | object | Keyed by existing twin ID. |
| `deployer_configs` | object | Keyed by existing twin ID. |
| `cloud_connections` | array | Unique IDs; provider and purpose enums are validated. |
| `cloud_access` | object | Provider inventory referencing existing connections. |
| `pricing_health` | object | Contract-compatible AWS/Azure/GCP entries. |
| `pricing_reports` | object | Provider-keyed reports with unique report/candidate IDs. |
| `pricing_traces` | object | Keyed by existing report ID. |
| `deployment_outputs` | object | Keyed by existing twin ID. |
| `deployment_logs` | object | Keyed by existing twin ID. |
| `verification` | object | Infrastructure and data-flow results keyed by twin ID. |

The `showcase` scenario must include:

- one draft twin with incomplete configuration;
- one configured twin ready to deploy;
- one deployed twin with optimizer result, deployment outputs, logs,
  simulator artifact, and verification data;
- pricing access and health for AWS, Azure, and GCP;
- at least one pricing review report with candidates, trace, and optional AI
  suggestion;
- purpose-separated pricing and deployment cloud connections.

`empty` must exercise empty onboarding states. `degraded` must exercise stale
pricing, missing provider access, failed/review-required evidence, and a twin in
an error state.

### 4.5 Demo adapters

- **Files:**
  - `lib/demo/demo_management_api.dart`
  - `lib/demo/demo_log_stream_client.dart`
- `DemoManagementApi` implements the complete `ManagementApi` contract.
- Reads use fixture-backed data; writes update the in-memory store.
- Create/update/delete twin, wizard persistence, cloud account CRUD,
  validations, pricing refresh/review, optimization, deployer configuration,
  deployment/destroy, outputs/logs, simulator download, and verification must
  all produce contract-compatible results.
- Operations use a short injected latency. Tests set it to zero.
- Invalid IDs, invalid state transitions, conflicting deletes, and malformed
  inputs must throw a typed `DemoApiException` containing a stable error code
  and a safe user-facing message instead of silently succeeding.
- The adapter must not import `dio`, `dart:io`, or any network package.
- Demo log streams emit deterministic log, completion, output, trace, and
  verification events. Stream cancellation must release controllers/timers.

### 4.6 Runtime composition and banner

- **Files:**
  - `lib/providers/runtime_providers.dart`
  - `lib/providers/twins_provider.dart`
  - `lib/providers/auth_provider.dart`
  - `lib/app.dart`
  - `lib/widgets/demo_mode_banner.dart`
- The composition provider chooses exactly one adapter graph:
  - `development`/`production`: `ApiService` + `SseService`;
  - `demo`: `DemoManagementApi` + `DemoLogStreamClient`.
- No widget or BLoC may branch on demo mode to alter business behavior.
- Demo authentication is initialized centrally with a fixture-backed user;
  routing starts at `/dashboard`.
- Logging out must expose the real login screen for inspection. Logging in
  again restores the same fixture user without network access.
- `DemoModeBanner` parameters:

| Name | Type | Required | Default |
|---|---|---:|---|
| `child` | `Widget` | yes | none |
| `scenario` | `DemoScenario` | yes | none |

- Stateless widget; uses existing theme color scheme, spacing tokens, and
  Material icons. It must remain one compact row and adapt its wording on
  compact widths.

### 4.7 Startup command

- **Files:**
  - `thesis.sh`
  - `config/demo.json`
  - `README.md`
- Add `./thesis.sh demo [--device ID] [--scenario NAME] [--setup]`.
- The command must run Flutter only; it must not inspect or start Docker.
- It must pass `config/demo.json` and a validated scenario override.
- `config/demo.json` is tracked and contains no URL, token, or secret.
- Unsupported scenarios and demo-only incompatible flags fail before Flutter
  starts.

## 5. Responsive Behavior

| Breakpoint | Width | Behavior |
|---|---:|---|
| Wide Desktop | >= 1440 px | Full banner message in one row. Existing screen layout unchanged. |
| Narrow Desktop/Web | 800-1439 px | Full message may flex; banner remains one row. |
| Compact Web | < 800 px | Short banner labels; no horizontal overflow. Existing screen owns its current responsive behavior. |

The banner uses a stable minimum height and must not overlap app bars, dialogs,
or routed content.

## 6. State Flow (BLoC and Providers)

Provider composition owns infrastructure selection. Existing feature BLoCs own
all feature state.

```text
APP_MODE + DEMO_SCENARIO
          |
          v
AppRuntimeConfigProvider
          |
          +----------------------+----------------------+
          |                                             |
    real runtime                                  demo runtime
          |                                             |
 ApiService + SseService              DemoManagementApi + DemoLogStreamClient
          |                                             |
          +----------------------+----------------------+
                                 |
                         repository providers
                                 |
                    existing BLoCs / FutureProviders
                                 |
                         existing production UI
```

Demo operation flow:

```text
UI action -> existing BLoC event -> ManagementApi port
          -> DemoManagementApi -> validated DemoFixtureStore mutation
          -> contract response -> existing BLoC state -> existing UI
```

Deployment/verification flow:

```text
UI action -> existing BLoC -> DemoManagementApi starts session
          -> injected DemoLogStreamClient emits ordered events
          -> existing BLoC log/completion handlers -> terminal and outputs UI
```

## 7. Design Tokens

- Reuse `ThemeData.colorScheme` for banner foreground/background.
- Reuse `AppSpacing` for banner height, padding, icon gap, and compact
  breakpoint.
- Add tokens only if the current spacing catalog has no semantically compatible
  value. No literal colors or spacing values are permitted in the new widget.
- Use `Icons.science_outlined` and `Icons.cloud_off_outlined`; no new icon
  dependency.

## 8. Interactions and Animations

- Banner is informational and non-interactive.
- Existing route, hover, focus, and button behavior is reused unchanged.
- Demo calls use deterministic short latency so existing loading indicators are
  visible without making navigation slow.
- Deployment, destroy, trace, and verification streams use deterministic event
  intervals and terminal events.
- Empty and error behavior comes from `empty` and `degraded`; failures are
  scenario-defined, never random.

## 9. Accessibility

- Banner is a single semantic live-region-neutral status description.
- Decorative icons are excluded from semantics when the text already conveys
  the state.
- Banner text must retain WCAG AA contrast through the active color scheme.
- No new focus target is introduced.
- Existing screen tab order remains unchanged.

## 10. Integration Points

The HTTP adapter keeps all existing Management API endpoints unchanged. The
demo adapter performs no integration calls.

| Runtime | Management API | Optimizer/Deployer | Network |
|---|---|---|---|
| development | Existing port 5005 contracts | only through Management API | allowed |
| production | Existing deployed API contracts | only through Management API | allowed |
| demo | in-memory adapter | none | forbidden |

Routes remain:

| Route | Screen | Demo behavior |
|---|---|---|
| `/login` | Login | redirects to dashboard because fixture user is authenticated |
| `/dashboard` | Dashboard | fixture twins/stats/pricing health |
| `/settings` | Settings | fixture cloud accounts and mutations |
| `/pricing-review` | Pricing Review | fixture refresh, candidates, trace, decisions |
| `/wizard` | Wizard create | mutable in-memory twin creation |
| `/wizard/:twinId` | Wizard edit | complete fixture configuration journey |
| `/twins/:id/overview` | Twin Overview | deployed/configured/error fixture states and operations |

The initial demo location is `/dashboard`; `/login` remains reachable after
the existing logout action and must not be replaced by a demo-only screen.

## 11. Test Plan

### Unit and contract tests

1. Runtime parsing accepts all modes/scenarios and rejects unknown values.
2. Every fixture scenario validates successfully.
3. Invalid schema version, duplicate IDs, dangling connection references,
   missing collections, and unknown providers fail validation.
4. Demo API contract tests exercise every method at least once with hard value
   assertions.
5. Twin and cloud account mutations persist during one session and reject
   unknown/conflicting resources.
6. Pricing refresh creates deterministic runs/reports/traces/decisions.
7. Optimization and wizard save/read round trips preserve values.
8. Deployment/destroy enforce state transitions and update outputs/logs.
9. Simulator and verification return non-empty, contract-compatible data.
10. Demo stream emits ordered events, closes after a terminal event, and can be
    cancelled.
11. Static dependency test asserts demo sources do not import HTTP/SSE network
    packages.

### Widget and flow tests

1. Demo app starts authenticated at dashboard with visible demo marker.
2. Every registered route renders with the showcase fixture and no uncaught
   exception.
3. Empty scenario renders dashboard onboarding state.
4. Degraded scenario renders pricing/access/error states.
5. Full create/edit wizard flow reaches authoritative review.
6. Pricing provider refresh exposes candidates and persists a selected
   decision.
7. Configured twin deploy flow renders logs and final outputs.
8. Deployed twin verification renders infrastructure and data-flow results.
9. Compact and wide banner layouts have no overflow.

### Regression and build gates

```bash
flutter analyze
flutter test
flutter build web --dart-define-from-file=config/demo.json
flutter build macos --dart-define-from-file=config/demo.json
./thesis.sh demo --help
bash -n thesis.sh
```

No cloud E2E is allowed. Demo flow tests are offline widget/application tests,
not mocked live-API integration tests. Existing real Management API integration
boundaries remain unchanged.

## 12. Definition of Done

- [ ] All five implementation slices are complete; none may be skipped.
- [ ] Existing UI screens and BLoCs are reused, not duplicated.
- [ ] `ApiService` and `SseService` implement explicit ports.
- [ ] Twin overview and verification BLoCs construct no concrete SSE client.
- [ ] All three fixture scenarios pass schema/reference validation.
- [ ] Demo API implements and tests the complete Management API contract.
- [ ] Demo mutations and streams are deterministic and stateful.
- [ ] Demo mode performs zero HTTP/SSE network calls.
- [ ] `./thesis.sh demo` starts without Docker, credentials, or generated files.
- [ ] Demo runtime is visibly and accessibly marked on every screen.
- [ ] Every route is reachable with representative fixture data.
- [ ] Loading, data, empty, degraded, and terminal states are covered.
- [ ] `flutter analyze` reports zero issues.
- [ ] Full `flutter test` suite passes.
- [ ] Web and macOS demo builds pass.
- [ ] `bash -n thesis.sh` passes and help text is accurate.
- [ ] README documents demo start, scenarios, reset semantics, and safety.
- [ ] Worktree contains no generated or unrelated changes.
- [ ] Implementation is ready for independent audit.
