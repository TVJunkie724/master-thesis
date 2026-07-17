---
title: "Azure Digital Twins Billable Quantity Contract"
description: "Replace fabricated query-unit tiers with explicit workload assumptions, provider billing increments, and end-to-end traceability."
tags: [optimizer, azure, pricing, contracts, flutter]
lastUpdated: "2026-07-17"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #114 "Harden Azure Digital Twins billable quantity contract"
- GitHub epic #31 "Implement tiered pricing for additional optimizer services"
- docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md
- 2-twin2clouds/backend/calculation_v2/components/azure/digital_twins.py
- 2-twin2clouds/backend/calculation_v2/engine.py
- 2-twin2clouds/backend/calculation_v2/strategy_contracts.py
- 2-twin2clouds/backend/calculation_v2/strategy_traceability.py
- 2-twin2clouds/backend/fetch_data/cloud_price_fetcher_azure.py
- 2-twin2clouds/backend/fetch_data/calculate_up_to_date_pricing.py
- 2-twin2clouds/pricing_registry/workload_contracts.yaml
- 2-twin2clouds/pricing_registry/provider_pricing_contracts.yaml
- 2-twin2clouds/pricing_registry/service_models.yaml
- twin2multicloud_backend/src/api/routes/optimizer.py
- twin2multicloud_backend/src/services/optimizer_configuration_service.py
- twin2multicloud_flutter/lib/models/calc_params.dart
- twin2multicloud_flutter/lib/widgets/calc_form/calc_form.dart
- Microsoft Azure Digital Twins pricing documentation
- Microsoft Azure Digital Twins Query Units documentation
- Microsoft Azure Digital Twins monitoring and billing metrics documentation
- 3-cloud-deployer/src/terraform/azure_twins.tf
- 3-cloud-deployer/src/terraform/azure_compute.tf
- 3-cloud-deployer/src/providers/azure/azure_functions/adt-updater/function_app.py
EXTRACTED: 2026-07-17 | VERSION: 1.0
-->

# Azure Digital Twins Billable Quantity Contract

## Issue Context

