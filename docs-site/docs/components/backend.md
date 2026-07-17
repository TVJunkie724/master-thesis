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
| `/twins/{id}/optimizer-runs/{run_id}/pricing-evidence` | owner-scoped compact, field-level, and exact transfer-route calculation evidence |
| `/twins/{id}/deployer` | deployment configuration and readiness |
| `/cloud-connections` | reusable encrypted credentials, validation, binding/defaults |
| `/cloud-bootstrap` | transient admin credential bootstrap/validate workflows |
| `/cloud-access` | account-level capability inventory |
| `/platform/provider-capabilities` | aggregate Optimizer/Deployer provider-layer capability contract |
| `/optimizer/pricing-refresh` | provider refresh run lifecycle |
| `/optimizer/pricing-review` | health, candidates, evidence, decisions |
| `/optimizer/pricing-status`, `/optimizer/pricing-health` | owner-scoped status of the exact immutable catalogs used for calculation |
| `/optimizer/pricing/catalogs/{provider}/{region}/snapshots/{id}` | authenticated, size-bounded inspection of one exact catalog |
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
lifecycle/operation state, credential audit events, immutable pricing-catalog
references, and legacy credential disablement. Migration `019` adds the compact
three-provider context and backfills it only when a historical Optimizer result
contains a complete, internally valid exact reference set.

SQLite is the local single-node storage choice. A production multi-replica deployment would
require a managed relational database and a migration framework appropriate to it.

## Pricing Catalog Trust Boundary

The Management API resolves the catalog context before every calculation:

```text
owner-scoped successful refresh reference
  -> exact reference verification in Optimizer
  -> fallback to committed reviewed baseline when no owner reference is usable
  -> strict AWS + Azure + GCP reference set
  -> calculation request
  -> result must return the identical set
  -> compact references persisted with run and optimizer projection
```

`PricingCatalogReference` validates provider, canonical region, versions, UTC
fetch time, digest, review/publication state, calculation source, and the derived
snapshot identity. A run cannot be selected for deployment when any referenced
catalog is missing, stale, malformed, or different from the Optimizer's exact
read result.

For route-aware results, Management additionally validates
`complete-path-transfer-pricing.v1` and `complete-path-optimization.v1` before
returning or persisting a calculation. The gate requires exactly the six
baseline segments and checks their endpoints, selected providers, regions,
route classes, provider network tiers, pool identities, source snapshot IDs,
tier arithmetic and continuous marginal quantity coverage, aggregate
bytes/cost, currency, and winning candidate against the server-resolved catalog
context. The non-persisting diagnostic calculation proxy and the durable run
workflow share this one validation service.

`POST /twins/{id}/optimizer-runs` is the only application command that may
persist an optimizer result and its deployment-path projection. Management
resolves the trusted pricing context, invokes the Optimizer, validates the
returned contracts, derives the path from `calculationResult`, and commits the
run, result items, and `OptimizerConfiguration` projection atomically. Generic
twin updates and optimizer-parameter drafts cannot carry a result or cheapest
path. `GET /twins/{id}/optimizer-config` retains a read-only result projection
for configuration, validation, and deployment compatibility.

The Management database does not store full public pricing catalogs. Existing
legacy snapshot/timestamp columns are outside the live contract and do not make
pricing calculable. Full pricing remains in the Optimizer's immutable regional
catalog store and is returned only through the explicit authenticated diagnostic
route. The client enforces an 8 MiB response limit.

For AWS TwinMaker, the user/account observation remains separate from the public
catalog reference. Region and content digest must agree before calculation, and
an AWS L4 result must return the exact Management-injected account context.

## Persisted Pricing Trace

Cost-calculation result JSON is an immutable snapshot of the Optimizer response. The
pricing-evidence detail endpoint projects three calculation-evidence levels plus
the immutable catalog context from that snapshot:

- `intent_trace` for the compact selected-path explanation;
- `field_trace_records` plus `field_trace_schema_version` for provider-field audit
  details;
- `transfer_pricing_context` plus `optimization_diagnostics` for all exact
  baseline routes, provider billing pools, tier contributions, assumptions,
  and bounded path-selection diagnostics;
- `pricing_catalog_context` for the exact AWS, Azure, and GCP catalog identities;
- explicit availability flags and compatibility warnings for historical runs.

Management creates one queryable transfer result item per baseline edge from
the validated route contract. Each item stores source provider, monthly byte
quantity, cost, evidence ID, and the bounded route detail. It never trusts or
persists a competing downstream or client-authored transfer item when the exact
route contract is present.

The service applies recursive secret and local-path redaction before returning either
trace. Malformed field or transfer evidence is omitted with a warning instead
of making an entire historical run unreadable. A historical run without the
new transfer contract remains readable with
`transfer_pricing_context_available=false`; Management does not reconstruct or
invent missing evidence. No separate trace table or migration is required
because the durable run result and existing result-item columns already
represent the bounded metadata.

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
