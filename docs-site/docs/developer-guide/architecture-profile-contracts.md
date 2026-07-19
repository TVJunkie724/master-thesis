# Architecture Contract Development

The canonical source is:

```text
contracts/architecture-profiles/v1/
  architecture-profile.schema.json
  provider-implementation-profile.schema.json
  deployment-component-catalog.schema.json
  resolved-twin-architecture.schema.json
  semantic-registry.schema.json
  semantic-registry.json
  runtime.py
  fixtures/
```

Do not edit generated copies below the Optimizer, Management API, or Deployer.

## Change Procedure

1. Change the canonical schema, registry, runtime, or deterministic fixture
   builder.
2. Keep logical architecture free of provider SDK, Terraform, physical name,
   endpoint, and credential fields.
3. Increment semantic versions when capability, formula, package, Terraform
   binding, permission, or behavior changes.
4. Add positive and fail-closed negative coverage for the change.
5. Regenerate reviewed fixtures and service copies.
6. Run the focused cross-service gate and relevant full safe suites.
7. Update compatibility and current-system documentation.

```bash
python scripts/sync_architecture_profile_contracts.py \
  --generate-fixtures --sync
python scripts/sync_architecture_profile_contracts.py --check
python -m unittest \
  scripts.tests.test_architecture_profile_contract_sync -v
./thesis.sh test deployment-contract --focused
```

Run these commands in a project/container Python environment with the locked
dependencies. No cloud credentials or live provider resources are required.

## Adding A Reviewed Profile

A new profile version needs all of the following before runtime activation:

- a complete logical responsibility/component/edge graph;
- one mutually compatible optimization, calculation, formula, workload,
  pricing, scoring, and deployment-specification bundle;
- provider implementation mappings with explicit capability evidence;
- registered deployment components and edge implementations;
- deterministic positive and negative fixtures;
- compatible readers, migration behavior, documentation, and drift gates.

This is not a graph-editor extension point. Runtime clients never add arbitrary
nodes, edges, services, Terraform values, or physical bindings.

## Generated-Copy Rule

The sync script calculates a digest over canonical source paths and bytes,
copies the complete bundle, and writes `.contract-sha256`. `--check` rejects a
missing file, changed byte, extra generated file, or stale marker. CI watches
the canonical directory, sync/check implementation, generated copies, and
cross-project tests.

## Safe Reader Boundary

Phase 8.2 readers validate and return immutable views only. They are not wired
to Optimizer calculation, Management persistence/API routes, Deployer
package/Terraform execution, or Flutter. Those integrations belong to later
reviewed phases.
