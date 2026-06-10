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
| GCP tiering and unit-aware calculation | #95 | implemented on this branch |
| Provider-specific tiering/calculation reviews | #90/#92/#95 | implemented baseline; live/e2e finalization remains later |
| Strategy/formula/pricing-contract bundle | TBD | planned |
| Contract-backed calculation validation | TBD | planned |
| Calculation strategy execution refactor | TBD | planned |
| Intent-to-result traceability | TBD | planned |

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
Calculation Strategy / Scoring Strategy
        |
        +--> cost-only                 enabled
        +--> weighted multi-objective  disabled / TBD
        +--> constraint-first          disabled / TBD
        |
        v
Ranked Architecture Candidates
```

The selected optimization profile is the compatibility boundary. Users and
callers must not freely mix metric providers, calculation strategies, formula
sets, provider pricing contracts, scoring strategies, workload contracts, and
intent groups. A profile validates that those pieces belong together before
execution.

```text
OptimizationProfile
    |
    +--> metric providers
    +--> calculation strategy
    +--> formula set
    +--> provider pricing contracts
    +--> workload contract
    +--> scoring strategy
    +--> compatible intent groups
    +--> enabled/disabled state
```

Calculation strategies own their formula sets. Provider calculators must not
implicitly pick formulas outside the selected strategy. This matters because
provider pricing models are not always reducible to the same normalized price
unit: AWS IoT Core is tiered per billable message, Azure IoT Hub is monthly
capacity-unit pricing, and GCP Pub/Sub is throughput-volume pricing. The shared
boundary is the workload contract and final metric output, not a false universal
provider price unit.

```text
OptimizationProfile: cost_minimization_v1
        |
        v
CalculationStrategy: cost_calculation_v2
        |
        +--> WorkloadContract: digital_twin_workload_v1
        +--> FormulaSet: cost_formula_set_v1
        |       +--> CM / message_based_cost
        |       +--> CE / execution_based_cost
        |       +--> CA / action_based_cost
        |       +--> CS / storage_based_cost
        |       +--> CU / user_based_cost
        |       +--> CTransfer / transfer_cost
        |       +--> CapacityTier / capacity_tier_cost
        |       +--> TieredUnit / tiered_unit_cost
        |
        +--> ProviderPricingContracts
                +--> aws.iot.l1: tiered_message_unit
                +--> azure.iot.l1: monthly_capacity_unit
                +--> gcp.iot.l1: throughput_volume
