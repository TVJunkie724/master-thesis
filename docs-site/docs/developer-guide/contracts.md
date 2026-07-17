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
