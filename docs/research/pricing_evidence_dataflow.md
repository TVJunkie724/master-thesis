# Pricing Evidence Dataflow

## Purpose

This note documents the planned dataflow for evidence-backed multi-cloud cost
calculation in Twin2MultiCloud. It is intended as thesis input and architecture
reference, not as a low-level implementation plan.

The dataflow explains how a provider-neutral optimization intent becomes an
auditable cost result across AWS, Azure, and Google Cloud without relying on
hidden defaults, string-matching assumptions, or publishable fallback values.

## High-Level Flow

```text
User / Twin Configuration
        |
        v
Business Intent
        |
        v
Workload Contract
        |
        v
Optimization Profile
        |
        v
Validated Optimization Bundle
        |
        +--> Metric Provider
        +--> Calculation Strategy
        +--> Formula Set
        +--> Pricing Model Classifications
        +--> Price Source Classifications
        +--> Provider Pricing Contracts
        +--> Scoring Strategy
        |
        v
Evidence / Price Resolution
        |
        v
Contract Validation
        |
        v
Provider-Specific Calculation
        |
        v
Scoring / Ranking
        |
        v
Result + Trace
```

## Step 1: Business Intent

The business intent describes what the user wants to optimize or compare. For
the current thesis scope, the executable intent is cost minimization for a
multi-cloud Digital Twin architecture.

Example:

```text
intent: compare_multi_cloud_digital_twin_cost
metric: cost
objective: minimize_total_monthly_cost
```

The intent must not contain provider-specific pricing assumptions. It defines
the comparison goal, not the pricing model.

## Step 2: Workload Contract

The workload contract converts user and Twin configuration into provider-neutral
usage inputs.

Example:

```text
workload_contract: digital_twin_workload_v1
fields:
  - messages_per_month
  - average_message_size_kb
  - number_of_devices
  - storage_gb
  - operation_count
  - transfer_gb
  - execution_count
  - execution_duration_ms
```

This is the shared boundary between providers. Providers may price services
differently, but they must consume workload fields from the same contract.

## Step 3: Optimization Profile

The optimization profile is the compatibility boundary. It prevents callers
from mixing unrelated metric providers, calculation strategies, formula sets,
source classifications, and scoring logic.

Example:

```text
optimization_profile: cost_minimization_v1
enabled: true
metric_provider: cost
calculation_strategy: cost_calculation_v2
formula_set: cost_formula_set_v1
pricing_model_classification_group: cost_pricing_models_v1
price_source_classification_group: cost_price_sources_v1
provider_pricing_contract_group: cost_provider_pricing_contracts_v1
workload_contract: digital_twin_workload_v1
scoring_strategy: min_total_cost_v1
```

Future profiles such as latency minimization or weighted multi-objective
optimization may exist as disabled declarations, but they must not emit fake
scores.

## Step 4: Pricing Model Classification

The pricing model classification explains how a provider service is priced.
This avoids embedding hidden pricing assumptions directly in provider-specific
calculation code.

Example:

```text
aws.iot.l1
  pricing_model_type: tiered_message_unit
  billing_unit_semantics: billable_message
  tier_semantics: graduated_monthly_usage
  included_usage: none
  region_scope: regional
  currency: USD
  review_status: verified

azure.iot.l1
  pricing_model_type: monthly_capacity_unit
  billing_unit_semantics: iot_hub_unit_per_month
  tier_semantics: capacity_tier_with_included_messages
  included_usage: tier_defined
  region_scope: regional
  currency: USD
  review_status: verified

gcp.iot.l1
  pricing_model_type: throughput_volume
  billing_unit_semantics: data_volume
  tier_semantics: volume_tiered_monthly_usage
  included_usage: free_tier_if_documented
  region_scope: regional_or_multi_region
  currency: USD
  review_status: verified
```

The calculation must not execute in publishable mode if the classification is
missing, ambiguous, unsupported, stale, or not reviewed.

## Step 5: Price Source Classification

The price source classification explains where a concrete price or model value
comes from. This is necessary because not every required value is fetchable from
a provider pricing API.

Allowed source classes:

```text
provider_api
official_static_documentation
official_calculator_reference
curated_model_constant
derived_from_provider_api
not_applicable
unsupported
fallback_static
```

Source semantics:

- `provider_api` is preferred for public list prices where provider APIs expose
  the required price and unit metadata.
- `official_static_documentation` is allowed for global/static official values,
  included quotas, or deterministic pricing rules that are not exposed by an
  API.
- `official_calculator_reference` may support deterministic provider-specific
  estimation semantics when no structured API is available.
- `curated_model_constant` is allowed for non-price model assumptions, such as
  month length or workload conversion constants, but must never masquerade as a
  fetched price.
- `derived_from_provider_api` is allowed when the value is reproducibly derived
  from provider API fields.
- `not_applicable` is allowed when a provider/service has no equivalent charge
  for a field.
- `unsupported` is an explicit non-publishable state.
- `fallback_static` is an emergency diagnostic state and is never publishable.

## Step 6: Provider Pricing Contract

The provider pricing contract binds the provider-specific pricing model to the
provider-neutral workload contract and the active formula set.

Example:

