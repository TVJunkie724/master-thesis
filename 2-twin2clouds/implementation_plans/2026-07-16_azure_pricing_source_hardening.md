---
title: Azure Pricing Source Hardening
status: Approved for implementation
issue: 110
parentIssue: 32
baseBranch: master
featureBranch: codex/azure-pricing-source-hardening
provider: azure
---

# Azure Pricing Source Hardening

## 1. Objective

Replace the four Azure `fallback_static` paths in the generated pricing contract
with deterministic Azure Retail Prices API evidence:

- `cosmosDB.storagePrice`;
- `blobStorageCool.storagePrice`;
- `blobStorageArchive.storagePrice`;
- `blobStorageCool.transferCostFromCosmosDB`.

The resulting Azure snapshot must be calculation-compatible, inspectable, and
`publishable`. Missing, ambiguous, structurally invalid, or drifted provider rows
must fail closed rather than reintroduce a silent fallback.

## 2. Verified Provider Findings

The public West Europe catalog was inspected on 2026-07-16. The required source
rows exist:

| Output | Required Azure row |
|---|---|
| Cosmos DB storage | `Azure Cosmos DB` / `Azure Cosmos DB` / `RUs` / `Data Stored` / `1 GB/Month` / Consumption / primary meter |
| Cool blob storage | `Storage` / `Blob Storage` / `Cool LRS` / `Cool LRS Data Stored` / `1 GB/Month` / Consumption / primary meter |
| Archive blob storage | `Storage` / `Blob Storage` / `Archive LRS` / `Archive LRS Data Stored` / `1 GB/Month` / Consumption / primary meter |
| Internet egress | `Bandwidth` / `Rtn Preference: MGN` / `Standard` / `Standard Data Transfer Out` / `1 GB` / Consumption, grouped by `tierMinimumUnits` |

The current archive fallback is `0.00099`, while the exact intended West Europe
Blob Storage Archive LRS meter currently returns `0.0018`. Broad keyword matching
also sees unrelated Files, Data Lake, redundancy, reservation, and free-tier rows.
Selecting the cheapest paid row is therefore forbidden.

## 3. Target Architecture

```text
Azure Retail Prices API rows
  -> sanitized canonical catalog candidates
  -> versioned Azure mapping from pricing_registry/providers/azure/mappings.yaml
  -> deterministic single-row or tier-series matcher
  -> intent evidence with selected and rejected rows
  -> normalized field/tier builder
  -> generated Azure pricing payload + source metadata
  -> provider pricing contract validation
  -> calculation formulas
```

The versioned provider mapping remains the editable matching SSOT. Fetcher code
may transform a reviewed match into the legacy calculation payload, but it must
not define a second independent set of product/SKU/meter selection strings.

## 4. Contract Changes

### 4.1 Exact Azure mappings

Update the four affected Azure mappings to exact reviewed predicates. Predicates
must include service, product, SKU, meter, unit, price type, and primary-meter
state. The requested region is injected from the runtime request scope and must
not be hardcoded to West Europe in the editable mapping. Current stable provider
identifiers are stored as evidence and drift markers, not as the only semantic
match criterion. Mapping versions, classification evidence references, retrieval
dates, review dates, and reviewed identifiers must change together.

### 4.2 Tier-series selection

`transfer.egress_gb` is not a single row. Extend the generic intent matcher with
an explicit `selection_mode: tier_series` contract:

- multiple rows are valid only when all rows share the reviewed meter identity;
- each row must have a numeric, non-negative, unique `tierMinimumUnits`;
- rows are sorted by threshold;
- conflicting duplicate thresholds are invalid;
- a threshold-zero row must exist;
- selected rows and rejected alternatives remain inspectable;
- ordinary mappings retain the existing exactly-one behavior.

The evidence schema gains additive `selected_rows` and `normalized_tiers` fields.
The existing singular `selected_row` stays populated for single-row mappings and
remains backward compatible. The Azure transfer provider-pricing contract must
require `selected_rows` and `normalized_tiers`; single-row provider contracts keep
requiring `selected_row`.

### 4.3 Generated pricing evidence

The provider fetch result carries bounded internal field evidence. The generated
Azure pricing file exposes a reserved, schema-versioned evidence section for the
affected paths. Calculation loaders ignore reserved evidence keys.

Evidence includes:

- intent and output field path;
- request region and mapping version;
- selected provider row(s), stable IDs, effective date, currency, and unit;
- rejected alternatives with rejection reasons, bounded to a documented limit;
- normalization rule and normalized value/tier table;
- match/review status.

Rejected alternatives are capped at 25 rows per intent and sorted
deterministically. This keeps API responses and generated snapshots bounded.

No credentials, request headers, or unbounded raw payloads may be stored. The
reserved evidence key must be added to the canonical metadata-key allowlist so
calculation and schema traversal never interpret evidence as a billable service.

## 5. Field Builders

### 5.1 Storage fields

