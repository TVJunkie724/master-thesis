# API And Contracts

## Contract Direction

```text
Flutter models/ManagementApi
          |
          v
Management API Pydantic schemas
      |                   |
      v                   v
OptimizerClient       DeployerClient
      |                   |
Optimizer OpenAPI     Deployer OpenAPI
```

The Management API adapts internal service contracts into stable user-facing contracts.
Flutter must not mirror internal provider payloads directly.

## Versioning

Schema versions appear on durable/result contracts such as deployment status/outputs,
pricing registry/evidence, optimization results, and the deployment manifest. A version
change requires compatibility behavior or an explicit coordinated migration.

Provider support uses two internal `provider-service-capabilities.v1` contracts and the
public `platform-provider-capabilities.v1` aggregate. Flutter consumes only the public
Management API contract. See
[Provider Capabilities](../architecture/provider-capabilities.md).

Pricing calculation traceability uses two additive result contracts:

| Contract | Role | Compatibility rule |
|---|---|---|
| `intent-result-trace.v1` | compact selected path and publishability envelope | may exist without field trace on historical runs |
| `intent-to-result-trace.v1` | provider-field calculation audit | new semantics are additive; missing fields use explicit legacy defaults |

The Optimizer constructs both contracts, the Management API persists and redacts the
immutable result, and Flutter only renders typed read models. A contribution amount is
not additive unless its record explicitly proves that property. Alternative providers
and rejected pricing rows are different concepts and must remain separate fields.

The public Management calculation input and the internal Optimizer input intentionally
differ by two server-owned fields. `providerPricingCatalogs` is the mandatory exact
public-catalog context; `providerPricingContexts` carries optional owner-scoped account
observations. Flutter supplies neither. The Management API resolves and injects them,
and the live integration gate compares every remaining workload field exactly.

### Transfer Pricing Catalog

Every provider-region pricing snapshot contains one
`transfer-pricing-catalog.v1` object. The calculation contract requires its
route class, source region/geography, destination geographies, network tier,
billing scope, native billing unit, byte divisor, currency, evidence ID,
aggregation semantics, and contiguous explicit tier ranges. Unknown,
missing, gapped, overlapping, unit-inconsistent, or non-terminal data fails
before a transfer value can enter scoring.

AWS and Azure use decimal GB; GCP uses GiB. The common comparison quantity is
bytes. No API adapter, Management service, or Flutter model may reconstruct a
scalar transfer rate or substitute a default when the catalog is unavailable.
Aggregate pool allocation and complete-path selection are owned by
`calculation_v2/path_optimizer.py`, not by clients. The Optimizer evaluates all
executable combinations of the seven baseline slots and all six approved
directed edges before the active scoring strategy selects a winner. Clients may
display `complete-path-transfer-pricing.v1` and
`complete-path-optimization.v1`; they must not recalculate pools, infer missing
routes, or replace exact catalog references.

The Management API is the trust boundary for these two result contracts. Its
shared transfer-pricing validator compares route endpoints and regions with the
server-owned catalog context, checks provider policy and pool/tier arithmetic,
requires marginal tier intervals to cover the provider pool's normalized byte
quantity without gaps, and binds the diagnostic winner to
`calculationResult`. Numeric strings and booleans are not coerced. Only
validated route objects become persisted transfer result items, and
client-supplied transfer result items are ignored. Historical results without
these additive contracts remain readable but are explicitly unavailable for
route evidence.

## Errors

Public errors should provide stable code, safe message, actionable suggestion where
possible, HTTP status, and request ID. Downstream exception strings are not public
contracts and must pass redaction/shaping.

## Discover Exact APIs

Start services and use OpenAPI:

| Contract | URL | Intended client |
|---|---|---|
| Management API | `http://localhost:5005/openapi.json` | Flutter/external application client |
| Optimizer | `http://localhost:5003/openapi.json` | Management API/developer diagnostics |
| Deployer | `http://localhost:5004/openapi.json` | Management API/developer diagnostics |

When adding an endpoint, test both serialization and the consuming typed adapter.
Avoid duplicating exhaustive field tables in prose because generated schemas are more
reliable; document semantics, invariants, ownership, and examples here.
