# Implementation Plan: Production Credential Security Controls

**Status:** Implemented, twice reviewed, and verified.

## 0. Delivery Context

- **Branch:** `codex/credential-security-controls`
- **Base:** `master` at `aafeef1`
- **GitHub issue:** [#8](https://github.com/TVJunkie724/master-thesis/issues/8)
- **Depends on:** #9 local runtime secret bootstrap (complete)

## 1. Goal

Complete the production boundary around stored cloud credentials. Credential
mutations and validation calls must be attributable, rate-limited, secret-free
in all persisted diagnostics, and transport-protected in production. The local
runtime key source delivered by #9 remains the only automatic key bootstrap;
this slice does not invent an application-managed vault or automatic key
rotation.

## 2. Security Invariants

1. API responses, audit events, logs, rate-limit keys, and errors never contain
   credential payloads, authorization headers, tokens, request bodies, raw IP
   addresses, or secret-derived hashes.
2. Successful CloudConnection create/update/delete and validation-state changes
   commit their audit event in the same database transaction.
3. Rejected and rate-limited attempts are recorded independently because their
   business transaction is rolled back or never starts.
4. Audit fields are an allowlisted typed contract, not arbitrary metadata.
5. Rate limits are keyed by authenticated user and operation class. Production
   requires a shared Redis-compatible backend; process-local memory is allowed
   only in development and tests.
6. Production rejects insecure HTTP at the application boundary. Forwarded
   scheme headers are trusted only from explicitly configured proxy networks.
7. Production CORS origins use HTTPS, and secure responses carry HSTS.
8. Security-control failure is fail-closed for credential mutation and
   validation endpoints; it must not silently disable auditing or limiting.

## 3. Protected Surface

| Operation class | Endpoints | Default quota |
|---|---|---|
| `credential-write` | CloudConnection create, update, delete; bootstrap import; wizard/config credential persistence | 10 per minute per user |
| `credential-validation` | CloudConnection validate/preflight; stored and inline validation routes | 6 per minute per user |
| `credential-bootstrap` | Bootstrap plan and import | 5 per minute per user |

Read-only, secret-free connection inventory and audit-history queries are not
credential attempts and use the normal API controls. Pricing refresh and
deployment preflight already consume stored connection IDs; their own run
contracts remain responsible for operational throttling and are outside this
credential-input slice.

## 4. Subphase 8.1: Request Context And Audit Trail

Add a validated/generated request ID middleware and an append-only
`credential_security_events` table. Events contain only: event ID, actor user
ID, typed action, typed outcome, resource type/ID, provider, purpose, HTTP
status, request ID, and UTC timestamp.

The CloudConnection service accepts a typed audit context for mutations and
validation updates and appends the event before its existing commit. A failed
audit insert rolls back the business mutation. Rejected attempts use a small
independent writer after the request transaction is rolled back. A paginated,
user-scoped read endpoint exposes the current user's events without any global
role assumption.

Database migration `017_credential_security_events` creates the table and
indexes for user/time, request ID, action, and resource lookup. No update or
delete repository methods or API endpoints are provided.

## 5. Subphase 8.2: Distributed Rate Limiting

Use the established `limits` library and its async storage abstraction. Do not
hand-roll counters. A credential security dependency authenticates first,
derives a non-reversible user-key digest scoped only to limiter storage, checks
the operation quota, and returns standard `RateLimit-*` plus `Retry-After`
headers. A rejected request returns a structured `429 RATE_LIMITED` response
and records a secret-free audit outcome.

Configuration:

- `CREDENTIAL_RATE_LIMIT_ENABLED` (production must be true)
- `CREDENTIAL_RATE_LIMIT_STORAGE_URI` (`memory://` locally; `redis://` or
  `rediss://` required in production)
- typed quota strings for write, validation, and bootstrap classes

Malformed quotas and unsupported production storage fail during settings
validation. Storage is initialized lazily once per API process and the client
connection pool is released with process shutdown; tests reset only their
process-local memory backend.

## 6. Subphase 8.3: Production Transport Boundary

Add a pure ASGI middleware that:

- accepts direct HTTPS;
- accepts `X-Forwarded-Proto: https` only when the direct peer belongs to
  `TRUSTED_PROXY_CIDRS`;
- rejects insecure production requests with `400 INSECURE_TRANSPORT` instead
  of redirecting a credential-bearing request;
- adds `Strict-Transport-Security: max-age=31536000; includeSubDomains` to
  accepted production responses;
- preserves the request ID on rejection and response.

`REQUIRE_HTTPS` defaults to true in production and may be disabled only outside
production. Production CORS rejects wildcard, HTTP, malformed, and empty
origins. Deployment documentation must state that the edge proxy terminates
TLS and that Uvicorn proxy trust must match the application CIDR allowlist.

## 7. Subphase 8.4: Documentation And Verification

Update `.env.example`, `HANDBOOK.md`, and the refactoring roadmap with the
runtime contract, rate-limit backend, audit retention boundary, proxy setup,
and key-rotation limitation. Key rotation remains explicit future work because
all encrypted payloads require transactional re-encryption; no unsafe rotation
command is added here.

## 8. Error Contract

| Failure | HTTP/result | Required behavior |
|---|---|---|
| Quota exhausted | 429 `RATE_LIMITED` | Retry headers, audited, no provider call |
| Limiter unavailable | 503 `SECURITY_CONTROL_UNAVAILABLE` | Fail closed, no credential mutation/provider call |
| Insecure production transport | 400 `INSECURE_TRANSPORT` | No redirect/body processing, request ID returned |
| Atomic audit insert fails | 503 `AUDIT_WRITE_FAILED` | Business mutation rolled back |
| Invalid trusted proxy/rate config | startup failure | Actionable setting name, no secret value |

## 9. Test Plan

### Unit and contract tests

- request IDs are generated, valid inbound IDs are retained, malformed IDs are
  replaced, and concurrent requests do not leak context;
- audit schemas reject unknown fields and expose no secret-bearing field;
- successful mutation and audit event commit together;
- simulated audit failure rolls back CloudConnection mutation;
- failed, forbidden, and rate-limited attempts produce secret-free events;
- audit listing is owner-scoped, newest-first, bounded, and paginated;
- quotas isolate users and operation classes and emit deterministic headers;
- production rejects memory/disabled limiting and malformed quota strings;
- limiter backend failure returns 503 without calling the endpoint;
- direct HTTPS and trusted forwarded HTTPS pass; untrusted spoofing and plain
  HTTP fail; production responses include HSTS;
- production CORS accepts only explicit HTTPS origins.

### Regression and security gates

- complete Management API suite excluding live-cloud E2E;
- migration runner/idempotency tests;
- Bandit over Management API source, scripts, and migrations;
- `docker compose config` and real OrbStack Management API startup/health;
- repository scans for credential values in audit fixtures/responses/logs;
- `git diff --check` and documentation strict build.

No live provider call, cloud mutation, or paid E2E test is part of this slice.

## 10. Reviews

1. **Security review:** secret-flow, transaction atomicity, bypass behavior,
   trusted-proxy spoofing, user isolation, and fail-closed controls.
2. **Operations review:** migration idempotency, distributed deployment,
   startup/shutdown, error observability, local developer compatibility, and
   documentation completeness.

Both reviews must report zero unresolved findings before merge.

### Final evidence

- Complete Management API suite excluding live-cloud E2E: **679 passed**.
- Focused final credential/security regressions after the last audit-outcome
  refinement: **45 passed**.
- Ruff: passed with zero findings.
- Bandit over source, scripts, and migrations: passed with zero findings.
- Rebuilt Management API image and real OrbStack health check: passed.
- Two independent limiter instances against a temporary real Redis 7 backend:
  shared counter and rejection verified.
- `docker compose config`, dependency integrity, migration idempotency,
  `git diff --check`, and MkDocs strict build: passed.
- No live-cloud E2E, paid provider call, or cloud mutation was executed.

## 11. Definition Of Done

- [x] Protected credential endpoints are rate-limited by authenticated actor.
- [x] Production requires a shared rate-limit store and HTTPS.
- [x] Credential operations produce durable, owner-scoped, secret-free events.
- [x] Successful mutations and audit events are transactionally consistent.
- [x] Security-control outages fail closed with structured errors.
- [x] Request IDs connect API errors, audit events, and operational logs.
- [x] Explicit migration and rollback-safe tests exist.
- [x] Existing response redaction and all backend regressions remain green.
- [x] Runtime/deployment documentation reflects only the final contract.
- [x] Two reviews report no unresolved findings.
