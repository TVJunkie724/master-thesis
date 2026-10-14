# State Ownership

## Durable state

| State | Owner | Mutation rule |
|---|---|---|
| user and Twin lifecycle | Management | owner-scoped transactional commands |
| canonical architecture pin | Management | created automatically; read-only afterwards |
| draft configuration and extension bindings | Management | editable only before deployment immutability |
| encrypted deployment CloudConnections | Management | write-only secret input; metadata updates invalidate validation |
| calculation runs/results/traces | Management | append-only outcome from Optimizer response |
| resolved graph and deployment specification | Management | immutable and digest-bound to a run |
| readiness/preparation evidence | Management | invalidated by graph, credential, or binding drift |
| deployment operations and replay cursor | Management | one active mutation per Twin |
| Terraform/runtime state | Deployer | operation-owned; needed for explicit Destroy |
| frozen pricing and formula sources | Optimizer repository | changed only through reviewed source commits |

## Portable state

Twin Export/Import contains versioned allowlisted configuration and bounded
extension sources. It excludes credentials, Terraform state, generated secret
outputs, operation history, and arbitrary executable project layouts.

## Lifecycle consequences

- A draft can be edited and recalculated.
- A deployed definition is immutable.
- Duplicate or Import creates a new independent draft and unique name.
- The source Twin remains untouched until the user explicitly destroys it.
- Same-Twin re-deployment is allowed only after successful Destroy.
- Reconnect or page refresh resumes an existing operation; it does not create
  another provider command.

SQLite and local runtime storage are appropriate for the single-user thesis
PoC. High availability, multi-tenant isolation, backups, distributed locks,
and production disaster recovery are outside scope.
