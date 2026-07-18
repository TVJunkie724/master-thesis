---
title: "Phase 8.2: Versioned Architecture Profile Contracts"
description: "Implementation plan for shared closed-world architecture, provider implementation, component catalog, and resolved architecture contracts."
tags: [architecture, contracts, json-schema, versioning, drift-gate, issue-149]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #149
- Phase 8.1 five-layer-baseline@1 decision contract
- docs/plans/resolved_deployment_specification/README.md
- contracts/resolved-deployment-specification
- Existing cross-project contract synchronization and drift-gate patterns
- User-approved ArchitectureProfile, ProviderImplementationProfile, DeploymentComponentCatalog, and ResolvedTwinArchitecture model
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Phase 8.2: Versioned Architecture Profile Contracts

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#149 Define versioned architecture profile contracts](https://github.com/TVJunkie724/master-thesis/issues/149) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-profile-contracts` |
| Base branch | `master` |
| Blocked by | Phase 8.1 / #139 |
| Produces | Shared contracts consumed by Phases 8.3-8.10 |
| Runtime behavior change | Contract readers only; no profile selection or deployment change |
| Live cloud E2E | Forbidden |

All four contracts, semantic validators, generated service copies, fixtures,
error codes, and drift gates are mandatory.

## 1. Outcome

Define and distribute four provider-neutral, versioned contracts:

```text
ArchitectureProfile
ProviderImplementationProfile
DeploymentComponentCatalog
ResolvedTwinArchitecture
```

The contracts must make logical architecture, provider implementation,
deployable component metadata, and one immutable resolved Twin instance
separate and traceable. Runtime users select reviewed profile IDs; they cannot
author arbitrary nodes, edges, services, Terraform values, or physical
resource bindings.

### Scope Boundary

| Included | Excluded |
|---|---|
| Draft 2020-12 schemas, semantic validators, canonicalization/digests, positive/negative fixtures, generated project readers, and drift gates | Concrete provider catalog population, DB/API migration, candidate optimization, package/Terraform execution, Flutter workflow, Eventing provider selection, and live provider execution |

## 2. Contract Layout

Create the repository SSOT:

```text
contracts/architecture-profiles/v1/
  architecture-profile.schema.json
  provider-implementation-profile.schema.json
  deployment-component-catalog.schema.json
  resolved-twin-architecture.schema.json
  semantic-registry.schema.json
  semantic-registry.json
  fixtures/
    valid/
      five-layer-baseline-profile.json
      aws-baseline-provider-profile.json
      baseline-component-catalog.json
      mixed-baseline-resolved-architecture.json
    invalid/
      unknown-version.json
      duplicate-id.json
      unresolved-reference.json
      illegal-cycle.json
      capability-mismatch.json
      secret-like-field.json
      digest-tamper.json
```

Distribute byte-identical generated copies to:

```text
2-twin2clouds/backend/contracts/generated/architecture-profiles/
twin2multicloud_backend/src/contracts/generated/architecture-profiles/
3-cloud-deployer/src/contracts/generated/architecture-profiles/
```

Flutter consumes typed Management API DTOs in Phase 8.7; it does not receive a
raw contract directory.

Add:

```text
scripts/sync_architecture_profile_contracts.py
scripts/tests/test_architecture_profile_contract_sync.py
.github/workflows/deployment-contract.yml
```

The sync script must validate, canonicalize, calculate a source-directory
digest, write `.contract-sha256` markers, support `--check`, and reject stale
generated files. The existing deployment-contract workflow must trigger for
the root contract, sync/check scripts, and every generated service copy.

## 3. Common Contract Rules

- JSON Schema Draft 2020-12.
- `additionalProperties: false` for every object.
- Stable IDs match
  `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$`.
- Versions are positive integer strings.
- Providers are `aws`, `azure`, or `gcp`.
- Currency is ISO 4217; v1 calculation fixtures use `USD`.
- Timestamps are RFC 3339 UTC and excluded from content digests.
- Monetary values and calculated quantities use canonical decimal strings, not
  binary JSON floats.
- Arrays representing sets are unique and lexicographically sorted by stable
  ID before hashing.
- Canonical JSON is UTF-8, keys sorted recursively, no insignificant
  whitespace, no NaN/Infinity, normalized decimal strings, and no Unicode
  normalization-dependent identifiers.
