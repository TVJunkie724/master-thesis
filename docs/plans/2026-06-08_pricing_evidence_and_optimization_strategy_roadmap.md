# Pricing Evidence And Optimization Strategy Roadmap

## Purpose

This roadmap defines the phased path from the current cost-only optimizer toward
an enterprise-grade, evidence-backed pricing pipeline and an extensible
optimization architecture.

The immediate implementation remains cost optimization. Future optimization
metrics such as latency, sustainability, resilience, compliance, operational
complexity, or lock-in must be possible without rewriting the optimizer core.

## Principles

- No quick fixes.
- No hidden defaults in publishable pricing.
- No generated pricing file as editable SSOT.
- No runtime LLM matching.
- No fake disabled feature implementations.
- No manual price override table as the final source of truth.
- No real cloud deployment E2E in this roadmap phase.
- One implementation phase must be planned, reviewed, implemented, reviewed,
  and committed before the next phase starts.

## GitHub Tracking

| Scope | GitHub issue | Status |
|---|---:|---|
| Architecture debt / refactoring epic | #69 | existing epic |
| Pricing catalog reliability | #32 | existing active issue |
| Pricing evidence registry foundation | #32 | implemented on this branch |
| Pricing registry contract/API | #32 | implemented on this branch |
| Optimization strategy architecture | #87 | implemented on this branch |
| Cost calculation run store | #88 | implemented on this branch |
| Azure pricing evidence artifacts | #89 | implemented on this branch |
| Azure tiering and unit-aware calculation | #90 | implemented on this branch |
| AWS pricing evidence artifacts | #91 | implemented on this branch |
| AWS tiering and unit-aware calculation | #92 | implemented on this branch |
| GCP pricing credential preflight and evidence artifacts | #93 | implemented on this branch |
| Cross-provider evidence-backed cost validation | #94 | implemented on this branch |
| Intent-to-result traceability | #100 | implemented on this branch |
| Provider-specific tiering/calculation reviews | #90/#92/#93 | implemented baseline; live/e2e finalization remains later |

Issue numbers must be added here when planned phases are split into GitHub
issues. The markdown roadmap remains the thesis/dev narrative; GitHub remains
the operational tracker.

## Target State

```text
Twin / Usage Input
        |
        v
Optimization Profile
        |
        +--> cost_minimization_v1       enabled
        +--> latency_minimization_v1    disabled / TBD
        +--> weighted_multi_objective   disabled / TBD
        |
        v
Validated Optimization Bundle
        |
        +--> Metric Providers
        |       |
        |       +--> cost              enabled
        |       +--> latency           disabled / TBD
        |       +--> sustainability    disabled / TBD
        |       +--> resilience        disabled / TBD
        |       +--> compliance        disabled / TBD
        |
        v
Calculation Model / Scoring Strategy
        |
        +--> cost-only                 enabled
        +--> weighted multi-objective  disabled / TBD
        +--> constraint-first          disabled / TBD
        |
        v
Ranked Architecture Candidates
```

The selected optimization profile is the compatibility boundary. Users and
callers must not freely mix metric providers, calculation models, scoring
strategies, and intent groups. A profile validates that those pieces belong
together before execution.

```text
OptimizationProfile
    |
    +--> metric providers
    +--> calculation models
    +--> scoring strategy
    +--> compatible intent groups
    +--> enabled/disabled state
```

Cost metrics are backed by the pricing evidence registry:

```text
Cloud Pricing APIs
        |
        v
Raw Catalog Snapshots
        |
        v
Pricing Candidates
        |
        v
Editable Registry SSOT
        |
        v
Evidence Report
        |
        v
Zero-Fallback Publish Gate
        |
        v
Cost Metric Provider
```

The editable SSOT sits in source-controlled registry files. Generated snapshots,
candidate lists, and evidence reports are inspectable artifacts, but not the
place where developers make lasting mapping decisions.

```text
Editable Registry SSOT
    |
    +--> provider-neutral intents
    +--> unit normalization rules
    +--> service model assumptions
    +--> provider mapping rules
    +--> reviewed mapping decisions
```

Registry access is centralized through a typed service boundary and read-only
API. The cost calculation uses the internal service contract; Management API and
future UI diagnostics may use read-only endpoints.

```text
Pricing Registry Files
        |
        v
PricingRegistryService
        |
        +--> CostCalculationModel internal access
        +--> Provider evidence fetcher internal access
        +--> Read-only registry API
```

