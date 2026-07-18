---
title: "Phase 8.3: Provider Profiles And Deployment Component Catalog"
description: "Implementation plan for explicit AWS, Azure, and GCP baseline implementations and a deterministic deployment component catalog."
tags: [architecture, provider-profiles, component-catalog, deployer, optimizer, issue-150]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #150
- Phase 8.2 shared architecture contracts
- GitHub issue #113 user-function extension prerequisite
- Current provider capability, package registry, Terraform, permission, and resolved-deployment-specification matrices
- 2-twin2clouds and 3-cloud-deployer provider implementations
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Phase 8.3: Provider Profiles And Deployment Component Catalog

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#150 Register provider implementation profiles and deployment component catalog](https://github.com/TVJunkie724/master-thesis/issues/150) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-provider-component-catalog` |
| Base branch | `master` |
| Blocked by | Phase 8.2 / #149 and user-function contract #113 |
| Produces | Complete baseline registries for Phases 8.4-8.7 |
| Runtime activation | Dark/read-only; current deployment path remains active |
| Live cloud E2E | Forbidden |

The issue may not start until #113 is complete. The baseline contains approved
user logic, so omitting its extension slots is not a valid way around the
blocker. Partial extension-slot metadata is forbidden.

## 1. Outcome

Register every approved AWS, Azure, GCP, and mixed-provider implementation of
`five-layer-baseline@1` through:

- one immutable architecture profile definition;
- one provider implementation profile per provider;
- one versioned deployment component catalog;
- explicit package/template, Terraform, port/binding, runtime, permission,
  pricing/formula, deployment-dimension, observability, error, cleanup, and
  extension-slot references.

Terraform and provider templates remain explicit source code. The catalog makes
their contracts discoverable and machine-validated; it does not generate them.

### Scope Boundary

| Included | Excluded |
|---|---|
| Concrete baseline AWS/Azure/GCP provider profile definitions, component catalog entries, package/Terraform/permission bindings, semantic registration code, and completeness/drift checks | Management persistence, Optimizer ranking, Deployer graph execution, Flutter workflow, Eventing components, arbitrary user-defined provider entries, and live cloud execution |

## 2. Required Inputs

- approved Phase 8.1 baseline decision and digest;
- Phase 8.2 schemas and generated contract readers;
- current function/edge/Terraform inventory;
- completed #113 artifact/slot/package contract;
- active `thesis-demo-v1` permission capability mappings;
- resolved-deployment-specification v1 dimension registry;
- current pricing registry, service models, formulas, provider capability
  matrix, and deployment drift matrix.

Any stale input digest blocks catalog publication.

## 3. Repository Definitions

Create:

```text
contracts/architecture-profiles/definitions/
  profiles/
    five-layer-baseline/1/profile.json
  provider-implementations/
    five-layer-baseline/1/aws/1.json
    five-layer-baseline/1/azure/1.json
    five-layer-baseline/1/gcp/1.json
  component-catalogs/
    baseline/1/catalog.json
  fixtures/
    resolved/
      all-aws.json
      all-azure.json
      mixed-providers.json
    unsupported/
      all-gcp.json
```

The exact unsupported fixture set must follow the Phase 8.1 admissibility
decision. `all-gcp.json` is named here because current deployment contracts
explicitly reject GCP L4; if Phase 8.1 proves a different support state, the
fixture name and expected code must be updated in the reviewed decision before
implementation.

Generated copies use the Phase 8.2 sync path. Do not add hand-maintained
service-local catalog files.

## 4. Code Ownership

Add:

```text
2-twin2clouds/backend/architecture_profiles/
  __init__.py
  registry.py
  capability_resolver.py

3-cloud-deployer/src/architecture_profiles/
  __init__.py
  registry.py
  catalog.py
  completeness.py

twin2multicloud_backend/src/services/
  architecture_catalog_read_service.py
```

The Optimizer registry resolves logical/provider cost capability metadata.
The Deployer registry resolves package, Terraform, runtime, and port metadata.
The Management service reads summaries only; persistence and APIs begin in
Phase 8.4.

No module may duplicate contract JSON into Python dictionaries.

## 5. Catalog Registration Rules

### 5.1 Logical Profile

The committed `five-layer-baseline@1` profile must be generated from the
approved Phase 8.1 decision without changing:

- five responsibilities;
- seven optimization/deployment slots;
- logical components and ports;
- six baseline edges;
- extension slots;
- functional-completeness rules;
- optimization/calculation/formula bundle;
- graph policy and compatibility.

The profile content digest must be referenced by every provider profile.

### 5.2 Provider Profiles

Each provider profile must:

- map every logical component it can implement;
- map every required edge mechanism;
- distinguish mandatory, extra, and missing capabilities;
- declare exact supported deployment and pricing regions;
- reference current pricing service models and formula IDs;
- reference deployable component options;
- reference `thesis-demo-v1` permission capabilities;
- declare unsupported responsibilities with stable codes;
- declare compatibility with resolved-deployment-specification v1;
- contain no cloud account, project, subscription, resource name, or endpoint.

