# Pricing Evidence Registry Foundation

## Issue Context

Parent epic: GitHub issue #69

Primary active issue: GitHub issue #32

Roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

## Goal

Create the first enterprise-grade slice toward reliable cloud pricing without
quick fixes, hidden defaults, or untraceable keyword choices.

This slice defines the editable pricing SSOT and evidence pipeline that future
provider-specific work must use. It does not attempt to fix every provider,
tier, or calculation model at once.

## Problem

The optimizer currently needs prices for provider-neutral calculation intents,
but provider catalogs expose provider-specific products, SKUs, meters, units,
tiers, regions, and billing modes. The previous implementation mixed three
different things:

- values fetched from cloud provider APIs
- values derived from fetched values
- static fallback/default values

That made generated pricing files look complete even when some fields were not
backed by current provider evidence.

The required target is stricter:

```text
publishable pricing must have fallback_static = 0
```

If a value is not directly returned by a provider pricing API, it must still be
backed by official cloud evidence that can be re-queried, reproduced, or traced
to a stable provider source. The registry may edit mapping and normalization
decisions, but it must not become a manual price table.

## Mini Roadmap

Only one slice should be implemented and reviewed at a time.

| Step | Status | Purpose |
|---|---|---|
| 1. Evidence Registry Foundation | planned | Define editable SSOT, evidence contract, and zero-fallback publish rules |
| 2. Optimization Strategy Architecture | future | Make cost the first metric strategy and keep future metrics disabled/TBD |
| 3. Azure Evidence Implementation | future | Implement provider-row capture and mapping for Azure first |
| 4. Azure Tiering and Calculation Review | future | Fix Azure Digital Twins, IoT Hub, transfer, storage, and related tier calculations |
| 5. AWS Evidence Implementation | future | Apply the same evidence model to AWS Price List and service-specific APIs |
| 6. AWS Tiering and Calculation Review | future | Fix AWS IoT TwinMaker, IoT, transfer, storage, Grafana, and related tier calculations |
| 7. GCP Credential and Evidence Implementation | future | Fix GCP auth/permissions, then capture and map GCP Catalog evidence |
| 8. Cross-Provider Calculation Validation | future | Validate all provider-neutral intents and calculation formulas against the final evidence model |

## Target Architecture

```text
                 +---------------------------------+
                 | Editable Pricing Registry SSOT  |
                 | intents / provider mappings /   |
                 | normalization / service models  |
                 +---------------+-----------------+
                                 |
                                 v
+------------------+     +------------------+     +--------------------+
| Cloud Pricing    | --> | Raw Catalog      | --> | Pricing Candidate  |
| APIs             |     | Snapshots        |     | Extraction         |
| AWS/Azure/GCP    |     | sanitized rows   |     | all possible rows  |
+------------------+     +------------------+     +---------+----------+
                                                              |
                                                              v
                                                    +--------------------+
                                                    | Deterministic      |
                                                    | Matcher            |
                                                    | selected/rejected  |
                                                    +---------+----------+
                                                              |
                                                              v
                                                    +--------------------+
                                                    | Unit Normalizer    |
                                                    | 1M/100K/10K/GB/GiB |
                                                    | GB-s/GiB-hour/tier |
                                                    +---------+----------+
                                                              |
                                                              v
                                                    +--------------------+
                                                    | Evidence Report    |
                                                    | chosen row, query, |
                                                    | alternatives       |
                                                    +---------+----------+
                                                              |
                                                              v
                                                    +--------------------+
                                                    | Publish Gate       |
                                                    | fallback_static=0  |
                                                    +---------+----------+
                                                              |
                                                              v
                                                    +--------------------+
                                                    | Calculation Input  |
                                                    +--------------------+
```

## Editable SSOT

The SSOT must be editable source files, not generated pricing output.

Proposed structure:

