---
title: "Phase 8.0: Current Graph Reconstruction"
description: "Implementation plan for a code-verified Function-and-Edge Matrix of the currently deployable Twin architecture."
tags: [architecture, inventory, graph, contracts, evidence, issue-144]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #144
- docs/plans/phase_08_architecture_profiles_eventing/HANDOFF.md
- docs/plans/resolved_deployment_specification/README.md
- 2-twin2clouds, twin2multicloud_backend, 3-cloud-deployer, and twin2multicloud_flutter current source trees
- docs/research/digital_twin_architecture_and_eventing_layer.md
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Phase 8.0: Current Graph Reconstruction

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#144 Inventory the current Twin deployment graph and Function-and-Edge Matrix](https://github.com/TVJunkie724/master-thesis/issues/144) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-current-graph` |
| Base branch | `master` |
| Blocked by | None |
| Produces | Required input for Phase 8.1 |
| Runtime behavior change | Forbidden |
| Live cloud E2E | Forbidden |

Every artifact, validation rule, test, documentation change, and Definition of
Done item in this plan is mandatory.

## 1. Outcome

Create a code-verified reconstruction of the currently deployable Twin graph.
The result must identify every logical responsibility, static or user function,
Terraform resource, package/template, deployment-time binding, runtime edge,
cross-cloud transition, trust boundary, observable signal, and cost owner for
AWS, Azure, GCP, and mixed-provider paths.

The output is evidence for later decisions. It must not describe the inherited
topology as approved merely because it exists.

## 2. Scope

This phase must inventory:

- Optimizer responsibilities, fixed slots, provider capabilities, formula
  ownership, deployment selections, transition runtimes, and six transfer
  edges;
- Management API fixed optimizer columns, calculation-run evidence,
  deployment-package projections, credential selection, simulator/test
  projections, and Flutter API read models;
- Deployer static/user function registry entries, provider templates, package
  builders, Terraform resources/data/outputs, environment bindings,
  dependencies, cleanup ownership, and executable-topology checks;
- current Flutter fixed-slot models, architecture widgets, configuration
  workspace, optimizer review, deployment review, and demo fixtures;
- all provider-specific and mixed-provider differences;
- discrepancies between paper layer numbering, historical L0 glue naming, the
  Optimizer's seven slots, and the Deployer's `Layer` enum.

## 3. Non-Goals

- No function, Terraform, Optimizer, API, database, or Flutter behavior change.
- No retain/replace/remove decision for an edge.
- No Eventing service comparison or provider selection.
- No architecture-profile runtime schema.
- No cleanup of legacy files or credentials.
- No real provider API, Terraform apply, destroy, or E2E execution.

## 4. Required Artifacts

Create:

```text
contracts/architecture-inventory/v1/
  current-graph.schema.json
  current-graph.json
  README.md
scripts/architecture_inventory/
  __init__.py
  canonical.py
  extractors.py
  checker.py
scripts/check_architecture_inventory.py
3-cloud-deployer/tests/unit/architecture_inventory/
  test_current_graph_contract.py
  test_current_graph_extractors.py
  test_current_graph_checker.py
docs/research/phase_08_current_function_edge_matrix.md
docs-site/docs/architecture/current-deployment-graph.md
```

`current-graph.json` is the machine-readable audit SSOT.
`phase_08_current_function_edge_matrix.md` adds audit interpretation,
unresolved evidence, predecessor debt, and Phase 8.1 decision inputs.
`current-deployment-graph.md` documents implemented behavior only and must not
contain future-profile claims.

## 5. Stable Identifier Rules

IDs must be lower-case ASCII and match
`^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$`.

Prefixes:

| Entity | Prefix | Example |
|---|---|---|
| Responsibility | `responsibility.` | `responsibility.ingestion` |
| Component | `component.` | `component.l2.processor-wrapper` |
| Runtime edge | `edge.runtime.` | `edge.runtime.dispatcher-to-processor-wrapper` |
| Deployment binding | `edge.binding.` | `edge.binding.processor-wrapper-target` |
| Terraform resource | `terraform.` | `terraform.aws.lambda.dispatcher` |
| Template/package | `artifact.` | `artifact.aws.dispatcher` |
| Cost owner | `cost.` | `cost.l1.ingestion` |
| Trust boundary | `trust.` | `trust.management-to-deployer` |

IDs describe stable responsibility or implementation identity, not generated
resource names. Provider variants share a logical component ID only if they
implement the same current responsibility and envelope; their provider
implementation IDs remain distinct.

