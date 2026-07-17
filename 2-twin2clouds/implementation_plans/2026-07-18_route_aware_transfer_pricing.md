---
title: "Route-Aware Transfer Pricing"
description: "Replace source-provider-only egress estimates with exact route contracts, aggregate tier billing, global path scoring, and persisted transfer evidence."
tags: [optimizer, management-api, flutter, pricing, architecture]
lastUpdated: "2026-07-18"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #116 "Introduce route-aware cross-cloud transfer pricing contracts"
- GitHub epic #31 "Implement tiered pricing for additional optimizer services"
- GitHub issue #119 "Make provider pricing catalogs immutable and region-scoped"
- docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md
- docs/research/digital_twin_architecture_and_eventing_layer.md
- 2-twin2clouds/backend/calculation_v2/engine.py
- 2-twin2clouds/backend/calculation_v2/traceability.py
- 2-twin2clouds/backend/calculation_v2/strategy_traceability.py
- 2-twin2clouds/backend/calculation_v2/strategy_contracts.py
- 2-twin2clouds/backend/fetch_data/cloud_price_fetcher_aws.py
- 2-twin2clouds/backend/fetch_data/cloud_price_fetcher_azure.py
- 2-twin2clouds/backend/fetch_data/cloud_price_fetcher_google.py
- 2-twin2clouds/backend/fetch_data/calculate_up_to_date_pricing.py
- 2-twin2clouds/backend/pricing_registry.py
- 2-twin2clouds/pricing_registry/providers/aws/mappings.yaml
- 2-twin2clouds/pricing_registry/providers/azure/mappings.yaml
- 2-twin2clouds/pricing_registry/providers/gcp/mappings.yaml
- twin2multicloud_backend/src/services/optimizer_calculation_service.py
- twin2multicloud_backend/src/services/cost_calculation_run_service.py
- twin2multicloud_flutter/lib/models/calc_result.dart
- twin2multicloud_flutter/lib/widgets/results/calculation_trace_summary.dart
- AWS EC2 On-Demand Data Transfer pricing
- Microsoft Azure Bandwidth pricing
- Google Cloud VPC Network pricing
- Google Cloud Network Service Tiers documentation
EXTRACTED: 2026-07-18 | VERSION: 1.0
-->

# Route-Aware Transfer Pricing

## Issue Context