- Digests use `sha256:<64 lowercase hex>`.
- `$ref` is allowed only within the repository contract bundle; remote schema
  fetching is forbidden.
- Unknown schema/profile/catalog/component versions fail closed.
- Secret-like field names and known credential shapes are forbidden in
  profiles, catalogs, fixtures, and resolutions.

## 4. `ArchitectureProfile` v1

Purpose: define the reviewed logical Twin architecture independently from cloud
services and Terraform.

Required top-level fields:

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | Constant `architecture-profile.v1` |
| `profile_id` | string | Stable ID, for example `five-layer-baseline` |
| `profile_version` | string | Positive integer string |
| `lifecycle_status` | enum | `draft`, `active`, `deprecated`, `retired` |
| `display_name` | string | Bounded user-facing name |
| `description` | string | Functional purpose, not thesis conclusion |
| `workload_contract_ref` | versioned ref | One supported workload contract |
| `optimization_bundle` | object | Coupled strategy/calculation/formula refs |
| `responsibilities` | array | Required logical responsibility records |
| `components` | array | Required logical component records |
| `edges` | array | Required logical edge records |
| `extension_slots` | array | Approved user-function slot references |
| `graph_policy` | object | Cycle and optionality policy |
| `compatibility` | object | Supported contract versions |
| `content_digest` | string | Deterministic digest |

### 4.1 Optimization Bundle

Required fields:

- `optimization_strategy_id` and `optimization_strategy_version`;
- `calculation_strategy_id` and `calculation_strategy_version`;
- `formula_set_id` and `formula_set_version`;
- `scoring_strategy_id` and `scoring_strategy_version`;
- `pricing_registry_id` and compatible version range;
- `deployment_specification_versions`;
- `compatibility_digest`.

The semantic validator must reject a bundle whose strategy, formulas, workload,
or deployment specification are not mutually declared as compatible. This is
the required coupling between optimization type, calculation model, and
formula set.

### 4.2 Responsibility

Required fields:

- `responsibility_id`;
- `display_name`;
- `required`: constant `true` for v1 profiles;
- `capability_requirements`;
- `workload_field_refs`;
- `cost_category_ids`;
- `logical_component_ids`;
- `evaluation_order`.

`evaluation_order` is deterministic processing order, not proof of a linear
runtime topology.

### 4.3 Logical Component

Required fields:

- `component_id`;
- `responsibility_id`;
- `component_kind`;
- `required`: constant `true`;
- `required_capability_ids`;
- `input_port_ids`;
- `output_port_ids`;
- `extension_slot_ids`;
- `cost_owner_ids`;
- `observability_contract_id`.

Ports are stable logical contracts. They contain schema/envelope references and
semantics, never provider endpoint values.

### 4.4 Logical Edge

Required fields:

- `edge_id`;
- `source_component_id` and `source_port_id`;
- `destination_component_id` and `destination_port_id`;
- `edge_contract_id` and version;
- `required`: constant `true`;
- `delivery_requirements`;
- `trust_requirements`;
- `observability_requirements`;
- `transfer_workload_ref`;
- `cost_owner_ids`.

`delivery_requirements` explicitly states sync/async, timeout, retry,
dead-letter, idempotency, ordering, and replay requirements using closed enums.

### 4.5 Graph Policy

Required fields:

- `cycle_policy`: `acyclic` or `allowlisted`;
- `allowed_cycle_ids`;
- `optional_components`: empty for both thesis profiles unless a later profile
  version explicitly changes this;
- `user_topology_editable`: constant `false`.

For `acyclic`, `allowed_cycle_ids` must be empty. For `allowlisted`, every
strongly connected component must have a stable cycle ID and explicit workflow
semantics.

## 5. `ProviderImplementationProfile` v1

Purpose: declare how one provider implements one logical profile version.

Required fields:

| Field | Rule |
|---|---|
| `schema_version` | Constant `provider-implementation-profile.v1` |
| `implementation_profile_id` / `implementation_profile_version` | Stable versioned identity |
| `architecture_profile_ref` | Profile ID, version, and digest |
| `provider` | `aws`, `azure`, or `gcp` |
| `lifecycle_status` | Draft/active/deprecated/retired |
| `region_policy_ref` | Supported deployment/pricing region rules |
| `permission_set_ref` | Versioned permission capability set |
| `component_mappings` | Logical component to catalog component options |
| `edge_mappings` | Logical edge to catalog edge mechanism options |
| `capability_claims` | Required/extra/missing capability evidence |
| `unsupported_reasons` | Stable fail-closed reasons |
| `compatibility` | Catalog, resolver, runtime, and deployment versions |
| `content_digest` | Deterministic digest |