The three storage prices use `per_gb_month`. The builder accepts only an exact
matched evidence record with USD currency and the reviewed `1 GB/Month` unit. It
copies the normalized value into the established calculation keys.

### 5.2 Transfer tiers

Convert Azure lower-bound thresholds into the absolute upper-bound table expected
by `tiered_unit_cost`:

```text
source threshold[i], price[i]
  -> output tier[i].limit = source threshold[i + 1]
  -> output tier[i].price = price[i]
last output tier limit = Infinity
```

Adjacent source tiers with identical prices may be coalesced only after coverage
has been proven. `egressPrice` is the first paid tier price and exists only as a
compatibility/derivation input. `blobStorageCool.transferCostFromCosmosDB` derives
from that fetched first paid tier and is classified `derived`, not `fetched`.

## 6. Error Handling

- Transport/API failures retain the previous published last-known-good snapshot;
  they do not publish partial data.
- Missing, ambiguous, changed, or invalid mappings return structured review state.
- A tier series with gaps in structural preconditions is rejected before writing.
- Currency or unit mismatches are explicit contract failures.
- Logging includes provider, intent, region, and status but no secrets or complete
  unbounded catalogs.

The refresh path must call the existing pricing-publication decision boundary
before atomic replacement. Only a structurally valid, non-review-required fresh
snapshot may replace the calculation file. A rejected fresh candidate remains in
the response/evidence path for UI review while the tracked/runtime last-known-good
file remains unchanged.

## 7. Compatibility

- Existing public pricing endpoint shapes remain additive.
- Existing calculation keys remain unchanged.
- Reserved metadata/evidence keys are ignored by calculation loaders.
- Single-row intent matching behavior remains unchanged unless the mapping opts
  into `tier_series`.
- The baseline snapshot remains usable offline after the refresh.
- Existing single-row evidence records and contract validation remain compatible;
  transfer is the only contract opting into multi-row tier evidence.

## 8. Test Strategy

### Deterministic unit fixtures

- exact Cosmos DB storage row plus backup, analytics, free-tier, and nonprimary
  alternatives;
- exact Blob Storage Cool/Archive LRS rows plus Files, Data Lake, other redundancy,
  reservation, and nonprimary alternatives;
- exact egress tier series plus China, inter-zone, Internet routing-preference,
  reservation, duplicate-threshold, missing-zero, and conflicting-price variants;
- unit, currency, effective-date, and stable-identity drift;
- bounded evidence and secret-key redaction;
- backward compatibility for ordinary single-row mappings.
- publication-gate tests prove that failed/review-required candidates never replace
  a last-known-good calculation snapshot.

### Calculation regression

- Cool and Archive GB-month cost uses fetched normalized prices;
- transfer cumulative boundary tests at 0, 100, each threshold, and above the last
  threshold;
- derived Cosmos-to-Blob transfer value equals the first paid fetched egress tier;
- existing provider strategy and formula tests remain green.

### Live diagnostic

Use the unauthenticated public Azure Retail Prices API in an isolated temporary
target. Compare values, source classifications, selected IDs, and tier thresholds
against the candidate snapshot before replacing the tracked baseline. This is a
diagnostic verification, not a cloud-resource E2E deployment.

## 9. Documentation

Update together:

- Optimizer component internals and pricing baseline lifecycle;
- pricing evidence/data flow and exact Azure intent decisions;
- current limitations/evidence;
- refactoring roadmap and GitHub issues with full titles.

External Azure source links must open in a new tab on the MkDocs site.

## 10. Verification Gates

1. Focused Azure matcher/fetcher/evidence tests.
2. Full `tests/unit/pricing` and `tests/unit/calculation_v2` suites in Docker.
3. Registry validation, provider-pricing-contract validation, publication-state,
   and API compatibility tests.
4. Isolated live Azure diagnostic with zero fallback fields.
5. Strict MkDocs build.
6. `git diff --check` and secret-pattern scan of generated evidence.
7. First implementation review with all findings fixed.
8. Independent second audit against this plan and issue acceptance criteria.

The live diagnostic must write to an isolated temporary path first. Promotion to
the tracked baseline is a separate, explicit step after all gates pass.

## 11. Definition Of Done

- [ ] Exact reviewed mappings are the only selection SSOT for affected fields.
- [ ] Tier-series matching is explicit, deterministic, and backward compatible.
- [ ] Selected/rejected provider rows are inspectable and bounded.
- [ ] Storage and transfer values are normalized from provider evidence.
- [ ] All four former fallback paths are `fetched` or `derived`.
- [ ] Azure transfer tiers are classified as fetched rather than curated.
- [ ] Azure generated pricing validates as `publishable`.
- [ ] Rejected fresh candidates cannot overwrite last-known-good pricing.
- [ ] Calculation and API contracts remain compatible.
- [ ] Deterministic and live verification gates pass.
- [ ] Canonical documentation and issue state match implementation reality.
- [ ] Two review passes have no unresolved findings.
