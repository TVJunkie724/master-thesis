# Flutter guardrails — current thesis PoC

Read this shared reference completely before Flutter work. It is the single
guardrail source used by the project UI skills.

## Sources and scope

Read `FRONTEND_ARCHITECTURE.md`, `integration_vision.md`, `ONBOARDING.md`,
and `twin2multicloud_flutter/README.md`. The active thesis target and execution
plan define scope. If a required source is missing, report it before changing
the affected behavior. Current code/contracts and these architecture sources
take precedence over superseded examples in older plans.

The app is a fixed `six-layer-eventing@1` research workflow for Web, macOS,
Windows and Linux. Mobile is outside scope. No product dashboard, interactive
application-login provider, architecture selector or pricing-refresh UI.

## Ownership and transport

- Riverpod composes configuration, local PoC profile, theme, adapters and simple
  global resources. Feature BLoCs own commands, retries and multi-step state.
  Do not introduce another state framework or duplicate mutable ownership.
- Widgets render immutable state and dispatch actions. No HTTP or heavy
  business logic in `build()`. Reuse existing widgets before adding new ones.
- Services use `dio` and contact Management API only. Flutter must never call
  Optimizer (5003), Deployer (5004) or cloud-provider APIs directly.
- Operation logs use SSE with persisted Management replay/cursors. A reconnect
  must not issue another Deploy/Destroy command. Dispose subscriptions and
  controllers; preserve loading, error, empty, retry and terminal states.
- Application startup uses a configured static local bearer and `/auth/me`.
  There is no OAuth/JWT issuance or interactive application login. Provider
  Entra/IAP/workload identity remains a separate deployment/access concern.
- Routing uses `go_router`; Web back/forward must keep working.

## Presentation

Keep the four current surfaces and their dominant next action. Preserve their
documented responsive boundaries and high text scaling. Use existing theme
colors, spacing and typography tokens, Material icons and const constructors
where appropriate. Maintain keyboard navigation, semantics and local failure
feedback. Do not add mobile-only packages or redesign unrelated screens.
Use ASCII layouts in plans, not Mermaid.

Feature BLoC state remains immutable (`copyWith`/Equatable). Dumb children
receive data and callbacks instead of owning services or workflow state.
Simple global state keeps its existing Riverpod owner.

## Credentials, data and cloud safety

Never put administrator secrets in BLoC state, logs, diagnostics, archives or
commits. Preserve the transient one-time resource-access credential boundary.
Do not inspect real credential contents. Do not modify runtime uploads, local
evidence, user files, Terraform state or another checkout.

A Flutter-only task does not authorize companion-service changes. For an
explicit cross-project task, handle each service as its own verified slice.
Never run real cloud E2E, Apply, Destroy or provider preparation without the
specific reviewed resources/cost/cleanup plan and user authorization.

## Verification and Git

Use the current task's feature branch; never work on master. New branches use
`codex/<task>` unless the user specifies otherwise. Follow onboarding's
conventional commits; push/merge only when requested. Do not invent session
prefixes, alternate branch hierarchies or issue-tracking obligations.

Establish the pre-change build baseline and fix regressions before moving to
another layer. Run `flutter analyze`, relevant tests and the full widget/unit
suite; verify Web and the current host's desktop build for UI changes. Run
`python3 scripts/check_flutter_architecture.py` from the repository root.
Formatting uses `dart format`. Use existing dependencies without an unrelated
upgrade. Report environmental build blockers separately from code failures.

Local API integration tests require awareness of the services being started;
never start or stop unrelated containers. Do not run cloud E2E implicitly.
Offline demo/widget tests are not live-provider evidence.
