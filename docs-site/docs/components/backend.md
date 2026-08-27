# Management API

The Management API is the only application backend visible to Flutter. It owns
authentication, users, Twins, encrypted deployment CloudConnections,
configuration, immutable calculation evidence, readiness/repair, deployment
operations, verification, cleanup, and public errors.

## Main public surfaces

| Surface | Responsibility |
|---|---|
| `/twins` | draft lifecycle, Duplicate, typed Export/Import, explicit deletion |
| `/architecture-contract` | read the fixed Six-layer contract |
| `/twins/{id}/architecture-contract` | read the Twin's immutable contract pin |
| `/optimizer-runs` | create, inspect, and select immutable cost calculations |
| `/cloud-connections` | named write-only deployment credential records and identity validation |
| Twin deployment-readiness routes | graph-derived checks, confirmed preparation, repair evidence |
| Twin operation routes and `/sse` | Deploy/Destroy state, replay, resume, verification and cleanup |
| resolved architecture/specification reads | owner-scoped immutable evidence |

There are no public Optimizer proxy routes, pricing review/refresh APIs,
architecture catalog/selection APIs, or generic provider command endpoints.

## Internal clients

`OptimizerClient` sends exact calculation metadata, validates the returned
pricing references, and retrieves only read-only capability/reference data.
`DeployerClient` owns credential identity checks, graph readiness, bounded
preparation, package staging, provider execution, probes, and cleanup.

Secrets are decrypted only for the current Deployer call and are never placed
in durable operation events, HTTP responses, logs, portable archives, or
Optimizer requests.

## Persistence and immutability

Management uses SQLAlchemy and SQLite for the single-node PoC. A successful
calculation atomically persists the result, trace, resolved deployment
specification, and resolved architecture. A deployed Twin cannot be edited in
place; its definition is reproduced through a new draft.

## Safe verification

The default pytest suite uses isolated SQLite databases and fake downstream
clients. It covers ownership, strict schemas, redaction, readiness drift,
operation idempotency/replay, archive roundtrips, verification, and cleanup
without contacting a provider.
