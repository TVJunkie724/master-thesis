# AWS Pricing Evidence Implementation

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

GitHub issue: #91

Depends on:

- `2026-06-08_pricing_evidence_registry_foundation.md`
- `2026-06-08_pricing_registry_contract_api.md`
- `2026-06-08_optimization_strategy_architecture.md`

## Goal

Apply the evidence pipeline to AWS pricing. Preserve selected AWS products,
terms, price dimensions, query scopes, and alternatives before publishing cost
values.

## Problem

AWS Price List data is nested and can expose several plausible dimensions for a
single optimizer intent. The current fetcher collapses this into values and does
not preserve enough evidence to debug future catalog drift.

Some AWS pricing dimensions may also require service-specific APIs or official
service pricing evidence, for example AWS IoT TwinMaker pricing-plan details.

## Scope

This phase is AWS evidence only. It must not change AWS cost formulas yet.

It must not:

- update AWS tier calculations
- change Azure or GCP behavior
- create manual price overrides
- treat static defaults as provider evidence

## AWS Evidence Sources

Expected sources:

- AWS Price List Query API
- AWS Price List Bulk API where useful
- service-specific pricing APIs where available
- official AWS pricing pages only as reproducible official cloud evidence

## AWS Services In Scope

- Data Transfer
- AWS IoT Core
- AWS Lambda
- DynamoDB
- S3 Standard-IA
- S3 Glacier Deep Archive
- AWS IoT TwinMaker
- Amazon Managed Grafana
- Step Functions
- EventBridge
- API Gateway
- Scheduler

## Evidence Requirements

For every selected AWS value, preserve:

- ServiceCode
- product sku
- productFamily
- attributes
- offer term code
- rate code
- price dimension description
- unit
- begin/end range
- pricePerUnit
- filters used for `GetProducts`
- rejected dimensions and reasons

Evidence must be persisted as structured artifacts under the registry generated
evidence path. Logs may summarize the refresh, but logs are not sufficient for
diagnosing provider catalog drift.

## Implementation Steps

1. Add AWS raw snapshot writer for sanitized Price List products.
2. Add AWS candidate extraction preserving products, terms, and dimensions.
3. Add mapping rules for AWS services in scope.
4. Add selected/rejected dimension evidence output.
5. Add support for service-specific evidence where AWS Price List is insufficient.
6. Access intents, mappings, and normalization rules through
   `PricingRegistryService`, not direct YAML reads.
7. Add a developer-readable evidence report showing selected product, term,
   dimension, alternatives, and rejection reasons per intent.
8. Keep `pricing_dynamic_aws.json` generation compatible and review-required
   when evidence is missing.

## Test Strategy

Required fixtures:

- Lambda requests and GB-second dimensions
- Step Functions state transition dimensions
- API Gateway request dimensions
- S3 storage/request/retrieval dimensions
- DynamoDB read/write/storage dimensions
- IoT Core message/rule/device candidate ambiguity
- empty Grafana/TwinMaker evidence paths that become review-required

Required assertions:

- selected price dimension is preserved
- ambiguous dimensions become review-required
- missing dimensions are not replaced by publishable defaults
- derived fields require fetched source fields
- AWS evidence code uses `PricingRegistryService` for registry metadata

## Definition Of Done

- [x] AWS raw products are captured as sanitized snapshots.
- [x] AWS candidates preserve term and price dimension identity.
- [x] AWS selected and rejected evidence is inspectable.
- [x] AWS evidence reports expose the exact Price List dimension selected per
  intent.
- [x] AWS missing/ambiguous evidence is review-required.
- [x] AWS pricing output remains calculation-compatible.
- [x] No AWS static fallback is publishable.
- [x] AWS provider evidence code does not add scattered direct registry-file
  reads.

## Self Review

### Architect Review

- AWS-specific complexity is captured without changing formulas prematurely.
- Service-specific pricing APIs are allowed where Price List is insufficient.
- Static defaults are explicitly non-publishable.

### Builder Review

- Required AWS fields are concrete.
- Fixture targets map to known optimizer services.
- The phase boundary is clear.

### Review Findings

- Fixed: AWS IoT TwinMaker service-specific evidence is explicitly allowed.
- Fixed: Managed Grafana absence must be review-required, not hidden fallback.
- Fixed: selected AWS products/terms/dimensions must be inspectable in evidence
  reports, not only logs.
- Fixed: AWS evidence implementation depends on the registry service/API
  boundary.
- Fixed: AWS registry mappings use AWS-facing names such as `service_code`,
  `product_family`, and `storage_class`; the evidence builder translates those
  centrally to canonical candidate fields.
- Fixed: AWS offer term keys include the SKU prefix. Evidence now preserves the
  full `offerTermKey` and the extracted `offerTermCode`.

No open findings after review.

## Verification

- `docker compose exec -T 2twin2clouds sh -lc 'PYTHONPATH=/app pytest tests/unit/pricing/test_aws_pricing_evidence.py tests/unit/pricing/test_pricing_catalog_candidates.py -q'`
  - Result: `11 passed`
- `docker compose exec -T 2twin2clouds sh -lc 'PYTHONPATH=/app pytest tests/unit/pricing tests/unit/optimization tests/unit/calculation_v2 -q'`
  - Result: `182 passed`
