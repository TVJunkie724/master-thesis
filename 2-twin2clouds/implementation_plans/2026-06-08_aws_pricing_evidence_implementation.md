# AWS Pricing Evidence Implementation

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

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

- [ ] AWS raw products are captured as sanitized snapshots.
- [ ] AWS candidates preserve term and price dimension identity.
- [ ] AWS selected and rejected evidence is inspectable.
- [ ] AWS evidence reports expose the exact Price List dimension selected per
  intent.
- [ ] AWS missing/ambiguous evidence is review-required.
- [ ] AWS pricing output remains calculation-compatible.
- [ ] No AWS static fallback is publishable.
- [ ] AWS provider evidence code does not add scattered direct registry-file
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

No open findings after review.