## 6. Machine-Readable Contract

`current-graph.schema.json` must use JSON Schema Draft 2020-12,
`additionalProperties: false`, closed enums, bounded strings, unique arrays,
and deterministic ordering rules documented in `README.md`.

Top-level fields:

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | Constant `architecture-inventory.v1` |
| `inventory_id` | string | Constant `current-five-layer-implementation` |
| `source_commit` | string | Full Git SHA used as audit provenance |
| `audited_source_paths` | array | Exact repository-relative files/directories included in source drift |
| `audited_source_tree_digest` | string | SHA-256 of canonical path/content-digest pairs |
| `generated_at` | RFC 3339 | Audit metadata, excluded from content digest |
| `paper_model_references` | array | Repository-relative paper/provenance references |
| `responsibilities` | array | Stable logical responsibility records |
| `components` | array | Logical and provider implementation records |
| `artifacts` | array | Template/package/source records |
| `terraform_objects` | array | Resource/data/output/module records |
| `edges` | array | Runtime and deployment binding records |
| `fixed_assumptions` | array | Cross-project fixed-slot/name/config assumptions |
| `unresolved_findings` | array | Explicit evidence gaps |
| `content_digest` | string | SHA-256 of canonical inventory content excluding audit timestamp/digest |

`source_commit` records provenance but is not compared to `HEAD`, because the
inventory commit necessarily changes the repository commit. Drift enforcement
uses `audited_source_paths` and `audited_source_tree_digest`. The digest input
is a lexicographically sorted array of repository-relative path plus
SHA-256 content digest; it excludes this inventory, generated docs, Git
metadata, ignored files, credentials, runtime state, and caches.

### 6.1 Responsibility Record

Required fields:

- `responsibility_id`;
- `name`;
- `paper_layer_reference`;
- `optimizer_slot_ids`;
- `required_capability_ids`;
- `cost_owner_ids`;
- `description`;
- `source_references`.

`paper_layer_reference` is nullable only for implementation glue. Null must not
be rewritten as L0 or a new research layer.

### 6.2 Component Record

Required fields:

- `component_id`;
- `implementation_id`;
- `responsibility_id`;
- `provider`: `platform`, `aws`, `azure`, or `gcp`;
- `kind`: `api`, `function`, `workflow`, `storage`, `twin-service`,
  `visualization`, `bridge`, `scheduler`, or `user-extension`;
- `deployment_lifecycle`: `always`, `provider-selected`,
  `cross-provider-only`, `feature-gated`, or `unsupported`;
- `package_artifact_ids`;
- `terraform_object_ids`;
- `runtime_entrypoint`;
- `platform_owned_fields`;
- `user_owned_fields`;
- `required_permission_capabilities`;
- `observable_signals`;
- `source_references`.

An implementation record must never infer a package or Terraform object from a
name. Every relationship is an explicit ID reference.

### 6.3 Edge Record

Required fields:

| Field | Rule |
|---|---|
| `edge_id` | Stable unique ID |
| `source_component_id` / `destination_component_id` | Existing component IDs |
| `phase` | `deployment` or `runtime` |
| `edge_kind` | `in_process`, `http`, `provider_trigger`, `schedule`, `storage_lifecycle`, `queue`, `topic`, `workflow`, `terraform_reference`, `environment_binding`, or `package_binding` |
| `protocol` | Exact current protocol/trigger/reference mechanism |
| `payload_contract` | Schema/shape reference or explicit `untyped` finding |
| `invocation_semantics` | `synchronous`, `asynchronous`, `scheduled`, `lifecycle`, or `deployment_only` |
| `delivery_guarantee` | Current evidenced claim or `unknown` |
| `retry_policy` | Current evidenced behavior or `none`/`unknown` |
| `dead_letter_policy` | Current evidenced behavior or `none`/`unknown` |
| `idempotency_scope` | Current evidenced behavior or `none`/`unknown` |
| `ordering_scope` | Current evidenced behavior or `none`/`unknown` |
| `trust_boundary_id` | Explicit trust boundary |
| `authentication` | Current mechanism without secret values |
| `transfer_route_id` | Existing pricing route or null |
| `cost_owner_ids` | Every function, trigger, workflow, request, transfer, or storage owner |
| `observability` | Correlation, log, metric, and operation evidence |
| `reference_mechanism` | Output reference, environment value, duplicated name, constructed URL, etc. |
| `classification` | `baseline_required`, `implementation_internal`, `unsafe_debt`, or `eventing_candidate` |
| `evidence_status` | `verified`, `partial`, or `unresolved` |
| `source_references` | File and line-anchor evidence |

