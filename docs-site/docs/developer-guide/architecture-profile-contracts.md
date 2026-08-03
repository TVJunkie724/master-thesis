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
contracts/architecture-profiles/definitions/
  manifest.json
  profiles/five-layer-baseline/1/profile.json
  provider-implementations/five-layer-baseline/1/{aws,azure,gcp}/1.json
  component-catalogs/baseline/1/catalog.json
  fixtures/{resolved,unsupported}/
```

Do not edit generated copies below the Optimizer, Management API, or Deployer.

## Change Procedure

1. Change the canonical schema, registry, runtime, deterministic fixture
   builder, or reviewed catalog generator.
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
python scripts/check_architecture_profile_catalog.py --json
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

## Registering A Provider Component

Provider components are developer-authored, closed-world definitions. Update
the reviewed Phase 8.1 decision and evidence first, then update the binding
table in `scripts/architecture_profile_catalog.py`. Every component must name
real HCL resource, variable, and output symbols; deployment-dimension IDs;
`thesis-demo-v1` capabilities; pricing intents and formulas; a static package
or managed-source artifact; runtime/port/error/observability/cleanup contracts;
and compatibility versions. Regeneration pins canonical source digests.

The gate rejects stale decisions and source digests, missing or duplicate HCL
ownership, package-builder/package/handler drift, symlinks, unknown
pricing/formula/dimension/permission IDs, and invalid extension adapters.
Account-scope and usage-tier dimensions cannot become Terraform selections.

`processor.telemetry@1` is the only baseline extension slot. Its catalog
entries reference the #113 AWS, Azure, and GCP Python 3.11 adapters and
platform wrappers. The catalog never stores user source, configuration values,
resource names, endpoints, or user-supplied permissions.

## Safe Runtime Boundary

Management Phase 8.4 now uses the generated definitions for authenticated
profile list/detail/select/preview APIs, pinned Twin selections, migration 022,
fixture-gated atomic resolution admission, and owner-scoped immutable reads.
The public API accepts only profile ID/version, revision, and a server-derived
invalidation digest; assignments and infrastructure evidence remain
server-owned.

Optimizer calculation output and Deployer package/Terraform execution are active.
Flutter presentation remains the reviewed Phase 8.7 boundary.

## Extending The Deployment Graph

The Deployer does not generate Terraform or infer dependencies from source code.
To extend one reviewed profile:

1. register the deployment component, package artifact closure, ports,
   permissions, runtime/error/observability/cleanup contracts, and exact
   Terraform resource/variable/output symbols;
2. register every compatible logical-edge implementation, including direction,
   trust, transfer, delivery, cost, and any destination-owned support component;
3. update the provider implementation mapping and source-digest inventory;
4. regenerate architecture and Manifest v3 fixtures/copies;
5. add negative graph tests plus an offline package/tfvars path;
6. run `./thesis.sh test deployment-contract --focused`.

The graph uses exactly four stages: `package`, `preplan`, `terraform`, and
`postapply`. A separate apply stage requires a reviewed contract proving that a
direct Terraform output/reference cannot represent the dependency. Runtime code
must consume injected bindings; it may not reconstruct another component's name,
ARN, URL, topic, key, or handler from a naming convention.

Azure deserves one packaging-specific check: Terraform deploys aggregate Function
App bundles. Graph selection therefore produces only the selected L0/L1/L2/L3
aggregate bundles, and tfvars must reference the matching package evidence. AWS
and GCP retain per-function archives. User extensions remain immutable,
source-preserving packages bound to the registered `processor.telemetry@1` slot.
