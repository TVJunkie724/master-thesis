# Multi-Cloud Digital Twin Deployer

The infrastructure execution service of the Twin2MultiCloud PoC. It receives
a Management-owned deployment package, validates it, builds function packages
and Terraform inputs, then executes provider operations.

## Run

From the repository root:

```bash
./thesis.sh up --no-flutter
```

The internal API reference is at [localhost:5004/docs](http://localhost:5004/docs).
Flutter calls the Management API, never the Deployer directly.

## Execution boundary

New deployment packages use **DeploymentManifest v3**, with the frozen
architecture and deployment specification. The Deployer compiles a deterministic
graph, validates package/Terraform bindings, and acquires the staged package
through a one-use token. Manifest v2 remains historical read compatibility;
it is not the format for new deployments.

Execution uses a temporary workspace. Only allowlisted Terraform/device outputs
return to the private runtime-state store. Reusable credentials remain owned
by Management Cloud Connections, not project folders or templates.

Graph compilation is implemented. Final live-cloud evidence and the current
L4→L5/Grafana binding gap remain separate limitations:
[Results and Limits](../docs-site/docs/runtime/known-limitations.md).

## Code and reference

| Path | Purpose |
|---|---|
| `src/api/` | internal HTTP operations |
| `src/architecture_profiles/` | resolved deployment graph |
| `src/deployment_specification/`, `src/terraform_inputs/` | manifest validation and typed input translation |
| `src/providers/` | provider and Terraform execution |
| `src/operation_packages.py` | short-lived operation packages |
| `src/runtime_state.py` | durable private execution state |
| `templates/digital-twin/` | canonical read-only template |
| `tests/` | safe tests and separately opt-in live E2E |

- [Deployer reference](../docs-site/docs/components/deployer.md)
- [Deployment lifecycle](../docs-site/docs/contracts-and-data-flow/deployment-lifecycle.md)
- [Cloud setup](../docs-site/docs/cloud-setup/index.md)
- [Testing](../docs-site/docs/developer-guide/testing.md)

Live deploy/destroy and provider E2E require deliberate cloud access and can
incur costs.