`unknown`, `partial`, and `unresolved` are visible findings, not defaults that
permit later implementation.

### 6.4 Fixed Assumption Record

Each assumption must state:

- stable ID;
- affected project(s);
- exact field/name/convention;
- current consumer(s);
- failure mode;
- whether an automated drift test exists;
- Phase 8 owner.

The list must include at least fixed `cheapest_l*` columns, Optimizer slot
order, `layer_*_provider` config keys, Terraform output suffixes, provider
template path/handler conventions, user-function paths, and fixed Flutter
architecture slots.

## 7. Evidence Standard

Each inventory row must have one of:

- direct source reference plus a focused test reference;
- direct source reference plus generated Terraform/package evidence;
- explicit `unresolved` status with a bounded finding.

Comments, README prose, historical HTML, and predecessor diagrams are context,
not proof. Runtime claims must be traced to executable code or tests.

Source references must be repository-relative and use an immutable symbol,
Terraform address, registry key, route name, or test name. Raw line numbers may
be included for review but are not the only locator.

## 8. Inventory Procedure

### Slice A: Optimizer

Must inspect:

- `2-twin2clouds/backend/calculation_v2/layers/contracts.py`;
- provider layer calculators;
- `path_optimizer.py`;
- `deployment_profiles.py`;
- `executable_topology.py`;
- `deployment_specification/builder.py`;
- pricing, formula, transfer, strategy, and capability registries;
- resolved-deployment contract fixtures and tests.

Must reconcile:

- seven optimization slots versus five scientific layers;
- six fixed transfer edges;
- two source-owned transition runtimes;
- cross-cloud glue cost ownership;
- provider/profile unsupported combinations;
- all emitted component/service/dimension identifiers.

### Slice B: Management API

Must inspect models, schemas, routes, services, migrations, and tests related to:

- `OptimizerConfiguration.cheapest_l*`;
- `CostCalculationRun` and result items;
- selected resolved deployment specification;
- deployment package/config projections;
- credential provider selection;
- simulator, verification, export, and read models;
- OpenAPI and Flutter-facing response shapes.

Every read/write consumer of a fixed layer field must appear in
`fixed_assumptions`.

### Slice C: Deployer And Terraform

Must inspect:

- `function_registry.py` and provider registry;
- static/user package builders;
- executable-topology and validation rules;
- all provider function/template directories;
- every Terraform `resource`, `data`, `output`, and local used for component
  binding;
- Terraform output policy, runtime outputs, operation packages, cleanup, and
  destroy behavior.

Use `python-hcl2` from `3-cloud-deployer/requirements-dev.txt` to parse HCL.
Do not build a regex-based Terraform parser.

### Slice D: Flutter And Demo

Must inspect:

- `ArchitecturePath`, optimizer/result/deployment specification models;
- architecture graph/service-map widgets;
- configuration journey and shell;
- Wizard BLoC state/events/helpers;
- Management API interface/adapter;
- demo fixture store and demo Management API;
- tests and supported-platform gates.

Every fixed slot, label, ordering assumption, and editable infrastructure field
must be listed.

### Slice E: Cross-Project Reconciliation

Must compare component, edge, provider, service, formula, package, Terraform,
API, and Flutter IDs. A row is `verified` only when every applicable project
agrees.

Mixed-provider scenarios must cover:

- L1 to L2;
- L2 to L3 hot;
- L3 hot to cool;
- L3 cool to archive;
- L3 hot to L4;
- L4 to L5;
- source-owned transition runtimes;
- destination-owned bridge/writer behavior.

## 9. Inventory Checker

`scripts/check_architecture_inventory.py` must:

1. validate `current-graph.json` against the schema;
2. verify canonical serialization and digest;
3. recompute and compare `audited_source_tree_digest`;
4. reject duplicate or unresolved referenced IDs;
5. load all `STATIC_FUNCTIONS`;
6. parse all Terraform files and collect resource/data/output addresses;
7. collect package/template directories and handlers through Deployer registry
   APIs rather than path-name guesses;
8. collect Optimizer slots, baseline edges, and deployment component IDs;
9. scan declared Management fixed-field consumers and Flutter fixed-slot
   models through explicit allowlisted source anchors;
