# Twin2MultiCloud Cloud Deployer

The Deployer translates one immutable Six-layer deployment graph into
graph-derived readiness, bounded account preparation, isolated Terraform and
provider operations, runtime verification, access handoff, and cleanup
evidence.

It is an internal service. Flutter calls it only through the Management API.

## Scope

- validate request-scoped deployment administrator credentials;
- derive exact APIs, resource providers, permissions, quotas, identities,
  packages, Terraform inputs, probes and cleanup expectations from the graph;
- return a non-mutating readiness result;
- execute only reviewed, confirmed, idempotent account preparation;
- stage one-use immutable operation packages;
- Deploy and Destroy in isolated workspaces;
- report typed progress, verification and cleanup results;
- expose provider-accurate L4/L5 access metadata.

The Deployer does not own users, Twin lifecycle, cost calculation, credential
persistence, arbitrary deployment projects, architecture selection, or a
provider administration console.

## Input boundary

The canonical operation package is bound to:

- calculation run and architecture/specification digests;
- exact component and directed-edge assignments;
- allowlisted typed Twin configuration and bounded extensions;
- selected CloudConnection fingerprints and current readiness evidence;
- Deployment Manifest v4 integrity.

Unknown project layouts, secret-bearing portable evidence, and downstream
reconstruction of missing graph values fail closed.

## Provider preparation

Readiness is non-mutating. Supported preparation may register exact Azure
resource providers and enable exact GCP APIs after explicit confirmation.
External billing, quota, organization policy, consent, legal, capacity, and
credential-lifecycle tasks remain typed manual blockers.

Twin Destroy removes Twin-owned resources. Shared account capabilities remain
recorded as retained prerequisites.

## Operation model

Management creates and persists the operation; the Deployer performs the
provider work. Reconnect/replay is handled through Management so a UI transport
failure cannot duplicate Apply or Destroy.

Terraform source templates are protected. Each operation receives an isolated
workspace, exact packages, and graph-derived tfvars. Only allowlisted outputs,
verification results, access metadata, and cleanup evidence leave it.

## Safe verification

```bash
cd 3-cloud-deployer
PYTHONPATH=. python -m pytest -q
```

Unit/contract tests and credential-free Terraform validation create no cloud
resources. Live E2E is opt-in, supervised, budgeted, and followed by explicit
Destroy plus residual inventory.
