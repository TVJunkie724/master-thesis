# Phase 7d: Non-HTTP Azure Runtime Observability

**Issue:** [#137](https://github.com/TVJunkie724/master-thesis/issues/137)
**Status:** Implemented and verified
**Blocked by:** #136

## Target

Every non-HTTP Azure Function in the executable five-layer baseline must
produce bounded, redacted, correlatable failure logs without changing Azure
trigger retry behavior. Runtime logs must not contain telemetry, object
contents, provider response bodies, signed URLs, secret values, runtime paths,
or raw tracebacks.

This phase extends the shared runtime failure boundary from #136 to triggers
that cannot return an HTTP error body. It does not invent an HTTP contract for
Event Grid or timer triggers.

## Closed-World Inventory

The source decorator inventory and package registry identify exactly three
non-HTTP Azure baseline functions:

| Component | Trigger | Package | Current exposure |
| --- | --- | --- | --- |
| `dispatcher` | Event Grid | L1 Function App | normalized telemetry, downstream body/reason, raw traceback |
| `hot-to-cold-mover` | timer | L3 Function App | remote URL, device/object identifiers, raw config/provider traceback |
| `cold-to-archive-mover` | timer | L3 Function App | remote URL, blob identifiers, raw config/provider traceback |

HTTP-triggered system adapters remain owned by phase 7c. User-authored
processors and actions are outside this provider-runtime slice.

## Runtime Contract

### Successful and routine progress logs

Allowed fields are static component/phase names, bounded counts, safe status
codes, chunk indices, and timer lateness. Dynamic telemetry values, device IDs,
blob/object names, request/response bodies, endpoints, signed URLs, and
connection diagnostics are not logged.

### Propagated failures

Each top-level trigger boundary must:

1. catch the failure once;
2. call `_shared.http_errors.log_runtime_failure` with a stable component/phase
   name and `include_diagnostic=False`;
3. emit exactly one log record containing generated `correlation_id`,
   exception type, and a static `diagnostic=<suppressed>` marker;
4. re-raise with bare `raise` so the original exception identity, traceback for
   the Azure host, and provider retry/dead-letter semantics remain unchanged.

The diagnostic is deliberately suppressed at these boundaries because Event
Grid payloads and provider SDK exceptions can contain arbitrary telemetry or
resource identifiers that cannot be proven safe by pattern redaction. The
existing HTTP boundary keeps bounded redacted diagnostics because callers
receive a correlation reference and its tests inject known secret forms.

The application log must not emit the traceback itself. The Azure host may
record platform-level invocation failure metadata after the exception is
re-raised; application code must not duplicate raw diagnostics.

Permanent no-op conditions such as an Event Grid payload without a usable
device identifier remain non-retried to preserve current behavior, but receive
a safe warning without payload content. This phase does not claim a durable
dead-letter path; that topology belongs to the later eventing work.

## Component Changes

### Dispatcher

- Import `MissingEnvironmentVariableError` and `log_runtime_failure`; remove
  `read_http_error_body`.
- Remove inner downstream HTTP/network failure logs. The top-level correlated
  failure record owns the application diagnostic.
- Remove normalized telemetry logging.
- Configuration loading failures use component
  `azure.dispatcher.configuration`; other failures use
  `azure.dispatcher.execution`. Both suppress diagnostics and use bare
  `raise`.
- Preserve Event Grid parsing, device resolution, normalization, target
  selection, invocation, and no-device no-op behavior.

### Hot-to-Cold Mover

- Import `MissingEnvironmentVariableError` and `log_runtime_failure`.
- Replace remote URL, device ID, blob path, and cutoff-value logs with static
  phases and aggregate counts.
- `ConfigurationError`, `MissingEnvironmentVariableError`, and invalid
  `DIGITAL_TWIN_INFO` JSON use
  `azure.hot-to-cold-mover.configuration`; other failures use
  `azure.hot-to-cold-mover.execution`. Both suppress diagnostics and use bare
  `raise`.
- Preserve query, chunking, local/remote writes, configured blob tier, and
  delete-after-success ordering.

### Cold-to-Archive Mover

- Import `MissingEnvironmentVariableError` and `log_runtime_failure`.
- Replace remote URL, blob/object name, and cutoff-value logs with static
  phases and aggregate counts.
- `ConfigurationError`, `MissingEnvironmentVariableError`, and invalid
  `DIGITAL_TWIN_INFO` JSON use
  `azure.cold-to-archive-mover.configuration`; other failures use
  `azure.cold-to-archive-mover.execution`. Both suppress diagnostics and use
  bare `raise`.
- Preserve age filtering, memory guard, local copy/remote transfer, configured
  archive tier, and delete-after-success ordering.

## Packaging Contract

All three packages already include the complete canonical `_shared/` directory.
The implementation must retain one-line `_shared` imports because the current
Azure bundler extracts those imports through a line-oriented merge step.

Bundle tests must prove:

- L1 and L3 generated Python remains syntactically valid;
- `_shared/http_errors.py` is present in both packages;
- generated function code imports `log_runtime_failure`;
- Dispatcher and both mover functions remain registered exactly once.

## Tests And Gates

### Behavioral tests

- Inject an exception containing an exact environment secret, signed query
  value, Unix/Windows runtime path, and payload marker into each top-level
  trigger.
- Assert the original exception instance propagates.
- Assert one UUID correlation identifier appears in the matching log.
- Assert secret, signature, path, payload marker, and traceback text do not.
- Assert Dispatcher downstream HTTP/network logs omit response body and reason.
- Assert normal Dispatcher invocation passes the unchanged normalized payload
  while the payload is absent from logs.
- Assert `log_runtime_failure(include_diagnostic=False)` never evaluates or
  serializes the exception message and emits `diagnostic=<suppressed>`.
- Retain mover local/remote, tier, schedule, chunk, memory-guard, and
  delete-after-success tests.

### Source drift gates

- Discover non-HTTP decorators from the source tree and assert the discovered
  set equals the closed-world inventory.
- Reject `logging.exception`, `logger.exception`, `raise e`, and
  `read_http_error_body` in those functions.
- Reject known dynamic payload/URL/body log patterns.

### Repository gates

- focused non-HTTP runtime and Azure package tests;
- full Deployer suite excluding live E2E;
- Ruff, Bandit, compileall, source drift, and `git diff --check`;
- strict MkDocs build;
- no provider credentials and no live cloud operation.

## Compatibility And Failure Semantics

- Function decorators, names, schedules, and package membership do not change.
- Successful provider calls and returned values do not change.
- Exceptions are not swallowed or wrapped; Azure observes the original
  exception and therefore retains current retry behavior.
- No public API, manifest, resolved specification, tfvar, or Terraform schema
  changes.
- No new observability backend or durable dead-letter capability is claimed.

## Required Files

Implementation must be limited to:

- `3-cloud-deployer/src/providers/azure/azure_functions/_shared/http_errors.py`;
- the three inventoried `function_app.py` files;
- focused Azure runtime and package tests under
  `3-cloud-deployer/tests/unit/azure_functions/` and
  `3-cloud-deployer/tests/unit/terraform/test_function_bundler.py`;
- Deployer/runtime documentation and this phase/roadmap.

Changes to provider resources, Terraform, schedules, API schemas, optimizer
contracts, Management persistence, or Flutter are forbidden in this phase.

## Definition Of Done

- [x] Closed-world trigger inventory is executable and drift-tested.
- [x] All three trigger boundaries use correlated redacted failure logging.
- [x] No in-scope application log contains payloads, bodies, URLs, secrets,
  runtime paths, or raw tracebacks.
- [x] Original failure identity and trigger retry semantics remain intact.
- [x] L1/L3 package registration and shared-helper inclusion are verified.
- [x] Focused and full safe tests pass.
- [x] Static, security, compile, source, diff, and docs gates pass.
- [x] Runtime and developer documentation describe the implemented boundary.
- [x] #137 is closed with commit and verification evidence.

## Verification Evidence

- Focused non-HTTP runtime and package suite: 90 passed.
- Full safe Deployer suite: 1,631 passed and 63 skipped.
- Ruff, Bandit, `compileall`, AST/source drift, real-package import and
  registration, and `git diff --check` gates passed.
- Strict MkDocs build passed.
- No provider credentials or live cloud operation were used.
