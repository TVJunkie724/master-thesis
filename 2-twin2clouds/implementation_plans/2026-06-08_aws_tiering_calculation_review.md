# AWS Tiering And Calculation Review

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

GitHub issue: #92

Depends on:

- `2026-06-08_aws_pricing_evidence_implementation.md`

## Goal

Review AWS service tiering and update AWS cost calculations only where AWS
evidence proves the current calculation model is incomplete or wrong.

## Problem

AWS services may expose tiered pricing, per-request pricing, monthly unit
pricing, free tiers, and provider-specific billing modes. The current cost model
must be reviewed against evidence, especially for Digital Twin equivalent
services.

## Scope

This phase is AWS-only and cost-only.

It must not:

- change Azure or GCP calculations
- add non-cost metrics
- introduce manual price overrides
- publish fallback-backed values

## Review Targets

### AWS IoT TwinMaker

Must verify:

- entities
- unified data access API calls
- queries
- any pricing plan or tiering model exposed by AWS service-specific APIs or
  official evidence

### AWS IoT Core

Must verify:

- message tiering
- rule/action pricing
- device shadow / registry dimensions where relevant
- mapping to optimizer IoT usage model

### AWS Lambda

Must verify:

- request pricing
- GB-second pricing
- free request and compute tiers as official cloud evidence

### AWS Transfer / S3 / DynamoDB

Must verify:

- transfer tier boundaries
- storage classes
- read/write/request/retrieval units
- free storage tiers as official cloud evidence

### AWS Managed Grafana / API Gateway / Step Functions / EventBridge / Scheduler

Must verify:

- billing modes
- per-user/month versus request/event/action units
- tier boundaries where applicable

## Implementation Steps

1. Compare AWS formulas against captured AWS evidence.
2. Document each service model decision in `service_models.yaml`.
3. Update only formulas proven incomplete or wrong.
4. Add boundary tests for every changed tier formula.
5. Add regression tests for low, medium, and high usage.
6. Ensure AWS calculations consume normalized evidence fields.

## Test Strategy

Required tests:

- IoT TwinMaker dimensions are calculated separately.
- IoT Core tier selection changes with message volume.
- Lambda free tiers are represented as official cloud evidence, not fallback.
- Transfer and S3 tiers handle boundaries.
- DynamoDB read/write/storage units normalize correctly.
- Step Functions/API Gateway/EventBridge/Scheduler unit conversions are stable.

## Definition Of Done

- [x] AWS service model assumptions are documented in the editable SSOT.
- [x] AWS calculation changes are evidence-backed.
- [x] No AWS calculation uses fallback_static as publishable data.
- [x] Tiered service tests cover boundaries.
- [x] Existing optimizer API contract remains compatible.

## Self Review

### Architect Review

- Calculation work is correctly delayed until AWS evidence exists.
- TwinMaker and IoT tiering are first-class review targets.
- Free tiers must be official evidence, not defaults.

### Builder Review

- Review targets and tests are concrete.
- Scope prevents cross-provider churn.

### Review Findings

- Fixed: AWS Lambda free tiers are explicitly official-evidence work, not
  fallback work.
- Fixed: TwinMaker pricing plan/tiering is explicitly included.
- Fixed: Missing required AWS unit prices initially still returned silent zero
  through the generic helper. Required AWS prices now fail visibly.
- Fixed: Existing engine fixtures used legacy `tierPricing` or omitted IoT
  tiers. Fixtures now use canonical `pricing_tiers`.
- Fixed: AWS EventBridge now distinguishes explicit per-event prices from true
  per-million legacy keys.
- Fixed: Conditional AWS retrieval and model-storage prices initially still
  defaulted to zero when those usage dimensions were used. They now fail
  visibly and have regression tests.

No open findings after review.

## Verification

- `docker compose exec -T 2twin2clouds sh -lc 'PYTHONPATH=/app pytest tests/unit/calculation_v2/test_core_formulas.py tests/unit/calculation_v2/test_aws_tiering.py tests/unit/calculation_v2/test_pricing_keys.py -q'`
  - Result: `41 passed`
- `docker compose exec -T 2twin2clouds sh -lc 'PYTHONPATH=/app pytest tests/unit/pricing tests/unit/optimization tests/unit/calculation_v2 -q'`
  - Result: `198 passed`
