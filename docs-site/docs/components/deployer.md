# Cloud Deployer

The Deployer is the only service allowed to validate deployment credentials,
inspect provider readiness, perform confirmed account preparation, execute
Terraform/provider operations, verify runtime behavior, and produce cleanup
evidence.

It does not own users, Twin lifecycle, cost calculation, public UI contracts,
or credential persistence.

## Inputs

Every operation is bound to an immutable package containing the selected
calculation ID, canonical architecture pin, resolved graph, deployment
specification, bounded configuration/extensions, connection fingerprints, and
manifest digest. Unknown files, arbitrary project layouts, and secret-bearing
portable evidence are rejected.

## Graph-derived behavior

The resolved graph determines:

- provider packages and directed edge adapters;
- required APIs/resource providers and permissions;
- regions, quotas and identity prerequisites;
- Twin-scoped runtime identities and trust objects;
- Terraform variables and bounded SDK stages;
- verification probes, access surfaces, and cleanup expectations.

This prevents fixed legacy provider permission packs from drifting away from
the costed/deployed architecture.

## Readiness and preparation

Identity validation is separate from deployment readiness. Readiness is
non-mutating. Supported account preparation is digest-bound, listed before
execution, explicitly confirmed, idempotent, and followed by a readiness rerun.
External billing, quota, policy, capacity, consent, and legal blockers remain
typed manual actions.

## Operations

Deploy and Destroy run in isolated workspaces. Management persists progress and
terminal evidence and exposes SSE replay. A successful Deploy includes
resource probes and the defined telemetry roundtrip. Destroy reports removed
Twin-owned resources, retained shared prerequisites, and residual failures.

Ordinary unit/contract/Terraform validation uses fakes or credential-free
plans. Live provider execution is opt-in and supervised because it can create
costs.