GitHub issue:
[114](https://github.com/TVJunkie724/master-thesis/issues/114)

Parent epic:
[31](https://github.com/TVJunkie724/master-thesis/issues/31)

Roadmap:
`docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`

This is Phase 17 of the pricing evidence and optimization strategy roadmap. It
must be completed, reviewed, and committed before the AWS TwinMaker
pricing-plan phase begins.

Related Deployer hardening:
[117](https://github.com/TVJunkie724/master-thesis/issues/117) removes the
unreachable historical `adt-updater` package after this phase aligns the cost
model with the canonical ADT Pusher path.

Downstream deployment-specification work:
[118](https://github.com/TVJunkie724/master-thesis/issues/118) will bind
deployable pricing decisions to the Management API, DeploymentManifest, and
Terraform. Azure Digital Twins message/operation/query meters in this phase are
usage dimensions rather than deployable SKUs, so this phase must expose them as
pricing and workload evidence but must not invent an ADT Terraform tier.

## Goal

The implementation must calculate Azure Digital Twins costs from explicit,
auditable billable quantities:

- billable operations;
- billable event-route messages;
- query units.

The implementation must remove the fabricated `queryUnitTiers` table from all
runtime, registry, generated-data, test, and documentation contracts. Query
units are workload consumption, not a price tier.

## Evidence Boundary

The implementation must use these official references:

- Azure Digital Twins pricing:
  <https://azure.microsoft.com/en-us/pricing/details/digital-twins/>
- Query Units in Azure Digital Twins:
  <https://learn.microsoft.com/en-us/azure/digital-twins/concepts-query-units>
- Azure Digital Twins monitoring and billing metrics:
  <https://learn.microsoft.com/en-us/azure/digital-twins/how-to-monitor>

The provider evidence establishes:

- operations are metered in 1 KB increments of response body;
- event-route messages are metered in 1 KB increments of payload;
- Query API calls consume query units based on query complexity and result size;
- actual query-unit consumption is available through the `query-charge`
  response value;
- Query API usage also produces billable operation usage.

The executable five-layer baseline establishes:

- Digital Twin updates are SDK/API calls from the processing/storage path;
- the Azure Digital Twins Event Route shown in `azure_twins.tf` is commented
  out and is not deployed;
- the IoT Hub to Event Grid dispatcher path belongs to L1 and is priced by its
  own Event Grid contract;
- therefore the baseline produces zero Azure Digital Twins routed messages.

The thesis application estimates future workloads and cannot collect production
`query-charge` values before deployment. It must therefore use explicit
estimation inputs and label them as assumptions in the result trace.

## Scope

| Area | In scope ✅ | Out of scope ❌ |
|---|---|---|
| Optimizer | Canonical workload fields, derived billable quantities, Azure L4 calculation, trace | AWS, GCP, route-aware transfer |
| Pricing registry | Remove false tier field; update workload, provider, formula, source, and service-model contracts | Runtime registry editor |
| Pricing fetcher | Keep the three real Azure price meters; remove query-unit default construction | Broad Azure fetcher rewrite |
| Baseline topology | Price the deployed ADT Pusher path and stop double-counting L1 Event Grid inside L4 | Removing the stale Deployer artifact; tracked by #117 |
| Management API | Validate and forward the additive inputs; persist them in existing JSON state | New table or migration |
| Flutter | Typed fields and compact advanced controls in Twin capabilities | New global wizard step |
| Documentation | Optimizer contract and user-facing assumption guidance | Thesis evaluation results |
| Verification | Deterministic unit, API, widget, integration, and regression tests | Live Azure deployment or paid E2E |
| Deployment resolution | Preserve exact meter/formula evidence for later `ResolvedDeploymentSpecification` composition | Terraform SKU/capacity propagation; owned by #118 |

## Required File Impact

Every listed production area must be handled. Additional fixtures or tests
discovered through references must be updated rather than bypassed.

| Project | Required files or boundaries |
|---|---|
| Optimizer API | `2-twin2clouds/api/calculation.py`, request examples, API validation tests |
| Calculation engine | `2-twin2clouds/backend/calculation_v2/engine.py`, `components/azure/digital_twins.py`, `layers/azure_layers.py`, a shared formula helper under `calculation_v2/` |
| Strategy contracts | `strategy_contracts.py`, `traceability.py`, `strategy_traceability.py`, `pricing_source_inventory.py` |
| Pricing construction | `pricing_schema.py`, `cloud_price_fetcher_azure.py`, `calculate_up_to_date_pricing.py`, committed canonical/generated pricing JSON |
| Pricing registry | `backend/pricing_intent_registry.py`, `intents.yaml`, `workload_contracts.yaml`, `service_models.yaml`, `formula_sets.yaml`, `normalization.yaml`, `pricing_model_classifications.yaml`, `price_source_classifications.yaml`, `provider_pricing_contracts.yaml`, `optimization_bundles.yaml`, `providers/azure/mappings.yaml` |
| Management API | `twin2multicloud_backend/src/schemas/optimizer_calculation.py` [NEW], `src/schemas/cost_calculation.py`, `src/schemas/optimizer_config.py`, `src/schemas/twin_config.py`, `src/api/routes/optimizer.py`, `src/api/routes/optimizer_runs.py`, affected services, API/proxy/configuration/run tests, and shared fixtures |
| Flutter model/form | `lib/models/calc_params.dart`, `lib/widgets/calc_form/calc_form.dart`, `lib/widgets/results/service_breakdown.dart`, `integration_test/management_api_readiness_test.dart`, model/form/fixture/demo tests that construct `CalcParams` |
| Documentation | this plan, pricing roadmap, docs-site Optimizer and configuration pages, legacy Azure pricing page |

## Canonical Workload Contract

Two additive provider-neutral fields must be introduced:

| Wire field | Type | Validation | Default | Meaning |
|---|---|---|---:|---|
| `averageDigitalTwinQueryUnitsPerQuery` | number | finite and `> 0` | `1.0` | Estimated average Azure Digital Twins Query Units consumed by one logical query |
| `averageDigitalTwinQueryResponseSizeInKb` | number | finite and `> 0` | `1.0` | Estimated average response payload per logical Digital Twin query |

The defaults are compatibility defaults, not hidden provider data. They must:

- be declared by both Optimizer and Management API schemas;
- be emitted by Flutter `CalcParams.toJson()`;
- be restored by Flutter `CalcParams.fromJson()` when old saved JSON omits them;
- be visible and editable in the advanced Twin usage assumptions controls;
- appear in result trace workload inputs;
- be documented as estimates that should later be calibrated from observed
  `query-charge` and response-size telemetry.

No Azure Digital Twins event-route payload field may be introduced in this
phase. The current profile has no deployed ADT event route, so its billable
routed-message quantity is a topology-derived constant of zero. A later
architecture profile that deploys an ADT event route must introduce its own
versioned workload/topology contract instead of silently reusing
`averageSizeOfMessageInKb`.

## Billable Quantity Model

The implementation must centralize 1 KB billing increments in a
provider-independent formula helper:

```text
billable_1kb_units(item_count, average_size_kb)
    = item_count * max(1, ceil(average_size_kb / 1 KB))
```

The helper must:

- reject negative item counts;
- reject non-finite or non-positive sizes when item count is positive;
- return zero when item count is zero;
- operate on the existing numeric `...InKb` wire unit without claiming a byte
  convention that the current API does not encode;
- avoid floating-point boundary drift around exact integer KB values;
- have direct boundary tests at `0`, `0.25`, `1.0`, `1.01`, `2.0`, and
  `2.01` KB.

The Azure Digital Twins quantities must be derived as follows:

```text
telemetry_update_operations
    = total_messages_per_month

query_response_operations
    = billable_1kb_units(
          queries_per_month,
          averageDigitalTwinQueryResponseSizeInKb
      )

billable_operations
    = telemetry_update_operations
      + query_response_operations

billable_event_route_messages
    = 0

billable_query_units
    = queries_per_month
      * averageDigitalTwinQueryUnitsPerQuery
```

The one-operation-per-telemetry-update assumption represents the current
five-layer baseline, where each telemetry message updates the operational twin.
The zero-message rule represents the absence of an ADT outbound Event Route.
Both topology assumptions must be declared in `service_models.yaml`, both trace
projections, and optimizer documentation. This phase must not generalize the
architecture topology.

The complete Azure L4 baseline component model must be:

```text
Azure L4 monthly cost
    = digital_twins_operation_cost
    + digital_twins_query_unit_cost
    + digital_twins_routed_message_cost  # exactly zero in this profile
    + adt_pusher_function_cost           # one invocation per telemetry update
```

The L4 result must not include `adt_updater_function` or
`event_grid_subscription`. The Azure L1 result continues to own the real IoT Hub
to Event Grid to Dispatcher costs.

## Pricing Contract

The Azure Retail Prices API remains the price source for:

| Pricing field | Canonical unit | Source meter | Observed Westeurope meter ID |
|---|---|---|---|
| operation | USD per operation | Standard Operations | `07468ba4-7fcc-5483-ac11-db92ef466bd0` |
| message | USD per 1 KB message unit | Standard Message | `25f20fec-df26-50c6-a1fc-7268b04bd8ad` |
| query | USD per query unit | Standard Query Units | `922d2f08-f5b6-5efe-a33b-0778db401639` |

The reviewed 2026-07-17 Retail Prices rows share:

```text
serviceName   = Digital Twins
productName   = Digital Twins
skuName       = Standard
unitOfMeasure = 1K
productId     = DZH318Z0BZ0T
skuId         = DZH318Z0BZ0T/000C
priceType     = Consumption
```

Azure meter and SKU IDs are region-specific. The same 2026-07-17 query returned
different IDs and prices for `eastus` and `northeurope`. The mapping must
therefore select by the exact semantic tuple `serviceName`, `productName`,
`skuName`, exact `meterName`, `unitOfMeasure`, `priceType`,
`is_primary_meter_region`, and requested region. It must not hardcode one
region's meter ID as a global match condition.

The selected row must preserve its exact `meterId`, `productId`, `skuId`,
region, price, unit, effective date, and candidate identity as evidence.
Multiple rows matching the semantic tuple, a changed unit, or a changed
product/SKU/meter name must produce an ambiguous/changed review state rather
than falling back to keyword-only publication. Tests must include two regions
with different provider IDs and prove both resolve to their own exact selected
evidence.

All three source meters are prices per 1,000 billable units. The registry must
add and use these exact normalization rules:

| Rule | Source unit | Target unit | Multiplier |
|---|---|---|---:|
| `per_1k_operations` | `1K` | `operation` | `0.001` |
| `per_1k_message_units` | `1K` | `message_unit` | `0.001` |
| `per_1k_query_units` | `1K` | `query_unit` | `0.001` |

The existing Azure `digital_twin.query_unit` mapping must stop using
`per_query_unit`, because that rule has multiplier `1` and would overstate the
normalized Retail Prices API evidence by a factor of 1,000. Calculator aliases
may continue accepting historical raw `...Price` keys per 1K, but registry
evidence and trace must expose the normalized per-unit value.

`queryUnitTiers` must be removed from:

- `EXPECTED_PRICING_SCHEMA`;
- `CURATED_FIELDS`;
- Azure static defaults;
- Azure generated pricing construction;
- optimization strategy intents;
- pricing source inventory classifications;
- pricing registry source/model contracts;
- `pricing.json`;
- `pricing_dynamic_azure.json`;
- tests and legacy HTML documentation.

No replacement tier table may be added. Query-unit weight comes exclusively
from the workload contract.

The registry must expose three independent Azure Digital Twins pricing
contracts and formula references:

| Intent field | Provider contract | Consumed quantity | Formula ref | Result component |
|---|---|---|---|---|
| `digital_twin.operation` | `azure.digital_twin_operation.pricing_contract.v1` | `monthly_digital_twin_billable_operations` | `request_unit_cost` | `digital_twins_operations` |
| `digital_twin.message` | `azure.digital_twin_message.pricing_contract.v1` | `monthly_digital_twin_routed_messages` | `message_unit_cost` | `digital_twins_routed_messages` |
| `digital_twin.query_unit` | `azure.digital_twin_query_unit.pricing_contract.v1` | `monthly_digital_twin_query_units` | `query_unit_cost` | `digital_twins_query_units` |

The two new intent definitions are Azure-only and must declare
`expected_providers: [azure]`. The existing cross-provider
`digital_twin.query_unit` intent remains unchanged for AWS and GCP compatibility.
The implementation must add `digital_twin.operation` and
`digital_twin.message` to `CANONICAL_PRICING_INTENTS`, and add exact Azure
mapping rows for `Standard Operations` and `Standard Message`.

The matching classification IDs are mandatory:

```text
azure.digital_twin_operation.model.v1
azure.digital_twin_operation.source.v1
azure.digital_twin_message.model.v1
azure.digital_twin_message.source.v1
```

`message_unit_cost` must be added to `cost_formula_set_v1` with the expression
`message_units * normalized_message_unit_price`. It must not be represented as
an event-bus or generic layer-total formula.

The Azure optimization bundle, service model, formula set, source
classification, model classification, provider contracts, and registry
validation tests must agree on those identifiers. Existing AWS and GCP
contracts must not be reinterpreted by this phase.

The workload contract must add these exact fields:

| Workload field | Type | Unit | Source |
|---|---|---|---|
| `monthly_digital_twin_billable_operations` | number | operation | derived Azure ADT quantity |
| `monthly_digital_twin_routed_messages` | number | message_unit | topology-derived constant `0`; quantity already represents 1 KB billable message units |
| `monthly_digital_twin_query_units` | number | query_unit | existing field, now mapped to the derived Azure quantity |

## Calculation Boundary

`AzureDigitalTwinsCalculator.calculate_cost()` must receive already derived,
typed quantities:

```text
calculate_cost(
    billable_operations,
    billable_query_units,
    billable_messages,
    pricing
)
```

The component module must expose a typed immutable breakdown containing exact
operation, query-unit, routed-message, and total costs. `calculate_cost()` may
remain a total-returning compatibility facade, while `AzureLayerCalculators`
uses the breakdown to publish these stable component keys:

```text
digital_twins_operations
digital_twins_query_units
digital_twins_routed_messages
adt_pusher_function
```

Flutter's existing service-breakdown label map must receive labels for those
keys. No consumer may infer component meaning from display text.

The calculator must own price normalization and multiplication only. It must not:

- inspect raw UI parameters;
- invent query-unit weights;
- read registry files directly;
- make network calls;
- apply architecture assumptions.

The engine must own workload derivation and pass explicit quantities to the
calculator. Formula bindings and provider pricing contracts must name those
quantities exactly.

## Trace Contracts

The API currently has two trace projections and both are mandatory:

- `intentTrace`, built by `calculation_v2/traceability.py`, explains the
  selected pricing intents, formulas, evidence identities, and selected path;
- `resultTrace`, built by `calculation_v2/strategy_traceability.py`, explains
  provider-contract workload inputs and cost contributions.

They must remain separate response properties in this phase. The implementation
must not merge or rename them.

Both additive traces must expose or reference:

| Trace field | Required value |
|---|---|
| raw query-unit assumption | `averageDigitalTwinQueryUnitsPerQuery` |
| raw query-response assumption | `averageDigitalTwinQueryResponseSizeInKb` |
| logical query count | `queries_per_month` |
| telemetry update count | `total_messages_per_month` |
| billable operations | derived value |
| billable routed messages | `0`, with baseline topology reference |
| billable query units | derived value |
| billing increment | `1 KB` |
| assumption source | `explicit_input` or `compatibility_default` |
| formula references | explicit operation/message/query formula identifiers |

`resultTrace` must map `monthly_digital_twin_query_units` to the derived
`billable_query_units`, never directly to `queries_per_month`. It must also map
the operation and message workload fields to their derived quantities.
`intentTrace` must include the two raw assumptions, all three derived
quantities, and the formula identifiers used by the selected Azure L4 path.
Each `resultTrace` pricing contract must point to the matching exact L4
component key, rather than attributing all three meters to the shared layer
total.

Trace output must remain bounded and secret-free. Neither projection may expose
credentials or raw provider request/response bodies.

The Optimizer owns assumption-source classification. It must derive the source
from its validated request model before defaults are materialized:

```text
field present in request model_fields_set -> explicit_input
field absent from request model_fields_set -> compatibility_default
```

`explicit_input` means the caller supplied the value. It does not claim that a
human manually edited the field; Flutter intentionally emits its visible
default values and they are therefore explicit application input. Internal
source metadata may be added to the calculation context, but it must not become
a second public request field or be trusted when supplied by a client.

## API And Persistence Compatibility

The Optimizer API and Management API must accept the two additive fields with
the same type, default, and validation. A mismatch is a release-blocking
finding.

Both Pydantic models must declare each field as:

```text
float, default 1.0, gt 0, allow_inf_nan false
```

Flutter must represent each field as `double`. `fromJson()` must accept JSON
integers and decimals through the existing `num.toDouble()` boundary and must
restore `1.0` only when the key is absent. A present non-number must fail
deserialization instead of being silently replaced.

The Management API must define one shared
`OptimizerCalculationParams` Pydantic model in
`src/schemas/optimizer_calculation.py`. The following mutation contracts must
reuse that model rather than accepting an untyped `dict` or declaring local
duplicates:

- `PUT /optimizer/calculate`;
- `POST /twins/{twin_id}/optimizer-runs/`;
- `PUT /twins/{twin_id}/optimizer-config/params`;
- `PUT /twins/{twin_id}/optimizer-config/result`;
- `PUT /twins/{twin_id}/config/` when `optimizer_params` is present.

This shared model must match the Optimizer request contract for every existing
field, including storage-duration ordering, disabled GCP self-hosted paths,
currency values, finite-number checks, and defaults. This phase may remove
Management-only permissiveness that allowed payloads the Optimizer could never
execute. Read responses remain JSON objects for compatibility.

The shared Management model must expose two explicit projections:

```text
to_optimizer_payload()
    complete validated payload
    minus only additive compatibility-default fields omitted by the caller

to_persisted_payload()
    complete validated canonical payload including defaults
```

The direct calculate route and calculation-run service must use
`to_optimizer_payload()` for the downstream call so the Optimizer can
distinguish omitted compatibility fields through its own `model_fields_set`.
Configuration and run persistence must use `to_persisted_payload()`. The
implementation must not apply global `exclude_unset=True`, because doing so
would silently change the established defaults of unrelated fields.

The Management API continues to persist canonical `CalcParams` in the existing
`optimizer_configurations.params` and calculation-run JSON text. No relational
schema change or migration is required.

Compatibility rules:

- old payload without either field: accepted; both additive keys remain omitted
  in the downstream request, the Optimizer applies `1.0`, and trace marks
  `compatibility_default`;
- new payload with valid fields: forwarded unchanged and trace marks
  `explicit_input`;
- zero, negative, NaN, or infinity: rejected before downstream calculation;
- old stored JSON: readable and canonicalized with explicit `1.0` fields on the
  next write;
- current response shape: additive trace changes only.

## Flutter UI

The primary configuration journey must remain compact. The existing Twin
capabilities substep receives one initially collapsed advanced section after
the 3D settings and before dashboard usage.

### Desktop And Web Layout

The layout is identical on desktop and web. It extends the existing single
column `CalcFormSection.twinCapabilities` layout and does not introduce a new
responsive breakpoint.

```text
+--------------------------------------------------------------+
| Twin capabilities                                            |
| Describe 3D representation and dashboard usage requirements. |
|                                                              |
| 3D representation                                            |
| [ Existing 3D controls ]                                     |
|                                                              |
| > Advanced twin usage assumptions                            |
|   Used to estimate provider-specific billing quantities.     |
|                                                              |
|   Expanded:                                                  |
|   Avg. query units/query                 [ 1.0             ] |
|   Avg. query response size (KB)          [ 1.0             ] |
|                                                              |
| Dashboard usage                                              |
| [ Existing dashboard controls ]                              |
+--------------------------------------------------------------+
```

No new navigation item, modal, page, or provider-specific Azure card may be
introduced.

### Widget Tree

```text
CalcForm [MODIFY]
`-- _CalcFormState [MODIFY]
    |-- _buildTwinManagementSection() [MODIFY]
    |   `-- Card [REUSE]
    |       `-- Column [REUSE]
    |           |-- existing 3D controls [REUSE]
    |           `-- ExpansionTile [REUSE MATERIAL]
    |               |-- title/supporting text [NEW]
    |               `-- Column [REUSE]
    |                   |-- _buildDecimalInput(query units) [REUSE]
    |                   `-- _buildDecimalInput(response KB) [REUSE]
    `-- _buildVisualizationSection() [REUSE, UNCHANGED]
```

Existing pricing, review, and overview screens already use Material
`ExpansionTile`; no new disclosure widget is justified. Existing private
`_buildDecimalInput()` owns field layout and validation. It must be tightened to
reject non-finite values for every decimal field without changing valid
existing behavior.

The implementation must use the existing theme tokens and input builders. It
must not add inline colors, new third-party icons, or direct service calls.
`CalcForm` remains a presentation-owned form boundary: it may hold transient
field state and emit typed `CalcParams`, but it must not call the Management
API, Optimizer, or Deployer. The owning wizard BLoC and existing callback
contract remain unchanged.

## Error Handling

- Pydantic validation must return `422` for invalid input values.
- Direct calculator misuse must raise a descriptive `ValueError` naming the
  invalid quantity.
- Missing Azure operation or query prices must fail visibly through the existing
  required-price boundary.
- The message price remains provider evidence, but the baseline calculation
  must not require it to multiply a topology-derived zero quantity.
- Registry validation and pricing publication still require a valid message
  evidence record. The zero-quantity calculation exception must not turn
  missing provider evidence into publishable evidence.
- No error response may include credentials, access tokens, provider payloads,
  or local file paths.
- Flutter must show existing field-level validation and preserve the current
  form state after an invalid edit.

## Required Implementation Sequence

Every step is mandatory and must not be skipped.

1. Update registry and service-model contracts first.
2. Add and test the shared 1 KB billable-unit helper.
3. Add derived quantity fields to `_calculate_derived_params()`.
4. Simplify `AzureDigitalTwinsCalculator` to accept explicit quantities.
5. Reconcile Azure L4 components with the ADT Pusher path and remove the stale
   L4 Event Grid/ADT Updater cost entries.
6. Add the exact operation/message/query intent, mapping, classification,
   source, provider-contract, formula, and optimization-bundle identifiers
   specified above.
7. Remove `queryUnitTiers` from fetcher/schema/generated baselines and all
   affected tests.
8. Update Optimizer API request schema, omission-source capture, and API
   examples.
9. Introduce the shared Management API request schema and apply it to direct
   calculation, persisted runs, optimizer configuration mutations, and wizard
   persistence.
10. Update Flutter `CalcParams`, defaults, fixtures, demo data, and serialization
   tests.
11. Add the compact advanced controls, result labels, and widget tests.
12. Update `intentTrace`, `resultTrace`, and persisted-run projection tests.
13. Update developer and user documentation.
14. Run focused tests, full project regression suites, strict docs build, and
   two independent code-review passes.
15. Fix every finding before committing.

## Test Matrix

### Optimizer Unit Tests

| Type | Case | Required hard assertion |
|---|---|---|
| Happy | 0.25 KB and 1.0 KB responses | one operation per query |
| Happy | 1.01 KB and 2.01 KB responses | two and three operations per query |
| Unhappy | negative count | descriptive `ValueError` |
| Unhappy | zero, NaN, or infinity size with positive count | descriptive `ValueError` |
| Edge | zero count and zero size | exact zero |
| Edge | exact 2.0 KB boundary | exact two units, no drift |
| Edge | fractional query-unit weight | exact decimal query quantity and cost |
| Edge | zero baseline routed messages | exact zero message quantity and cost |
| Edge | nonzero L1 Event Grid usage | ADT routed-message quantity stays zero |
| Topology | Azure L4 component set | exact ADT meter keys plus ADT Pusher only |
| Regression | missing operation/query price | visible required-price failure |
| Regression | repository search | no runtime/fixture `queryUnitTiers` remains |

### Optimizer API And Integration Tests

| Type | Case | Required hard assertion |
|---|---|---|
| Happy | omitted additive fields | both engine values are exactly `1.0` |
| Happy | valid decimal fields | values reach derived quantities unchanged |
| Unhappy | zero/negative value | `422` names the rejected field |
| Unhappy | NaN/infinity JSON value | `422`; calculation is not invoked |
| Edge | low-volume request | exact Azure L4 component values |
| Edge | exact 1 KB response | exact operation count |
| Edge | just-over-1 KB response | next billing increment applied |
| Edge | high-volume decimal query weight | stable exact expected result |
| Edge | Azure L4 not selected | trace retains alternative evidence without claiming selection |
| Trace | `intentTrace` | raw assumptions, three quantities, formulas, evidence and topology present |
| Trace | `resultTrace` | workload values come from derived quantities, not raw query count |
| Trace | omitted additive fields | source is `compatibility_default` |
| Trace | supplied additive fields | source is `explicit_input`, including supplied value `1.0` |
| Registry | inventory and bundle | no false tier; three Azure meter contracts resolve |
| Registry | Azure-only coverage | operation/message require Azure only; query-unit retains AWS/Azure/GCP coverage |
| Registry | normalized ADT evidence | each 1K source row normalizes to exactly `raw_price / 1,000` |
| Registry | mapping drift | changed meter identity is review-required and cannot publish through keywords alone |
| Registry | missing message evidence | calculation of zero remains deterministic but publication remains non-publishable |

### Management API Tests

| Type | Case | Required hard assertion |
|---|---|---|
| Happy | valid additive fields | direct proxy and run service forward exact numeric values once |
| Happy | persisted configuration/run | canonical fields and both trace projections round-trip |
| Contract | all five mutation boundaries | reuse the shared typed schema; no untyped params mutation remains |
| Contract | Management/Optimizer schemas | field names, required flags, defaults, numeric bounds, and currency enum match |
| Unhappy | invalid finite/range input at each mutation boundary | local `422`, no downstream call or persistence |
| Unhappy | downstream standardized validation error | existing safe error mapping preserved |
| Edge | old direct/run request | additive keys omitted downstream; canonical persisted values are `1.0` |
| Edge | explicit `1.0` request | additive keys forwarded and classified as explicit |
| Edge | old stored JSON | readable and canonicalized on next write |
| Edge | integer JSON value | serialized downstream as valid number |
| Edge | decimal JSON value | precision retained |
| Edge | unrelated optimizer fields | unchanged in forwarded and stored payload |

### Flutter Tests

| Type | Case | Required hard assertion |
|---|---|---|
| Happy | model default and JSON round-trip | both values equal expected doubles |
| Happy | expand and edit both controls | one typed callback state contains both edits |
| Unhappy | zero/negative field text | exact field error and invalid form callback |
| Unhappy | NaN/infinity text | rejected; no non-finite `CalcParams` emitted |
| Edge | old JSON omits fields | both defaults equal `1.0` |
| Edge | integer JSON values | converted to `double` |
| Edge | section first renders | advanced controls are absent/collapsed |
| Edge | initial saved custom values | expanded controls show exact values |
| Edge | apply existing preset | assumptions retain documented defaults |
| Regression | section navigation and other fields | existing callbacks and values unchanged |
| Integration | Management OpenAPI | both fields expose number type, `1.0` default, and exclusive minimum `0` |
| Integration | invalid Management request | authenticated local request returns `422` before any Optimizer/provider work |

### Regression Gates

Required commands must use the repository Docker/runtime conventions:

```bash
docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/unit/calculation_v2 \
  tests/unit/pricing tests/unit/optimization -q'

docker compose exec -T 2twin2clouds sh -lc \
  'PYTHONPATH=/app pytest tests/integration -q'

docker compose exec -T management-api sh -lc \
  'PYTHONPATH=/app pytest tests -q'

cd twin2multicloud_flutter
flutter analyze
flutter test
flutter build web
flutter build macos

./thesis.sh test frontend
./thesis.sh test frontend-integration

docker compose --profile docs exec -T docs mkdocs build --strict
```

Windows and Linux remain supported application targets. The implementation must
touch platform-neutral Dart only. Existing Linux and Windows CI build jobs must
be inspected after push and must remain green; local macOS and Web builds are
the executable host gates for this phase.
No live provider deployment E2E may be run.

## Documentation Updates

The implementation must update:

- this plan with implementation notes, review findings, and exact verification;
- `docs/plans/2026-06-08_pricing_evidence_and_optimization_strategy_roadmap.md`;
- `2-twin2clouds/pricing_registry/service_models.yaml`;
- `docs-site/docs/components/optimizer.md`;
- `docs-site/docs/user-guide/configuration-workspace.md`;
- legacy Azure pricing HTML only to remove the false field or replace it with a
  pointer to canonical documentation.

Thesis analysis and evaluation conclusions must not be added to the user/developer
documentation site.

## Review Gates

### Architect Review

The reviewer must verify:

- query units are modeled as workload consumption, never pricing tiers;
- all API datatypes/defaults are identical;
- quantity derivation and price multiplication have separate ownership;
- both trace projections are reproducible and use derived query units;
- no ADT message volume is inferred from the separate L1 Event Grid path;
- scope does not leak into AWS, transfer, or Phase 8 architecture work;
- defaults are visible and documented;
- no relational migration is required.

### Builder Review

The reviewer must verify:

- every touched file and test is named by this plan;
- no implementation decision remains ambiguous;
- old payload and old saved-state behavior is explicit;
- UI placement and interaction are fully specified;
- all commands can run without real cloud credentials;
- no placeholder, fallback tier, or fake provider evidence is introduced.

Both reviews must be repeated after implementation. Findings must be fixed and
the review repeated until zero findings remain.

## Definition Of Done

- [ ] Issue #114 is linked and reflects the implemented scope.
- [ ] `queryUnitTiers` is absent from runtime, registry, generated data, tests,
      and canonical documentation.
- [ ] The canonical workload contract contains both additive fields with
      matching validation and explicit defaults.
- [ ] Every Management API CalcParams mutation uses one shared typed schema;
      no alternate untyped write path remains.
- [ ] Azure operation, message, and query quantities follow the formulas in
      this plan.
- [ ] Baseline ADT routed-message quantity and cost are exactly zero and the L1
      Event Grid path remains independently priced.
- [ ] Azure L4 publishes ADT operation/query/message and ADT Pusher components;
      stale ADT Updater/Event Grid components are absent.
- [ ] The calculator consumes explicit derived quantities only.
- [ ] `intentTrace` and `resultTrace` prove every changed quantity, topology
      assumption, formula, and evidence reference.
- [ ] Old API payloads and persisted JSON remain readable.
- [ ] Trace distinguishes `explicit_input` from `compatibility_default`
      without trusting client-supplied provenance.
- [ ] Flutter exposes the assumptions in a collapsed advanced section.
- [ ] Optimizer, Management API, Flutter, and docs tests pass.
- [ ] Web and macOS builds pass; platform-neutral Windows/Linux support is not
      regressed.
- [ ] Strict MkDocs build passes.
- [ ] No real cloud deployment was executed.
- [ ] Two post-implementation reviews report zero open findings.
- [ ] The implementation is committed separately with `Refs #114`.