Cost calculation runs are persisted by the Management API in the existing
Management database. The optimizer remains a calculation service; it must not
own a separate app database for Twin/User-scoped result history.

```text
Flutter Step 2
        |
        v
Management API
        |
        +--> stores Twin/User/config context
        +--> calls Optimizer /calculate
        +--> persists CostCalculationRun
        +--> persists result items and evidence references
        |
        v
Existing Management DB
```

Data ownership:

```text
Registry files     = rules, intents, mappings, service models
Evidence artifacts = observed provider pricing rows and selected/rejected data
Management DB      = Twin-scoped calculation runs, results, history, audit state
Optimizer service  = stateless calculation and ranking
```

## Completed Baseline Before This Roadmap

| Plan | Status | Purpose |
|---|---|---|
| `2-twin2clouds/implementation_plans/2026-06-08_pricing_schema_fetcher_contract.md` | completed | Hardened current pricing schema/fetcher contract, explicit quality metadata, and visible fallback provenance |

This roadmap builds on that completed baseline. It does not replace the schema
hardening slice retroactively; it defines the next target architecture that
removes publishable fallbacks and makes evidence, profiles, and run history
first-class.

## Phase Roadmap

| Phase | Plan | Status | Objective |
|---|---|---|---|
| 1 | `2026-06-08_pricing_evidence_registry_foundation.md` | implemented | Define editable pricing SSOT, evidence contract, and publish gate |
| 2 | `2026-06-08_pricing_registry_contract_api.md` | implemented | Expose registry files through typed internal services and read-only API |
| 3 | `2026-06-08_optimization_strategy_architecture.md` | implemented | Make cost the first metric strategy, not a hardcoded optimizer assumption |
| 4 | `twin2multicloud_backend/implementation_plans/2026-06-08_cost_calculation_run_store.md` | implemented | Persist typed Twin-scoped calculation runs in the existing Management DB |
| 5 | `2026-06-08_azure_pricing_evidence_implementation.md` | implemented | Capture Azure raw rows, candidates, selected evidence, and rejected alternatives |
| 6 | `2026-06-08_azure_tiering_calculation_review.md` | implemented (#90) | Review Azure tiers and adapt cost calculation where the current model is incomplete |
| 7 | `2026-06-08_aws_pricing_evidence_implementation.md` | implemented (#91) | Capture AWS Price List and service-specific evidence with selected dimensions |
| 8 | `2026-06-08_aws_tiering_calculation_review.md` | implemented (#92) | Review AWS tiers including IoT TwinMaker and adapt cost calculation where required |
| 9 | `2026-06-08_gcp_credentials_pricing_evidence.md` | implemented (#93) | Fix GCP pricing credentials/permissions, then capture GCP Catalog evidence |
| 10 | `2026-06-08_cross_provider_cost_validation.md` | implemented (#94) | Validate all cost intents across providers with zero publishable fallbacks |
| 16 | `2026-06-21_intent_to_result_traceability.md` | implemented (#100) | Expose bounded, secret-free calculation trace metadata from intent to selected result |
| 17 | `2026-07-17_azure_digital_twins_billable_quantity_contract.md` | implemented (#114) | Replace fabricated Azure query tiers with explicit billable-quantity inputs, 1 KB increments, and traceability |
| 18 | `2026-07-17_aws_twinmaker_pricing_plan_contract.md` | implemented locally (#115); platform CI pending | Align AWS TwinMaker estimates with functional and account-scoped pricing-plan semantics |
| 18.1 | `2026-07-17_immutable_region_pricing_catalogs.md` | implementation in progress (#119) | Replace mutable provider-wide pricing files with immutable provider-and-region keyed catalog snapshots and deterministic calculation bindings |
| 19 | Plan created after Phase 18.1 completion | planned (#116) | Resolve transfer cost through explicit route, region, transfer-class, and network-tier contracts |
| 20 | Plan created after Phase 19 completion | planned (#118) | Bind deployable service selections from the selected optimization run to the DeploymentManifest and Terraform |

## Phase Boundaries

### Phase 1

Defines registry/evidence architecture only. It must not rewrite providers or
calculations.

### Phase 2

Adds a typed internal registry access service and read-only registry API.
Cost calculation must use the internal service contract, not scattered file
reads or local HTTP calls.

### Phase 3

Defines optimizer extension seams for metrics and scoring models. It must keep
only cost enabled. Strategies, metric providers, calculation models, and intent
groups must be selected through validated optimization profiles, not combined
ad hoc.

Implemented in GitHub issue #87. The optimizer now exposes
`cost_minimization_v1` as the only executable profile, routes provider selection
through `CostMetricProvider` and `CostOnlyScoringStrategy`, rejects invalid or
disabled profile combinations, and returns profile/result-schema metadata for
future Management API run history.

### Phase 4

Adds a Management API calculation-run store in the existing Management DB. It
must not create a separate optimizer database. It must preserve the current
Step-2 compatibility path while introducing typed run history.

Implemented in GitHub issue #88. The Management API now exposes
`/twins/{twin_id}/optimizer-runs` create/list/detail/select endpoints, stores
typed run and result-item records, validates optimizer profile metadata, updates
`optimizer_configurations` compatibility fields transactionally, and keeps the
optimizer service stateless.

### Phase 5

Implements Azure evidence first because the Azure Retail Prices API is public
and easiest to inspect broadly.

Implemented in GitHub issue #89. Azure Retail Prices rows can now be converted
into deterministic catalog snapshots and evidence reports with selected rows,
candidate rows, enriched rejected alternatives, normalization metadata, match
status, and review-required/publishability state.

### Phase 6

Updates Azure-specific tiering and cost formulas only after Azure evidence is
visible.

Implemented in GitHub issue #90. The executable scope is Azure-only and cost-only:
central unit/tier primitives, deterministic IoT Hub unit-tier selection,
Azure Digital Twins 1K meter normalization, Blob Storage per-operation
normalization, Logic Apps/Event Grid action normalization, and Azure transfer
tier calculation. Provider questions that need later live/e2e validation remain
documented as open research, not hidden as defaults.

### Phase 7

Applies the evidence model to AWS. AWS must preserve selected Price List
products, terms, price dimensions, and service-specific API evidence where
available.

Implemented in GitHub issue #91. AWS Price List products can now be converted
into deterministic evidence reports with selected product/term/price-dimension
identity, rejected alternatives, request scope, normalization metadata, and
review-required status for missing or ambiguous evidence. AWS calculation
formulas remain unchanged in this phase.

### Phase 8

Updates AWS-specific tiering and cost formulas only after AWS evidence is
visible.

Implemented in GitHub issue #92. AWS calculators now use shared unit/tier
primitives for IoT Core, S3 request/lifecycle operations, IoT TwinMaker
dimensions, Step Functions, EventBridge, and AWS transfer tiers. Missing
required AWS pricing fields fail visibly instead of producing silent zero cost.

### Phase 9

Fixes GCP pricing credential/permission validation before applying evidence
capture to GCP.

Implemented in GitHub issue #93. GCP now has a secret-redacted Billing Catalog
preflight for service/SKU listing and deterministic evidence reports for
selected Catalog SKU/rate identity, rejected alternatives, normalization
metadata, request scope, and review-required status. GCP formulas remain
unchanged until live Catalog evidence is validated.

### Phase 10

Validates the final cost-only path across providers and enforces that
publishable pricing contains no `fallback_static` values. The validation result
must be persistable as a Management API cost-calculation run with evidence
references.

Implemented in GitHub issue #94. The optimizer now has a structured
cross-provider cost validation gate that checks active cost intents across AWS,
Azure, and GCP, rejects missing provider evidence, rejects unresolved
`review_required` evidence in publishable mode, rejects `fallback_static`,
validates normalized units, validates the active `cost_minimization_v1`
optimization profile, and exposes selected evidence ids per provider/intent.
Calculation results now include `evidenceReferences`, and the Management API
run store rejects optimizer responses that omit evidence-reference metadata.

### Phase 16

Exposes intent-to-result traceability for calculation results without changing
legacy response consumers.

Implemented in GitHub issue #100. The Optimizer now returns additive
`trace_schema_version` and `intentTrace` metadata from `/calculate`. The trace
connects the selected optimization profile, bounded workload inputs and derived
usage values, selected provider/layer path, pricing source policy, canonical
units, formula binding, cost contribution, registry evidence references, and
verification state. Transfer costs are represented as segment-level
`transfer_trace` entries. The trace is read-only, bounded, and secret-free; raw
provider pricing rows, credentials, and full pricing payloads remain out of the
calculation response.

The completion slice in
`docs/plans/2026-07-17_intent_to_result_traceability_completion.md` additionally
assigns the existing `resultTrace` an explicit field-audit role. It adds canonical
selection/alternative/unsupported state, distinguishes provider alternatives from
rejected catalog evidence, labels shared contribution amounts non-additive, exposes
both traces through persisted Management API runs, and adds compact-by-default Flutter
drill-down. Historical runs remain readable.

### Phase 17

**Status:** Complete on 2026-07-17 in commit `4bf4a10` (`Refs #114`).

Removes the fabricated Azure Digital Twins `queryUnitTiers` field and replaces
it with an explicit workload contract for average query units and query response
size. The engine derives operation, routed-message, and query-unit billable
quantities, including Azure's 1 KB increments, before the calculator multiplies
them by normalized prices. Optimizer, Management API, persisted JSON, Flutter,
trace output, tests, and documentation must agree on the additive contract.

The completed implementation uses exact reviewed Azure Retail Prices evidence
for operation, message, and query-unit meters in `westeurope`, preserves the
selected catalog rows in the generated snapshot, and fails closed on drift.
The executable baseline explicitly reports zero ADT routed-message units because
it has no ADT Event Route. A read-only desktop integration gate compares the live
Optimizer and Management API input schemas field by field.

Implementation plan:
`2-twin2clouds/implementation_plans/2026-07-17_azure_digital_twins_billable_quantity_contract.md`.

### Phase 18

Must distinguish AWS IoT TwinMaker Basic, Standard, and Tiered Bundle pricing
modes. Basic is not functionally equivalent to the semantic L4 baseline.
Tiered Bundle is account-scoped and must not be allocated to one twin without
explicit aggregate context and an allocation policy. The application must
observe and model pricing mode but must never switch it automatically.

The final contract separates global, region-scoped AWS Price List evidence from
user-scoped `GetPricingPlan` observations persisted in Management API pricing
refresh runs. Public requests cannot inject trusted account context. Standard
is executable only when the account observation is fresh and compatible;
Basic, pending changes, and Tiered Bundle without explicit aggregate allocation
are excluded from AWS L4 comparison with structured diagnostics. The detailed
implementation plan is
`2-twin2clouds/implementation_plans/2026-07-17_aws_twinmaker_pricing_plan_contract.md`.

### Phase 18.1

Must remove the remaining last-writer-wins provider pricing cache before
route-aware transfer pricing. Public catalog snapshots become immutable and
keyed by provider plus canonical region, and every calculation persists exact
snapshot IDs and digests. Last-known-good and review state are isolated per
provider/region. This is tracked by
[#119](https://github.com/TVJunkie724/master-thesis/issues/119); Phase 19 is
blocked until this ownership boundary is complete.

The reviewed implementation plan is
`2-twin2clouds/implementation_plans/2026-07-17_immutable_region_pricing_catalogs.md`.
It separates committed read-only baseline seeds from the durable runtime
catalog volume, removes client-authored full pricing snapshots, and migrates
Pricing Health, Pricing Review, calculation history, and Twin Overview to one
exact three-provider reference contract.

### Phase 19

Must replace source-provider-only egress pricing with an immutable route
contract. Source/destination provider and region, transfer class, and
provider-specific network tier must select exact evidence. Unsupported routes
must fail closed. This phase prices the current five-layer edges only; the
future Eventing Layer bridge remains Phase 8 architecture work in issue #112.

### Phase 20

Must introduce a versioned `ResolvedDeploymentSpecification` that distinguishes
deployable resource choices from cumulative usage tiers, account-scoped plans,
and calculation-only assumptions. The selected calculation run must freeze the
supported SKU, capacity, memory, storage-class, billing-mode, and related
resource settings that materially affect the calculated cost. The Management
API must persist and digest the specification; the DeploymentManifest must
carry it without secrets; the Deployer must validate it against allowlisted
component contracts; and Terraform must consume typed values instead of making
independent business decisions. Provider-specific implementation is split only
after a complete optimizer-to-Terraform matrix has been approved. Phase 8
architecture profiles consume this boundary rather than defining a second
deployment-selection contract. This is pre-Phase-8 hardening, despite its
sequence number inside this pricing mini-roadmap, and it is blocked by the
canonical Five-Layer deployment-path cleanup in issue #117.

## Explicit Future Metrics

The architecture should make these possible, but they remain disabled/TBD:

- latency
- sustainability / carbon
- availability / resilience
- compliance / data residency
- operational complexity
- vendor lock-in
- deployment risk / permission risk

These metrics may be backed by APIs, official documentation, static files,
benchmark outputs, or model files. They must expose their evidence level instead
of pretending to be live cloud pricing.

## Required Extension Shape

Future metrics and calculation models must be added through explicit strategy
and provider contracts:

```text
OptimizationProfile
    +--> bundles compatible metrics, calculation models, scoring strategy,
         and intent groups

MetricProvider
    +--> declares metric id, enabled state, evidence level, required inputs
    +--> produces typed metric results

CalculationModel
    +--> converts evidence-backed inputs into metric values
    +--> declares compatible intent groups

ScoringStrategy
    +--> declares compatible metrics
    +--> ranks candidates from typed metric results

SourceAdapter
    +--> fetches or loads evidence for one metric/source type
    +--> never writes final optimizer decisions directly
```

The current thesis implementation enables only `cost`. Disabled future metrics
may be declared in configuration or documentation, but must not emit fake values
or participate in rankings.

## Implementation Governance

Every phase must satisfy these gates before implementation is considered ready:

- create or link the GitHub issue before implementation starts
- keep phase scope narrow and avoid adjacent refactors
- run deterministic unit/integration tests named in the phase plan
- do not run real cloud deployment E2E tests unless explicitly requested
- perform a review against this roadmap and the phase plan after implementation
- fix review findings before committing the phase implementation
- update this roadmap with issue numbers, status changes, and any approved
  scope changes

## Optimization Profile Rule

Optimization execution must be profile-based.

```text
optimization_profiles:
  cost_minimization_v1:
    enabled: true
    metric_providers:
      - cost
    calculation_models:
      - cost_model_v1
    scoring_strategy: min_total_cost_v1
    intent_groups:
      - cost
```

Future profiles such as latency minimization or weighted multi-objective
optimization may be declared as disabled/TBD. They must not execute until their
metric providers, calculation models, scoring strategies, and intent groups are
implemented and validated as a compatible bundle.

## Publishability Rule

Fallback is an emergency diagnostic path, not the target architecture.

Publishable pricing must satisfy:

- `fallback_static = 0`
- every active cost field has evidence or explicit non-applicability
- every derived value references source evidence
- every official-documentation value has a reproducible source reference
- every normalized unit is validated against the registry

## Registry API Rule

Registry read access must go through one typed service boundary. Internal cost
calculation code uses `PricingRegistryService`; external callers use read-only
Optimizer API endpoints. No API endpoint writes registry mappings or price
values.

## Persistence Rule

Do not introduce a separate optimizer database for Twin/User-scoped calculation
results. Cost runs are application data and belong to the existing Management
API database.

The current `optimizer_configurations.result_json` field may remain as a
compatibility/current-state bridge during migration, but typed
`CostCalculationRun` records are the target history model.

## Review Findings

- Fixed: Optimization strategy architecture is now a separate phase before
  provider-specific evidence implementation.
- Fixed: Future metrics are explicitly disabled/TBD, not fake scaffolding.
- Fixed: Provider evidence and tiering/calculation changes are split to avoid a
  single oversized refactor.
- Fixed: GCP credential repair is its own phase before GCP evidence work.
- Fixed: fallback is explicitly documented as emergency-only, not target state.
- Fixed: GitHub issue mapping is represented without inventing placeholder
  issue numbers.
- Fixed: pricing registry access is now its own typed contract/API phase.
- Fixed: optimization strategies are bundled through validated profiles so
  metric providers, calculation models, scoring strategies, and intent groups
  cannot drift apart.
- Fixed: cost calculation run persistence is now its own Management API phase
  and explicitly uses the existing Management DB.
- Fixed: optimizer-owned result databases are out of scope to avoid distributed
  Twin/User truth.
- Fixed: completed pricing schema/fetcher hardening is documented as the
  baseline that this roadmap builds on.
- Fixed: extension contracts now include `OptimizationProfile` and
  `CalculationModel`, not only metric/scoring/source contracts.
- Fixed: roadmap-level implementation governance is explicit.

No open findings after roadmap review.
