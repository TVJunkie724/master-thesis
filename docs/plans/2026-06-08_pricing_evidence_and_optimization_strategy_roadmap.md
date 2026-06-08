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
| Optimization strategy architecture | TBD | create before implementation if tracked separately |
| Cost calculation run store | TBD | create before Management API implementation |
| Provider-specific tiering/calculation reviews | TBD | create per provider before implementation |

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
| 3 | `2026-06-08_optimization_strategy_architecture.md` | planned | Make cost the first metric strategy, not a hardcoded optimizer assumption |
| 4 | `twin2multicloud_backend/implementation_plans/2026-06-08_cost_calculation_run_store.md` | planned | Persist typed Twin-scoped calculation runs in the existing Management DB |
| 5 | `2026-06-08_azure_pricing_evidence_implementation.md` | planned | Capture Azure raw rows, candidates, selected evidence, and rejected alternatives |
| 6 | `2026-06-08_azure_tiering_calculation_review.md` | planned | Review Azure tiers and adapt cost calculation where the current model is incomplete |
| 7 | `2026-06-08_aws_pricing_evidence_implementation.md` | planned | Capture AWS Price List and service-specific evidence with selected dimensions |
| 8 | `2026-06-08_aws_tiering_calculation_review.md` | planned | Review AWS tiers including IoT TwinMaker and adapt cost calculation where required |
| 9 | `2026-06-08_gcp_credentials_pricing_evidence.md` | planned | Fix GCP pricing credentials/permissions, then capture GCP Catalog evidence |
| 10 | `2026-06-08_cross_provider_cost_validation.md` | planned | Validate all cost intents across providers with zero publishable fallbacks |

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

### Phase 4

Adds a Management API calculation-run store in the existing Management DB. It
must not create a separate optimizer database. It must preserve the current
Step-2 compatibility path while introducing typed run history.

### Phase 5

Implements Azure evidence first because the Azure Retail Prices API is public
and easiest to inspect broadly.

### Phase 6

Updates Azure-specific tiering and cost formulas only after Azure evidence is
visible.

### Phase 7

Applies the evidence model to AWS. AWS must preserve selected Price List
products, terms, price dimensions, and service-specific API evidence where
available.

### Phase 8

Updates AWS-specific tiering and cost formulas only after AWS evidence is
visible.

### Phase 9

Fixes GCP pricing authentication and permissions before treating GCP Catalog data
as live evidence.

### Phase 10

Validates the final cost-only path across providers and enforces that
publishable pricing contains no `fallback_static` values. The validation result
must be persistable as a Management API cost-calculation run with evidence
references.

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
