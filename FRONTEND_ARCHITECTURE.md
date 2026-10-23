# Twin2MultiCloud Flutter Architecture

Status: current architecture source

The Flutter client presents one fixed research workflow and communicates only
with the Management API. It never contacts Optimizer, Deployer, Terraform, or
cloud-provider APIs directly.

## Supported targets

Web, macOS, Windows, and Linux are maintained application targets. Mobile and
Fuchsia are outside scope. Build support does not imply installer, signing,
store, or production-distribution readiness.

## Runtime boundary

```text
Screens / widgets
       |
       v
feature BLoCs and simple providers
       |
       v
ManagementApi interface
       |----------------------|
       v                      v
real ApiService          DemoManagementApi
       |                      |
       v                      v
Management HTTP/SSE      deterministic fixtures
```

Direct downstream service calls are architecture defects. Demo branches are
implemented through adapters, not scattered UI conditionals.

## State ownership

- Riverpod composes runtime configuration, the local PoC profile, theme, API/log
  adapters, and simple global async resources.
- BLoC owns feature workflows with commands, concurrent responses, retries,
  partial results, replay cursors, and destructive confirmations.
- Widgets render immutable state and dispatch typed events.
- Repositories/adapters perform transport and file selection; they do not own
  presentation state.

One mutable concern must have one owner. A widget must not locally duplicate a
BLoC field or derive provider topology/cost from display data.

## Information responsibilities

The supported user journey is organized around four responsibilities rather
than a product dashboard hierarchy:

1. Twin scenario and bounded configuration;
2. cost result, assumptions, exclusions and immutable graph review;
3. deployment CloudConnection selection, readiness, preparation and repair;
4. deployment operation, access handoff, verification and cleanup.

These responsibilities may use several routes and task panels. Route count is
not itself the scope metric.

## Shared PoC shell

The four supported surfaces—Cloud access, Twin experiments, Configuration
Workspace and Twin lifecycle—reuse the branded app bar, theme control,
top-aligned content, bounded content width and the established spacing tokens.
Navigation utilities stay in the app bar; research tasks stay in the body.

Each surface has one dominant next outcome. Secondary, reproducibility and
safe-management actions use outlined controls or overflow menus. Destructive
and persistent provider actions retain explicit dialogs. Loading, empty and
error states stay local to the owning surface and always preserve a retry or
safe exit. Desktop and Web support includes the 640-pixel compact boundary and
high text scaling; mobile remains outside scope.

## Twin experiment inventory

The `/dashboard` route is a start-or-resume surface, not a product dashboard.
It sorts a defensive copy of the returned Twins by latest update, shows only
the name, lifecycle state and update date, and exposes exactly one visible
continuation per Twin. Drafts continue in Configuration Workspace; every other
state opens the lifecycle overview.

Portable import is secondary to `New Twin`. Duplicate, Export and safe Delete
remain in a row overflow menu because they support reproducibility or lifecycle
hygiene without competing with the next research task. Filtering, analytics,
provider columns, last-deployment columns and bulk operations are outside the
PoC inventory.

## Configuration Workspace

The `/wizard` and `/wizard/:twinId` routes present one dependency-aware
experiment configuration through four stable thesis phases: **Scenario**,
**Optimize**, **Prepare**, and **Review**. These phases are the only persistent
top-level navigation. The task selector exposes only the tasks in the current
phase; Back and Continue preserve the complete 15-task order.

Task status and UI selection are separate. Selecting a task must not turn an
available, complete, or attention status into a presentation-only state.
Blocked phases remain disabled with their dependency reason. Existing save,
invalidation, cost calculation, immutable-result selection, CloudConnection,
artifact validation and finish contracts remain owned by `WizardBloc` and the
Management API. The bottom navigation shows at most one filled primary action.

## Canonical architecture UI

The calculation form renders only the frozen Six-layer scenarios and their
existing read-only sections. Missing or unsupported profile pins block input
emission rather than exposing an old five-layer form. Historical DTO decoding
remains for non-destructive reads; it does not enable a legacy calculation UI.

The client loads `GET /architecture-contract` and the current Twin's immutable
pin. It checks ID, version and digest before calculation/review. There is no
catalog, selector, change preview, inheritance, registration, or arbitrary
topology editor.

Logical and resolved graphs are read-only server-owned evidence. Responsive
layouts may render them as a graph or list but cannot invent edges.
Native optimizer results and lifecycle configuration evidence reuse the resolved
graph, including independent Eventing, and immutable cost currency. They do not
render the compatibility L1–L5 path or pretend that uncalculated alternatives
are provider comparisons. Model contract completeness is not live proof.
Small live observations and Medium/Large offline model comparisons remain
distinct; GCP L4/L5 exclusions are explicit. Modeled L5 reads do not imply polling.

## Credential and readiness UI

Users may create/import several named deployment connections per provider and
bind the required ones to a Twin. Submitted secret values never enter BLoC
state, Equatable props, diagnostics, archives, or logs.

