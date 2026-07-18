# Phase 7c: Azure Function Runtime Error Contracts

**Issue:** [#136](https://github.com/TVJunkie724/master-thesis/issues/136)
**Status:** Reviewed and ready for implementation
**Blocked by:** #74

## Target

Every HTTP-triggered Azure runtime adapter must expose one bounded,
machine-readable error contract. Expected request and authentication failures
retain their deliberate HTTP status. Internal, configuration, provider, and
downstream failures return safe codes and messages without exception text,
provider response bodies, signed URLs, secrets, telemetry, or runtime paths.

Unexpected failures receive a correlation identifier that is present in both
the response and one redacted server log entry. The implementation must not
log an unredacted traceback as a secondary side effect.

## Inventory

| Adapter family | Functions | Current risk | Target behavior |
| --- | --- | --- | --- |
| Inbound routing | `ingestion` | raw exception response and traceback log | typed request/auth/internal errors |
| Outbound routing | `connector` | raw exception response and complete downstream body in success response/log | expose downstream status only; typed upstream/internal errors |
| Storage writers | `hot-writer`, `cold-writer`, `archive-writer` | raw SDK/config exception response and traceback log | typed request/auth/internal errors |
| Storage readers | `hot-reader`, `hot-reader-last-entry` | raw exception response; last-entry silently converts failures to empty `200` | typed request/auth/internal errors; no false success |
| Processing | `processor_wrapper` | user/system exception response and function-key URL log | typed upstream/user-logic/internal errors |
| Eventing | `event-checker` | config validation outside boundary; event and exception echoed in partial result | typed config/internal errors and safe indexed partial failures |
| Feedback | `event_feedback_wrapper` | redacted but still diagnostic-rich 500 body and signed function URL log | generic typed upstream/internal error |
| Persistence | `persister` | safe text but bespoke shapes; raw optional event-checker diagnostic log | shared response/logging policy |
| Digital twin update | `adt-pusher` | safe text but bespoke response shape and no correlation reference | shared response/logging policy |

Timer-triggered movers and user-authored business functions are not HTTP
adapters and are outside this slice. Their provider behavior must remain
unchanged.

## Canonical Error Shape

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "The request could not be completed.",
    "correlation_id": "5fb16a61-87bf-4de7-9001-c8c9a71765c2"
  }
}
```

`correlation_id` is required for logged server-side failures and omitted for
ordinary client errors that do not create an internal diagnostic.

Stable codes used by this slice:

| Code | Meaning | Typical status |
| --- | --- | --- |
| `INVALID_REQUEST` | malformed JSON or invalid request shape | 400 |
| `UNAUTHORIZED` | missing or invalid runtime credential | existing 401/403 |
| `CONFIGURATION_ERROR` | required runtime configuration is absent or invalid | 500 |
| `SERVICE_UNAVAILABLE` | an optional/configured provider service is unavailable | 503 |
| `USER_LOGIC_ERROR` | a called user function failed | 502 |
| `UPSTREAM_ERROR` | another required runtime endpoint failed | 502 |
| `ADT_DELIVERY_FAILED` | required Azure Digital Twins update failed | 502 |
| `INTERNAL_ERROR` | unexpected adapter or provider failure | 500 |
| `EVENT_ACTION_FAILED` | one event action failed while the batch continued | embedded result |

The contract deliberately does not expose provider exception categories as
public codes. Provider diagnostics remain implementation details and can
change independently of callers.

## Shared Runtime Boundary

Add `_shared/http_errors.py` with these responsibilities:

1. serialize the canonical JSON error shape;
2. parse request JSON without exposing decoder diagnostics;
3. generate UUID correlation identifiers;
4. redact known secret syntax and values from sensitive environment variables;
5. redact SAS/function-key query values and Azure/runtime filesystem paths;
6. collapse diagnostics to one bounded line;
7. log correlation ID, component, exception type, and redacted diagnostic
   without `exc_info`;
8. create safe partial-failure references for Event Checker.

The helper is provider-runtime code and is bundled through the existing Azure
`_shared/` packaging path. It must not import the Deployer process logger
because deployed Functions run independently of the Deployer container.

## Adapter Changes

1. Replace every bespoke error body with the shared response builder.
2. Replace raw `logging.exception(...)` and exception interpolation with one
   shared failure logger.
3. Do not include downstream response bodies in Connector success responses or
   logs; retain only the status code.
4. Do not log function URLs containing `code=` or telemetry/query payloads.
5. Move Event Checker configuration validation inside the HTTP boundary.
6. Represent Event Checker partial failures by event index, stable code, and
   correlation ID. Do not echo the event definition.
7. Return an internal error from `hot-reader-last-entry` instead of an empty
   successful result when the query fails.
8. Keep successful response payloads and provider operations unchanged.

## Compatibility

- Existing successful responses remain unchanged except Connector, whose
  `remote_response` object becomes `remote_status_code`.
- Existing 400, 401, and 403 behavior remains at the same status for each
  endpoint.
- Existing server errors remain 5xx, with downstream/user-function failures
  becoming explicit 502 responses where applicable.
- Callers in the current closed-world runtime only require success status and
  payload. No current caller consumes legacy error text.
- The canonical contract is additive at the platform level and does not alter
  Optimizer, Management API, manifest, tfvars, or Terraform schemas.

## Tests and Gates

### Shared helper

- exact JSON shape and content type;
- UUID correlation identity shared by response and log;
- direct key/value, JSON, bearer, private-key, SAS/function-key URL, known
  environment-value, Unix path, and Windows path redaction;
- bounded single-line diagnostics;
- invalid JSON parsing without decoder details.

### Adapter behavior

- inject a secret-bearing failure into every adapter family in the inventory;
- assert stable code, expected status, correlation ID, and no secret in body or
  captured logs;
- assert request/auth failures preserve their status and omit diagnostics;
- assert Connector never returns or logs a downstream body;
- assert Event Checker partial failures are safe and do not expose the event;
- assert Last Entry no longer returns `200` after a provider failure;
- retain existing ADT Pusher success and validation coverage.

### Drift gates

- AST/source gate rejects exception values in `HttpResponse` payloads;
- source gate rejects `logging.exception` in core HTTP adapters;
- source gate rejects Connector `remote_response`;
- Azure bundle tests prove `_shared/http_errors.py` is included;
- full Deployer safe suite excluding live E2E;
- Ruff, Bandit, compileall, and repository diff checks;
- no live cloud deployment.

## Review Findings Resolved in the Plan

1. Redacting a response is insufficient because traceback logging can emit the
   original exception again. The target forbids `exc_info` at this boundary.
2. Regex-only redaction misses a bare secret value. Sensitive runtime
   environment values are replacement inputs.
3. A successful Connector response can leak a remote error or provider body.
   Only downstream status is public.
4. Returning empty data on a provider error creates false correctness. Last
   Entry must fail explicitly.
5. Event Checker partial success needs a safe result contract rather than
   failing the whole batch or exposing the event definition.
6. Configuration validation outside `try` bypasses the error contract. It moves
   inside the boundary.

## Definition of Done

- [ ] Every core Azure HTTP adapter uses the shared response policy.
- [ ] No 5xx or partial-failure response contains raw diagnostics.
- [ ] No runtime failure log contains known secrets, signed URL values, or
  runtime paths.
- [ ] Unexpected failures have response-to-log correlation.
- [ ] No provider failure is silently returned as success.
- [ ] Existing successful runtime behavior remains covered.
- [ ] Packaging includes the shared helper in every relevant Azure bundle.
- [ ] Full safe tests and static/security gates pass.
- [ ] Runtime/developer documentation matches the implemented contract.
- [ ] #136 is closed with commit and verification evidence.