10. fail when an extracted entity lacks a matrix row or a row points to a
   nonexistent source entity;
11. print only bounded IDs and source paths, never file contents or secrets.

An allowlist entry must contain an owner, rationale, and expiry phase. Empty
catch-all allowlists are forbidden.

## 10. Diagrams

The research document must include:

- predecessor/paper model;
- current logical responsibility graph;
- current deployment/package binding graph;
- provider-specific AWS/Azure/GCP runtime graphs;
- one representative mixed-provider graph;
- trust/credential boundaries;
- cost and transfer ownership overlay.

Use Mermaid for navigable relationships and retain a concise ASCII equivalent
for long-term plain-text readability. Diagrams must be generated or checked
against the matrix IDs; hand-drawn labels must not silently diverge.

## 11. Failure Handling And Security

- The checker fails with stable categories:
  `SCHEMA_INVALID`, `DIGEST_MISMATCH`, `DUPLICATE_ID`,
  `REFERENCE_UNRESOLVED`, `SOURCE_ENTITY_UNMAPPED`,
  `MATRIX_ENTITY_STALE`, or `EVIDENCE_INCOMPLETE`.
- Output lists at most 100 findings and gives a total count.
- The inventory stores no source content, user payload, account ID, resource
  instance name, endpoint, token, credential path, or secret.
- Ignored credential files and runtime workspaces must not be traversed.
- Provider claims without code evidence remain `unresolved`.

## 12. Test And Verification Plan

Add focused tests for:

- positive schema fixture;
- every missing required field and additional property;
- duplicate IDs and broken references;
- canonical digest stability and mutation;
- audited source-tree digest stability and relevant/irrelevant path mutation;
- complete function registry extraction;
- HCL resource/data/output extraction;
- package/template inventory;
- Optimizer slot/edge/component inventory;
- stale and missing matrix rows;
- secret-like key/path rejection;
- deterministic diagram ID extraction where implemented.

Safe verification:

```bash
python scripts/check_architecture_inventory.py
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/unit/architecture_inventory/ -v
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/ --ignore=tests/e2e -v
cd twin2multicloud_flutter
flutter analyze
flutter test
docker compose --profile docs run --rm docs mkdocs build --strict
```

The builder must resolve current container names and run commands directly.
No provider credentials or live resources are needed.

## 13. Documentation

- Add the implemented current graph page to the Architecture section of
  `docs-site/mkdocs.yml`.
- Link the research matrix from this plan and from the Phase 8 roadmap, not from
  ordinary user setup pages.
- Update `docs-site/docs/architecture/refactoring-roadmap.md` with Phase 8.0
  status and issue title, never only `#144`.
- Update #144 with artifact links, checker output, unresolved finding count,
  and verification evidence.

## 14. Rollback And Compatibility

This phase changes no runtime contract or persistence. Rollback consists of
removing the new inventory artifacts and checker. No migration or data rollback
is permitted or required.

The source tree digest freezes what was audited. If a covered source file
changes before Phase 8.1, the checker must fail until the inventory is
regenerated and reviewed. A docs-only or inventory-only commit must not create
false drift.

## 15. Definition Of Done

- [ ] The JSON Schema and canonical `current-graph.json` are committed.
- [ ] Every Optimizer slot, baseline edge, transition runtime, and emitted
      deployment component is represented.
- [ ] Every Management fixed-field consumer and API/DB projection is listed.
- [ ] Every Deployer static/user function, package/template, Terraform object,
      output, and binding is represented.
- [ ] Every Flutter fixed-slot and architecture presentation assumption is
      represented.
- [ ] AWS, Azure, GCP, and required mixed-provider paths reconcile across
      projects.
- [ ] Every edge records semantics, delivery, trust, transfer, cost,
      observability, reference mechanism, classification, and evidence status.
- [ ] Paper, historical L0, five scientific layers, and seven Optimizer slots
      are clearly distinguished.
- [ ] The checker detects missing and stale entities without reading secrets.
- [ ] Research and current-product diagrams are complete and context-correct.
- [ ] Focused checker tests and all relevant safe project suites pass.
- [ ] Strict MkDocs succeeds.
- [ ] No runtime behavior, database data, Terraform state, or cloud resource is
      changed.
- [ ] Two reviews find no unresolved plan/implementation issue.
- [ ] Roadmap and #144 are updated with named evidence.
- [ ] The structured commit references #144.
