# Phase 7c: Azure Function Error Contracts

**Issue:** [#136](https://github.com/TVJunkie724/master-thesis/issues/136)
**Status:** Reviewed and implementation-ready
**Blocked by:** #74

## Target

Every deployed Azure Function HTTP adapter returns a stable, bounded,
secret-free error contract. Expected request failures remain actionable;
unexpected provider/runtime failures are diagnosable through a correlation ID
without exposing raw exception text to callers.

## Canonical Error Contract

All affected HTTP functions use one shared response builder:

```json
{
  "error": {
    "code": "STABLE_MACHINE_CODE",
    "message": "Bounded safe message",
    "correlationId": "opaque identifier"
  }
}
```

- `400`: malformed or semantically invalid caller payload;
- `401` or `403`: missing/invalid inter-cloud authentication;
- `409` or `422`: only where an existing runtime domain contract already
  distinguishes conflict or configuration semantics;
- `500`: generic `INTERNAL_RUNTIME_ERROR`; never raw exception text.

The correlation ID comes from an accepted bounded request header when present,
otherwise from a generated UUID. It is returned and attached to the matching
server log record.

## Implementation

1. Inventory every `HttpResponse` under
   `src/providers/azure/azure_functions/` and classify its expected failures.
2. Add one `_shared` runtime error module that owns:
   - response shape and bounded codes/messages;
   - correlation-ID validation/generation;
   - central redaction for known environment secret values and sensitive key
     patterns;
   - safe exception logging with function and correlation context.
3. Migrate ingestion, connector, hot/cold/archive writers, hot readers, event
   checker, ADT pusher, and other HTTP adapters found by the inventory.
4. Preserve the current success payloads and function routes.
5. Add a source drift gate forbidding exception interpolation in HTTP response
   payloads.
6. Document the public runtime error semantics and residual provider logging
   limitations.

## Security Rules

- Never serialize `str(exception)`, traceback text, provider response bodies,
  signed URLs, filesystem paths, or environment values into a client response.
- Server logging must redact exact configured secret values plus token,
  password, key, connection-string, authorization, signature, and credential
  patterns.
- Redaction must be bounded and deterministic; it must not log an unredacted
  fallback when formatting itself fails.
- Error responses must not reveal whether a particular secret value exists.
- Authentication comparison continues to use the shared constant-time token
  path.

## Tests And Gates

- parameterized response tests for every affected adapter family;
- malformed payload and auth status/code tests;
- injected secret-bearing provider/configuration exception tests;
- correlation-ID propagation and invalid-header replacement tests;
- redacted server-log tests;
- source scan for raw exception interpolation;
- Azure package/import tests;
- full Deployer non-E2E suite;
- Ruff, Bandit, compileall, and strict docs build.

## Definition Of Done

- [ ] One shared Azure runtime error contract owns every HTTP failure response.
- [ ] No Azure Function 5xx response exposes raw exception or secret material.
- [ ] Expected client/auth failures retain correct statuses and stable codes.
- [ ] Correlation IDs connect client-safe responses to redacted server logs.
- [ ] Focused and full safe test suites pass.
- [ ] #136 is closed with commit and verification evidence.

