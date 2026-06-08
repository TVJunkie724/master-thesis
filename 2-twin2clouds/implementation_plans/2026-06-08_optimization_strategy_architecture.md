# Optimization Strategy Architecture

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

Depends on:

- `2026-06-08_pricing_registry_contract_api.md`

Related epic: GitHub issue #69

## Goal

Make cost optimization the first enabled optimization metric, not a hardcoded
optimizer assumption.

This phase creates extension seams for future optimization metrics and
calculation models while keeping the thesis implementation cost-only.

## Problem

The current optimizer is organized around cost calculation. That is acceptable
for the current thesis scope, but it makes future metrics harder to add:

- latency
- sustainability
- resilience
- compliance
- operational complexity
- vendor lock-in
- deployment risk

These metrics cannot all be fetched from cloud APIs. Some will be static files,
benchmarks, official documentation, or model-derived values. The architecture
must make that explicit.

## Target Architecture

```text
Usage Input
    |
    v
OptimizationProfileRegistry
    |
    +--> cost_minimization_v1             enabled
    +--> latency_minimization_v1          disabled / TBD
    +--> weighted_multi_objective_v1      disabled / TBD
    |
    v
ValidatedOptimizationProfile
    |
    +--> MetricProviderRegistry
    |       |
    |       +--> CostMetricProvider              enabled
    |       +--> LatencyMetricProvider           disabled / TBD
    |       +--> SustainabilityMetricProvider    disabled / TBD
    |       +--> ResilienceMetricProvider        disabled / TBD
    |
    v
ScoringStrategyRegistry
    |
    +--> CostOnlyStrategy                        enabled
    +--> WeightedMultiObjectiveStrategy          disabled / TBD
    +--> ConstraintFirstStrategy                 disabled / TBD
    |
    v
RankedOptimizationResult
```

The selected profile bundles compatible metric providers, calculation models,
scoring strategy, and intent groups. Callers must not configure these pieces
independently.

Persistence of concrete Twin-scoped calculation runs is outside the optimizer
service and belongs to the Management API run store phase.

## Scope

This phase must define the architecture and initial contracts. It must only
adapt the current cost path where required to sit behind the new contracts.

It must not:

- implement non-cost metrics
- create placeholder fake metric providers
- alter pricing evidence rules
- rewrite provider-specific pricing fetchers
- rewrite all calculation formulas
- change Flutter UI
- make disabled metrics visible as calculated optimizer output
- persist Twin/User-scoped calculation history in the optimizer service

## Proposed Files

```text
2-twin2clouds/backend/optimization/
  profiles.py
  metrics.py
  models.py
  scoring.py
  config.py
  context.py
```

The exact module names may be adjusted to fit existing optimizer package
boundaries during implementation.

## Metric Provider Contract

Each metric provider must expose:

```text
metric_id
enabled
evidence_level
required_inputs
compute(context) -> metric result
```

Metric provider implementations must be real for enabled metrics and absent for
disabled/TBD metrics. Disabled future metrics may exist as configuration entries
or documentation records, but not as classes returning placeholder values.

Allowed evidence levels:

- `api_backed`
- `official_documentation`
- `static_file`
- `benchmark_file`
- `model_assumption`
- `tbd`

Only cost is enabled in this phase.

## Strategy Contracts

The implementation must separate three responsibilities:

```text
MetricProvider
    +--> obtains or derives one metric from typed inputs

CalculationModel
    +--> converts evidence-backed inputs into metric values

ScoringStrategy
    +--> ranks candidates using one or more metric results
```

For this phase:

- `CostMetricProvider` is enabled.
- `CostCalculationModel` wraps the current cost calculation behavior.
- `CostOnlyStrategy` is the only enabled scoring strategy.
- `cost_minimization_v1` is the only enabled optimization profile.
- Future strategies are documented as disabled/TBD only.

The optimizer core must depend on these contracts, not on provider-specific
pricing fetcher internals.

The returned optimization result should be typed enough for the Management API
to persist a future `CostCalculationRun`, but this phase must not implement the
Management API run store itself.

Cost calculation must obtain registry metadata through `PricingRegistryService`
from the registry contract/API phase. It must not introduce new direct YAML
reads for intents, mappings, service models, or normalization rules.

## Optimization Profile Contract

Metric providers, calculation models, scoring strategies, and intent groups must
be bundled through a validated optimization profile.

Required profile fields:

```text
profile_id
enabled
metric_provider_ids
calculation_model_ids
scoring_strategy_id
intent_group_ids
evidence_requirements
result_schema_version
description
```

The optimizer must reject configurations that attempt to combine incompatible
pieces outside a profile.

Examples:

```yaml
optimization_profiles:
  cost_minimization_v1:
    enabled: true
    metric_provider_ids:
      - cost
    calculation_model_ids:
      - cost_model_v1
    scoring_strategy_id: min_total_cost_v1
    intent_group_ids:
      - cost
    evidence_requirements:
      pricing: evidence_backed
    result_schema_version: cost_result_v1

  latency_minimization_v1:
    enabled: false
    status: tbd
    metric_provider_ids:
      - latency
    calculation_model_ids:
      - latency_model_v1
    scoring_strategy_id: min_latency_v1
    intent_group_ids:
      - latency

  cost_latency_weighted_v1:
    enabled: false
    status: tbd
    metric_provider_ids:
      - cost
      - latency
    calculation_model_ids:
      - cost_model_v1
      - latency_model_v1
    scoring_strategy_id: weighted_sum_v1
    intent_group_ids:
      - cost
      - latency
```

Disabled/TBD profiles are documentation/configuration declarations only. They
must not produce result values or appear as executable options.

## Configuration Contract

The configuration must make the enabled profile and disabled future profiles
explicit:

```yaml
active_optimization_profile: cost_minimization_v1
optimization_profiles:
  cost_minimization_v1:
    enabled: true
    metric_provider_ids: [cost]
    calculation_model_ids: [cost_model_v1]
    scoring_strategy_id: min_total_cost_v1
    intent_group_ids: [cost]
```

Disabled metrics must not create fake outputs.

## Test Strategy

Required tests:

- cost metric is the only enabled metric by default
- disabled metrics do not affect ranking
- unknown enabled metric fails configuration validation
- unknown scoring strategy fails configuration validation
- unknown active optimization profile fails configuration validation
- incompatible metric/model/strategy/profile combinations fail validation
- disabled profile cannot be selected for execution
- cost-only strategy preserves current optimizer behavior for an existing
  fixture
- metric results include evidence level metadata
- provider-specific pricing fields do not leak directly into scoring strategy
- disabled/TBD metric declarations cannot produce result objects
- optimizer result contract is serializable by the Management API without
  giving the optimizer ownership of run history
- cost calculation accesses registry metadata through `PricingRegistryService`
- `cost_minimization_v1` result includes the active profile id and result schema
  version for Management API persistence

## Definition Of Done

- [ ] Cost is represented as an enabled metric provider.
- [ ] `cost_minimization_v1` is the only enabled optimization profile.
- [ ] Metric providers, calculation models, scoring strategy, and intent groups
  are selected through a validated profile.
- [ ] Future metrics are declared as disabled/TBD without fake implementations.
- [ ] Scoring strategy is explicit and defaults to cost-only.
- [ ] Existing cost optimization behavior remains unchanged for verified
  fixtures.
- [ ] Configuration validation rejects unknown enabled metrics or scoring
  strategies.
- [ ] Configuration validation rejects unknown, disabled, or incompatible
  optimization profiles.
- [ ] Documentation explains how a future developer can add a static-file or
  programmatic metric source.
- [ ] The optimizer can rank candidates through the cost-only strategy without
  importing provider-specific fetchers.
- [ ] The optimizer does not persist Twin/User-scoped calculation history.
- [ ] The optimizer does not add scattered direct registry-file reads.
- [ ] Optimization results include active profile metadata for run history.

## Self Review

### Architect Review

- Scope keeps the thesis behavior cost-only while creating a clean extension
  point.
- Future metrics are not over-engineered into fake classes.
- The evidence-level field prevents non-cost metrics from pretending to be API
  backed.
- Profile bundling prevents future strategies, models, metrics, and intent
  groups from drifting into invalid combinations.

### Builder Review

- Contracts and tests are concrete enough to implement without guessing.
- Existing cost behavior has a regression requirement.
- Disabled metric behavior is explicit.
- The active profile contract gives builders one place to validate compatibility
  before execution.

### Review Findings

- Fixed: plan forbids fake metric providers for disabled metrics.
- Fixed: evidence level is required for every metric result.
- Fixed: existing cost behavior must be protected by fixture regression tests.
- Fixed: provider-specific fetchers are kept behind metric/calculation
  boundaries.
- Fixed: disabled metrics cannot create placeholder result values.
- Fixed: calculation-run persistence is explicitly delegated to the Management
  API phase.
- Fixed: registry access is delegated to `PricingRegistryService`.
- Fixed: metric providers, calculation models, scoring strategies, and intent
  groups are bundled through validated optimization profiles.
- Fixed: disabled/TBD profiles cannot execute or produce placeholder results.
- Fixed: proposed module layout now includes profile and calculation-model
  modules.
- Fixed: result metadata must expose the active profile for Management API run
  storage.

No open findings after review.
