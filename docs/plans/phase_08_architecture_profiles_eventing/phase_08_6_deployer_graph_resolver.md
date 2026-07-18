---
title: "Phase 8.6: Deployer Graph Resolver And Staged Binding Preflight"
description: "Implementation plan for deterministic graph resolution, package binding, and fail-closed Terraform preflight."
tags: [architecture, deployer, graph, manifest, terraform, preflight, issue-152]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #152
- Phase 8.2 architecture contracts
- Phase 8.3 deployment component catalog
- Phase 8.5 ResolvedTwinArchitecture output
- contracts/deployment-manifest and contracts/resolved-deployment-specification
- Current Deployer package, operation-state, Terraform, logging, and ephemeral-workspace boundaries
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Phase 8.6: Deployer Graph Resolver And Staged Binding Preflight

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#152 Build the Deployer graph resolver and staged binding preflight](https://github.com/TVJunkie724/master-thesis/issues/152) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-deployer-graph-resolver` |
| Base branch | `master` |
| Blocked by | Phase 8.5 / #151 |
| Produces | Executable profile-driven baseline for Flutter and Eventing gate |
| Live cloud E2E | Forbidden |

All graph, manifest, binding, package, Terraform, state, error, security, and
compatibility requirements in this plan are mandatory.

## 1. Outcome

The Deployer must validate one immutable resolved architecture and convert it
into one deterministic `ResolvedDeploymentGraph` before Terraform.

Every component, package, extension artifact, input, output, dependency,
provider boundary, permission, configuration value, and Terraform symbol must
resolve through the registered catalog. Missing, duplicate, incompatible,
unauthorized, stale, or illegal cyclic bindings fail before `terraform plan`.

Functions and user code must not construct another component's resource name,
ARN, URL, topic, key, handler, or endpoint.

### Scope Boundary

| Included | Excluded |
|---|---|
| DeploymentManifest v3, deterministic graph resolution, typed bindings/stages, package selection, tfvars translation, symbol preflight, operation lifecycle, compatibility, errors, security, and offline Terraform gates | Eventing components/profile, arbitrary graph authoring, dynamic Terraform generation, new cost decisions, Flutter workflow, and live provider plan/apply/destroy |

## 2. DeploymentManifest v3

Create a versioned repository contract:

```text
contracts/deployment-manifest/v3/
  schema.json
  fixtures/
    valid/
      all-aws.json
      all-azure.json
      mixed-providers.json
    invalid/
scripts/sync_deployment_manifest_contract.py
scripts/tests/test_deployment_manifest_contract_sync.py
twin2multicloud_backend/src/contracts/generated/deployment-manifest/
3-cloud-deployer/src/contracts/generated/deployment-manifest/
```

`scripts/sync_deployment_manifest_contract.py` must validate fixtures,
canonicalize the source directory, write byte-identical generated copies and
`.contract-sha256` markers, and support `--check`. The existing
`.github/workflows/deployment-contract.yml` must trigger on the source,
sync/tests, and generated-copy paths.

Manifest v3 required fields:

| Field | Rule |
|---|---|
| `manifest_version` | Constant `3.0` |
| `generated_at` / `producer` | Audit metadata |
| `package` | Existing file/secret-bearing-file metadata |
| `twin` | Opaque ID, name, resource-name projection |
| `calculation_run_id` | Must match both resolved contracts |
| `resolved_twin_architecture_digest` | Exact architecture digest |
| `resolved_twin_architecture` | Full secret-free canonical v1 contract |
| `resolved_deployment_specification_digest` | Exact specification digest |
| `resolved_deployment_specification` | Full v1 contract |
| `credentials` | Existing sources/providers plus `contains_secret_payloads: false` |
| `compatibility` | Catalog/resolver/package/Terraform contract versions |

For baseline transition only, `providers` may remain as a derived
`layer_*_provider` compatibility map. The Deployer must recompute it from
architecture assignments and reject any difference. It is never an independent
input.

Manifest v2 remains readable for historical inspection and destroy of frozen
operations. New deploy/redeploy/verify/package operations require v3 after the
activation flag is enabled. There is no fallback from invalid v3 to v2.

## 3. Resolved Deployment Graph

Add:

```text
3-cloud-deployer/src/architecture_profiles/
  graph_models.py
  graph_resolver.py
  binding_resolver.py
  stage_planner.py
  graph_evidence.py
```

The internal immutable graph contains:

### 3.1 Graph Metadata

- graph schema version `resolved-deployment-graph.v1`;
- graph ID derived deterministically from architecture/catalog digests;
- calculation run/profile/catalog/specification refs;
- ordered nodes, edges, stages, and compatibility data;
- content digest.

### 3.2 Node

- graph node ID;
- architecture assignment ID;
- logical and deployment component IDs/versions;
- provider, service, region;
- package artifact and package digest;
- Terraform resource addresses;
- typed configuration/deployment-dimension bindings;
- extension artifact refs;
- input/output port declarations;
- permission/error/observability/cleanup refs;
- lifecycle stage IDs.

### 3.3 Edge

- graph edge and resolved architecture edge IDs;
- source/destination node and port IDs;
- catalog edge implementation ID/version;
- binding mechanism;
- payload/envelope, delivery, trust, transfer, cost, and observability refs;
- resolution stage;
- Terraform dependency/output/input symbols;
- sensitivity classification.

### 3.4 Stage

The baseline uses:

1. `package`: validate/build deterministic static and user artifacts;
2. `preplan`: resolve all static values, deployment dimensions, and symbolic
   Terraform references;
3. `terraform`: execute one explicit root-module plan/apply whose native HCL
   dependency graph resolves resource outputs;
4. `postapply`: collect allowlisted runtime outputs and verify deployed
   operation evidence.

Do not split one Terraform root into provider-by-provider applies merely to
simulate dynamism. Add a separate apply stage only when a reviewed component
contract proves that a value cannot be represented by a Terraform reference.
No such stage exists in baseline v1 by default.

## 4. Graph Resolution Algorithm

Execute before side effects:

1. validate Manifest v3 size, schema, secret scan, and version;
2. validate both resolved contracts and digests;
3. verify run/profile/specification/catalog cross-links;
4. load exact provider profiles and component catalog by pinned digest;
5. build one node for every architecture component assignment;
6. resolve every node's package, Terraform, deployment dimension, runtime,
   permission, error, observability, cleanup, and extension contract;
7. build one graph edge for every resolved logical edge;
8. resolve every declared input to exactly one compatible output,
   platform-owned constant, deployment dimension, extension artifact, or
   approved platform runtime secret reference;
9. reject undeclared or multiply bound inputs/outputs;
10. validate provider/region/trust/transfer constraints;
11. validate graph cycles against the profile's graph policy;
12. topologically order acyclic nodes; collapse only explicitly allowlisted
    workflow cycle groups;
13. construct package/preplan/terraform/postapply stages;
14. calculate deterministic graph digest and evidence;
15. only then create packages, tfvars, or invoke Terraform.

The resolver must not inspect user source to infer dependencies.

## 5. Binding Types

Closed v1 binding kinds:

- `catalog_constant`;
- `deployment_dimension`;
- `component_output`;
- `platform_configuration`;
- `extension_artifact`;
- `platform_runtime_secret_reference`.

Each binding requires:

- stable binding ID;
- source kind/ID and destination node/input port;
- value type and sensitivity;
- resolution stage;
- validator/transformer ID;
- compatibility version.

Transformers may normalize a typed value into an allowlisted Terraform shape.
They may not create resource identifiers from naming patterns.

Sensitive binding values are resolved only in the operation workspace and are
excluded from graph/manifest/evidence digests. Secret reference metadata may be
present only for platform-owned runtime/provider bindings; values may not. The
#113 user-function v1 contract cannot create this binding kind.

## 6. Package Pipeline

Modify:

- `3-cloud-deployer/src/providers/terraform/package_builder.py`;
- provider package builders;
- `operation_packages.py`;
- user package adapter from #113.

Package builders must consume graph nodes rather than provider/layer string
lists. They must:

- build only catalog-selected artifacts;
- verify source and builder versions/digests;
- bind immutable extension artifacts to declared slots;
- preserve deterministic ZIP content/order/mode/timestamp;
- write package evidence without source/secret content;
- fail on an unregistered template, handler, shared library, or extra package;
- preserve private operation package permissions and TTL cleanup.

## 7. Terraform Input Generation

Refactor `tfvars_generator.py` into:

```text
3-cloud-deployer/src/terraform_inputs/
  models.py
  graph_translator.py
  compatibility_projection.py
  serializer.py
```

The translator:

