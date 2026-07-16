# Flutter UI

`twin2multicloud_flutter` is the user-facing application for Web, macOS, Windows,
and Linux. It owns
presentation, local interaction state, navigation, and runtime adapter composition.
It does not own business persistence, cloud credentials, pricing semantics, or
deployment execution.

## Boundary

```text
widgets/screens -> feature state -> ManagementApi interface -> Management API
                                      |
                                      +-> DemoManagementApi (demo only)
```

Direct Flutter calls to Optimizer or Deployer are architecture defects. Network code
is contained behind `ManagementApi`; SSE uses a separately injected `LogStreamClient`.

## Entrypoints And Structure

| Path | Responsibility |
|---|---|
| `lib/main.dart` | load runtime composition and start `ProviderScope` |
| `lib/app.dart` | Material app, GoRouter, route guards |
| `lib/config/` | fail-closed runtime profile and composition |
| `lib/providers/` | Riverpod application composition and simple global queries/commands |
| `lib/bloc/` | multi-step feature workflows with explicit events and states |
| `lib/features/configuration_workspace/` | task model, sidebar, workspace shell, review/deployment presentation |
| `lib/screens/` | route-level UI entrypoints |
| `lib/widgets/` | reusable presentation and form components |
| `lib/models/` | typed Management API contracts |
| `lib/services/` | network adapter, API interface, SSE/log adapter |
| `lib/demo/` | deterministic in-memory repository adapters and fixtures |

## State Management Decision

The application deliberately uses both Riverpod and BLoC, with separate ownership:

| Tool | Owns | Examples |
|---|---|---|
| Riverpod | app composition, runtime dependencies, theme/auth, simple global async resources | `appRuntimeProvider`, `apiServiceProvider`, `authProvider`, twins/dashboard/pricing health |
| BLoC | feature workflows with multiple commands, transitions, retries, and partial results | configuration wizard, pricing review, twin overview, cloud access, deployment verification |

This is not interchangeable duplication. A feature should not expose the same mutable
state through both systems. Riverpod injects dependencies; a route-level `BlocProvider`
owns the workflow lifecycle.

## Navigation And Screens

GoRouter defines login, dashboard, settings/profile, pricing review, twin overview,
and create/edit configuration routes. Auth state drives redirects. The primary flow is:

```text
login -> dashboard -> create/edit twin -> configuration workspace
                       |                   |
                       |                   +-> intent / optimizer / deployment tasks
                       +-> pricing review
                       +-> twin overview -> deploy/destroy/status/logs/verification
```

The configuration experience is task-oriented. Global stages provide orientation;
the sidebar exposes smaller tasks so large forms are not presented as one uninterrupted
page. Provider pricing moved out of the optimizer step and into a dashboard-level
review workspace because pricing readiness is account-level, not twin configuration.

## Runtime Adapters

`AppRuntimeConfig` accepts only `development`, `production`, or `demo`.
`runtime_composition.dart` chooses adapters before UI construction:

- development/production: network `ApiService` and SSE/log client;
- demo: `DemoManagementApi`, fixture identity, and `DemoLogStreamClient`.

Demo mode uses the same `ManagementApi` interface and screens. Its fixture store
supports `showcase`, `empty`, and `degraded`; requesting network dependencies fails.

Production sign-in is capability-driven. `AuthNotifier` creates a login transaction,
opens a system browser, polls the one-time Management API exchange, retains the access
token in memory, and clears identity/token state after logout or any authenticated
`401`. Web reserves its popup synchronously before the API call to satisfy browser
popup-blocking rules; desktop opens the external system browser. Provider callbacks
and secrets never enter Flutter routes or URL parameters.

## Error And Logging Behavior

- `Result` and typed models keep expected API failures out of widget parsing;
- `ApiErrorHandler` converts transport/API errors into user-facing messages;
- feature BLoCs preserve retryable workflow state rather than dropping the screen;
- `AppLogger` is the application logging boundary;
- deployment and pricing streams are rendered as operation output, not application logs;
- secret material must never enter snackbars, debug logs, or raw JSON viewers.

The centralized notification experience is still evolving; pages must therefore keep
errors close to the affected task and preserve actionable recovery controls.

## Tests And Quality Gates

```bash
./thesis.sh test frontend
./thesis.sh test frontend-integration
```

The frontend gate checks architecture constraints, formatting, analysis, unit/widget
tests, demo behavior, and local Web/current-host builds. Native CI builds Web,
macOS, Windows, and Linux. The integration gate is read-only against the
credential-free stack. It must not refresh provider pricing, validate real cloud
access, deploy, destroy, or run cloud simulator operations.

The central runtime platform classifier rejects Android, iOS, and Fuchsia
before repositories or authentication state are composed. Platform
prerequisites and distribution boundaries are defined under
[Supported Platforms](../getting-started/supported-platforms.md).

## Extension Points

- add a route in `app.dart`, then a route-level screen with injected dependencies;
- extend `ManagementApi` first, then implement both network and demo adapters;
- use Riverpod for composition/simple global resources and BLoC for stateful workflows;
- add typed request/response models rather than parsing raw maps in widgets;
- extend `ConfigurationJourney` for a new task while preserving navigation invariants;
- add deterministic fixture coverage for every new user-visible screen or state.

`scripts/check_flutter_architecture.py` enforces important boundaries. Extension TODOs
in state/composition entrypoints identify where future developers must register new
strategy-backed functionality.

## Evolution And Gaps

The original integrated UI grew as three large wizard pages with direct service calls,
long forms, raw JSON, and mixed state concerns. It was decomposed into typed adapters,
Riverpod composition, workflow BLoCs, reusable controls, and the task-oriented
configuration workspace. Pricing review became a first-class account workflow.

Remaining gaps include live institutional UIBK activation, selected simulator defects, and
continued consolidation of cross-screen notifications. These are not reasons to bypass
the Management API or introduce mock-only production paths.