```text
2-twin2clouds/pricing_registry/
  intents.yaml
  normalization.yaml
  service_models.yaml
  providers/
    azure/mappings.yaml
    aws/mappings.yaml
    gcp/mappings.yaml
  review_decisions.yaml
  generated/
    evidence/
    snapshots/
```

`generated/` artifacts are written by the pipeline. They may be inspected, but
they are not the editable source of truth.

The registry is an evidence and mapping SSOT, not a manually curated price
catalog. A developer may edit intents, unit normalization, mapping constraints,
service-model assumptions, and reviewed decisions. They must not edit generated
prices to make validation pass.

### `intents.yaml`

Defines provider-neutral calculation intents owned by the optimizer cost model.

Examples:

- `digital_twin.message_1k`
- `digital_twin.operation_1k`
- `digital_twin.query_unit_1k`
- `iot.hub_unit_month`
- `iot.message_tier`
- `functions.request`
- `functions.compute_gb_second`
- `storage.cool.gb_month`
- `transfer.egress_gb_tier`

### `normalization.yaml`

Defines exact unit conversions and rejects ambiguous conversions.

Required examples:

- `1M` to per-one or per-million
- `100K` to per-one or per-million
- `10K` to per-one or per-million
- `1K` to per-one or per-thousand
- `GB` versus `GiB`
- `GB Second` versus `GiB Second`
- `GB Hour` versus `GiB Hour`
- tier minimums, maximums, and free-tier boundaries

### `service_models.yaml`

Defines how pricing dimensions are used by the optimizer calculation model.

This file must explicitly capture tiering assumptions. Digital Twins, AWS IoT
TwinMaker, IoT Hub, transfer pricing, and storage operation tiers must be
reviewed here before calculation changes are implemented.

### `providers/*/mappings.yaml`

Defines deterministic provider-specific mapping rules:

- provider service identifier
- product name constraints
- SKU constraints
- meter constraints
- unit constraints
- region scope
- tier constraints
- negative/exclusion rules
- normalization rule id
- expected result cardinality

### `review_decisions.yaml`

Stores reviewed mapping and interpretation decisions. It must not store arbitrary
price overrides.

Allowed review decisions:

- approve a provider row mapping
- reject a provider row mapping
- document why a provider dimension is not applicable
- document how an official provider tier model maps to an optimizer service model
- document a temporary emergency fallback as non-publishable

If a value is not direct provider API data, the decision must include a stable
official cloud source, source date, reason, reviewer, version, and the method
used to reproduce or re-check it.

Static fallback values must not live here unless explicitly marked as emergency
and non-publishable.

## Evidence Contract

Every generated price field must be inspectable.

Required evidence shape:

```text
provider
intent_id
field_path
source_type
source_api
request_scope
selected_row
candidate_rows
rejected_rows
normalization_rule
normalized_value
currency
region
tier
mapping_version
registry_version
fetched_at
review_required
errors
```

Allowed `source_type` values:

- `fetched`
- `derived`
- `official_cloud_evidence`
- `not_applicable`
- `fallback_static`

Publishable output must not contain `fallback_static`.

Publishable output must also reject `official_cloud_evidence` entries that lack
a reproducible source reference. A future developer must be able to re-check the
chosen value or tier model without reading old chat context.

This evidence must be available as a structured artifact, not only as log
output. The selected provider result, candidate alternatives, and rejection
reasons must be inspectable after a refresh so future drift can be debugged
without rerunning the exact same cloud query.

## Scope For This Slice

This slice must only create the foundation plan and, when implemented later,
the empty/initial registry contract plus validation scaffolding.

It must not:

- rewrite all provider fetchers
- rewrite calculation formulas
- change Flutter UI
- create a manual admin product
- silently accept static fallbacks as valid pricing
- rely on GPT/LLM runtime matching

## Implementation Steps For The Future Slice

