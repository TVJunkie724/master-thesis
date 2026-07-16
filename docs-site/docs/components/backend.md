# Management API

`twin2multicloud_backend` is the application and orchestration boundary. It is the only
backend Flutter may call and the only service that owns users, twins, durable workflow
history, CloudConnections, and lifecycle transitions.

## Responsibilities

- authenticate users and enforce owner scope;
- persist twins, configuration, file versions, calculation runs, reviews, deployments, and logs;
- encrypt and manage reusable CloudConnections;
- validate configuration and deployment readiness;
- call Optimizer and Deployer through typed clients;
- build canonical deployment archives/manifests;
- expose operation state, outputs, history, audit events, and SSE streams.

Provider SDK logic and cost formulas do not belong here.

## Layering

```text
FastAPI route
   -> schema + dependency/auth boundary
   -> application/domain service
   -> repository ----------> SQLAlchemy/SQLite
   -> typed client ---------> Optimizer or Deployer
```

| Path | Responsibility |
|---|---|
| `src/api/routes/` | thin HTTP adapters and status/error mapping |
| `src/schemas/` | Pydantic request/response contracts and schema versions |
| `src/services/` | workflows, validation, lifecycle, projections, orchestration |
| `src/repositories/` | owner-scoped persistence access |
| `src/clients/` | typed downstream HTTP contracts and response validation |
| `src/models/` | SQLAlchemy persistence model |
| `src/security/` | transport, request IDs, rate limiting |
| `migrations/` | idempotent SQLite schema upgrades |

## Main API Areas

| Area | Purpose |
|---|---|
| `/auth` | provider capabilities, durable OAuth/SAML login, session exchange/revocation, current user/profile |
| `/twins` | CRUD, lifecycle, assets, operations, history, status, outputs |
| `/twins/{id}/config` | configuration workspace persistence and validation |
| `/twins/{id}/optimizer-config` | typed optimization inputs and projections |
| `/twins/{id}/optimizer-runs` | durable calculation execution/results |
| `/twins/{id}/deployer` | deployment configuration and readiness |
| `/cloud-connections` | reusable encrypted credentials, validation, binding/defaults |
| `/cloud-bootstrap` | transient admin credential bootstrap/validate workflows |
| `/cloud-access` | account-level capability inventory |
| `/platform/provider-capabilities` | aggregate Optimizer/Deployer provider-layer capability contract |
| `/optimizer/pricing-refresh` | provider refresh run lifecycle |
| `/optimizer/pricing-review` | health, candidates, evidence, decisions |
| `/credential-security-events` | owner-scoped credential audit history |
| `/sse` | server-sent operation/log streams |

Use live OpenAPI at `http://localhost:5005/docs` for exact fields.

## Data Model

```text
User
  +-- ExternalIdentity
  +-- AuthSession
  +-- DigitalTwin
  |     +-- TwinConfiguration
  |     +-- OptimizerConfiguration -- CostCalculationRun -- ResultItem
  |     +-- DeployerConfiguration
  |     +-- FileVersion
  |     +-- Deployment -- DeploymentLog
  |     +-- DeploymentPreflightCache
  +-- CloudConnection

PricingRefreshRun
PricingCandidateReport
PricingReviewDecision
CredentialSecurityEvent
AuthLoginTransaction
AuthenticationEvent
```

Twins are soft-deleted to `inactive`. CloudConnection references are checked before
deletion. Configuration edits can regress a previously configured twin to `draft`.

## Credential SSOT

`CloudConnection` stores provider, purpose, scope metadata, permission-set version,
validation status, a non-secret fingerprint, and an encrypted payload. API responses
never return the decrypted payload. Purpose distinguishes deployment and pricing use;
one user-level pricing default is enforced per provider.

Credential mutation/validation/bootstrap operations are rate limited and audited.
Downstream validation messages are redacted before response or persistence.

## Provider Capability Aggregation

`ProviderCapabilityService` concurrently loads the Optimizer calculation matrix and
Deployer provisioning matrix, validates both strict versioned contracts, and derives
one complete platform response. Drift, malformed payloads, and source outages produce
sanitized typed `502`/`503` errors; the service never guesses or returns a partial
selectable matrix. Configuration validation preserves a Deployer
`CAPABILITY_UNAVAILABLE` error with provider/layer context.

See [Provider Capabilities](../architecture/provider-capabilities.md) for the matrix and
extension sequence.

## Deployment Orchestration

`DeploymentOrchestrator` and deployment services coordinate readiness, lifecycle,
archive generation, package staging, stream handling, result persistence, rollback,
and recovery. A deployment record is separate from twin state, enabling operation
history and correlation by session/operation ID.

The Management API builds `deployment_manifest.json` version `1.0`, submits exact
archive bytes to the Deployer, receives an operation-package token, and uses that token
for the deploy/destroy operation. It does not write into Deployer templates directly.

## Database Startup And Migrations

Startup calls `Base.metadata.create_all()` for missing tables and then the explicit
idempotent migration runner for existing SQLite databases. Migrations cover Cloud
Connections, purpose/version fields, pricing reviews, calculation runs, deployment
lifecycle/operation state, credential audit events, and legacy credential disablement.

SQLite is the thesis/local storage choice. A production multi-replica deployment would
require a managed relational database and a migration framework appropriate to it.

## Security And Errors

- settings fail startup on weak/missing/duplicated runtime secrets;
- dev auth, seeding, and test routes are forbidden in production;
- production HTTPS and trusted proxy rules are explicit;
- external login uses durable one-time transactions, Google PKCE, SAML request
  correlation, and server-side revocable sessions;
- identity ownership is keyed by provider subject; email collisions require
  explicit future account linking rather than implicit merge;
- authentication and credential operations use separate fail-closed rate limits;
- structured service errors map to stable HTTP status/error codes;
- request IDs correlate errors and credential audit events;
- required credential security-control outages return `503` and fail closed;
- downstream response shapes are validated at client boundaries;
- sensitive messages and outputs are redacted.

## Tests

```bash
./thesis.sh test backend
```

Tests cover routes, services, repositories, migrations, security controls, client
contracts, lifecycle transitions, credentials, pricing review, configuration, and
deployment orchestration. Tests under E2E boundaries are excluded by default.

## Extension Points

- add a schema, service use case, repository method if persistence is needed, then a thin route;
- extend `OptimizerClient`/`DeployerClient` before consuming new downstream contracts;
- keep lifecycle changes in `TwinLifecycleService`;
- add schema-versioned responses for new durable/public result types;
- add an idempotent migration for every existing-database schema change;
- add demo adapter support when a new API is visible in Flutter.

## Evolution And Gaps

The first integration concentrated queries, state transitions, downstream HTTP calls,
and archive construction in large route modules. The current structure separates
repositories, lifecycle/application services, typed clients, and orchestration.

The production authentication implementation is complete, while live UIBK activation
remains externally gated by institutional federation registration and configuration.
Encryption-key rotation is explicit future operational work. SQLite remains a bounded
deployment choice, not a claim of horizontally scalable production persistence.
