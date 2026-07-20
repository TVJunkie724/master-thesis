---
title: "Phase 8.5: Optimizer Profile Resolution"
description: "Implementation plan for profile-bounded functional-completeness resolution before cost ranking."
tags: [architecture, optimizer, functional-completeness, strategy, cost, issue-151]
lastUpdated: "2026-07-20"
version: "1.2"
---

<!-- SOURCES:
- GitHub issue #151
- Phase 8.2 architecture contracts
- Phase 8.3 provider implementation profiles and component catalog
- Phase 8.4 Management API ingestion and persistence contract
- Current Optimizer strategy, formula, pricing evidence, transfer-path, and resolved-deployment-specification implementations
EXTRACTED: 2026-07-20 | VERSION: 1.2
-->

# Phase 8.5: Optimizer Profile Resolution

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#151 Resolve architecture profiles in the Optimizer with functional completeness](https://github.com/TVJunkie724/master-thesis/issues/151) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-optimizer-resolution` |
| Base branch | `master` |
| Blocked by | Phase 8.4 / #142 |
| Implementation status | Complete and reviewed locally; activation remains default-off |
| Produces | Complete, dark-integrated `ResolvedTwinArchitecture v1` compiler input; new-profile activation remains Phase 8.9A |
| Live cloud E2E | Forbidden |

The existing `five-layer-baseline@1` cost behavior must remain golden-tested.
No incomplete or unsupported candidate may reach cost ranking.

## Corrective Activation Addendum

The completed resolver is generic default-off infrastructure and historical
`@1` reproduction evidence. A priceable seven-slot candidate is not a complete
new-profile architecture. Repository-backed activation requires the immutable
complete-service decision, workload v2, corrected cross-cloud storage routes,
native/provider-hosted L4/L5 bundles, and their capacity/cost contracts.
Phase 8.6 does not satisfy these requirements by compiling the old catalog.

## 1. Outcome

The Optimizer resolves one selected, reviewed architecture profile into:

- a functionally complete provider/component assignment;
- complete resolved logical edges and transfer/runtime costs;
- the existing `ResolvedDeploymentSpecification v1`;
- a new immutable `ResolvedTwinArchitecture v1`;
- bounded rejection diagnostics for excluded candidates.

Architecture optimization is extensible through a registered profile strategy,
but remains closed-world. The Optimizer does not generate arbitrary nodes,
edges, Terraform, or provider services.

### Scope Boundary

| Included | Excluded |
|---|---|
| Profile-bounded strategy registry, candidate construction, functional-completeness gate, whole-path ranking, exact cost ownership, immutable resolution builder, compatibility projection, and default-off Management integration | Pricing-source refresh redesign, provider catalog authoring or support-state promotion, DB migration, deployment graph/Terraform execution, runtime activation, Flutter workflow, Eventing profile implementation, and live provider execution |

### Activation Boundary

Phase 8.3 intentionally publishes the historical provider profiles as
`supported: false`. The shared semantic validator therefore must not admit a
repository-backed publishable resolution during Phase 8.5.

Phase 8.5 implements and fully tests resolution with the canonical supported
contract fixtures, integrates the Management request/response path behind a
default-off activation gate, and keeps the existing audited legacy path
unchanged while that gate is off. Phase 8.6 proves the deployment compiler,
but keeps it dark. Phase 8.9A registers complete new-profile provider bundles,
enables the gate, and removes legacy run selection after the separate
complete-service decision. No service may bypass or reinterpret the
provider-profile `supported` field to activate earlier.

## 2. Internal Request Contract

The Management API continues to expose workload input through its current run
creation route. It enriches the internal `PUT /calculate` request with:

```json
{
  "calculationRunId": "uuid",
  "architectureProfile": {
    "profileId": "five-layer-baseline",
    "profileVersion": "1",
    "contentDigest": "sha256:..."
  },
  "extensionBindings": [
    {
      "slotId": "processor.telemetry",
      "slotVersion": "1",
      "artifactId": "uuid",
      "artifactDigest": "sha256:...",
      "configurationDigest": "sha256:..."
    }
  ],
  "providerPricingCatalogs": {},
  "providerPricingContexts": {},
  "...existing workload fields": "unchanged"
}
```

The Optimizer accepts references only. It loads the exact repository profile,
provider profiles, and component catalog and verifies all digests. Clients
cannot submit profile content, components, edges, service IDs, formulas, prices,
or deployment values.

The response adds:

```text
result.resolvedTwinArchitecture
```

and preserves:

```text
result.resolvedDeploymentSpecification
result.calculationResult
result.resultTrace
result.intentTrace
result.transferPricingContext
result.transitionRuntimeContext
```

The two resolved contracts must reference the same calculation run, profile,
component IDs, deployment specification digest, formulas, evidence, and
catalogs.

## 3. Strategy Boundary

Add:

```text
2-twin2clouds/backend/architecture_profiles/
  strategy.py
  five_layer_strategy.py
  candidate_factory.py
  completeness.py
  resolution_builder.py
  diagnostics.py
```

### 3.1 `ArchitectureOptimizationStrategy`

Define a typed protocol:

```text
strategy_id
supported_profile_refs
validate_request(context)
enumerate_candidates(context)
validate_functional_completeness(candidate, context)
calculate_candidate(candidate, context)
resolve_edges(candidate, context)
build_resolution(winner, context)
```

Register strategies by the exact optimization bundle reference. Duplicate
registration and unknown bundle IDs fail at startup.

### 3.2 Baseline Implementation

`FiveLayerCompletePathStrategy` must adapt, not duplicate:

- `calculation_v2.engine`;
- provider layer calculators;
- `path_optimizer`;
- transfer pricing;
- transition runtime pricing;
- current strategy context and traceability;
- resolved deployment specification builder.

The existing seven-slot candidate path remains the baseline's calculation
kernel. Logical components/edges and provider catalog metadata wrap its typed
results.

Do not replace established formula engines or reimplement provider pricing in
the architecture layer.

## 4. Resolution Algorithm

Execute exactly:

1. validate request schema and supported versions;
2. load profile, optimization bundle, provider profiles, and component catalog
   by exact IDs/versions/digests;
3. validate workload and extension bindings against the profile;
4. resolve exact published pricing catalogs and account-scoped contexts;
5. construct closed provider/deployment-component options for every required
   logical component;
6. reject options lacking region, capability, formula, pricing evidence,
   deployment specification, permission, package, or edge implementation;
7. enumerate complete baseline assignments in deterministic profile order;
8. validate complete functional and edge coverage before any candidate can win;
9. calculate component/layer, transfer, registered transition-runtime adapter,
   account, and edge costs using the profile's compatible strategy/formula
   bundle; the historical `cost.cross-cloud-glue` ID remains only the
   compatibility name for its explicit adapter owner;
10. reject calculation failures with bounded diagnostics;
11. rank admissible candidates by exact canonical decimal total cost;
12. break equal-cost ties by lexicographic canonical assignment tuple
    `(logical_component_id, provider, deployment_component_id)`;
13. build both resolved contracts and validate cross-contract invariants;
14. return the winner plus bounded aggregate rejection diagnostics.

No preference for fewer providers, a specific cloud, or historical layer
choice is allowed unless a later scoring strategy explicitly versions that
criterion.

## 5. Functional Completeness Gate

A candidate is complete only if:

- every required responsibility has every required logical component;
- every component has all required capabilities;
- every logical input/output port is compatible;
- every required logical edge has one compatible provider implementation;
- every cross-provider edge has transfer route, adapter, trust, observability,
  and cost ownership;
- every required extension slot has a valid immutable artifact binding;
- every service has formula, pricing evidence, and deployment mappings;
- every provider profile and catalog version is active and compatible;
- all graph-policy and region constraints pass.