```

Provider pricing contracts bind evidence fields to the calculation strategy.
Each contract declares which source evidence is required, which formula refs are
allowed, which workload fields are consumed, which provider-specific normalized
fields are produced, and which final metric unit is emitted.

```text
ProviderPricingContract
    +--> provider / layer / service
    +--> pricing_model
    +--> required_evidence_fields
    +--> curated_model_constants
    +--> normalization_rules
    +--> allowed_formula_refs
    +--> calculation_component
    +--> consumed_workload_fields
    +--> output_metric_unit
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
| 11 | `2026-06-09_gcp_tiering_calculation_review.md` | implemented (#95) | Review GCP tiers/units and adapt cost calculation where the current model is incomplete |
| 12 | `TBD_strategy_formula_pricing_contract_bundle.md` | planned | Formalize the versioned bundle between optimization profile, calculation strategy, formula set, provider pricing contracts, and workload contract |
| 13 | `TBD_contract_backed_calculation_validation.md` | planned | Validate fetched pricing/evidence against provider pricing contracts before calculation can run in publishable mode |
| 14 | `TBD_calculation_strategy_execution_refactor.md` | planned | Refactor calculation execution so provider calculators are selected through the active calculation strategy and allowed formula set |
| 15 | `TBD_intent_to_result_traceability.md` | planned | Expose an inspectable trace from intent and selected evidence through normalization, formula application, and final result fields |

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
only cost enabled. Strategies, metric providers, calculation strategies, formula
sets, provider pricing contracts, and intent groups must be selected through
validated optimization profiles, not combined ad hoc.

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

### Phase 11

Completes the missing provider-specific hardening step for GCP. This phase must
review Google Cloud billing units and tiers for Pub/Sub, Firestore, Cloud
Storage, Workflows, Cloud Run functions, Compute Engine, and transfer pricing.
It must update GCP formulas only where Billing Catalog evidence or official
Google Cloud pricing documentation proves the current model incomplete or wrong.

Implemented in GitHub issue #95. The executable scope is GCP-only and cost-only:
tiered Pub/Sub throughput, Firestore operation/storage normalization, Cloud
Storage operation/retrieval normalization, Workflows internal/external step
normalization, Cloud Run functions request/GB-second normalization, Compute
Engine VM/disk separation, GCP transfer tiering, typed missing-price failures,
and continued rejection of fallback or review-required GCP data in publishable
mode. This phase did not run real cloud deployment E2E and did not change AWS or
Azure behavior.

### Phase 12

Formalizes the missing strategy contract layer. This phase creates the
versioned SSOT that explicitly binds:

- optimization profile
- calculation strategy
- formula set
- workload contract
- provider pricing contracts
- compatible intent groups
- executable/disabled state

This phase must not rewrite calculation formulas yet. It defines the source of
truth and validation schema that later phases consume.

Required target bundle:

```text
cost_minimization_v1
    -> calculation_strategy: cost_calculation_v2
    -> scoring_strategy: min_total_cost_v1
    -> formula_set: cost_formula_set_v1
    -> workload_contract: digital_twin_workload_v1
    -> pricing_contract_group: cost_provider_pricing_contracts_v1
```

Provider pricing contracts must allow different provider models under the same
business intent. Example for L1 ingestion:

```text
aws.iot.l1
    pricing_model: tiered_message_unit
    allowed_formula_refs: [CM, TieredUnit]
    consumed_workload_fields:
      - messages_per_month
      - average_message_size_kb
      - number_of_devices
    output_metric_unit: usd_per_month

azure.iot.l1
    pricing_model: monthly_capacity_unit
    allowed_formula_refs: [CapacityTier]
    consumed_workload_fields:
      - messages_per_month
    output_metric_unit: usd_per_month

gcp.iot.l1
    pricing_model: throughput_volume
    allowed_formula_refs: [CTransfer, TieredUnit]
    consumed_workload_fields:
      - messages_per_month
      - average_message_size_kb
      - data_volume_gb
    output_metric_unit: usd_per_month
```

Definition of Done:

- Versioned YAML or JSON registry files exist for calculation strategies,
  formula sets, workload contracts, and provider pricing contracts.
- `PricingRegistryService` or a sibling typed service can load and validate the
  new contracts without HTTP calls.
- Cost-only remains the only executable strategy.
- Future metric strategies may be declared disabled/TBD only; they must not
  emit fake scores.
- Tests reject unknown formula refs, unknown workload fields, incompatible
  profile bundles, missing provider pricing contracts, and duplicate contract
  ids.

### Phase 13

Adds contract-backed validation between fetched evidence/pricing payloads and
the active calculation strategy. This phase closes the current gap where a
pricing payload can be schema-valid while the calculation assumptions remain
implicit in provider calculators.

This phase must not change formula behavior. It validates that every active
provider/layer has the fields and evidence sources required by its provider
pricing contract.

Validation must check:

- required fetched evidence fields are present
- required curated model constants are explicitly listed and source-classified
- derived fields reference valid source fields
- normalized provider fields match the contract unit
- every calculation component referenced by the contract exists
- every formula ref belongs to the active strategy formula set
- publishable mode rejects fallback/static emergency values

Definition of Done:

- Cross-provider validation uses provider pricing contracts, not only broad
  intent ids and schema keys.
- AWS/Azure/GCP L1 ingestion validates despite different pricing models.
- Invalid examples fail deterministically: AWS message tiers marked per-million
  but consumed as per-message, Azure IoT Hub missing included-message
  thresholds, GCP Pub/Sub missing GiB unit metadata, and formula refs outside
  `cost_formula_set_v1`.
- Unit tests cover positive and negative contract validation paths.

### Phase 14

Refactors calculation execution to use the active calculation strategy as the
entry point. Provider calculators remain provider-specific, but they are no
longer just implicitly called by the engine. The active strategy must select
which formula set and provider pricing contracts are legal for the run.

This phase is allowed to touch calculation orchestration. It should keep
existing public `/calculate` behavior compatible unless a request explicitly
selects an unsupported strategy.

Required execution flow:

```text
calculate(request)
    -> resolve optimization profile
    -> resolve calculation strategy
    -> resolve formula set
    -> validate workload contract
    -> validate provider pricing contracts
    -> execute provider/layer calculators
    -> score candidates
    -> return result + contract metadata
```

Definition of Done:

- `cost_calculation_v2` is the only executable calculation strategy.
- Formula helpers used by calculators are traceable to `cost_formula_set_v1`.
- Provider calculators fail if invoked with pricing fields not compatible with
  their pricing contract.
- Result metadata includes optimization profile id, calculation strategy id,
  formula set id, pricing contract group id, and workload contract id.
- Existing cost calculation tests remain green and new tests prove that
  disabled/future strategies cannot execute.

### Phase 15

Adds an inspectable intent-to-result trace for developer/thesis validation and
future UI diagnostics. This phase answers: "Why did this final cost field have
this value?"

The trace must connect:

- business intent or provider contract id
- selected provider evidence row or curated decision
- rejected alternatives, where available
- normalization rule and before/after value
- calculation formula ref
- workload inputs consumed by the formula
- final result field and cost contribution

This phase must not introduce editable UI. It may expose read-only API output
and deterministic JSON artifacts.

Definition of Done:

- A single calculation result can be inspected from intent/contract through
  selected evidence and formula application to final monthly cost.
- Trace output redacts credentials and excludes raw secret material.
- The trace covers at least AWS IoT Core, Azure IoT Hub, GCP Pub/Sub, AWS
  Managed Grafana, Azure Managed Grafana, and one storage service.
- Tests verify trace completeness and stable ids for snapshot comparison.
- Thesis documentation can use the trace as evidence that different provider
  pricing models are compared through a shared workload/monthly-cost boundary,
  not through a false universal price unit.

## Phase Readiness Review

Every phase below was reviewed against the plan-readiness criteria: clear goal,
explicit scope and non-goals, narrow side effects, typed contract boundaries,
test strategy, no real cloud deployment E2E, documentation/update target, and a
verifiable Definition of Done.

| Phase | Readiness result | Fixes made during review |
|---|---|---|
| 1 | Ready as foundation architecture plan. | No change required; provider-specific formula work remains explicitly out of scope. |
| 2 | Ready after issue-mapping cleanup. | Phase issue was corrected from `TBD` to #32. |
| 3 | Ready as strategy/profile architecture plan. | No change required; disabled future metrics are explicit non-executable declarations. |
| 4 | Ready as Management API persistence plan. | No change required; optimizer-owned DB remains out of scope. |
| 5 | Ready as Azure evidence plan. | No change required; formula changes remain out of scope for this phase. |
| 6 | Ready as Azure tiering/calculation plan. | No change required; tests and evidence boundary are explicit. |
| 7 | Ready as AWS evidence plan. | No change required; formula changes remain out of scope for this phase. |
| 8 | Ready as AWS tiering/calculation plan. | No change required; tests and missing-price behavior are explicit. |
| 9 | Ready as GCP credential/evidence plan only. | Roadmap wording was clarified so #93 is not treated as GCP formula hardening. |
| 10 | Ready as cross-provider validation plan. | No change required; publishable mode rules remain explicit. |
| 11 | Implemented after plan review. | GCP formulas now use supported normalized fields or fail visibly with typed errors; tests cover tier/unit boundaries. |
| 12 | Ready as strategy/formula/pricing-contract bundle plan. | Added explicit formula-set ownership under calculation strategy and provider pricing contracts for heterogeneous cloud pricing models. |
| 13 | Ready as contract-backed validation plan. | Added negative validation cases for unit drift, missing tier metadata, missing curated constants, and formula refs outside the active formula set. |
| 14 | Ready as execution refactor plan. | Clarified that calculation orchestration must resolve the active strategy before selecting formulas or provider calculators. |
| 15 | Ready as traceability plan. | Added read-only intent-to-result trace requirements with evidence, rejected alternatives, normalization, formula refs, and redaction. |

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

Future metrics and calculation strategies must be added through explicit
strategy and provider contracts:

```text
OptimizationProfile
    +--> bundles compatible metrics, calculation strategy, formula set,
         provider pricing contracts, scoring strategy, workload contract, and
         intent groups

MetricProvider
    +--> declares metric id, enabled state, evidence level, required inputs
    +--> produces typed metric results

CalculationStrategy
    +--> converts evidence-backed inputs into metric values
    +--> owns/references one compatible FormulaSet
    +--> declares compatible ProviderPricingContracts
    +--> declares compatible WorkloadContract and intent groups

FormulaSet
    +--> declares formula refs, inputs, output units, and calculation semantics
    +--> belongs to a compatible CalculationStrategy

ProviderPricingContract
    +--> binds provider evidence fields to formula refs and workload fields
    +--> allows provider-specific pricing models under a shared business intent

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
    calculation_strategy: cost_calculation_v2
    formula_set: cost_formula_set_v1
    pricing_contract_group: cost_provider_pricing_contracts_v1
    workload_contract: digital_twin_workload_v1
    scoring_strategy: min_total_cost_v1
    intent_groups:
      - cost
```

Future profiles such as latency minimization or weighted multi-objective
optimization may be declared as disabled/TBD. They must not execute until their
metric providers, calculation strategies, formula sets, provider pricing
contracts, scoring strategies, workload contracts, and intent groups are
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
  metric providers, calculation strategies, formula sets, provider pricing
  contracts, scoring strategies, workload contracts, and intent groups cannot
  drift apart.
- Fixed: cost calculation run persistence is now its own Management API phase
  and explicitly uses the existing Management DB.
- Fixed: optimizer-owned result databases are out of scope to avoid distributed
  Twin/User truth.
- Fixed: completed pricing schema/fetcher hardening is documented as the
  baseline that this roadmap builds on.
- Fixed: extension contracts now include `OptimizationProfile`,
  `CalculationStrategy`, `FormulaSet`, and `ProviderPricingContract`, not only
  metric/scoring/source contracts.
- Fixed: roadmap-level implementation governance is explicit.
- Fixed: Phase 2 issue mapping no longer contains a stale `TBD`.
- Fixed: GCP evidence (#93) and GCP tiering/calculation hardening (#95) are now
  separate phases.
- Fixed: per-phase readiness review is documented so each phase can be used as
  an implementation handoff without relying on chat context.
- Fixed: formula ownership is explicit; provider calculators may only use
  formulas allowed by the active calculation strategy and provider pricing
  contract.

No open findings after roadmap review.