```text
aws.iot.l1
  pricing_model_classification: aws.iot.l1.tiered_message_unit.v1
  allowed_formula_refs:
    - CM
    - TieredUnit
  allowed_price_source_types:
    message_tiers:
      - provider_api
    connection_minutes:
      - provider_api
      - official_static_documentation
  consumed_workload_fields:
    - messages_per_month
    - average_message_size_kb
    - number_of_devices
  output_metric_unit: usd_per_month

azure.iot.l1
  pricing_model_classification: azure.iot.l1.monthly_capacity_unit.v1
  allowed_formula_refs:
    - CapacityTier
  allowed_price_source_types:
    unit_price:
      - provider_api
    included_messages:
      - provider_api
      - official_static_documentation
  consumed_workload_fields:
    - messages_per_month
  output_metric_unit: usd_per_month

gcp.iot.l1
  pricing_model_classification: gcp.iot.l1.throughput_volume.v1
  allowed_formula_refs:
    - CTransfer
    - TieredUnit
  allowed_price_source_types:
    throughput_tiers:
      - provider_api
    free_tier:
      - provider_api
      - official_static_documentation
  consumed_workload_fields:
    - messages_per_month
    - average_message_size_kb
    - data_volume_gb
  output_metric_unit: usd_per_month
```

The contract does not own formulas. It may only reference formula IDs that are
part of the active formula set owned by the calculation strategy.

## Step 7: Formula Set And Calculation Strategy

The calculation strategy owns the formula set. Provider-specific calculators
may only use formulas allowed by the active provider pricing contract.

Example:

```text
calculation_strategy: cost_calculation_v2
formula_set: cost_formula_set_v1
formula_refs:
  CM: message_based_cost
  CE: execution_based_cost
  CA: action_based_cost
  CS: storage_based_cost
  CU: user_based_cost
  CTransfer: transfer_cost
  CapacityTier: capacity_tier_cost
  TieredUnit: tiered_unit_cost
```

This prevents a provider calculator from silently choosing a formula that does
not belong to the active optimization profile.

## Step 8: Evidence Resolution

Evidence resolution selects the concrete provider data or reviewed static
source used for a field.

The result should preserve:

- selected provider SKU, meter, term, or API row
- selected official static source, where applicable
- selected curated non-price constant, where applicable
- rejected alternatives
- normalization steps
- source classification
- pricing model classification
- review status
- publishability status

This evidence is inspectable, but generated evidence artifacts are not the
editable SSOT. Long-lived mapping decisions remain in source-controlled registry
files.

## Step 9: Contract Validation

Before calculation results are trusted, validation must prove that the active
bundle is internally consistent.

Validation checks:

- the optimization profile is enabled
- workload fields required by the provider contract exist
- pricing model classification exists and is publishable
- every price/model field has an allowed source classification
- every required evidence field is present
- official/static values have source references and review metadata
- curated constants are classified as non-price model assumptions
- derived values reference source evidence
- units and tier semantics match the provider pricing contract
- formula references exist in the active formula set
- unsupported, ambiguous, stale, or fallback values are rejected in publishable
  mode

If validation fails, the system should return a typed validation error instead
of silently producing a cost estimate.

### Field-Level Verification Gates

Every active pricing field must pass deterministic verification before it can
contribute to publishable output.

```text
G1 Registry Completeness
G2 Source Buildability
G3 Evidence Presence
G4 Normalization
G5 Contract Compatibility
G6 Publishability
G7 Calculation Readiness
```

This means the system does not only test final totals. It proves, field by
field, whether a value was fetched from a provider API, loaded from official
static documentation, loaded as a curated non-price constant, derived from
provider evidence, declared not applicable, declared unsupported, or exposed as
diagnostic fallback only.

The verification result becomes part of the diagnostic trace so later
developers can inspect exactly why a field was accepted or rejected.

## Step 10: Provider-Specific Calculation

Provider-specific calculators translate validated provider evidence and
workload inputs into normalized monthly cost contributions.

Examples:

- AWS IoT Core may calculate tiered billable-message cost.
- Azure IoT Hub may calculate monthly capacity-unit cost.
- GCP Pub/Sub may calculate throughput-volume cost.

The common comparison boundary is not a universal provider price unit. The
common boundary is:

```text
same workload contract -> provider-specific pricing model -> usd_per_month
```

## Step 11: Scoring And Ranking

The scoring strategy ranks provider architecture candidates from typed metric
results.

For the current thesis scope:

```text
scoring_strategy: min_total_cost_v1
input_metric: usd_per_month
ranking: ascending total monthly cost
```

Future multi-objective strategies must be added as explicit disabled profiles
until their metrics, formula sets, and validation rules are implemented.

## Step 12: Result Trace

The final result must be inspectable. For each cost contribution, the trace
should answer why the value exists.

Trace fields:

- business intent
- workload input values
- optimization profile
- calculation strategy
- formula set
- provider pricing contract
- pricing model classification
- price source classification
- selected evidence
- rejected alternatives
- normalization before/after values
- formula reference
- result field
- final cost contribution

This trace is useful for development, audit review, and thesis explanation. It
also makes future pricing drift easier to diagnose because the chosen evidence
and classification path are visible.

## Compact Flow

```text
Intent
  -> WorkloadContract
  -> OptimizationProfile
  -> CalculationStrategy
  -> FormulaSet
  -> PricingModelClassification
  -> PriceSourceClassification
  -> ProviderPricingContract
  -> EvidenceResolution
  -> ContractValidation
  -> ProviderCalculation
  -> Scoring
  -> ResultTrace
```

## Key Design Decision

The design does not try to force every provider price into the same raw unit.
That would be incorrect for services whose billing models differ. Instead, the
system compares providers through:

```text
shared workload semantics + provider-specific pricing contracts + normalized
monthly cost output
```

This keeps the comparison auditable while preserving provider-specific pricing
semantics.