GitHub issue:
[#116](https://github.com/TVJunkie724/master-thesis/issues/116)

Parent epic:
[#31](https://github.com/TVJunkie724/master-thesis/issues/31)

Upstream pricing integrity boundary:
[#119](https://github.com/TVJunkie724/master-thesis/issues/119)

Downstream deployment specification:
[#118](https://github.com/TVJunkie724/master-thesis/issues/118)

This is Phase 19 of the pricing evidence roadmap and a mandatory
pre-Phase-8 hardening slice. It prices only the approved Five-Layer baseline.
It must not introduce the future Eventing Layer, a free-form topology, region
optimization, or private connectivity products.

## Current Findings

The implementation is not merely missing route labels. Its current selection
and billing behavior is materially incorrect:

1. `_calculate_egress_cost(data_gb, pricing, source_provider)` knows neither
   destination provider nor either endpoint region;
2. GCP Premium and Standard Network Service Tiers cannot be distinguished;
3. AWS and Azure silently fall back to `0.09` and `0.087`, unknown providers
   silently use `0.10`, and generated GCP transfer data contains a static
   `0.12` fallback;
4. every transfer segment applies the provider free allowance independently,
   although provider transfer tiers are aggregated billing pools;
5. the optimizer first selects the cheapest provider independently per layer
   and adds transfer cost afterwards, so it can miss the globally cheapest
   architecture;
6. `intentTrace.transfer_trace` reconstructs route details after calculation
   instead of carrying the exact priced object;
7. `_transfer_source_provider()` always returns `None`, so transfer pricing
   intent records cannot be selected honestly;
8. the Management API persists generic transfer result items with
   `pending_evidence` rather than exact route evidence;
9. the L4-to-L5 query-result edge is absent from transfer pricing;
10. the L3-hot-to-L4 volume uses telemetry message size instead of the explicit
    Digital Twin query-response size;
11. the committed GCP transfer baseline describes a 100 GB free allowance and
    only two paid tiers, while current official Premium Tier Europe pricing is
    expressed per GiB with 1 GiB free, then `0.12`, `0.11`, and `0.085`;
12. Azure documents decimal GB/TB transfer boundaries, while GCP documents
    GiB boundaries. A shared unlabelled numeric tier table cannot prove unit
    equivalence.

These defects can change the winning provider path. They are therefore
calculation correctness defects, not display or documentation debt.

## Goal

Every architecture candidate must be evaluated from an immutable set of layer
costs and exact transfer-route charges. A charged route must identify:

- source and destination layer;
- source and destination provider;
- source and destination canonical region;
- source and destination billing geography;
- transfer route class;
- provider routing or network tier;
- billing-pool identity;
- normalized transfer volume;
- exact pricing-catalog and registry evidence;
- cumulative tier contributions;
- egress cost, glue cost, and total segment cost.

The winning path must be the minimum total cost across complete supported
provider assignments, not the concatenation of independently cheapest layers.

## Scientific And Product Boundary

The Five-Layer thesis baseline uses a provider-level public-egress abstraction.
This phase hardens that abstraction without pretending to reproduce every
service invoice:

- public cross-provider traffic is modeled through the source provider's
  reviewed public internet egress schedule;
- the destination provider's public ingress is modeled as zero only where the
  approved route contract explicitly declares inbound transfer free;
- provider-specific processing products such as NAT Gateway, PrivateLink,
  ExpressRoute, Interconnect, CDN, load balancers, or negotiated rates are not
  silently added;
- account-level aggregate allowances are modeled within one calculation but
  are not claimed to include unrelated workloads in the user's real account;
- this limitation appears in trace assumptions and thesis-facing research
  notes, not as hidden code behavior.

The implementation is production-quality for this declared thesis model. It is
not a cloud invoice emulator.

## Official Evidence Boundary

The reviewed route registry must cite and encode the semantics from:

- AWS EC2 Data Transfer:
  <https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer>
- Azure Bandwidth:
  <https://azure.microsoft.com/en-us/pricing/details/bandwidth/>
- Google Cloud VPC pricing:
  <https://cloud.google.com/vpc/network-pricing>
- Google Cloud Network Service Tiers:
  <https://cloud.google.com/network-tiers/docs/overview>

The evidence establishes:

- AWS internet egress tiers aggregate usage across named AWS services and
  regions, including one account-level free allowance;
- Azure Internet Egress distinguishes Microsoft Premium Global Network and
  routing-preference ISP paths and uses source billing geography;
- GCP Premium Tier is the default unless an eligible resource explicitly uses
  Standard Tier;
- GCP Standard Tier applies only to eligible regional external-IP paths and
  cannot be assumed for the current managed/serverless baseline;
- provider units and thresholds differ and must be normalized explicitly.

## Scope

| Area | In scope | Out of scope |
|---|---|---|
| Architecture | Existing Five-Layer nodes and approved directed edges | Eventing Layer or arbitrary graph editor |
| Regions | Exact regions already bound by immutable pricing catalogs | Region as an optimization variable |
| Routes | Same-provider/same-region classification and cross-provider public internet | VPN, peering, Interconnect, ExpressRoute, private link |
| Pricing | Exact reviewed provider tier tables and billing-pool aggregation | Negotiated or committed-spend discounts |
| GCP | Explicit Premium policy for the current baseline; Standard represented as unsupported unless an eligible deployment profile declares it | Pretending all GCP services support Standard Tier |
| Optimization | Complete-path scoring including transfer and glue cost | New optimization objective |
| Management API | Trusted persistence and exact route result items | New database table |
| Flutter | Typed, collapsed read-only route evidence | Route editor or new wizard step |
| Verification | Deterministic safe unit, integration, contract, UI, and full regression gates | Real deployment or provider mutation |

## Non-Goals

- no Eventing Layer;
- no dynamic architecture engine;
- no region picker or route picker in the calculation UI;
- no manual transfer-rate override;
- no client-authored route evidence;
- no private networking products;
- no account-wide billing import;
- no live cloud deployment E2E;
- no selected service SKU/capacity propagation owned by #118.

## Canonical Ownership

| Concern | Owner | Persistence |
|---|---|---|
| Region-to-geography mapping | editable Optimizer transfer registry | versioned YAML |
| Supported route classes | editable Optimizer transfer registry | versioned YAML |
| Fixed provider routing/network policy | editable Optimizer transfer registry | versioned YAML |
| Provider transfer values | immutable provider-region pricing catalog | immutable JSON |
| Exact calculation route context | Optimizer result | immutable result JSON |
| Calculation run and transfer result items | Management API | existing run/result-item tables |
| Route display | Flutter | typed read model only |

YAML contains topology, matching, units, and policy. It must not duplicate
mutable fetched prices. Immutable pricing catalogs contain the normalized
values and provider evidence. Flutter and the Management API are not pricing
truth writers.

## Transfer Registry Contract

Create `pricing_registry/transfer_routes.yaml` with schema
`pricing-registry-transfer-routes.v1`.

It must contain:

```yaml
schema_version: pricing-registry-transfer-routes.v1
registry_version: "2026.07.18"

region_geographies:
  aws:
    eu-central-1: europe
  azure:
    westeurope: europe
  gcp:
    europe-west1: europe

provider_policies:
  aws:
    public_route_tier: provider_default
    billing_scope: account_aggregate_public_egress
    catalog_tier_path: [transfer, pricing_tiers]
  azure:
    public_route_tier: microsoft_premium_global_network
    billing_scope: account_aggregate_public_egress
    catalog_tier_path: [transfer, pricing_tiers]
  gcp:
    public_route_tier: premium
    billing_scope: sku_account_aggregate_public_egress
    catalog_tier_path: [transfer, pricing_tiers]

supported_routes:
  - route_class: same_provider_same_region
    charge_policy: no_egress_charge
  - route_class: cross_provider_public_internet
    charge_policy: source_provider_egress
    source_geographies: [europe]
    destination_geographies: [europe]
```

The concrete structure may be normalized during implementation, but it must
retain these semantics and pass strict duplicate-key, unknown-field, enum,
provider, geography, path, and reference validation.

`same_provider_inter_region` must exist as a recognized route class but remain
explicitly unsupported for the one-region-per-provider Five-Layer profile.
This is safer than accidentally applying internet or zero-cost pricing.

## Canonical Domain Contracts

Introduce frozen typed contracts under
`backend/calculation_v2/transfer_pricing.py` or a focused package:

```text
TransferEndpoint
  layer
  provider
  region
  geography

TransferRouteIntent
  segment_id
  source
  destination
  route_class
  network_tier
  volume_bytes

TransferPricingPool
  pool_id
  provider
  route_class
  source_geography
  destination_geography
  network_tier
  billing_scope
  catalog_snapshot_id
  evidence_id
  tier_table
  billing_unit
  bytes_per_billing_unit

TransferTierContribution
  tier_id
  from_quantity
  to_quantity
  billable_quantity
  unit_price
  cost

TransferSegmentCharge
  route
  pool_id
  tier_contributions
  egress_cost
  glue_cost
  total_cost
  assumptions
```

Contracts must reject:

- non-finite, negative, or unlabelled quantities;
- unknown providers, layers, regions, geographies, route classes, or tiers;
- duplicate segment or pool IDs;
- mismatched catalog provider/region;
- unsorted, overlapping, gapped, negative, or open-middle tier ranges;
- absent terminal tiers;
- unsupported routes;
- price tables without exact evidence.

Bytes are the only provider-neutral transfer quantity. A route must never pass
an unqualified `GB` number into a provider formula. Each pricing pool converts
bytes into its exact documented billing unit using
`bytes_per_billing_unit`.

## Approved Baseline Edges

The route evaluator owns one ordered topology list:

| Segment | Source | Destination | Volume |
|---|---|---|---|
| `L1_to_L2` | L1 Ingestion | L2 Processing | monthly telemetry payload |
| `L2_to_L3_hot` | L2 Processing | L3 Hot | monthly processed telemetry payload |
| `L3_hot_to_L3_cool` | L3 Hot | L3 Cool | monthly hot-to-cool transition volume |
| `L3_cool_to_L3_archive` | L3 Cool | L3 Archive | monthly cool-to-archive transition volume |
| `L3_hot_to_L4` | L3 Hot | L4 Twin Management | monthly query response payload |
| `L4_to_L5` | L4 Twin Management | L5 Visualization | monthly query response payload |

The query-response payload is:

```text
query_response_bytes
  = queries_per_month
  * averageDigitalTwinQueryResponseSizeInKb
  * 1024
```

It must not reuse `averageSizeOfMessageInKb`.

The existing `...InKb` workload fields are retained for API compatibility.
The Five-Layer v1 workload contract explicitly interprets one input KB as
1,024 bytes because this is the convention used by the historical formulas.
That compatibility assumption must appear in the workload and transfer trace.
A future contract may introduce byte-explicit inputs; this phase must not
silently reinterpret existing saved scenarios as decimal kilobytes.

Same-provider/same-region edges remain in the typed route trace with zero
egress and no glue. `transferCosts` remains a compatibility map containing
only charged cross-provider segments.

## Aggregate Tier Billing

Provider allowances and tier thresholds are billing-pool properties, not
segment properties.

For each candidate architecture:

1. build all six route intents;
2. resolve the exact pricing pool for every supported cross-provider route;
3. group volumes by `pool_id`;
4. sum pool volume in bytes and convert it once to the pool billing unit;
5. calculate cumulative tier cost exactly once per pool;
6. allocate marginal tier cost to segments in canonical edge order;
7. add destination glue cost per cross-provider segment;
8. preserve pool and segment tier contributions in trace.

The allocation rule is:

```text
segment_egress_cost
  = tier_cost(pool_volume_before + segment_volume)
  - tier_cost(pool_volume_before)
```

This preserves the exact pool total, avoids duplicated free allowances, and is
deterministic. Tests must prove:

- `sum(segment egress) == pool cost`;
- re-evaluation is deterministic;
- one provider free allowance is not repeated per segment;
- exact boundary quantities do not cross into the next tier;
- mixed zero and non-zero segments remain stable.

## Complete-Path Optimization

The current greedy layer selection must be replaced for
`cost_minimization_v1`.

The solver must:

1. obtain supported provider candidates per layer from the existing capability
   matrix;
2. enumerate or otherwise deterministically evaluate every complete valid
   provider assignment for the seven existing layer slots;
3. compute selected layer cost plus exact route and glue cost;
4. reject candidates containing an unsupported route;
5. select the minimum total cost through the existing scoring strategy;
6. apply a documented deterministic tie-break using canonical provider order;
7. retain candidate-count, rejected-route-count, and winning-score diagnostics.

The current closed-world space is bounded and small. A generic graph optimizer
is unnecessary. The implementation must favor an explicit, testable
closed-world solver over premature dynamic architecture machinery.

Regression tests must include a case where:

- independently cheapest layers produce a more expensive route-heavy path;
- a slightly more expensive same-provider layer produces the lower total;
- the complete-path solver selects the true lower total.

## Pricing Catalog Changes

Each provider-region snapshot's `transfer` object must carry:

- normalized cumulative tier table;
- source unit and normalized unit;
- route class;
- source geography;
- supported destination geographies;
- routing/network tier;
- billing scope;
- evidence identifier;
- official source type;
- aggregation semantics.

The canonical tier representation must use explicit ranges:

```json
{
  "tierId": "tier-1",
  "startQuantity": 0,
  "endQuantity": 100,
  "unit": "gb",
  "unitPrice": 0
}
```

Legacy dictionary tier tables may be accepted only by a one-time deterministic
baseline migration helper and tests. Runtime calculation must consume only the
canonical explicit representation.

Provider unit rules:

- AWS preserves the Pricing API billing unit and records the corresponding
  byte divisor explicitly;
- Azure keeps decimal GB/TB semantics (`1 GB = 10^9 bytes`,
  `1 TB = 1,000 GB`) and converts thresholds explicitly;
- GCP keeps GiB semantics (`1 GiB = 2^30 bytes`);
- all comparison formulas start from the same canonical byte quantity and
  convert only at the selected provider pricing pool.

No `egressPrice` scalar may remain a runtime fallback. A scalar may be emitted
only as non-authoritative compatibility display data derived from the first
paid canonical tier, and the calculation must never read it.

## Provider Refresh Requirements

### AWS

- retain exact `fromLocation`, `toLocation=External`, and
  `transferType=AWS Outbound` filters;
- preserve all returned paid tiers;
- attach the one account-aggregate allowance exactly once;
- fail refresh publication when the tier series is absent, ambiguous, gapped,
  or inconsistent with its reviewed mapping.

### Azure

- retain the reviewed Microsoft Global Network meter identity;
- distinguish it from Routing Preference ISP pricing;
- preserve official decimal threshold semantics;
- fail publication on meter identity or tier drift;
- record source billing geography for `westeurope`.

### GCP

- select the exact Premium Internet Egress destination-Europe SKU for
  `europe-west1`;
- parse every `pricing_expression.tiered_rates` entry rather than only the
  first positive price;
- retain SKU identity, service regions, usage unit, aggregation level, and
  tier ranges;
- reject a Standard Tier SKU for the current baseline;
- remove the static 100/10-TB fallback table.

## Optimizer API Contract

Flutter and the public Management API continue to omit route evidence.

The Optimizer:

1. receives exact `providerPricingCatalogs`;
2. resolves immutable provider-region snapshots;
3. resolves a `TransferPricingContext` from the catalog references, transfer
   registry, and canonical transfer data;
4. passes the context into complete-path calculation;
5. returns:

```text
transferPricingContext
transferCosts
intentTrace.transfer_trace
intentTrace.transfer_pools
optimizationDiagnostics
```

The context and trace must be metadata-only and size-bounded. They may contain
exact evidence IDs and tier contributions, but never full provider payloads or
credentials.

Stable failure codes must distinguish:

- `TRANSFER_ROUTE_UNSUPPORTED`;
- `TRANSFER_REGION_UNMAPPED`;
- `TRANSFER_PRICING_EVIDENCE_MISSING`;
- `TRANSFER_PRICING_TIER_INVALID`;
- `TRANSFER_NETWORK_TIER_UNSUPPORTED`.

Unsupported candidate paths are excluded during scoring. The request fails
with a structured 409 only when no complete architecture remains.

## Management API Contract

The Management API must:

- continue owning catalog context injection;
- verify that returned route regions and snapshot IDs match the trusted
  catalog context;
- persist the complete result unchanged in run history;
- create exact transfer result items from the typed transfer trace;
- store source provider, quantity, normalized unit, cost, evidence ID, and
  route/pool/tier details in `calculation_notes_json`;
- stop marking exact transfer items `pending_evidence`;
- expose the same bounded trace through pricing evidence detail;
- preserve user/twin isolation and secret redaction.

No migration is required if existing JSON and result-item columns can represent
the new metadata. If implementation discovers a missing typed column, the plan
must be amended before changing the schema.

## Flutter Contract And UX

Flutter must not gain route configuration controls.

Extend `IntentTraceTransferEntry` with strict optional parsing for historical
compatibility and required parsing for the new trace schema:

- source/destination region and geography;
- route class and network tier;
- canonical bytes, display GiB, provider billable quantity, and billing unit;
- egress, glue, and total cost;
- pricing pool and catalog evidence IDs;
- tier contributions and assumptions.

`CalculationTraceSummary` adds one collapsed **Transfer routes** section:

- one compact row per charged route by default;
- provider arrow, regions, volume, and total monthly route cost;
- nested technical details for route class, network tier, pool ID, evidence,
  tier contributions, and assumptions;
- no raw JSON and no default expansion;
- explicit unavailable text for historical traces.

The default wizard remains short. This evidence belongs to calculation review,
not configuration.

## Documentation Separation

Developer/user documentation must explain only the implemented system:

- route fields and fixed baseline assumptions;
- supported Europe regions;
- aggregate tier behavior;
- exact error behavior;
- how to extend the registry for a reviewed region or network tier;
- where route evidence appears in Flutter.

Thesis-facing research notes must separately record:

- why provider-only transfer prices were invalid;
- why global path scoring replaced greedy layer selection;
- provider unit and allowance differences;
- the declared limits of the provider-level egress abstraction.

No evaluation result or thesis conclusion belongs in the developer handbook.

## Required File Impact

| Project | Boundaries |
|---|---|
| Optimizer registry | `pricing_registry.py`, new `transfer_routes.yaml`, provider mappings, contracts, service models |
| Optimizer catalogs | pricing schema, provider fetchers, catalog builder, reviewed baseline snapshots/manifest |
| Optimizer calculation | new transfer domain/resolver, `engine.py`, trace builders, currency conversion |
| Optimizer API | `api/calculation.py`, error models/OpenAPI |
| Management API | calculation schemas/services, run result-item projection, evidence detail verification |
| Flutter | `calc_result.dart`, calculation trace widgets and focused tests |
| Documentation | this plan, pricing roadmap, docs-site Optimizer/contracts/pricing pages, research notes |

## Implementation Slices

Each slice is implemented, reviewed, tested, documented, and committed before
the next slice.

### Slice 1: Registry And Domain

- add strict transfer registry schema and loader validation;
- add frozen route, endpoint, pool, tier, and charge contracts;
- add canonical tier validation and cumulative/marginal formula helpers;
- add duplicate-key, unit, boundary, unsupported-route, and aggregation tests.

Commit:

```text
feat(pricing): define route-aware transfer contracts

Refs #116
```

### Slice 2: Provider Evidence And Baselines

- harden AWS, Azure, and GCP transfer evidence construction;
- remove transfer fallback rates and scalar calculation aliases;
- migrate reviewed Europe baselines and manifest identities;
- verify provider-specific units, tiers, routing policy, and evidence.

Commit:

```text
feat(pricing): publish exact transfer route evidence

Refs #116
```

### Slice 3: Complete-Path Optimizer

- build all baseline routes for each candidate path;
- aggregate billing pools;
- replace greedy layer choice with complete-path scoring;
- add L4-to-L5 and corrected query-response volumes;
- return exact route/pool diagnostics and structured failures.

Commit:

```text
feat(optimizer): score complete paths with route costs

Refs #116
```

### Slice 4: Trace And Management Persistence

- make Optimizer traces consume priced route objects directly;
- preserve exact source intent/evidence/tier contributions;
- validate trusted route context in Management;
- persist exact transfer result items and evidence detail.

Commit:

```text
feat(management): persist exact transfer route evidence

Refs #116
```

### Slice 5: Flutter Read Model And UX

- add typed version-aware route parsing;
- add collapsed transfer-route evidence;
- update demo and fixtures without synthesizing missing historical data;
- add model, widget, accessibility, and responsive tests.

Commit:

```text
feat(flutter): expose transfer route evidence

Refs #116
```

### Slice 6: Documentation And Contracts

- synchronize OpenAPI snapshots;
- update user/developer documentation and pricing roadmap;
- add the separate thesis research note;
- run strict MkDocs and link validation.

Commit:

```text
docs(pricing): document route-aware transfer model

Refs #116
```

### Slice 7: Independent Reviews And Full Gates

- review plan compliance and all data flows;
- review numerical boundaries, fail-closed behavior, trace honesty, security,
  UI density, and historical compatibility;
- fix every finding;
- run all safe local suites and builds;
- record evidence in this plan and GitHub.

## Verification Matrix

### Domain And Formula Tests

- exact zero, free-boundary, first-paid, tier-boundary, and terminal-tier cases;
- canonical byte conversion to decimal GB and GiB;
- no repeated free allowance across segments;
- pool total equals allocated segment total;
- deterministic allocation order;
- malformed, duplicate, overlapping, gapped, and non-terminal tiers fail.

### Route Resolution Tests

- AWS Europe to Azure/GCP Europe;
- Azure Europe to AWS/GCP Europe;
- GCP Premium Europe to AWS/Azure Europe;
- same-provider/same-region zero classification;
- same-provider/inter-region explicit unsupported result;
- unknown region/geography/network tier fails closed;
- catalog/route provider-region mismatch fails.

### Optimization Tests

- route-aware total changes the winning provider path;
- unsupported paths never enter scoring as zero;
- deterministic ties use canonical provider order;
- all-supported complete-path candidate count is stable;
- L4-to-L5 and corrected query-response volume are included;
- default Europe scenario remains calculable and deterministic.

### Provider Evidence Tests

- AWS exact outbound/external filters and all paid tiers;
- Azure exact MGN meter, decimal thresholds, and ISP rejection;
- GCP exact Premium destination-Europe SKU and all `tiered_rates`;
- no `0.09`, `0.087`, `0.10`, or `0.12` transfer fallback survives;
- immutable baseline manifest and snapshot hashes verify.

### Management Tests

- trusted catalog and transfer contexts match;
- result items contain exact route evidence;
- run history preserves old and new trace schemas;
- owner/twin isolation and secret redaction remain intact;
- Optimizer malformed context maps to stable safe errors.

### Flutter Tests

- strict new trace parsing;
- historical optional trace compatibility;
- compact collapsed route rows;
- nested tier/evidence details;
- narrow and wide layout;
- semantics labels and selectable technical IDs;
- demo parity without invented evidence.

### Full Safe Gates

```bash
docker compose --profile dev config

docker compose --profile dev exec optimizer \
  pytest -q
docker compose --profile dev exec optimizer \
  ruff check api backend tests
docker compose --profile dev exec optimizer \
  bandit -q -r api backend
docker compose --profile dev exec optimizer \
  python -m compileall -q api backend
docker compose --profile dev exec optimizer \
  pip check

docker compose --profile dev exec management-api \
  pytest -q
docker compose --profile dev exec management-api \
  ruff check src tests
docker compose --profile dev exec management-api \
  bandit -q -r src
docker compose --profile dev exec management-api \
  python -m compileall -q src
docker compose --profile dev exec management-api \
  pip check

cd twin2multicloud_flutter
flutter analyze
flutter test
flutter build web --release --dart-define-from-file=config/dev.example.json
flutter build macos --debug --dart-define-from-file=config/dev.example.json
cd ..

./thesis.sh test frontend-integration

docker compose --profile docs run --rm docs \
  mkdocs build --strict
```

No command may deploy infrastructure, mutate provider resources, or incur a
paid workload.

## Review Pass 1 Checklist

- [ ] Every issue acceptance criterion maps to implementation and tests.
- [ ] No source-provider-only calculation call remains.
- [ ] No transfer scalar fallback remains.
- [ ] Pricing values exist only in immutable catalogs, not route YAML.
- [ ] Free allowances are pool-scoped.
- [ ] Complete-path scoring includes route and glue cost.
- [ ] Route traces originate from priced domain objects.
- [ ] Management persists exact evidence.
- [ ] Flutter remains read-only and compact.

## Review Pass 2 Checklist

- [ ] Official provider semantics and units are current.
- [ ] Numerical boundaries and currency conversion are correct.
- [ ] Unsupported routes fail closed.
- [ ] Historical results remain readable without fabricated evidence.
- [ ] Errors and logs are secret-free.
- [ ] Documentation and OpenAPI match runtime behavior.
- [ ] Full safe gates pass.

## Definition Of Done

- [ ] Route identity includes both endpoints, both regions/geographies, class,
  tier, pool, and evidence.
- [ ] Transfer pricing uses exact immutable provider-region catalog evidence.
- [ ] No hidden transfer rate exists.
- [ ] Aggregate tiers and allowances are applied once per billing pool.
- [ ] Complete-path optimization selects the true minimum modeled total.
- [ ] L4-to-L5 and query-response transfer volumes are explicit.
- [ ] Optimizer trace and Management run history preserve exact route evidence.
- [ ] Flutter exposes compact, collapsed, typed route evidence.
- [ ] Existing Europe baseline remains deterministic.
- [ ] Safe full project gates pass.
- [ ] No cloud resource is created or mutated.