Each component mapping contains:

- logical `component_id`;
- one or more ordered `deployment_component_id` candidates;
- exact required capability coverage;
- service model and formula references;
- supported region constraints;
- deployment-specification component/slot compatibility.

Each edge mapping contains:

- logical `edge_id`;
- `edge_implementation_id`;
- source/destination deployment component constraints;
- mechanism;
- required catalog input/output port IDs;
- transfer route class;
- cost owner IDs.

`supported` cannot be inferred from an empty missing-capability list. It is a
derived semantic validation result requiring complete component, edge,
pricing/formula, permission, package, and deployment coverage.

## 6. `DeploymentComponentCatalog` v1

Purpose: register explicit deployable implementation units. A Terraform module
or resource is implementation metadata, not a logical layer.

Required top-level fields:

- `schema_version`: `deployment-component-catalog.v1`;
- `catalog_id` and `catalog_version`;
- `lifecycle_status`;
- `components`;
- `edge_implementations`;
- `package_artifacts`;
- `compatibility`;
- `content_digest`.

### 6.1 Component Entry

Required fields:

- `deployment_component_id` and `component_version`;
- `provider`;
- `logical_component_ids`;
- `service_id`;
- `component_kind`;
- `package_artifact_ref`;
- `terraform_binding`;
- `runtime_contract`;
- `configuration_schema_ref`;
- `input_ports`;
- `output_ports`;
- `required_permission_capabilities`;
- `pricing_model_refs`;
- `formula_refs`;
- `deployment_specification_bindings`;
- `extension_slot_refs`;
- `error_contract_ref`;
- `observability_contract_ref`;
- `cleanup_contract_ref`;
- `compatibility`.

`terraform_binding` contains explicit Terraform resource/module addresses,
allowlisted input variable IDs, output IDs, sensitive flags, and dependency
keys. It contains no runtime resource name.

`runtime_contract` contains the provider runtime ID, platform handler adapter,
timeout/memory bounds, trigger adapter, and package layout ID. User code cannot
override it.

### 6.2 Ports

Input and output ports require:

- stable `port_id`;
- JSON schema/envelope reference;
- value type and sensitivity;
- cardinality;
- producer/consumer phase;
- resolution stage;
- compatibility version.

Sensitive outputs may be referenced by ID but must never appear in catalog
fixtures or resolved architecture payloads.

### 6.3 Package Artifact

Required fields:

- `artifact_id` and version;
- repository-relative template/package source;
- platform handler;
- deterministic source/package digest policy;
- included/excluded path rules;
- builder adapter ID;
- supported runtimes;
- user-source policy;
- compatibility.

## 7. `ResolvedTwinArchitecture` v1

Purpose: represent one immutable, complete resolution for one optimizer run.

Required top-level fields:

| Field | Rule |
|---|---|
| `schema_version` | Constant `resolved-twin-architecture.v1` |
| `resolution_id` | Deterministic UUIDv5 generated by the Optimizer |
| `calculation_run_id` | UUID supplied by the Management API |
| `architecture_profile_ref` | ID, version, digest |
| `optimization_bundle_ref` | IDs, versions, compatibility digest |
| `provider_profile_refs` | Every provider profile used |
| `workload_contract_ref` | ID, version, digest |
| `pricing_evidence_refs` | Frozen catalog/evidence references |
| `component_assignments` | Complete logical-to-deployment assignments |
| `resolved_edges` | Complete logical-to-implementation edges |
| `extension_bindings` | Required slot plus immutable artifact reference |
| `deployment_specification_ref` | Version, digest, calculation-run ID |
| `cost_summary` | Layer/component/edge totals and currency |
| `functional_completeness` | Verified capabilities and gate result |
| `content_digest` | Deterministic digest |

`resolution_id` is UUIDv5 over the canonical tuple
`calculation_run_id`, architecture profile digest, optimization bundle digest,
and the canonical component/edge assignment payload. Replaying the same frozen
run inputs produces the same ID. `content_digest` covers every field except
itself and audit timestamps.

### 7.1 Component Assignment

Required fields:

- `assignment_id`;
- `responsibility_id`;
- `logical_component_id`;
- `provider`;
- `provider_implementation_profile_ref`;
- `deployment_component_id` and version;
- `service_id`;
- `region`;
- `capability_evidence`;
- `pricing_model_refs`;
- `formula_refs`;
- `deployment_specification_component_ids`;
- `cost_contribution`;
- `required`: constant `true`.

### 7.2 Resolved Edge

Required fields:

- `resolved_edge_id`;
- logical `edge_id`;
- source/destination assignment IDs and port IDs;
- `edge_implementation_id`;
- mechanism and delivery semantics;
- transfer route/evidence/formula references;
- cost contribution;
- trust/observability contract refs;
- declared deployment input/output binding IDs.

Physical names, URLs, ARNs, topics, keys, and Terraform values are absent. The
Deployer resolves them later from catalog-declared outputs.

### 7.3 Extension Binding

Required fields:

- `slot_id` and version;
- `artifact_id` and immutable digest;
- logical component ID;
- configuration digest;
- validation contract version.

No source, user-managed secret reference, or secret value is included. The v1
user-function contract is non-secret configuration only.

### 7.4 Functional Completeness

Required fields:

- `status`: constant `complete` for a successful resolution;
- sorted required/provided capability IDs;
- sorted provider-extra capability IDs;
- zero missing capability IDs;
- validator version;
- validation digest.

The schema may represent rejected candidates only in a separate diagnostic
contract. A publishable `ResolvedTwinArchitecture` can never have status
`partial`.

## 8. Compatibility With Existing Deployment Specification

`ResolvedDeploymentSpecification v1` remains unchanged in this phase:

- it is valid only for `five-layer-baseline@1`;
- its fixed slot enum cannot represent Eventing;
- its component/dimension values remain the deployment-dimension SSOT;
- `ResolvedTwinArchitecture` references its version/digest/component IDs and
  does not duplicate dimensions.

Phase 8.9 must introduce `ResolvedDeploymentSpecification v2` before Eventing
can become deployable. It must preserve v1 read support and must not add an
Eventing value to the closed v1 enum.

## 9. Field Ownership

| Author | Allowed fields |
|---|---|
| Repository developers | Profile, provider profile, catalog definitions |
| Optimizer | Resolution ID, assignments, resolved edges, completeness, cost/evidence/spec refs, digest |
| Management API | Calculation run ID input, ownership, immutable persistence, selection timestamps |
| Deployer | Validation result, physical output resolution, operation evidence; never mutates resolution |
| Flutter | Profile selection request and allowed workload/user artifact references only |

The API must reject client-authored resolved assignments, service IDs, provider
profiles, component IDs, edges, cost values, evidence, deployment values, and
digests.

## 10. Lifecycle And Versioning

- Schema versions change only for incompatible structural changes.
- Profile/catalog/component versions change for semantic behavior,
  capability, formula, package, Terraform binding, permission, or contract
  changes.
- An `active` profile may reference only `active` compatible definitions.
- `deprecated` remains readable and selectable only for existing drafts.
- `retired` remains readable for audit/destroy but cannot be newly selected.
- Digests pin exact content in resolutions.
- Compatibility ranges are explicit arrays of allowed versions, not open-ended
  comparison strings.
- No automatic upgrade changes an existing resolution.

## 11. Semantic Validators And Errors

Add shared semantic behavior in:

```text
2-twin2clouds/backend/architecture_profiles/contracts.py
twin2multicloud_backend/src/services/architecture_contract_service.py
3-cloud-deployer/src/architecture_profiles/contracts.py
```

The Python implementations may be project-local but must pass identical golden
fixtures and error codes.

Required stable error codes:

- `ARCH_SCHEMA_INVALID`
- `ARCH_VERSION_UNSUPPORTED`
- `ARCH_DIGEST_MISMATCH`
- `ARCH_DUPLICATE_ID`
- `ARCH_REFERENCE_UNRESOLVED`
- `ARCH_GRAPH_CYCLE_FORBIDDEN`
- `ARCH_CAPABILITY_INCOMPLETE`
- `ARCH_BUNDLE_INCOMPATIBLE`
- `ARCH_COMPONENT_UNAVAILABLE`
- `ARCH_EDGE_UNAVAILABLE`
- `ARCH_DEPLOYMENT_SPEC_INCOMPATIBLE`
- `ARCH_EXTENSION_BINDING_INVALID`
- `ARCH_SECRET_FIELD_FORBIDDEN`