An all-provider profile is `active` only if every required responsibility and
edge is deployable. A partial provider profile can remain `active` as a
component source for valid mixed resolutions, but its unsupported whole-profile
status must be explicit.

### 5.3 Component Entries

For every retained Phase 8.1 component/provider implementation, register:

- stable `deployment_component_id` and version;
- provider service ID;
- logical component/responsibility IDs;
- package artifact and deterministic source digest rule;
- platform handler and trigger adapter;
- Terraform resource/module address;
- allowlisted Terraform input variable IDs;
- declared Terraform output IDs;
- runtime ID, timeout, memory/capacity bounds;
- configuration schema;
- input/output ports and sensitivity;
- permission capability IDs and permission-set version;
- pricing model, formula, evidence, and deployment-specification references;
- error, observability, cleanup, and lifecycle contracts;
- supported regions and compatibility;
- optional #113 extension slot reference.

Every current package/template directory used by an approved component must be
owned by exactly one catalog artifact entry. Shared wrapper libraries may be
referenced by multiple artifacts but have one digest identity.

### 5.4 Edge Implementations

For every retained Phase 8.1 edge/provider combination, register:

- stable implementation ID and version;
- source output and destination input port IDs;
- Terraform dependency/output/input IDs;
- runtime mechanism;
- payload/envelope contract;
- delivery, timeout, retry, DLQ, idempotency, ordering, and replay behavior;
- trust/auth capability;
- transfer route class and formula/evidence refs;
- operation correlation and log/metric contract;
- required glue/adapter component IDs;
- source/destination provider constraints.

An edge implementation must not contain a formatted resource name, URL,
handler, ARN, topic, bucket, function key, or environment variable value.

## 6. Terraform Binding Contract

The catalog must reference existing HCL through structured fields:

```json
{
  "resource_addresses": ["aws_lambda_function.dispatcher"],
  "input_bindings": [
    {
      "input_id": "input.package.dispatcher",
      "terraform_variable": "aws_dispatcher_package_path",
      "sensitive": false
    }
  ],
  "output_bindings": [
    {
      "output_id": "output.runtime.dispatcher.function_name",
      "terraform_output": "aws_dispatcher_function_name",
      "sensitive": false
    }
  ],
  "depends_on_component_ids": []
}
```

Addresses and variable/output symbols are source identifiers, not deployed
values. The HCL parser gate must prove every symbol exists and that no symbol
is claimed by incompatible components.

Terraform implicit references may remain within one catalog component.
Cross-component references must use declared output/input IDs.

## 7. Package And Template Identity

The package artifact registry must:

- enumerate source roots and platform handlers;
- identify provider wrapper/shared library dependencies;
- exclude caches, ignored credentials, runtime state, Terraform state, build
  output, and user source from static artifact digests;
- use deterministic path/content-digest arrays;
- verify actual package builder inclusion/exclusion rules;
- reject source rewriting;
- bind user artifacts only through completed #113 extension slots;
- record package builder version and expected package layout.

Current real credentials under ignored template paths must never be traversed,
hashed, copied into fixtures, or logged.

## 8. Pricing, Formula, And Deployment Binding

For each deployment component:

```text
logical component
  -> provider service model
  -> pricing intent/evidence contract
  -> formula IDs
  -> deployment selection component IDs
  -> deployment dimension IDs
  -> Terraform input bindings
```

The completeness checker must reject:

- a deployable component without pricing/formula ownership;
- a priced component without deployable selection where the model requires a
  Terraform setting;
- a formula reference not present in the active formula set;
- a deployment dimension not present in
  `deployment-dimensions.json`;
- a Terraform target not owned by the component binding;
- an account-scoped or usage-tier dimension treated as a Terraform SKU.

## 9. User-Function Extension Binding

Only components approved by Phase 8.1 may expose extension slots. Each mapping
must include:

- #113 slot ID/version;
- platform wrapper artifact;
- supported `python311` provider adapter;
- canonical input/output/error/observability contracts;
- allowed configuration and capability IDs;
- artifact input binding ID;
- no user-controlled handler, resource name, permission, endpoint, or
  Terraform binding.

The catalog stores slot metadata, never user source, source digest, secret
value, or Twin binding.

## 10. Completeness And Drift Gate

The gate must:

1. validate all definitions and digests;
2. prove every Phase 8.1 target component and edge has required provider
   mappings;
3. parse HCL with `python-hcl2` and verify every resource/input/output symbol;
4. enumerate Deployer package builders and static templates;
5. verify package source digests and handlers;
6. verify pricing models, formula IDs, deployment components/dimensions, and
   permission capability IDs;
7. verify extension slots against the generated #113 contract;
8. reject duplicate ownership and unresolved references;
9. produce a provider/profile completeness report;
10. produce no runtime artifacts or cloud calls.

Stable failure codes:

- `CATALOG_SOURCE_DECISION_STALE`
- `CATALOG_COMPONENT_MISSING`
- `CATALOG_EDGE_MISSING`
- `CATALOG_TERRAFORM_REFERENCE_INVALID`
- `CATALOG_PACKAGE_REFERENCE_INVALID`
- `CATALOG_PACKAGE_DIGEST_MISMATCH`
- `CATALOG_PRICING_REFERENCE_INVALID`
- `CATALOG_FORMULA_REFERENCE_INVALID`
- `CATALOG_DEPLOYMENT_BINDING_INVALID`
- `CATALOG_PERMISSION_REFERENCE_INVALID`
- `CATALOG_EXTENSION_SLOT_INVALID`
- `CATALOG_DUPLICATE_OWNERSHIP`
- `PROVIDER_PROFILE_INCOMPLETE`

## 11. Implementation Slices

### Slice A: Profile Definition

Must translate the approved baseline decision into the canonical profile and
verify an exact decision-to-profile mapping.

### Slice B: Deployer Component Catalog

Must register static packages, Terraform bindings, ports, runtime contracts,
permissions, observability, errors, cleanup, and extension slots.

### Slice C: Optimizer Provider Profiles

Must map provider services, capabilities, pricing/formula evidence, deployment
components, regions, and unsupported states.

### Slice D: Management Read Service

Must expose typed internal profile summaries for Phase 8.4 without adding
public routes or persistence.

### Slice E: Complete Cross-Project Registry

Must synchronize definitions, run the full completeness/drift report, and add
golden all-AWS, all-Azure, mixed-provider, and explicit unsupported fixtures.

## 12. Tests And Verification

Tests must cover:

- valid provider profiles/catalog and every missing mapping;
- duplicate component, package, Terraform, port, and edge ownership;
- stale decision/profile/catalog/package digests;
- nonexistent Terraform resource/variable/output;
- package handler/path drift and ignored-secret path exclusion;
- pricing/formula/deployment-dimension/permission drift;
- invalid extension slot/runtime/wrapper;
- unsupported provider candidate visibility;
- component and edge completeness for every approved fixture;
- deterministic registry ordering and reports;
- no source rewriting;
- same definitions/digests in all service copies.

Add focused files:

```text
2-twin2clouds/tests/unit/architecture_profiles/
3-cloud-deployer/tests/unit/architecture_profiles/
twin2multicloud_backend/tests/test_architecture_catalog_read_service.py
scripts/tests/test_architecture_profile_contract_sync.py
```

Safe verification:

```bash
python scripts/sync_architecture_profile_contracts.py --check
python scripts/check_architecture_inventory.py
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/unit/architecture_profiles/ -v
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/test_architecture_catalog_read_service.py -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/unit/architecture_profiles/ -v
./thesis.sh test deployment-contract
```

Run full safe service suites after focused tests. Exclude Deployer
`tests/e2e`.

## 13. Security And Observability

- Registries load only repository-owned generated files.
- No runtime or client path can point a registry loader at an arbitrary file or
  URL.
- Catalog logs contain safe IDs, versions, digests, counts, and error codes
  only.
- All secret-like fixtures and ignored credential paths are negative tests.
- Package/source hashing never follows symlinks or leaves approved roots.
- A missing permission, error, observability, or cleanup contract blocks
  publication.

## 14. Documentation

Update:

- `docs-site/docs/developer-guide/` with profile/component registration and
  provider extension procedure;
- `docs-site/docs/contracts-and-data-flow/` with profile-to-catalog and
  catalog-to-Terraform maps;
- `docs-site/docs/architecture/` with implemented catalog boundaries, without
  claiming profile selection is active;
- `docs/research/five_layer_baseline_target_decision.md` only for deviations
  forced by implementation evidence;
- Phase 8 roadmap and #150 with completeness counts and fixture support.

## 15. Rollout And Rollback

Catalogs are loaded in validation/read-only mode. Existing calculation and
deployment paths remain authoritative until Phases 8.5 and 8.6 activate them.

Rollback disables catalog loading and removes generated copies/read services.
Root definitions remain reviewable evidence. No database or cloud rollback is
required.

## 16. Definition Of Done

- [ ] `five-layer-baseline@1` matches the approved Phase 8.1 decision exactly.
- [ ] AWS, Azure, and GCP provider implementation profiles are complete or
      explicitly unsupported per responsibility.
- [ ] Every retained component has one explicit package, Terraform, runtime,
      port, permission, pricing/formula, deployment, error, observability,
      cleanup, and compatibility contract.
- [ ] Every retained edge has explicit input/output, mechanism, delivery,
      trust, transfer, cost, and observability mappings.
- [ ] Every Terraform source symbol and package handler/path is parser-verified.
- [ ] No package relies on source rewriting or hidden resource-name
      construction.
- [ ] #113 extension slots are fully bound or no extension slot is published.
- [ ] Account/usage dimensions cannot become Terraform selections.
- [ ] All-AWS, all-Azure, supported mixed, and unsupported fixtures have
      deterministic completeness results.
- [ ] Registry copies and digests are byte-identical across services.
- [ ] Focused and full safe project suites plus deployment drift pass.
- [ ] No existing runtime path is activated or changed.
- [ ] No credential file, runtime state, or cloud resource is accessed.
- [ ] Product/developer docs, roadmap, and #150 are updated.
- [ ] Two reviews find no unresolved issue.
- [ ] The structured commit references #150.