- consumes validated graph nodes/bindings and deployment specification;
- emits only variables allowlisted by catalog Terraform bindings;
- verifies type, enum, range, sensitivity, and owner;
- derives current `layer_*_provider` values only for baseline HCL
  compatibility;
- rejects unknown/extra variables;
- emits deterministic JSON;
- excludes secret values from evidence and logs.

Terraform HCL must use direct resource/output references for cross-component
values wherever possible. The catalog/checker must fail if a function
environment value is assembled from a duplicate resource-name convention.

## 8. Operation State And Retry

Extend persisted operation metadata with:

- architecture and graph digests;
- profile/catalog versions;
- completed stage;
- Terraform plan/apply identifiers already retained by current lifecycle;
- bounded graph validation result.

Retry/recovery rules:

- a retry may resume only when manifest, architecture, specification, graph,
  catalog, and package digests match;
- validation/package/preplan may rerun deterministically;
- Terraform lifecycle continues to use the existing persisted state and lock
  safeguards;
- changed digests require a new operation, never an in-place resume;
- destroy uses frozen operation/profile/catalog evidence, not the latest
  profile definitions.

## 9. Management API Package Integration

Modify:

- `twin2multicloud_backend/src/services/deployment_service.py`;
- deployment package/build/orchestration tests;
- Deployer client manifest staging validation.

Management must:

- load the selected run's immutable architecture and specification;
- verify matching profile/catalog/run/digests;
- build Manifest v3;
- derive compatibility provider config from architecture assignments;
- materialize only server-owned config and immutable user artifacts;
- stage the existing one-shot secret-bearing operation package;
- reject legacy/non-resolvable/incomplete architecture before upload.

It must stop writing provider choices from `OptimizerConfiguration.cheapest_l*`
into executable packages. Fixed fields remain historical projections only.

## 10. Failure Contract

Stable codes:

- `DEPLOYMENT_MANIFEST_VERSION_UNSUPPORTED`
- `DEPLOYMENT_ARCHITECTURE_MISSING`
- `DEPLOYMENT_ARCHITECTURE_INVALID`
- `DEPLOYMENT_ARCHITECTURE_DIGEST_MISMATCH`
- `DEPLOYMENT_ARCHITECTURE_SPEC_MISMATCH`
- `DEPLOYMENT_PROFILE_CATALOG_MISMATCH`
- `DEPLOYMENT_GRAPH_NODE_UNRESOLVED`
- `DEPLOYMENT_GRAPH_EDGE_UNRESOLVED`
- `DEPLOYMENT_GRAPH_BINDING_MISSING`
- `DEPLOYMENT_GRAPH_BINDING_DUPLICATE`
- `DEPLOYMENT_GRAPH_BINDING_INCOMPATIBLE`
- `DEPLOYMENT_GRAPH_CYCLE_FORBIDDEN`
- `DEPLOYMENT_PACKAGE_CATALOG_MISMATCH`
- `DEPLOYMENT_TERRAFORM_BINDING_INVALID`
- `DEPLOYMENT_GRAPH_RESUME_MISMATCH`

All errors include safe field/component/edge/binding IDs and correlation ID.
They do not include source, credentials, secret refs beyond opaque IDs,
physical resource values, provider responses, tfvars content, or tracebacks.

## 11. Implementation Slices

### Slice A: Manifest v3

Must add schema, sync/drift fixtures, Management writer, Deployer reader, v2
historical compatibility, and strict activation rules.

### Slice B: Graph Resolver

Must implement typed graph models, node/edge/binding resolution, graph policy,
deterministic ordering/digest, and negative validation.

### Slice C: Package Integration

Must switch static and user package selection to catalog graph nodes and prove
deterministic package evidence.

### Slice D: Terraform Translation

Must replace executable fixed-field/provider-list ownership with graph-based
allowlisted inputs and HCL symbol verification.

### Slice E: Operation Lifecycle

Must bind graph digests/stages to operation state, retry, recovery, destroy,
logging, and cleanup.

### Slice F: Cross-Stack Offline Gate

Must prove all-AWS, all-Azure, mixed-provider, unsupported, invalid binding,
package, and Terraform mock-plan fixtures from Optimizer output through
Deployer inputs without live credentials.

## 12. Tests And Verification

### Manifest/Graph

- every missing/extra/tampered manifest field;
- architecture/spec/run/profile/catalog mismatch;
- missing/duplicate/incompatible node, edge, port, and binding;
- forbidden and allowlisted cycles;
- deterministic node/edge/stage order and digest;
- derived provider config equality and tamper rejection;
- bounded/redacted errors.