The `/settings` route is the focused **Cloud access** surface. Provider file
import is the primary action; typed entry remains a fallback. For Azure, the
client accepts either a standard administrator service-principal JSON or the
allowlisted Azure part of the repository compatibility bundle. It extracts
known metadata locally and sends only a rebuilt single-administrator JSON to
the existing Management import endpoint. Retired preparation fields,
other-provider members, and presentation metadata are never uploaded. The
fixed local runtime profile remains a bootstrap boundary and is not rendered
as an account-management card.

Identity validation, graph readiness and provider preparation are distinct UI
states. Persistent provider changes have a separate review/confirmation.
Failures show one of:

- supported automatic preparation;
- insufficient credential authority;
- external billing/quota/policy/consent/capacity action;
- transient retry; or
- unsupported canonical capability.

## Operation reliability

Deploy and Destroy can incur cost. The Twin overview therefore:

- catches up persisted operation events before opening SSE;
- resumes after the last cursor;
- ignores duplicate events and recovers bounded gaps;
- never converts a transport reconnect into a new mutation command;
- preserves terminal verification and cleanup evidence;
- requires explicit destructive confirmation.

## Twin lifecycle overview

The `/twins/:id/overview` route is the execution and evidence surface for one
bounded experiment. One summary owns the Twin identity, lifecycle state and
next safe step. Edit and Delete remain in a secondary overflow, while the app
bar owns return navigation, theme and direct Cloud access.

The visible section order follows lifecycle state rather than a product
dashboard grid:

1. configured or deploying: **Prepare and deploy**;
2. deployed: **Verify and access**, then **Destroy and cleanup**;
3. error: **Destroy and cleanup**; a previously deployed Twin stays immutable;
4. destroyed: recorded cleanup evidence and Duplicate guidance for a new Twin;
5. **Configuration evidence** remains last in every state.

Exactly one lifecycle mutation command is shown at a time. A ready preflight
re-check is secondary so Deploy is the only filled action; a blocking
preflight remains the primary remediation. All commands retain the existing
BLoC, confirmation, Management API, durable operation and SSE boundaries.
Eligibility uses both lifecycle state and deployment history. Only configured
or failed first-attempt Twins may Deploy; a populated `deployedAt` locks Edit
and Deploy permanently. Delete follows Management's separate state/history
rule. Direct Wizard entry also respects this lock. Deploy confirmation shows
available named connection bindings and the native monthly model estimate,
not an account-scope attestation, actual bill or spending cap.
Infrastructure checks, telemetry samples, simulator/command use and exact
L4/L5 data assertions have separate proof boundaries. Cleanup v1 reports its
recorded checks, not global account inventory or private research observations.
Error wording follows the persisted operation type: failed Destroy is **Cleanup
incomplete**, failed Deploy is **Deployment failed**, and unknown operation types
remain generic. The ERROR state and mutation guards are unchanged. During/after
cleanup, the existing telemetry evidence panel remains available read-only;
historical PASS does not establish current resource health or successful cleanup.
Live verification, simulator and access actions remain limited to deployed Twins.

## Access handoff

L4/L5 cards consume typed Management read models containing provider URL,
authentication kind, assigned identity, readiness, limitation, and optional
service-local one-time Viewer credential. Flutter opens provider-owned
L4 surfaces. AWS/Azure L5 instead uses the existing Open action to request one
bounded HTML/SVG snapshot through the owner-scoped Management API. Deployer
authenticates against the fixed deployed endpoint; cloud keys never enter
Flutter. Each click fetches fresh data; there is no polling, chart editor or
additional provider sign-in. Web uses a reserved isolated tab and a temporary
Blob URL; Desktop opens a temporary HTML file with best-effort delayed cleanup.
The one-shot L5 read has nested receive allowances: Azure cloud read 180 s,
Management-to-Deployer 240 s and Flutter-to-Management 300 s, leaving room for
key lookup and operation-package staging. AWS retains its 30 s cloud read.
These transport limits are not a latency guarantee or a cold-start claim;
authentication, payload-size, graphical-data and stale-response checks remain.
Neither implementation keeps HTML in BLoC state. Duplicate and stale requests
(Twin change or Destroy) cannot open a new snapshot. Flutter does not administer
these surfaces. One-time values are transient
and cleared after use, cancel, failure, Destroy, or Twin change.

## Portability

Twin Duplicate and typed Export/Import support reproducible secret-free sharing.
Individual allowlisted configuration files may be imported and validated.
Arbitrary deployment ZIP layouts, Terraform state, provider packages, and
credential files inside Twin archives are rejected.

## Verification gate

```bash
cd twin2multicloud_flutter
dart format --output=none --set-exit-if-changed lib test integration_test
flutter analyze
flutter test
python3 ../scripts/check_flutter_architecture.py
flutter build web --release
```

Run the native desktop release build on its matching host. Live provider
browser access and deployment remain separately supervised evidence.
