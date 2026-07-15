# Implementation Plan: Frontend Delta Phase 9 Quality Gate

## 0. Git Branch

- **Branch name:** `codex/frontend-phase-9-quality-gate`
- **Base branch:** `master` at `af26768`
- **Merge strategy:** merge commit; no rebase
- **Primary issue:** [#108](https://github.com/TVJunkie724/master-thesis/issues/108)
- **Safety boundary:** the existing local modification at
  `2-twin2clouds/json/fetched_data/pricing_dynamic_azure.json` is user-owned and
  must never be staged, rewritten, or used as test input.

## 1. Summary

This phase turns the accumulated frontend work into one reproducible,
thesis-ready quality gate. It does not add another product screen. It proves
that the Flutter application:

- composes production and offline-demo adapters correctly;
- calls only the Management API;
- renders all supported routes and representative loading, empty, degraded,
  blocked, success, compact, and wide states;
- can decode the current read-only Management API contracts against the local
  Docker stack without cloud credentials or cloud resource creation;
- does not expose secret values through presentation or diagnostics;
- builds for Web and macOS from tracked, secret-free runtime templates; and
- has an auditable evidence matrix that separates verified behavior from open
  future work.

The implementation must reuse the current BLoC/Riverpod split: Riverpod owns
runtime composition, auth/theme, app-level queries, and feature adapters;
feature BLoCs own multi-step workflows. Phase 9 must not migrate state
management or introduce a second application architecture.

## 2. Visual Layout And Audit Topology

No screen layout changes are planned. The existing product surfaces are the
audit subjects on both desktop and Web:

```text
+--------------------------------------------------------------------------+
| Twin2MultiCloud app shell                                                |
|                                                                          |
| Dashboard                                                                |
| + stats + pricing health + twin inventory                                |
|                                                                          |
| Cloud Accounts         Pricing Review         Configuration Workspace    |
| + purpose metadata     + provider refresh     + task sidebar             |
| + safe account labels  + candidate evidence  + typed workload/config    |
|                                                                          |
| Twin Overview                                                           |
| + readiness + operations + structured logs/outputs + test utilities      |
+--------------------------------------------------------------------------+

Wide desktop / Web >= 1024 px       Compact supported Web/Desktop >= 640 px
+-----------------------------+     +--------------------------------------+
| Existing multi-column views |     | Existing stacked/task-focused views |
| and persistent task sidebar |     | with no horizontal page overflow    |
+-----------------------------+     +--------------------------------------+
```

The quality pipeline is:

```text
./thesis.sh test frontend
  |
  +-- source-boundary/security audit
  +-- Dart format verification
  +-- flutter analyze
  +-- 547+ unit/widget/demo tests
  +-- Web release build from dev.example.json
  `-- macOS debug build from dev.example.json

./thesis.sh test frontend-integration
  |
  +-- start/reuse credential-free Docker services
  +-- existing HTTP health smoke
  +-- generate ignored config/dev.json
  `-- read-only Flutter integration tests -> Management API :5005
       +-- dashboard stats
       +-- cloud access inventory
       +-- cloud connections
       `-- pricing health
```

## 3. Component And File Tree

```text
thesis.sh                                                   [MODIFY]
|-- test backend                                            [REUSE]
|-- test frontend                                           [NEW COMMAND]
`-- test frontend-integration                               [NEW COMMAND]

scripts/
|-- check_flutter_architecture.py                           [NEW]
`-- tests/test_check_flutter_architecture.py                [NEW]

twin2multicloud_flutter/
|-- integration_test/
|   `-- management_api_readiness_test.dart                  [NEW]
|       `-- replaces credential_ssot_flow_test.dart         [REMOVE]
|-- test/
|   |-- demo/*                                              [REUSE]
|   |-- screens/*                                           [REUSE]
|   `-- widgets/*                                           [REUSE]
|-- docs/frontend_delta/
|   |-- ROADMAP_FRONTEND_DELTA.md                           [MODIFY]
|   `-- phases/PHASE_09_CROSS_CUTTING_QUALITY_GATE.md       [MODIFY]
`-- implementation_plans/
    `-- 2026-07-15_frontend_delta_phase_09_quality_gate.md   [NEW]

docs-site/docs/architecture/refactoring-roadmap.md          [MODIFY]
HANDBOOK.md                                                 [MODIFY]
```

No production widget, route, model, repository, provider, or BLoC is added by
default. A product-code edit is allowed only when the gate exposes a concrete
finding; every such remediation must receive a focused regression test and be
recorded in the evidence section before commit.

## 4. Component Specifications

### 4.1 `scripts/check_flutter_architecture.py`

The checker must be deterministic, read-only, dependency-free Python, and
return exit code `0` only when all rules pass. Findings must contain rule id,
repository-relative path, line, and a sanitized explanation. It must never
print matched source text for secret-related rules.

Required rules:

| Rule | Scope | Failure |
|---|---|---|
| `FLUTTER-DIRECT-SERVICE` | production Dart | direct Optimizer/Deployer host, port 5003/5004, or URL |
| `FLUTTER-PRESENTATION-HTTP` | `lib/screens`, `lib/widgets`, feature presentation | import/use of Dio, `ApiService`, or `ManagementApi` |
| `FLUTTER-DIAGNOSTIC` | production Dart | `print`, `debugPrint`, TODO, FIXME, or HACK |
| `FLUTTER-SECRET-LITERAL` | presentation and demo fixtures | PEM/private-key payload, concrete access token, client secret, OpenAI key, or credential file path value |
| `FLUTTER-RUNTIME-CONFIG` | tracked config | Management API/docs base URL or dev-auth token literal outside `lib/config/api_config.dart`, `lib/config/docs_config.dart`, and `config/dev.example.json`, or any such key in `config/demo.json` |
| `FLUTTER-SOURCE-READ` | scanned source | unreadable or non-UTF-8 source; diagnostic contains path only |

Identifiers and user-facing labels such as `serviceAccountJson`, `Client
secret`, or `private_key_id` are not secret values and must not fail merely by
name. Explicit credential-entry forms are valid, but tests must prove their
controllers are disposed and values are not echoed after submission.

The checker accepts one optional `--root PATH` argument solely for isolated
unit tests. It must not maintain a broad path allowlist; exceptions require a
rule-specific reason in code and a unit test.

### 4.2 `scripts/tests/test_check_flutter_architecture.py`

Use standard-library `unittest` and temporary repositories. Tests must assert
exact rule ids and sanitized paths while proving that secret source text is not
included in output.

### 4.3 `thesis.sh`

Extend the existing `test` command without changing startup, demo, docs, LaTeX,
or backend behavior.

| Command | Required behavior |
|---|---|
| `./thesis.sh test frontend` | checker, Python checker tests, format, analyze, full Flutter tests, Web release build, macOS debug build |
| `./thesis.sh test frontend-integration` | start/reuse credential-free app services, smoke them, generate `dev.json`, run the one read-only integration target on macOS |
| `./thesis.sh test backend` | unchanged |

`frontend-integration` must reject `--with-credentials`, must not enable test
endpoints, must not call mutation/deploy/destroy/refresh routes, and must not
stop pre-existing containers. It may start missing default-project services and
leave them running, matching `./thesis.sh up --no-flutter` behavior. The help
text must state these semantics and the macOS toolchain requirement.

The frontend gate uses `config/dev.example.json`; it must not require ignored
`config/dev.json`. Commands fail immediately and propagate their original exit
status. No command may suppress analyzer, test, checker, or build failures.

### 4.4 `management_api_readiness_test.dart`

Replace the single-purpose integration file with one read-only suite using the
real `ApiService` and runtime config. No mocked HTTP client is allowed.

Hard assertions:

| Endpoint through `ApiService` | Assertions |
|---|---|
| `GET /dashboard/stats` | typed non-negative counts/cost; `totalTwins >= deployedCount + draftCount` because other lifecycle states may exist |
| `GET /cloud-access` | exact `cloud-access-inventory.v1`; provider keys are exactly lowercase `aws`, `azure`, `gcp`; purpose/scope/status metadata is non-secret |
| `GET /cloud-connections/` | typed list; each item has provider, purpose, and display metadata; response model exposes no credential payload |
| `GET /optimizer/pricing-health` | exact `pricing-health.v1`; exact lowercase provider set `aws`, `azure`, `gcp`; each provider has state, severity, source, credential summary, and action list |

The suite must derive the host and port from `ApiConfig.baseUrl`; it must not
assert literal port 5005. A shared failure formatter may report URI, endpoint,
HTTP status, and Dio error type, but not response bodies or authorization
headers. Add unauthenticated and unknown-route assertions proving that
protected inventory rejects missing credentials with 401/403 and that an
authenticated unknown route returns 404. Both diagnostics must remain
body/header-free.

### 4.5 Documentation And Evidence

`PHASE_09_CROSS_CUTTING_QUALITY_GATE.md` becomes the final evidence record. It
must include exact commands, dates, test count, build targets, integration
endpoint matrix, checker rules, findings/remediations, residual warnings, and
explicitly deferred issues. It must not claim live-cloud validation.

Update the Frontend Delta and refactoring roadmaps to current GitHub state,
including #38 as done. The Handbook gains the two frontend test commands and
their no-cloud guarantees. Historical plans remain historical and are not
rewritten merely to tick stale checkboxes.

## 5. Responsive Behavior

No responsive production code changes are planned. Verification is binding:

| Width | Gate |
|---|---|
| `>= 1440 px` | Dashboard, Pricing Review, Configuration Workspace, and Twin Overview retain intended multi-column layouts. |
| `1024-1439 px` | no clipped controls or page-level horizontal overflow; task navigation remains usable. |
| `640-1023 px` | supported compact layouts expose all commands, dialogs, evidence expanders, and disabled reasons. |
| `< 640 px` | mobile remains out of scope; tests must not silently redefine this as supported. |

Existing widget/demo tests are the automated source. If a missing state is
found, add the narrowest focused widget test and only then remediate the widget.

## 6. State And Data Flow

No state ownership changes are allowed in this phase:

```text
Production runtime
Widget -> Riverpod query/command or feature BLoC -> ManagementApi adapter
       -> ApiService -> Management API -> typed response/failure -> UI state

Offline demo runtime
Widget -> same Riverpod/BLoC boundary -> DemoManagementApi
       -> DemoFixtureStore -> same typed response/state -> UI

Integration gate
Flutter integration test -> real ApiService -> local Management API
       -> local Optimizer/Deployer read path where required
       -> typed assertion; no cloud API and no mutation
```

Riverpod and BLoC are complementary in the current architecture. Phase 9 must
flag direct widget HTTP and duplicate feature state, but must not impose a
BLoC-only or Riverpod-only rewrite.

## 7. Design Tokens

No new tokens are planned. Any product remediation must use `AppSpacing`,
`AppColors`, and `ThemeData`; inline color literals, spacing literals, or new
typography systems are findings.

## 8. Interaction And State Verification

The audit must verify existing behavior rather than redesign it:

- loading, empty, degraded, blocked, error, success, and read-only states;
- disabled-action reasons and duplicate-command prevention;
- collapsed pricing trace/evidence by default with opt-in expansion;
- Save/Discard/Cancel handling for every Configuration Workspace exit;
- deploy/destroy acknowledgement and sensitive simulator-download consent;
- pricing refresh provider/account confirmation;
- SSE/log disconnect and terminal-state handling using deterministic tests; and
- all `showcase`, `empty`, and `degraded` demo scenarios across every route.

Animations are unchanged. Tests must use `pumpAndSettle` only for bounded
transitions and explicit pumping for streams/timers so hangs fail visibly.

## 9. Accessibility

The gate must assert:

- keyboard reachability and logical focus order for primary commands;
- Escape cancellation for dialogs;
- semantic labels for icon-only, destructive, sensitive, and trace actions;
- live-region semantics for operation/error feedback;
- no overflow at 640 px; and
- dark/light theme smoke coverage without secret text in semantics.

No claim of full WCAG certification is allowed. The evidence must say which
automated semantics/keyboard checks were run and what remains manual.

## 10. Integration Points

Phase 9 adds no API endpoint. Read-only local verification uses:

| Method | Path | Request | Typed response | Cloud effect |
|---|---|---|---|---|
| GET | `/health` | none | health JSON | none |
| GET | `/dashboard/stats` | dev bearer token | `DashboardStats` | none |
| GET | `/cloud-access` | dev bearer token | `CloudAccessInventory` | none |
| GET | `/cloud-connections/` | dev bearer token | `List<CloudConnection>` | none |
| GET | `/optimizer/pricing-health` | dev bearer token | `PricingHealthResponse` | local read/aggregation only |

No refresh, validate, bootstrap, deploy, destroy, simulator, or test endpoint is
called. Flutter must not contact ports 5003 or 5004. No route registration
changes are planned.

## 11. Test Plan

### 11.1 Checker Unit Tests

Happy paths:

1. clean layered fixture passes;
2. approved credential-entry labels without values pass.

Unhappy paths:

1. direct provider-service URL fails with `FLUTTER-DIRECT-SERVICE`;
2. presentation import of Dio/API service fails with
   `FLUTTER-PRESENTATION-HTTP`.

Edge paths:

1. secret literal is reported without printing its value;
2. PEM multiline payload is redacted;
3. TODO/debug output reports exact file and line;
4. similarly named model fields do not false-positive;
5. Windows and POSIX path separators normalize to repository-relative output;
6. absent optional directories do not crash;
7. malformed/non-UTF-8 source fails closed with a sanitized diagnostic.

### 11.2 Flutter Unit/Widget/Demo Tests

Run the complete suite. Existing hard assertions cover route composition,
runtime adapter boundaries, BLoC workflows, typed models, pricing evidence,
configuration tasks, operations, logs, dialogs, accessibility, and all demo
scenarios. Any failure is fixed at source; snapshots or tests must not be
weakened to make the gate pass.

### 11.3 Real Local Integration Tests

Happy paths:

1. all four typed read contracts decode from the real Management API;
2. credential-free local state, including empty connection inventories and
   stale/review-required pricing, remains a valid typed response.

Unhappy paths:

1. missing auth is rejected;
2. an authenticated unknown route returns 404 without leaking a response body,
   authorization header, or internal path.

Edge paths:

1. the suite derives a non-default or trailing-slash Management API URL from
   generated Dart defines when the caller supplies the corresponding
   `THESIS_API_BASE_URL`; it contains no literal host-port assertion;
2. empty database returns valid zero/empty read models;
3. all three provider keys remain present when credentials are absent;
4. stale pricing remains data, not a decoder failure;
5. no typed response contains credential payload fields;
6. trailing slash in `THESIS_API_BASE_URL` does not create malformed paths.

An unreachable stack is a startup-gate failure, not an integration-test case:
the existing bounded `wait_for_url` smoke must stop the command before Flutter
tests run and report only the service label and configured URL.

No HTTP mock is used at integration level. No real cloud E2E is run.

### 11.4 Required Commands

```bash
python3 -m unittest scripts.tests.test_check_flutter_architecture
python3 scripts/check_flutter_architecture.py
bash -n thesis.sh
./thesis.sh test frontend
./thesis.sh test frontend-integration
docker compose -f compose.yaml --profile docs --profile latex config --quiet
git diff --check
```

After implementation, run two review passes: first for functional/security
findings, then for plan fidelity, test completeness, docs accuracy, and
repository cleanliness. Fix every finding before commit.

## 12. Definition Of Done

- [x] Dedicated Phase 9 GitHub issue exists with plan, labels, milestone,
      verification, and explicit no-cloud scope.
- [x] Architecture checker and its exact, redaction-safe unit tests pass.
- [x] `thesis.sh test frontend` is documented and passes end to end.
- [x] `thesis.sh test frontend-integration` starts/reuses the credential-free
      local stack and passes against the real Management API.
- [x] Integration tests cover dashboard, cloud access, CloudConnections,
      pricing health, and missing-auth behavior with hard typed assertions.
- [x] No test enables backend test endpoints or invokes cloud mutations.
- [x] Full Flutter unit/widget/demo suite passes without weakened assertions.
- [x] `flutter analyze` reports zero issues.
- [x] Web release and macOS debug builds pass from tracked runtime config.
- [x] Format and `git diff --check` gates pass.
- [x] Static audit finds no direct provider service calls, presentation HTTP,
      unsafe diagnostics, production TODOs, or concrete secret literals.
- [x] All supported routes are covered in showcase, empty, and degraded demo
      scenarios; compact 640 px and wide desktop states remain overflow-free.
- [x] Accessibility evidence covers keyboard, Escape, semantics, live regions,
      and disabled reasons without claiming full WCAG certification.
- [x] Phase 9 evidence records exact commands, test count, builds, integration
      contracts, findings, fixes, residual warnings, and deferred issues.
- [x] Frontend Delta roadmap, refactoring roadmap, Handbook, and Issue #38 state
      are synchronized with GitHub.
- [x] Two review passes have no unresolved Critical, Major, or Minor findings.
- [ ] Changes are committed structurally and merged with a merge commit; no
      user-owned pricing or credential file is staged.