### Package/Security

- selected artifacts only;
- missing/extra/stale template or handler;
- deterministic package bytes/digests;
- immutable user artifact binding;
- no source rewrite;
- operation package ownership, one-shot acquire, TTL, permissions, and cleanup;
- secret value absent from manifest, graph, evidence, logs, and test snapshots.

### Terraform

- every catalog resource/variable/output exists;
- exact type/range/enum binding;
- unknown/extra tfvars rejected;
- all 50 current target bindings and 27 storage paths remain drift-gated;
- direct HCL references replace duplicated cross-resource name construction;
- `terraform fmt`, `validate`, native tests, and offline mock plans for all
  approved baseline fixtures.

### Lifecycle/Management

- selected native architecture required;
- fixed fields cannot affect executable package;
- retry with same digests and rejection with changed digest;
- destroy from frozen evidence;
- atomic operation state and safe error mapping;
- no fallback to Manifest v2 for new deploy/redeploy.

Safe verification:

```bash
python scripts/sync_architecture_profile_contracts.py --check
python scripts/sync_deployment_manifest_contract.py --check
python scripts/check_architecture_inventory.py
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/ --ignore=tests/e2e -v
./thesis.sh test deployment-contract
```

The deployment-contract gate may run Terraform validate/native mock plans only.
No apply, destroy, provider credential, or real resource is permitted.

## 13. Security And Observability

- Manifest/graph canonical payloads are bounded in bytes, depth, nodes, edges,
  bindings, and errors.
- Registry paths and Terraform symbols are repository-owned.
- The resolver never fetches schemas/catalogs from the network.
- Structured logs include operation/run/profile/catalog/graph digests, stage,
  node/edge counts, duration, safe error code, and correlation ID.
- Operation evidence includes graph summary/digest, not full payloads or
  secrets.
- Existing redaction, ephemeral workspaces, runtime-state ownership, locks,
  cancellation, and cleanup guarantees must remain intact.

## 14. Documentation

Update:

- `docs-site/docs/contracts-and-data-flow/deployment-lifecycle.md`;
- `docs-site/docs/contracts-and-data-flow/contract-map.md`;
- Deployer developer docs for graph, bindings, stages, package/catalog, HCL,
  retry, and extension procedure;
- Management package/orchestration docs;
- troubleshooting for stable graph/manifest errors;
- architecture roadmap and #152 with graph/package/Terraform evidence.

Current docs must distinguish Manifest v2 historical support from v3 required
new operations. Do not claim Eventing support. Do not edit LaTeX.

## 15. Rollout And Rollback

Rollout:

1. ship v3 readers/writers dark;
2. run cross-stack no-apply gates;
3. enable v3 for new deployments;
4. keep v2 historical read/destroy support;
5. monitor graph/preflight codes;
6. remove executable reads of fixed provider fields.

Rollback disables new deployment creation rather than silently using v2 or
fixed fields. Existing v3 operations remain inspectable/destroyable using
frozen evidence.

## 16. Definition Of Done

- [ ] Manifest v3 carries matching immutable architecture and deployment
      specification contracts.
- [ ] Every architecture component/edge becomes one deterministic graph
      node/edge with explicit catalog ownership.
- [ ] Every required input resolves exactly once from an approved binding.
- [ ] Forbidden cycles, missing/incompatible/unauthorized bindings, and stale
      catalogs fail before package or Terraform side effects.
- [ ] Package builders consume graph nodes and remain deterministic.
- [ ] Terraform inputs are typed, allowlisted, graph-derived, and symbol-checked.
- [ ] No domain/user function constructs another component's identity.
- [ ] Fixed `cheapest_l*` fields cannot influence a new executable package.
- [ ] Retry, recovery, destroy, state, logs, redaction, and ephemeral cleanup
      are bound to frozen graph evidence.
- [ ] v2 remains historical only; invalid v3 never falls back.
- [ ] All-AWS, all-Azure, mixed, unsupported, negative graph/package, and
      offline Terraform fixtures pass.
- [ ] Full safe Management and Deployer suites plus deployment drift pass.
- [ ] No live provider API, credentials, apply, destroy, or E2E runs.
- [ ] Product/developer docs, roadmap, and #152 are updated.
- [ ] Two reviews find no unresolved issue.
- [ ] The structured commit references #152.
