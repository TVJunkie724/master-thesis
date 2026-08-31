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

## Canonical architecture UI

The client loads `GET /architecture-contract` and the current Twin's immutable
pin. It checks ID, version and digest before calculation/review. There is no
catalog, selector, change preview, inheritance, registration, or arbitrary
topology editor.

Logical and resolved graphs are read-only server-owned evidence. Responsive
layouts may render them as a graph or list but cannot invent edges.

## Credential and readiness UI

Users may create/import several named deployment connections per provider and
bind the required ones to a Twin. Submitted secret values never enter BLoC
state, Equatable props, diagnostics, archives, or logs.

The `/settings` route is the focused **Cloud access** surface. Provider file
import is the primary action; typed entry remains a fallback. For Azure, the
client accepts either a standard deployment service-principal JSON or the
allowlisted Azure part of the repository compatibility bundle. It extracts
known metadata locally, keeps preparation fields transient and sends only a
rebuilt deployment-principal JSON to the existing Management import endpoint.
Other-provider members and presentation metadata are never uploaded. The
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

## Access handoff

L4/L5 cards consume typed Management read models containing provider URL,
authentication kind, assigned identity, readiness, limitation, and optional
service-local one-time Viewer credential. Flutter opens provider-owned
surfaces; it does not embed or administer them. One-time values are transient
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
python3 scripts/check_flutter_architecture.py
flutter build web --release
```

Run the native desktop release build on its matching host. Live provider
browser access and deployment remain separately supervised evidence.