The gate returns typed missing/extra capability evidence. Provider-extra
capabilities remain visible but do not compensate for a missing mandatory
capability.

Completeness runs before ranking. A candidate with a lower partial cost is
never publishable.

## 6. Cost Ownership And Precision

- Use `Decimal` internally for comparison and canonical output.
- Convert provider API numbers at the evidence boundary, never by binary float
  round-trip.
- Preserve provider billing blocks, free tiers, account-scoped pricing,
  progressive tiers, transfer pools, trigger costs, and transition runtimes.
- Every cost contribution references one formula and evidence source.
- Non-additive account costs are represented once and linked to affected
  components; they are not duplicated into every row.
- The architecture total must equal component/layer plus edge/transfer plus
  registered transition-adapter contributions plus account-scope
  contributions within exact decimal rules.
- Display rounding occurs only in API/Flutter projections, never in ranking or
  digests.

## 7. Resolution Builder

`ResolvedTwinArchitectureBuilder` must:

- consume only a complete winner and trusted registries;
- use deterministic UUIDv5 identity from the Phase 8.2 rule;
- map every logical component to one deployment component and provider profile;
- map every logical edge to one catalog edge implementation;
- copy only immutable extension artifact references;
- reference exact pricing/formula/catalog/workload evidence;
- reference, never duplicate, deployment specification dimensions;
- emit canonical decimal costs;
- calculate and validate content digest;
- rerun the shared semantic validator before returning.

The builder must reject any mismatch with the already-built
`ResolvedDeploymentSpecification v1`.

## 8. Transitional Result Compatibility

For `five-layer-baseline@1`, retain current response fields during migration:

- `calculationResult`;
- `cheapestPath`;
- provider cost sections;
- traces;
- transfer and transition runtime contexts.

They become server-derived compatibility projections from the same winning
candidate. A contract test must prove:

```text
legacy cheapestPath
  == providers derived from ResolvedTwinArchitecture assignments
  == providers in ResolvedDeploymentSpecification components
```

No new profile may depend on fixed `L1`/`L2`/`L3`/`L4`/`L5` result fields.
Phase 8.7 removes their use from generic Flutter presentation after typed
compatibility DTOs exist.

## 9. API And Error Contract

The Optimizer keeps `PUT /calculate`; unsupported/invalid architecture inputs
use the existing structured error envelope with stable codes:

- `ARCH_PROFILE_NOT_FOUND`
- `ARCH_PROFILE_DIGEST_MISMATCH`
- `ARCH_PROFILE_BUNDLE_INCOMPATIBLE`
- `ARCH_WORKLOAD_INCOMPATIBLE`
- `ARCH_EXTENSION_BINDING_INVALID`
- `ARCH_PROVIDER_IMPLEMENTATION_MISSING`
- `ARCH_COMPONENT_CANDIDATE_MISSING`
- `ARCH_EDGE_IMPLEMENTATION_MISSING`
- `ARCH_FUNCTIONAL_INCOMPLETE`
- `ARCH_PRICING_EVIDENCE_MISSING`
- `ARCH_FORMULA_MISSING`
- `ARCH_DEPLOYMENT_MAPPING_MISSING`
- `ARCH_NO_ADMISSIBLE_CANDIDATE`
- `ARCH_RESOLUTION_BUILD_FAILED`

Diagnostics include counts by safe error code and at most 25 representative
candidate IDs. They never include pricing blobs, credentials, user source,
provider responses, or tracebacks.

## 10. Management API Integration

Modify:

```text
twin2multicloud_backend/src/clients/optimizer_client.py
twin2multicloud_backend/src/services/optimizer_calculation_service.py
twin2multicloud_backend/src/services/cost_calculation_run_service.py
twin2multicloud_backend/src/schemas/optimizer_calculation.py
```

The Management service must:

- send the selected profile/digest and immutable extension references;
- validate the new response through its generated shared contract;
- verify trusted pricing context plus profile/spec/architecture cross-links;
- atomically persist result, deployment specification, and architecture through
  the Phase 8.4 service;
