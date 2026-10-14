# State and Persistence

The local thesis runtime is single-node. Management persists relational
application/evidence state in SQLite; the Deployer retains operation workspaces
and Terraform state needed for status and explicit Destroy.

## Management state

- users and Twin lifecycle;
- canonical architecture pins;
- typed configuration and bounded extension bindings;
- encrypted deployment CloudConnections and non-secret validation metadata;
- immutable calculations, pricing references, resolved graphs and deployment
  specifications;
- readiness/preparation evidence;
- deployment operations, replay history, verification and cleanup results.

## Repository state

The Optimizer's frozen price snapshots, formulas, provider contracts, and the
shared Six-layer schemas are versioned source evidence. Runtime users cannot
edit or refresh them.

## Deployer state

An operation uses an isolated workspace generated from an exact package. The
template source is protected. Terraform state and allowlisted outputs remain
available until Destroy/cleanup evidence is complete; arbitrary workspace
content is not copied into Management.

## Portability

Typed Twin Export/Import is the only user-facing interchange boundary. It does
not transport application databases, credentials, Terraform state, provider
outputs containing secrets, or operation history.

Production database HA, distributed locking, backup automation, cross-node SSE
coordination, multi-tenant retention, and disaster recovery are outside scope.
