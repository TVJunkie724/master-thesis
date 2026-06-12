# Contract-Backed Calculation Validation

## Metadata

- Phase: 14
- Status: implemented
- Parent roadmap: `docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`
- Depends on: Phase 12 and Phase 13
- Parent issues: #69, #32, #98
- Scope owner: `2-twin2clouds`
- No live cloud deployment E2E in this phase

## Goal

Validate that pricing evidence and calculation inputs satisfy the active
provider pricing contracts before cost calculation can run in publishable mode.

This phase closes the gap where a pricing payload can be schema-valid while the
calculation assumptions remain implicit in provider calculators.

## Target Flow

```text
calculate(request)
    -> resolve optimization bundle
    -> resolve provider pricing contracts
    -> resolve model/source classifications
    -> validate evidence and normalized fields
    -> allow calculation or return typed validation errors
```

## Implementation Steps

1. Add a contract validation service in `2-twin2clouds/backend/`.
   Suggested name: `pricing_contract_validation.py`.
2. Integrate the service with `backend/cross_provider_cost_validation.py`.
3. Validate both generated evidence reports and calculation pricing payloads.
4. Return structured validation errors with stable error codes.
5. Keep fallback/LKG diagnostic behavior available only outside publishable
   mode.
6. Do not rewrite formulas or provider calculation components in this phase.

## Implementation Notes

- Added `backend/pricing_contract_validation.py` with explicit gate reports for
  G1-G7 and deterministic error codes.
- Integrated contract validation into `backend/cross_provider_cost_validation.py`.
- Added field-level validation for registry completeness, source buildability,
  evidence presence, normalization, source/formula/workload/component
  compatibility, publishability, and calculation readiness.
- Added `get_provider_pricing_contract_for_field()` to `PricingRegistryService`
  so validators can resolve contracts by provider and pricing intent.
- Tightened `cost_calculation_v2` by declaring allowed calculation components.
- Aligned provider contract `required_evidence_fields` with the actual
  `pricing-evidence.v1` record shape.
- Kept formula behavior unchanged; this phase only validates that inputs are
  legal before calculation.

## Expected Touchpoints

- `2-twin2clouds/backend/pricing_contract_validation.py`
- `2-twin2clouds/backend/cross_provider_cost_validation.py`
- `2-twin2clouds/backend/pricing_evidence.py`
- `2-twin2clouds/backend/pricing_registry_service.py`
- `2-twin2clouds/tests/unit/pricing/test_contract_backed_calculation_validation.py`
- `2-twin2clouds/tests/unit/pricing/test_cross_provider_cost_validation.py`

## Data Ownership And Compatibility

- Validation reads registry SSOT and generated evidence artifacts.
- Validation must not write generated pricing files.
- Existing evidence report shape remains accepted where it satisfies the new
  contracts.
- Existing calculation requests fail only when publishability requirements are
  violated.

## Required Validation Checks

The service must validate:

- every active pricing field appears in the verification matrix
- every field has exactly one selected source path
- selected source path matches the field's `PriceSourceClassification`
- required pricing model classification exists
- pricing model classification is publishable
- every required source classification exists
- source classification is allowed by the provider pricing contract
- required fetched evidence fields are present
- official/static values include source URL and review metadata
- curated model constants are explicitly classified as non-price assumptions
- derived fields reference source evidence
- normalized units match contract expectations
- tier semantics match contract expectations
- every formula ref belongs to the active formula set
- every calculation component referenced by the contract exists
- publishable mode rejects fallback, unsupported, ambiguous, deprecated,
  review-required, or stale data

## Verification Gates

The validation service must expose explicit gates so the implementation can
prove field-level correctness instead of only testing final totals.

Gate order:

```text
G1 Registry Completeness
    -> every active provider/layer/service/field has model/source classification

G2 Source Buildability
    -> selected source type can be built by the declared build path

G3 Evidence Presence
    -> fetched/static/curated/derived/not-applicable/unsupported evidence exists

G4 Normalization
    -> source units are transformed into contract units with traceable rules

G5 Contract Compatibility
    -> source type, units, tiers, workload fields, and formula refs are allowed

G6 Publishability
    -> no fallback, unsupported, ambiguous, stale, deprecated, or review-required
       data enters publishable calculation

G7 Calculation Readiness
    -> provider calculator receives only validated fields
```

Each gate must return stable machine-readable status:

- `passed`
- `failed`
- `not_applicable`

Failures must include provider, layer, service, field, gate, error code, and a
secret-free explanation.

## Error Handling

Validation errors must be typed and deterministic.

Recommended error codes:

- `MISSING_PRICING_MODEL_CLASSIFICATION`
- `UNPUBLISHABLE_PRICING_MODEL_CLASSIFICATION`
- `MISSING_PRICE_SOURCE_CLASSIFICATION`
- `DISALLOWED_PRICE_SOURCE_TYPE`
- `MISSING_REQUIRED_EVIDENCE_FIELD`
- `INVALID_OFFICIAL_STATIC_SOURCE`
- `INVALID_CURATED_MODEL_CONSTANT`
- `INVALID_DERIVED_FIELD`
- `UNIT_SEMANTICS_MISMATCH`
- `TIER_SEMANTICS_MISMATCH`
- `UNKNOWN_FORMULA_REF`
- `UNKNOWN_CALCULATION_COMPONENT`
- `UNPUBLISHABLE_SOURCE_STATE`

Error responses must not include secrets, credential paths, or raw provider
payloads that could contain sensitive data.

## Security Requirements

- Validation must redact credential-like values from error details.
- Validation must not log raw credentials or local credential paths.
- API-facing errors must be stable enough for tests and UI diagnostics.
- Internal debug logs may include evidence IDs and sanitized provider IDs only.

## Non-Goals

- No formula rewrite.
- No provider fetcher rewrite except where validation adapters are required.
- No UI changes.
- No live provider E2E.
- No automatic repair or GPT matching.

## Test Plan

Add tests under `2-twin2clouds/tests/unit/pricing/`.

Required tests:

- AWS IoT L1 validates with tiered message provider API evidence
- Azure IoT Hub L1 validates with capacity unit provider API evidence and
  verified included-message source
- GCP Pub/Sub L1 validates with throughput-volume evidence
- official static source is accepted only when allowed by the contract
- official static source is rejected for a field requiring provider API evidence
- unsupported source marked publishable is rejected
- stale model classification is rejected
- ambiguous source classification is rejected
- missing tier metadata is rejected
- wrong normalized unit is rejected
- formula ref outside `cost_formula_set_v1` is rejected
- error messages are stable and secret-free
- all verification gates pass for representative AWS/Azure/GCP happy paths
- each gate has at least one deterministic failing test
- final calculation is blocked when any active field fails a required gate

Recommended command:

```bash
cd 2-twin2clouds
python -m pytest \
  tests/unit/pricing/test_cross_provider_cost_validation.py \
  tests/unit/pricing/test_contract_backed_calculation_validation.py \
  -q
```

## Definition Of Done

- [x] Contract validation service exists with typed errors.
- [x] Publishable mode validates classifications, sources, evidence, units,
      tiers, and formula refs.
- [x] Field-level verification gates exist and block calculation on failures.
- [x] Every active pricing field is verified before provider calculators run.
- [x] Fallback and unsupported values cannot pass publishable validation.
- [x] Non-fetchable official/static values pass only when verified and allowed.
- [x] Existing cross-provider validation tests remain green.
- [x] New negative tests cover drift and source misuse.
- [x] Roadmap phase 14 is updated to implemented when the phase is complete.

## Review Gate

Before commit:

- [x] Run the phase-specific pytest command.
- [x] Run `git diff --check`.
- [x] Review representative negative cases for unit drift, source misuse, and
      stale classifications.
- [x] Review that all error output is secret-free.
- [x] Update this plan with implementation notes and completed checkbox state.

## Verification

```bash
cd 2-twin2clouds
/tmp/t2mc-phase12-py311/bin/python -m pytest \
  tests/unit/pricing/test_cross_provider_cost_validation.py \
  tests/unit/pricing/test_contract_backed_calculation_validation.py \
  -q
```

Result: 26 passed.

```bash
cd 2-twin2clouds
/tmp/t2mc-phase12-py311/bin/python -m pytest \
  tests/unit/pricing/test_pricing_registry_foundation.py \
  tests/unit/pricing/test_pricing_model_source_classification.py \
  tests/unit/pricing/test_strategy_formula_pricing_contract_bundle.py \
  tests/unit/pricing/test_pricing_registry_api.py \
  tests/unit/optimization/test_optimization_profiles.py \
  -q
```

Result: 63 passed, 1 warning.

```bash
cd 2-twin2clouds
/tmp/t2mc-phase12-py311/bin/python -m pytest \
  tests/unit/pricing \
  tests/unit/optimization \
  --ignore=tests/unit/pricing/test_pricing_schema.py \
  -q
```

Result: 190 passed, 1 warning. The ignored `test_pricing_schema.py` expects
the historical Docker path `/app/json/pricing.json` during local collection.

```bash
git diff --check
```

Result: clean.

## Review Findings Fixed In Plan

- Fixed: schema-valid pricing payloads are not enough for calculation.
- Fixed: non-fetchable official/static values get explicit validation.
- Fixed: error handling is typed and secret-safe.
- Fixed: publishable mode remains zero-fallback.