Errors expose safe field paths, IDs, and bounded messages. They do not echo
payloads, source, provider responses, or secrets.

## 12. Implementation Slices

### Slice A: Schemas And Fixtures

Must implement all schemas, common definitions, semantic registry, positive and
negative fixtures, and deterministic canonicalization.

### Slice B: Sync And Drift Gate

Must implement byte-identical generated copies, digest markers, `--check`,
fresh-clone tests, and workflow path triggers.

### Slice C: Optimizer Reader

Must implement immutable typed readers and semantic validation. No calculation
path may use the new profile yet.

### Slice D: Management Reader

Must implement Pydantic read models and semantic validation. No database/API
authoring is added.

### Slice E: Deployer Reader

Must implement immutable typed readers and semantic validation. No package or
Terraform path may use the new profile yet.

### Slice F: Cross-Project Golden Gate

Must prove that all three services accept/reject the same fixtures with the
same stable code and calculate the same digest.

## 13. Tests And Verification

Contract tests must cover:

- schema metaschema validation;
- each valid contract independently and as a linked bundle;
- every required field absent and additional property;
- ID grammar, duplicate IDs, sorted/unique sets;
- unresolved profile/component/edge/port/formula/evidence/spec references;
- forbidden and allowlisted cycles;
- optimization/calculation/formula/workload incompatibility;
- provider capability and deployment gaps;
- invalid lifecycle/version transitions;
- digest stability and every mutation class;
- decimal canonicalization;
- secret-like keys and credential-shaped values;
- v1 deployment-specification compatibility;
- identical error codes across services;
- generated-copy drift.

Safe commands:

```bash
python scripts/sync_architecture_profile_contracts.py --check
python -m pytest scripts/tests/test_architecture_profile_contract_sync.py -v
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/ --ignore=tests/e2e -v
./thesis.sh test deployment-contract
```

No database migration, API behavior change, Terraform plan/apply, or cloud
credential is required.

## 14. Security And Observability

- Contract loaders enforce maximum document size, array counts, depth, and
  bounded error counts.
- Loaders do not resolve network references.
- Validation logs include contract kind, safe ID/version, digest, result, error
  code, and correlation ID where available.
- Logs never include whole contract payloads.
- Fixtures and generated copies pass repository secret scanning.

## 15. Documentation

Update:

- `docs-site/docs/contracts-and-data-flow/` with model boundaries, ownership,
  versioning, and resolution references;
- `docs-site/docs/developer-guide/` with contract synchronization and extension
  procedure;
- `docs/research/digital_twin_architecture_and_eventing_layer.md` only if the
  implemented contract reveals a new limitation or threat;
- Phase 8 roadmap and #149 with schema paths and verification evidence.

Do not present an unimplemented profile as selectable. Do not edit LaTeX.

## 16. Rollout And Rollback

The new readers are dark infrastructure. Existing calculations, API
persistence, deployments, and Flutter remain on current contracts.

Rollback removes the readers and generated copies. Root contract files may
remain as versioned evidence. No data rollback is required.

## 17. Definition Of Done

- [ ] All four schemas and the semantic registry exist in the repository SSOT.
- [ ] Field types, cardinalities, enums, IDs, digests, lifecycle, and
      compatibility are exact and fail closed.
- [ ] Optimization strategy, calculation strategy, formula set, workload, and
      deployment specification are coupled by one compatible bundle.
- [ ] Logical architecture contains no provider SDK, Terraform, physical name,
      endpoint, or credential detail.
- [ ] Provider profiles and component catalogs expose explicit implementation
      references behind stable IDs.
- [ ] Resolved architectures are complete, immutable, secret-free, and
      reference rather than duplicate deployment dimensions.
- [ ] `ResolvedDeploymentSpecification v1` remains baseline-only and unchanged.
- [ ] Optimizer, Management API, and Deployer accept/reject identical fixtures
      with identical codes and digests.
- [ ] Generated copies are byte-identical and drift-gated in CI.
- [ ] Unknown versions, bad references, illegal cycles, capability gaps,
      incompatible bundles, and secret fields fail closed.
- [ ] Focused and full safe service suites pass.
- [ ] Product/developer docs, roadmap, and #149 are updated.
- [ ] No runtime selection, database, Flutter, Terraform, or cloud behavior
      changes.
- [ ] Two reviews find no unresolved issue.
- [ ] The structured commit references #149.
