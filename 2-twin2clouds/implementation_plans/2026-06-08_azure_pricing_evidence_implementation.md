# Azure Pricing Evidence Implementation

## Issue Context

Parent roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

Depends on:

- `2026-06-08_pricing_evidence_registry_foundation.md`
- `2026-06-08_pricing_registry_contract_api.md`

## Goal

Implement the first provider-specific evidence pipeline for Azure. Azure is the
first provider because the Azure Retail Prices API is public, inspectable, and
well suited for deterministic fixtures.

## Problem

The current Azure fetcher returns final values but does not preserve enough
evidence:

- selected provider row
- candidate alternatives
- rejected rows and reasons
- exact request scope
- unit normalization path
- tier boundaries

Without this, a future developer cannot diagnose whether the wrong row was
selected after Azure changes product, SKU, meter, unit, or regional catalog
data.

## Scope

This phase must capture and expose Azure evidence. It must not change cost
formulas yet.

It must not:

- fix all Azure tiering
- update calculation logic
- implement AWS or GCP evidence
- create UI screens
- publish fallback-backed values as fresh

## Azure Services In Scope

The evidence pipeline must include these current optimizer services:

- Functions
- Storage / Blob Storage
- IoT Hub
- Azure Cosmos DB
- Digital Twins
- Managed Grafana
- Event Grid
- Logic Apps
- API Management
- Bandwidth

If the Retail Prices API uses unexpected service names, the evidence report must
show the attempted request and the absence of candidates.

## Evidence Requirements

For every Azure pricing intent, generated evidence must include:

```text
intent_id
field_path
retail_api_filter
region
selected_row
candidate_rows
rejected_rows
normalization_rule
normalized_value
currency
review_required
errors
```

Selected and candidate rows must preserve at least:

- serviceName
- productName
- skuName
- meterName
- unitOfMeasure
- retailPrice
- currencyCode
- armRegionName
- tierMinimumUnits
- meterId
- skuId
- productId

Evidence must be persisted as structured artifacts under the registry generated
evidence path. Logs may summarize a refresh, but logs are not the diagnostic
source of truth.

## Known Research Inputs

Current broad Azure checks show:

- Digital Twins returns `Standard Operations`, `Standard Message`, and
  `Standard Query Units`.
- IoT Hub returns Free, B1/B2/B3, and S1/S2/S3 unit rows.
- Logic Apps returns multiple action types and token meters.
- API Management returns both Consumption Calls and hourly SKU rows.
- Bandwidth returns multiple transfer-out prices and tiers.
- Grafana did not appear with the simple `serviceName == "Grafana"` filter and
  requires deeper provider investigation.

## Implementation Steps

1. Add Azure raw snapshot writer for sanitized Retail Prices rows.
2. Add Azure candidate extraction from snapshot rows.
3. Add Azure mapping rules for the services in scope.
4. Add selected/rejected row evidence output.
5. Add unit normalization through the registry, not hardcoded fetcher logic.
6. Access intents, mappings, and normalization rules through
   `PricingRegistryService`, not direct YAML reads.
7. Keep `pricing_dynamic_azure.json` generation compatible, but mark any missing
   evidence as `review_required`.
8. Add a developer-readable evidence report showing selected result,
   alternatives, and rejection reasons per intent.
9. Add tests for row preservation, selected row evidence, rejected alternatives,
   and ambiguity states.

## Test Strategy

Required deterministic fixtures:

- Digital Twins operations/messages/query unit rows
- IoT Hub Free/B/S tier rows
- Logic Apps built-in/standard/enterprise connector rows
- API Management Consumption Calls and hourly SKU rows
- Bandwidth multiple transfer tiers
- Storage rows with `10K`, `1 GB`, and `1 GB/Month`
- no Grafana rows found

Required assertions:

- selected row is preserved
- rejected alternatives are preserved
- ambiguous matches are `review_required`
- no candidate means `missing`, not fallback publish
- unit normalization references registry rules
- Azure evidence code uses `PricingRegistryService` for registry metadata

## Definition Of Done

- [ ] Azure raw rows are captured in sanitized snapshots.
- [ ] Azure candidates preserve provider row identity.
- [ ] Azure evidence includes selected and rejected rows.
- [ ] Azure evidence is inspectable without reading logs.
- [ ] Azure evidence reports expose the exact Retail Prices row selected per
  intent.
- [ ] Missing or ambiguous Azure evidence is review-required.
- [ ] Existing Azure pricing output remains calculation-compatible.
- [ ] No Azure static fallback is publishable.
- [ ] Azure provider evidence code does not add scattered direct registry-file
  reads.

## Self Review

### Architect Review

- Scope is limited to evidence, not calculation changes.
- Azure is correctly first because it is publicly inspectable.
- Known risky services are explicitly named.

### Builder Review

- Required row fields and fixtures are concrete.
- The plan says exactly what evidence must be preserved.
- Non-goals prevent tiering fixes from sneaking into this phase.

### Review Findings

- Fixed: Grafana is explicitly handled as investigation/missing evidence, not as
  a silent fallback.
- Fixed: calculation compatibility is required but formula changes are out of
  scope.
- Fixed: selected Azure provider rows must be inspectable in evidence reports,
  not only logs.
- Fixed: Azure evidence implementation depends on the registry service/API
  boundary.

No open findings after review.