- map Optimizer error codes to bounded stable Management errors;
- never fall back to a legacy result if resolution validation fails;
- keep architecture request enrichment and admission default-off until the
  repository provider profiles are supported by Phase 8.6.

## 11. Implementation Slices

### Slice A: Strategy Registry And Context

Must add the protocol, bundle registry, typed execution context, exact request
validation, and startup drift checks.

### Slice B: Baseline Candidate Adapter

Must adapt current seven-slot calculations into catalog component options and
preserve all pricing/transfer/runtime behavior.

### Slice C: Completeness And Edge Resolution

Must reject incomplete component/provider/edge combinations before ranking and
produce bounded diagnostics.

### Slice D: Resolution Builder

Must emit deterministic `ResolvedTwinArchitecture v1` and verify exact
cross-contract invariants with deployment specification v1.

### Slice E: Dark Management Integration

Must implement the preallocated run request, trusted response validation,
atomic persistence, fail-closed error mapping, and the default-off activation
gate. Tests enable the gate only with canonical supported fixtures.

### Slice F: Compatibility And Golden Gate

Must prove baseline costs, winners, traces, deployment specifications, and
legacy projections remain equal for frozen valid scenarios.

## 12. Test Plan

### Optimizer Unit/Property

- unknown/stale profile/catalog/bundle/version/digest;
- each missing responsibility/component/capability/port/edge;
- region, permission, formula, pricing, evidence, deployment, and extension
  incompatibility;
- complete candidate enumeration count and deterministic order;
- completeness before cost invocation;
- no admissible candidate;
- decimal precision and equal-cost deterministic tie;
- account/non-additive cost counted once;
- transfer and registered transition-adapter cost ownership, including the
  historical `cost.cross-cloud-glue` compatibility ID;
- deterministic resolution ID/digest;
- resolved architecture/deployment specification mismatch;
- bounded/redacted diagnostics.

### Golden Regression

For the historical `five-layer-baseline@1` all-AWS, all-Azure,
mixed-provider, unsupported all-GCP, and edge-heavy storage/transfer fixtures:

- identical provider cost outputs;
- identical total cost before display rounding;
- identical winning assignment;
- identical transfer and transition runtime contexts;
- identical resolved deployment specification;
- new complete resolved architecture;
- explicit unsupported reasons.

The valid baseline test must exhaust all current closed provider combinations
allowed by the capability matrix, not only the winner.

### Management Integration

- request enrichment cannot be client-authored;
- trusted profile/pricing context matching;
- invalid Optimizer response yields 502 and failed run without resolution;
- atomic run/spec/architecture/result persistence;
- selection and fixed-field projection invariants;
- ownership and error mapping.

Safe verification:

```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/unit/architecture_profiles/ \
    tests/unit/calculation_v2/ -v
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest \
    tests/test_optimizer_client.py \
    tests/test_optimizer_calculation_contract.py \
    tests/test_cost_calculation_runs.py \
    tests/test_resolved_architecture_service.py -v
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/ -v
./thesis.sh test deployment-contract
```

No pricing refresh, provider credential, Terraform, live deployment, or E2E is
required. Tests use frozen reviewed catalogs.

## 13. Security And Observability

- Profile/catalog paths are repository-owned and non-client-configurable.
- Calculation request size, candidate count, diagnostic count, and duration are
  bounded.
- Structured logs include run/profile/bundle/digest, enumerated/admissible/
  rejected counts, winner ID, duration, safe error code, and correlation ID.
- Logs do not include workload payload values that may identify users,
  pricing blobs, account IDs, source, or secrets.
- A timeout or unexpected exception returns a stable error and failed run; no
  partial resolution is persisted.

## 14. Documentation

Update:

- `docs-site/docs/contracts-and-data-flow/pricing-optimization.md`;
- `docs-site/docs/contracts-and-data-flow/contract-map.md`;
- Optimizer developer docs for profile strategy extension and completeness;
- Management API docs for trusted enrichment/persistence;
- `docs/research/research_questions_and_evaluation_design.md` only where the
  implemented completeness method refines evaluation;
- roadmap and #151 with candidate/rejection/golden evidence.

Do not claim Eventing support. Do not edit LaTeX.

## 15. Rollout And Rollback

Keep `five-layer-baseline@1` historical and stage the generic resolver dark.

1. deploy synchronized profile/catalog contracts;
2. ship Optimizer profile request validation and resolution dark;
3. ship Management enrichment, response validation, and persistence dark;
4. retain legacy response projections and selection while the gate is off;
5. let Phase 8.9A register complete `@2` bundles and enable both sides
   atomically;
6. monitor resolution failure and candidate rejection codes in fixture and
   offline integration gates.

Rollback leaves the activation gate off. After Phase 8.9A activation, rollback
disables new architecture-aware run creation but preserves already persisted
immutable resolutions. An enabled path must not silently create legacy runs
without architecture evidence.

## 16. Definition Of Done

- [x] `ArchitectureOptimizationStrategy` is registered by compatible profile
      bundle and has one baseline implementation.
- [x] The existing formula, pricing, transfer, transition, and deployment
      engines are reused rather than duplicated.
- [x] Functional completeness and edge coverage run before cost ranking.
- [x] Every publishable candidate has full component, edge, region, permission,
      pricing, formula, evidence, deployment, and extension coverage.
- [x] Ranking uses exact decimals and deterministic tie-breaking.
- [x] One deterministic, valid resolved architecture and matching deployment
      specification are emitted per architecture-aware successful fixture run.
- [x] Legacy baseline costs, winners, traces, and deployment selections match
      golden fixtures.
- [x] Unsupported and incomplete candidates remain visible and cannot win.
- [x] Management validates and persists run/spec/architecture atomically when
      the test activation gate is enabled with supported fixtures.
- [x] Runtime activation remains default-off while repository provider
      profiles are unsupported; no validator bypass is introduced.
- [x] Invalid Optimizer responses fail closed with no fallback resolution.
- [x] Unit, property, exhaustive candidate, golden regression, Management
      integration, full safe suites, and deployment drift gates pass.
- [x] No live provider API, credential, Terraform, deployment, or E2E runs.
- [x] Product/developer docs, research evidence where applicable, roadmap, and
      #151 are updated.
- [x] Two reviews find no unresolved issue.
- [x] The structured commits reference #151.

## 17. Completion Evidence

- The implementation is split across the reviewable commit series
  `eadced8b`, `c49a6194`, `98547c21`, `3d71f7a2`, `4907320e`,
  `9c10bac8`, `97a5c42a`, `a27be8c7`, `571778c6`, `17298eb8`, and
  `1ba9fa0a`; each commit references #151.
- Focused verification reports 353 passing Optimizer tests and 110 passing
  Management tests.
- The serial `./thesis.sh test deployment-contract` gate passes all 13 stages:
  66 root/contract, 40 Optimizer drift, 87 Management drift, 73 Deployer drift,
  885 Optimizer, 1,007 Management, 1,851 Deployer with one intentional skip,
  and 730 Flutter tests. Static analysis, security/package checks, Flutter
  web/macOS builds, strict MkDocs, and repository checks also pass.
- The architecture-inventory follow-up in `c8a34a42` makes the Phase 8.4
  resolved-architecture compatibility reader part of the audited source
  digest and leaves the historical Phase 8.0 evidence cut unchanged.
- GitHub issue #151 contains the same local completion evidence and remains open
  until the commits are published or merged.
- Repository activation is deliberately still off. Phase 8.9A must register
  the complete-service provider implementations and activate the typed
  compiler path; no
  live provider, credential-bearing, Terraform, deployment, or E2E operation
  was performed by Phase 8.5.
