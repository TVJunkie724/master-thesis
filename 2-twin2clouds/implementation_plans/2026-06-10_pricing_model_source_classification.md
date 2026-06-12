# Pricing Model And Source Classification

## Metadata

- Phase: 12
- Status: planned
- Parent roadmap: `docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`
- Parent issues: #69, #32, #96
- Scope owner: `2-twin2clouds`
- No live cloud deployment E2E in this phase

## Goal

Introduce explicit, versioned classifications for provider pricing models and
price sources. This removes the current implicit assumption that provider
calculators "know" how each service is priced.

The phase must make non-fetchable official/static values safe and auditable
without treating them as `fallback_static`.

## Problem

The optimizer currently has evidence records and publishability checks, but the
semantic reason why a provider field is usable is still partly implicit:

- provider services use different pricing models
- not every required value is available from a provider pricing API
- official static documentation, curated model constants, and derived values
  are not the same thing as emergency fallback values
- publishable mode cannot reliably distinguish verified static evidence from a
  hidden hardcoded value unless source classification is explicit

## Target Architecture

```text
PricingRegistryService
        |
        +--> pricing_model_classifications.yaml
        +--> price_source_classifications.yaml
        |
        v
Typed classification objects
        |
        v
Publishability validation
```

## Contracts To Add

### PricingModelClassification

Fields:

- `id`
- `provider`
- `layer`
- `service`
- `pricing_model_type`
- `billing_unit_semantics`
- `tier_semantics`
- `included_usage_semantics`
- `region_scope`
- `currency`
- `effective_date`
- `evidence_source_refs`
- `review_status`
- `publishable`

Allowed `review_status` values:

- `verified`
- `review_required`
- `ambiguous`
- `unsupported`
- `deprecated`
- `stale`

### PriceSourceClassification

Fields:

- `id`
- `provider`
- `layer`
- `service`
- `field`
- `source_type`
- `region_scope`
- `currency`
- `effective_date`
- `retrieved_at`
- `reviewed_at`
- `source_url`
- `api_request_id`
- `catalog_sku_id`
- `review_status`
- `publishable`

Allowed `source_type` values:

- `provider_api`
- `official_static_documentation`
- `official_calculator_reference`
- `curated_model_constant`
- `derived_from_provider_api`
- `not_applicable`
- `unsupported`
- `fallback_static`

## Implementation Steps

1. Add registry files under `2-twin2clouds/pricing_registry/`.
   - `pricing_model_classifications.yaml`
   - `price_source_classifications.yaml`
2. Add typed loaders and validators in `backend/pricing_registry_service.py` or
   a small sibling module if the service becomes too large.
3. Validate duplicate IDs, unknown providers, unknown status values, missing
   required metadata, and invalid publishability combinations.
4. Add API read access in `api/pricing_registry.py` only if the current registry
   API pattern can expose it without write capability.
5. Keep generated evidence artifacts unchanged in this phase.
6. Update docs/research notes only if naming changes during implementation.

## Expected Touchpoints

- `2-twin2clouds/pricing_registry/pricing_model_classifications.yaml`
- `2-twin2clouds/pricing_registry/price_source_classifications.yaml`
- `2-twin2clouds/backend/pricing_registry_service.py`
- `2-twin2clouds/api/pricing_registry.py`
- `2-twin2clouds/tests/unit/pricing/test_pricing_model_source_classification.py`
- `2-twin2clouds/tests/unit/pricing/test_pricing_registry_api.py`

## Data Ownership And Compatibility

- Classification files are source-controlled registry SSOT.
- Generated evidence artifacts are not edited by this phase.
- No optimizer database or Management API database migration is required.
- Existing pricing evidence and calculation responses remain backward-compatible.

## Security Requirements

- Classification files must not contain credentials, account IDs, local
  credential paths, or raw provider authentication errors.
- API output, if added, must expose read-only sanitized classification metadata
  only.
- Validation errors must include stable field paths and error codes, but no raw
  secret-bearing payloads.

## Publishability Rules

Publishable mode must reject:

- `fallback_static`
- `unsupported`
- `ambiguous`
- `deprecated`
- `review_required`
- stale classifications
- official/static sources without source URL and review metadata
- price-like values classified as `curated_model_constant`

Publishable mode may accept:

- verified `provider_api` values
- verified `official_static_documentation` values
- deterministic `official_calculator_reference` values
- verified `derived_from_provider_api` values
- explicit `not_applicable` fields
- `curated_model_constant` only for non-price model assumptions

## Field-Level Verification Matrix

This phase must introduce a machine-readable verification matrix for every
active pricing field. The matrix is the gate that proves every field has an
explicit source path and publishability decision.

Required matrix columns:

- `provider`
- `layer`
- `service`
- `field`
- `pricing_model_classification_id`
- `price_source_classification_id`
- `allowed_source_types`
- `selected_source_type`
- `expected_build_path`
- `required_evidence_refs`
- `normalization_rule_refs`
- `publishable`
- `review_status`
- `verification_status`
- `failure_reason`

Allowed `expected_build_path` values:

- `fetched_from_provider_api`
- `loaded_from_official_static_documentation`
- `loaded_from_official_calculator_reference`
- `loaded_from_curated_model_constant`
- `derived_from_provider_api`
- `declared_not_applicable`
- `declared_unsupported`
- `diagnostic_fallback_only`

Verification rules:

- every active provider/layer/service/field must have exactly one matrix row
- the selected source type must be allowed by the provider pricing contract
- API-backed fields must reference selected provider evidence
- official/static fields must reference official source metadata
- curated constants must be marked as non-price assumptions
- derived fields must reference their source fields and derivation rule
- `not_applicable` fields must include a reason
- `unsupported` fields must be non-publishable
- `fallback_static` fields must be non-publishable and diagnostic-only

## Non-Goals

- No formula rewrite.
- No provider fetcher rewrite.
- No calculation orchestration rewrite.
- No editable UI.
- No live cloud E2E.
- No automatic GPT/LLM classification.

## Test Plan

Add unit tests under `2-twin2clouds/tests/unit/pricing/`.

Required tests:

- valid pricing model classifications load successfully
- valid source classifications load successfully
- duplicate classification IDs fail
- unknown source type fails
- unknown review status fails
- `fallback_static` cannot be publishable
- `unsupported` cannot be publishable
- official static source without source URL fails
- official static source without `reviewed_at` fails unless documented as
  timeless/global
- curated model constant cannot be marked as a fetched price
- `not_applicable` requires explicit reason metadata
- stale classification fails publishability
- registry API, if exposed, returns read-only classification records
- every active pricing field appears in the verification matrix
- each source type has at least one positive and one negative verification case
- source-type/build-path mismatches fail validation
- matrix rows with missing evidence refs fail validation

Recommended command:

```bash
cd 2-twin2clouds
python -m pytest \
  tests/unit/pricing/test_pricing_registry_api.py \
  tests/unit/pricing/test_pricing_model_source_classification.py \
  -q
```

## Definition Of Done

- [ ] Classification registry files exist and are versioned.
- [ ] Typed loader validates model and source classifications.
- [ ] Publishability rejects unsafe source states.
- [ ] Non-fetchable official/static values are represented without using
      `fallback_static`.
- [ ] Field-level verification matrix covers every active provider/layer/field.
- [ ] Each supported source type has deterministic positive and negative tests.
- [ ] No secrets or credentials are stored in classification files.
- [ ] Tests cover positive, negative, and publishability paths.
- [ ] Roadmap phase 12 is updated to implemented when the phase is complete.

## Review Gate

Before commit:

- [ ] Run the phase-specific pytest command.
- [ ] Run `git diff --check`.
- [ ] Review that no `fallback_static` source is publishable.
- [ ] Review that official/static sources have source and review metadata.
- [ ] Update this plan with implementation notes and completed checkbox state.

## Review Findings Fixed In Plan

- Fixed: non-fetchable official/static values are no longer treated as a gap.
- Fixed: `pricing_model` is no longer implicit provider-specific code knowledge.
- Fixed: `fallback_static` remains emergency-only and non-publishable.
- Fixed: review status and source metadata are part of the contract.
