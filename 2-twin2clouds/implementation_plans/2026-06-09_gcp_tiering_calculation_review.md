# GCP Tiering And Unit-Aware Calculation Review

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

GitHub issue: #95

Depends on:

- `2026-06-08_gcp_credentials_pricing_evidence.md` (#93)
- `2026-06-08_cross_provider_cost_validation.md` (#94)

## Goal

Review Google Cloud service tiering, billing units, and calculation formulas,
then update GCP cost calculation only where official Google Cloud pricing
documentation or Billing Catalog evidence proves the current model incomplete or
wrong.

The final state must bring GCP to the same implementation-plan quality level as
the Azure and AWS tiering hardening phases: evidence-backed formulas, explicit
unit normalization, visible failure for missing required prices, and deterministic
tests for low, boundary, and high-volume usage.

## Problem

GCP currently has pricing credential preflight and evidence reports, but the
calculation formulas remain simpler than the Azure and AWS hardened paths. The
current GCP calculators still risk treating provider billing dimensions as flat
unit prices, even though official Google Cloud pricing includes throughput,
storage, request, operation, free-tier, regional, network-tier, and tiered-rate
dimensions.

This is not thesis-ready as a final GCP cost model. It is acceptable as the
completed #93 evidence baseline, but it must not be presented as final
provider-specific GCP hardening.

## Scope

This phase is GCP-only and cost-only.

It must review and harden the executable GCP cost path for:

- Pub/Sub as the current IoT/message-ingest equivalent
- Firestore as the current hot storage/read/write equivalent
- Cloud Storage for cool/archive storage, request operations, and retrieval
- Workflows for orchestration/state-transition equivalents
- Cloud Run functions / Cloud Functions for function request and compute cost
- Compute Engine for self-hosted digital twin/Grafana equivalents
- API Gateway / Service Control only where the executable layer model uses it
- Cloud Scheduler only where the executable layer model uses it
- VPC/network transfer for cross-provider egress

It must not:

- change AWS or Azure calculations
- add non-cost optimization metrics
- introduce runtime LLM matching
- introduce a manual price override table as final truth
- require real cloud deployment E2E
- make review-required or fallback-backed GCP data publishable
- add a Flutter pricing editor

## Official Research Inputs

The implementation must verify current behavior against these official Google
Cloud references before changing formulas:

- Pub/Sub pricing: <https://cloud.google.com/pubsub/pricing>
- Firestore pricing: <https://cloud.google.com/firestore/pricing>
- Cloud Storage pricing: <https://cloud.google.com/storage/pricing>
- Workflows pricing: <https://cloud.google.com/workflows/pricing>
- Cloud Run pricing, including Cloud Run functions billing context:
  <https://cloud.google.com/run/pricing>
- Compute pricing overview: <https://cloud.google.com/products/compute/pricing>
- VPC/network pricing: <https://cloud.google.com/vpc/pricing>
- Cloud Billing Pricing API:
  <https://docs.cloud.google.com/billing/docs/reference/pricing-api/rest>
- Cloud Billing pricing tiers:
  <https://docs.cloud.google.com/billing/docs/how-to/pricing-table>

If live Billing Catalog evidence differs from the documentation examples, the
implementation must preserve the Catalog SKU/rate identity in the evidence
report and mark the mismatch as review-required instead of guessing.

## Current GCP Calculator Risks

The review must explicitly check these current-model risks:

| Service | Current risk to review | Required target behavior |
|---|---|---|
| Pub/Sub | Flat `pricePerGiB * data_volume_gb` can miss 1 KB request minimums, throughput units, storage, free throughput, and transfer dimensions. | Normalize throughput/storage/transfer separately and document which usage dimensions are represented by the thesis input model. |
| Firestore | Reads/writes/storage are simplified and deletes/index-entry reads/free quota may be omitted. | Normalize document operations, storage GiB-month, delete/index assumptions, and free-tier applicability only with official evidence. |
| Cloud Storage | Storage classes and request/retrieval/minimum-duration dimensions can be collapsed into a single storage price. | Separate storage class, operation class, retrieval, and minimum-duration/early-deletion assumptions where executable. |
| Workflows | Single `pricePerStep` can hide internal/external step distinction and 1,000-step increments. | Calculate internal and external steps separately, including official free usage and increment rounding where represented. |
| Cloud Run functions | Legacy Cloud Functions assumptions can drift from the current Cloud Run-backed pricing model. | Map request/CPU/memory/GB-second inputs to the current executable contract or explicitly mark missing dimensions review-required. |
| Compute Engine | A single `e2MediumPrice` can hide vCPU, memory, disk, region, sustained-use, and machine-family assumptions. | Separate machine assumption from disk/storage assumption and document non-modeled discounts as non-goals. |
| Network transfer | Single egress price can hide region, Premium/Standard tier, intra-zone, intra-region, inter-region, and internet transfer differences. | Use tier-aware transfer evidence when the source/destination intent can be resolved; fail visibly otherwise. |

## Target Architecture

```text
GCP Billing Catalog / official pricing docs
        |
        v
GCP evidence report (#93)
        |
        v
PricingRegistryService
        |
        +--> normalized GCP service-model assumptions
        +--> provider mapping decisions
        +--> unit conversion rules
        |
        v
GCP calculation components
        |
        +--> require normalized price keys
        +--> calculate tiers with shared unit/tier helpers
        +--> raise explicit missing-price errors
        |
        v
Cross-provider validation (#94)
        |
        v
Management API cost run history
```

The calculation code must not read generated pricing/evidence files directly.
It must consume pricing data through the same typed registry/calculation
boundary used by the existing cost model.

## Service Model Decisions To Record

The implementation must update `2-twin2clouds/pricing_registry/service_models.yaml`
with a `gcp_calculation_model` section that records:

- status: `planned_for_phase_11` before implementation, then
  `reviewed_for_phase_11` after implementation
- issue: `95`
- assumptions for each executable service
- explicit non-goals for discounts, custom contracts, non-modeled regions, or
  thesis inputs that cannot express a provider billing dimension
- open research items that require later real cloud or thesis-evaluation E2E

Provider-specific mapping decisions must remain in registry mapping/review files,
not embedded as hardcoded string matching inside calculators.

## Implementation Steps

Every step is required and must not be skipped.

1. Inventory the current GCP calculation components and list every pricing key
   they consume.
2. Compare each consumed key against the GCP evidence report shape and the
   official research inputs listed above.
3. Add or extend provider-independent unit/tier helpers only if existing helpers
   cannot correctly express Google Cloud billing units.
4. Update `service_models.yaml` with the GCP calculation assumptions before
   changing formulas.
5. Harden Pub/Sub calculation:
   - normalize throughput units
   - model request-size minimums only when the workload input exposes message
     count and payload size
   - separate storage and transfer dimensions where represented
   - fail visibly when required throughput/storage/transfer prices are missing
6. Harden Firestore calculation:
   - normalize reads, writes, deletes, and storage separately
   - document index-entry read and named-database assumptions
   - apply free-tier behavior only when official evidence and workload scope make
     it valid
7. Harden Cloud Storage calculation:
   - separate storage class prices
   - normalize Class A/Class B or equivalent operation units
   - include retrieval pricing where the active archive/cool intent requires it
   - document minimum-duration/early-deletion handling
8. Harden Workflows calculation:
   - distinguish internal and external steps
   - apply 1,000-step billing increments and official free usage where applicable
   - preserve backward compatibility only through a single normalization boundary
9. Harden Cloud Run functions / Cloud Functions calculation:
   - map current request and compute inputs to Cloud Run-backed pricing fields
   - distinguish request, CPU, memory, and execution-time dimensions where the
     thesis input model supports them
   - mark missing dimensions review-required instead of fabricating defaults
10. Harden Compute Engine calculation:
    - separate machine family/type assumption from disk/storage assumption
    - require explicit machine price evidence for selected type/region
    - document sustained-use, committed-use, Spot, and custom-contract discounts
      as non-goals unless explicit evidence is added
11. Harden network transfer calculation:
    - separate intra-zone, intra-region, inter-region, internet egress, and
      network-tier assumptions where the intent can identify them
    - use cumulative tier calculation for tiered internet egress
    - fail visibly when the route cannot be mapped to a supported transfer intent
12. Update cross-provider validation fixtures so publishable GCP evidence remains
    zero-fallback and non-review-required for supported intents.
13. Update this plan and the roadmap with implementation notes, verification
    results, and any open research that remains after review.

## Error Handling And Security

- Missing required GCP price fields must raise typed calculation errors. They
  must not return zero, `None`, or fallback values.
- Error messages must include provider, service, intent, missing field, and
  evidence id where available.
- Error messages must not include credential file paths, service-account JSON,
  private keys, tokens, billing account IDs where not necessary, or raw request
  bodies.
- Billing Catalog authentication failures remain in the #93 preflight boundary;
  formula code must not perform ad hoc credential checks.
- Review-required evidence must remain visible in validation output and must
  block publishable mode.

## Test Strategy

No real GCP deployment E2E is required.

Required automated tests:

- new `tests/unit/calculation_v2/test_gcp_tiering.py`
- Pub/Sub tests for throughput, storage, transfer, request-size minimum handling
  when supported, and missing required prices
- Firestore tests for reads, writes, deletes, storage, free-tier boundary, and
  index-entry read assumptions
- Cloud Storage tests for storage class, operation unit normalization, retrieval,
  minimum-duration/early-deletion assumptions, and missing required prices
- Workflows tests for internal/external steps, 1,000-step increments, free-tier
  boundaries, and legacy-key normalization
- Cloud Run functions tests for request and compute dimensions supported by the
  current input model
- Compute Engine tests for machine-price/disk separation and missing required
  fields
- Transfer tests for cumulative tiers and unsupported route failures
- cross-provider validation tests proving GCP publishable mode rejects
  `fallback_static`, unresolved `review_required`, and missing evidence

Required verification commands:

```bash
docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/calculation_v2/test_gcp_tiering.py -q'

docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/pricing/test_gcp_pricing_evidence.py tests/unit/pricing/test_cross_provider_cost_validation.py tests/unit/calculation_v2 -q'

docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/pricing tests/unit/optimization tests/unit/calculation_v2 -q'
```

## Documentation Updates

The implementation must update:

- this implementation plan with implementation notes and verification results
- `docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`
  with Phase 11 status
- `2-twin2clouds/pricing_registry/service_models.yaml` with reviewed GCP
  assumptions and remaining research

No separate user-facing pricing-editor documentation is required in this phase.

## Definition Of Done

- [x] GitHub issue #95 is linked from the roadmap and this plan.
- [x] GCP service model assumptions are documented in the editable SSOT.
- [x] GCP calculation changes are evidence-backed by Billing Catalog evidence or
  reproducible official Google Cloud pricing documentation.
- [x] No GCP calculation uses `fallback_static` as publishable data.
- [x] Pub/Sub, Firestore, Cloud Storage, Workflows, Cloud Run functions, Compute
  Engine, and transfer calculations either use supported normalized fields or
  fail visibly with typed errors.
- [x] Tiered and unit-normalized service tests cover low, boundary, and high
  usage volumes.
- [x] Cross-provider validation still rejects missing, fallback, or
  review-required GCP evidence in publishable mode.
- [x] Existing optimizer API and Management API run-history contracts remain
  compatible.
- [x] No real cloud deployment E2E is introduced.
- [x] Implementation notes and verification results are recorded before commit.

## Implementation Notes

- GCP Pub/Sub now supports tiered throughput pricing, explicit per-GiB/per-TiB
  pricing, optional storage/transfer dimensions, and 1 KB minimum request-size
  billing when the workload exposes message count and average payload size.
- GCP Cloud Run functions / Cloud Functions now require normalized request and
  GB-second prices; per-million request keys are normalized at the component
  boundary.
- Firestore now separates write, read, delete, index-entry read, and storage
  dimensions. Free storage is applied only when an explicit free-storage field is
  present.
- Cloud Storage Nearline/Coldline now separates storage, write/Class A,
  read/Class B, and retrieval pricing. Missing required operation prices fail
  visibly when that usage dimension is used.
- Workflows now supports internal/external step pricing as separate dimensions
  while preserving legacy single per-step keys through one normalization
  boundary.
- Compute Engine self-hosted equivalents now require explicit VM-hour and disk
  storage prices instead of falling back to hidden defaults. GCP L4/L5 remain
  disabled in the optimizer path unless the existing `allowGcpSelfHostedL4/L5`
  inputs opt into comparison.
- GCP transfer now uses tiered transfer pricing when available and fails visibly
  if no supported GCP egress price can be resolved.

## Implementation Verification

Verification commands:

```bash
docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/calculation_v2/test_gcp_tiering.py -q'

docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/calculation_v2/test_core_formulas.py tests/unit/calculation_v2/test_gcp_tiering.py tests/unit/calculation_v2/test_engine.py -q'

docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/pricing/test_gcp_pricing_evidence.py tests/unit/pricing/test_cross_provider_cost_validation.py tests/unit/calculation_v2/test_gcp_tiering.py -q'
```

Observed results before final full-suite verification:

- `tests/unit/calculation_v2/test_gcp_tiering.py`: `17 passed`
- `test_core_formulas.py`, `test_gcp_tiering.py`, `test_engine.py`: `42 passed`
- `test_gcp_pricing_evidence.py`, `test_cross_provider_cost_validation.py`,
  `test_gcp_tiering.py`: `37 passed`
- `tests/unit/pricing tests/unit/optimization tests/unit/calculation_v2`:
  `235 passed`

## Self Review

### Architect Review

- Scope is GCP-only and cost-only, matching the missing provider hardening gap.
- The plan separates evidence (#93), validation (#94), and formula hardening
  (#95), so previous completed work is not redefined retroactively.
- Provider pricing facts are tied to official Google Cloud documentation and
  Billing Catalog evidence rather than string heuristics or manual overrides.
- Failure modes are explicit and block publishable pricing instead of creating
  hidden defaults.

### Builder Review

- Each target service names concrete billing dimensions to inspect and either
  implement or mark review-required.
- Implementation steps are ordered so registry assumptions are recorded before
  formulas are changed.
- The test strategy names the expected new test file, boundary cases, and full
  regression commands.
- No builder should need a follow-up question to know whether live deployment
  E2E, UI editor work, AWS/Azure changes, or non-cost metrics are in scope.

### Review Findings

- Fixed: GCP tiering/calculation hardening is now a separate phase instead of
  being implied by the completed GCP evidence phase.
- Fixed: official Google Cloud pricing sources are named before implementation,
  including Billing Catalog/Pricing API tier semantics.
- Fixed: fallback remains an emergency diagnostic path and is explicitly
  forbidden for publishable GCP output.
- Fixed: plan includes concrete tests and verification commands.
- Fixed: GCP calculators no longer return silent zero/default values when
  required supported pricing fields are missing.
- Fixed: GCP transfer now follows the same tier-aware path as AWS/Azure.
- Fixed: GCP Workflows internal/external step pricing is supported without
  changing AWS/Azure behavior.
- Fixed after implementation review: the engine docstring still described a
  simplified GCP egress fallback; it now documents that GCP requires explicit
  egress pricing or tier data.

No open findings after plan review.