1. Add `pricing_registry/` with initial YAML files and schema documentation.
2. Add Python loaders and validators for registry files.
3. Add an evidence schema module for selected/candidate/rejected rows.
4. Add deterministic validation that fails when:
   - an intent has no provider mapping
   - a normalization rule is missing
   - a provider mapping can match multiple rows without an ambiguity state
   - a publishable result contains `fallback_static`
   - official cloud evidence has no reproducible source reference
   - a review decision attempts to override a price without provider evidence
5. Add tests with small provider fixtures for:
   - Azure Digital Twins rows
   - Azure IoT Hub tier rows
   - Azure Logic Apps mixed action rows
   - Azure Bandwidth tier rows
   - unit normalization edge cases
6. Update the pricing reliability roadmap with the new slice boundary and issue
   links.

## Test Strategy

No live cloud E2E is required for this foundation slice.

Required tests:

- registry YAML parses and validates
- unknown intent fails validation
- unknown normalization rule fails validation
- ambiguous provider row match returns `review_required`
- `fallback_static` fails publish validation
- unit conversion fixtures cover `1M`, `100K`, `10K`, `1K`, `GB`, `GiB`,
  `GB Second`, and `GiB Hour`
- evidence output preserves selected row and rejected alternatives
- review decisions cannot override prices without provider evidence
- non-reproducible official evidence fails validation
- selected/candidate/rejected result evidence is persisted as structured JSON
- generated price output cannot be modified to bypass registry validation

Live provider checks are research evidence, not CI requirements.

## Open Research Items

These are intentionally not solved in this first plan:

- Verify Azure Digital Twins pricing dimensions and tiering. Do not assume the
  current calculation model is complete.
- Verify AWS IoT TwinMaker pricing dimensions and tiering. Do not assume the
  current calculation model is complete.
- Verify all IoT Hub tier assumptions and message/unit limits.
- Verify transfer pricing tiers for all providers.
- Verify storage request/read/write operation tiers for all providers.
- Fix GCP credentials and permissions before treating GCP Catalog data as live
  evidence.
- Evaluate Infracost as reference material or secondary validation source, not
  as the runtime authority.

## Definition Of Done

- [ ] Mini-roadmap is documented and limited to one slice at a time.
- [ ] Editable SSOT target is explicit and separate from generated pricing files.
- [ ] Evidence contract requires selected rows and rejected alternatives.
- [ ] Publish rule states that `fallback_static = 0` is mandatory.
- [ ] Review decisions cannot become manual price overrides.
- [ ] Official cloud evidence must be reproducible or non-publishable.
- [ ] Tiering and unit-normalization risks are explicitly captured.
- [ ] Digital Twins / TwinMaker / IoT Hub tiering is tracked as future work.
- [ ] Plan avoids quick fixes, one-off defaults, and runtime LLM matching.
- [ ] Plan can be implemented by a builder without guessing the architecture.
- [ ] Evidence artifacts expose selected rows, alternatives, and rejection
  reasons outside logs.

## Self Review

### Architect Review

- Scope is intentionally limited to the foundation and does not attempt to fix
  every provider at once.
- Editable SSOT is separated from generated artifacts.
- Evidence and publish-gate rules prevent hidden fallback publication.
- Provider-specific tiering is captured as future work instead of being buried.
- Manual price overrides are explicitly forbidden in the editable SSOT.
- Non-reproducible evidence is non-publishable, which preserves auditability.

### Builder Review

- The future implementation steps are ordered and concrete.
- Test expectations are explicit.
- Out-of-scope items are clear.
- No builder should need to infer where registry files or evidence files belong.

### Review Findings

- Fixed: clarified that `review_decisions.yaml` cannot become a manual price
  override table.
- Fixed: added publish validation for non-reproducible official evidence.
- Fixed: made Digital Twins, TwinMaker, and IoT Hub tiering non-assumptive
  research items.
- Fixed: added Optimization Strategy Architecture as a separate future phase so
  cost becomes the first metric strategy rather than a hardcoded endpoint.
- Fixed: evidence must be inspectable as structured artifact, not only log text.
- Fixed: generated pricing output cannot become the editable SSOT.

No open findings after fixes.
