# Optimizer

`2-twin2clouds` is the pricing and optimization engine. It owns provider catalog
acquisition, pricing evidence, semantic intents, normalization, formulas, optimization
profiles, and cost result traceability. It does not own users, twins, review history,
or cloud deployment.

## Internal Structure

| Path | Responsibility |
|---|---|
| `rest_api.py`, `api/` | FastAPI entrypoint and internal service contracts |
| `backend/fetch_data/` | provider-specific pricing and region acquisition |
| `backend/pricing_*` | registry, evidence, candidate matching, publication, cache |
| `pricing_registry/` | editable versioned pricing/strategy source of truth |
| `backend/calculation_v2/` | typed components, formulas, layers, engine, traceability |
| `backend/optimization/` | metric, model, scoring, and executable profile registry |
| `json/pricing_catalog_baselines/` | pinned reviewed provider-region seed catalogs |
| `json/fetched_data/` | region lists and currency snapshot only |
| runtime catalog volume | immutable provider-region snapshots and atomic published pointers |

## Pricing Registry SSOT

The editable registry is YAML, not generated JSON and not the Management API DB:

| Registry | Defines |
|---|---|
| `intents.yaml` | semantic values needed by calculations |
| `normalization.yaml` | source-unit to canonical-unit transformations |
| `service_models.yaml` | provider-neutral service model groupings |
| `providers/*/mappings.yaml` | provider catalog filters and candidate extraction |
| `pricing_model_classifications.yaml` | model/tier interpretation and review status |
| `price_source_classifications.yaml` | provider API, official static, derived, unsupported, fallback |
| `review_decisions.yaml` | reviewed mapping decisions that are source-controlled |
| `optimization_bundles.yaml` | coherent metric/calculation/formula/workload/provider binding |
| `calculation_strategies.yaml` | calculation strategy metadata |
| `formula_sets.yaml` | formula ownership by bundle |
| `workload_contracts.yaml` | required usage inputs and units |
| `provider_pricing_contracts.yaml` | provider-specific required fields/build paths |
| `transfer_routes.yaml` | price-free region, geography, route-class, network-tier, billing-scope, and immutable-catalog path policy |

The loader rejects duplicate keys, schema/version mismatches, missing coverage,
invalid references, non-publishable source types, and incoherent strategy bundles.
Reviewed decisions may select mappings but may not store price overrides.

### Transfer Route Contract

The route-aware transfer foundation is implemented as a closed-world contract
for the current Europe baseline. `transfer_routes.yaml` declares only routing
and billing semantics; it cannot contain rates or tier boundaries. Exact
transfer prices remain owned by immutable provider-region pricing catalogs.

The typed domain under
`backend/calculation_v2/transfer_pricing.py` represents both endpoints,
provider regions and geographies, the route class, source network tier,
canonical byte volume, aggregate billing pool, exact catalog and evidence IDs,
and cumulative tier contributions. Decimal GB and GiB are converted from bytes
with distinct, validated divisors. Same-provider/inter-region transfer is
recognized but fails closed because the current profile supports one region per
provider.

The runtime formula rejects missing or malformed catalogs and has no scalar
egress fallback. `calculation_v2/path_optimizer.py` evaluates every executable
complete baseline path, prices all six approved edges including `L4 -> L5`,
and applies each source-provider transfer allowance once per exact billing
pool. It then passes complete totals to the active scoring strategy; the
engine no longer chooses providers greedily per layer.

The additive `complete-path-transfer-pricing.v1` result records every winning
route, same-provider zero routes, regions, geographies, network tier, byte
volume, exact catalog/evidence identities, cumulative tier contributions,
egress/glue totals, and model assumptions. Bounded
`complete-path-optimization.v1` diagnostics expose enumerated, evaluated, and
rejected path counts plus the deterministic winner. The Management API now
validates these objects against its trusted catalog context, persists the
immutable result, and creates one exact transfer result item per baseline edge.
Flutter consumes the durable Management run contract and exposes the six routes,
solver diagnostics, billing pools, and tier contributions as collapsed,
read-only evidence. No client may author or recalculate this result.

### Storage Transition Runtime Ownership

The fixed baseline storage transitions are not destination-layer costs.
Hot-to-cool is executed by the selected hot-storage provider and
cool-to-archive by the selected cool-storage provider:

```text
source storage
  -> source-owned mover runtime + schedule
  -> optional destination-owned writer
  -> destination storage
```

Every complete-path candidate therefore contains two independent
`TransitionRuntimeResult` values in addition to its seven layer results and
six transfer routes. Destination writer/glue and egress remain part of the
corresponding transfer route and exist only when the providers differ.
Destination cool/archive layer results contain storage cost and storage
deployment selections only.

The winning result exposes `baseline-transition-runtime.v1`,
`transitionRuntimeCosts`, and
`optimizationDiagnostics.winningTransitionRuntimeCost`. The runtime context
records exact source/destination ownership, invocations, formula/evidence
references, runtime component, function/trigger cost, optional destination
writer, egress, and reconciled total. Candidate scoring adds the source runtime
once; it does not add the context's explanatory writer/egress total a second
time.

For AWS, the deployed transition trigger is a legacy EventBridge scheduled
rule, not custom event-bus ingestion. Its transition result therefore charges
the mover Lambda but does not consume
`aws.eventBridge.pricePerMillionEvents`. A future migration to EventBridge
Scheduler must introduce its own reviewed pricing intent instead of reusing the
custom event-bus row.

## Evidence And Candidate Flow

```text
provider API/static official source
  -> raw provider row/evidence
  -> provider mapping predicates
  -> collision-safe canonical candidates
  -> single-row or explicit tier-series selection
  -> selected/rejected rows with bounded reasons
  -> intent-specific normalization
  -> classification + verification gates
  -> publication decision
       | publishable: atomically replace last-known-good
       | review-required: retain last-known-good and expose candidate evidence
```

Raw result identity and relevant dimensions remain inspectable so a future developer
can determine why a row was selected. Ambiguous or drifted rows become review-required
instead of silently falling back. Diagnostic fallback classifications are explicitly
non-publishable.

## Dynamic And Static Pricing

Not every billable field is available from the same provider API. The source
classification distinguishes:

- provider API;
- official static documentation;
- official calculator reference;
- reviewed curated model constant;
- value derived from provider API fields;
- not applicable or unsupported;
- diagnostic fallback only.

Each field declares its build path and verification status. This prevents a static
global charge from pretending to be a failed dynamic fetch and prevents an emergency
fallback from becoming normal calculation input.

### Immutable Regional Pricing Catalogs

The tracked seed package under
`2-twin2clouds/json/pricing_catalog_baselines/` is the inspectable offline
baseline. Each provider baseline is pinned by `baseline.json` to one exact
provider-region snapshot, including schema, registry and mapping versions,
fetch or review time, content digest, source, and review state.

At runtime, the Optimizer initializes the named
`optimizer_pricing_catalogs` volume at
`/var/lib/twin2multicloud-optimizer/pricing-catalogs`. A refresh creates a new
immutable snapshot. It atomically advances only the matching
provider-and-region `published.json` pointer when every publication gate
passes. Review-required candidates remain inspectable by exact snapshot ID but
cannot replace last-known-good calculation pricing.

Every calculation receives exactly one published AWS, Azure, and GCP reference
through `providerPricingCatalogs`. All three documents are resolved and
integrity-checked before formulas execute. The result returns the same
references, so a later refresh cannot change the evidence of an existing run.
Internal consumers verify a selected snapshot through the reference-only exact
read endpoint. The full exact-snapshot endpoint is reserved for authenticated,
explicit diagnostics through the Management API.
The former provider-wide `pricing_dynamic_*.json` files and unscoped export
endpoint are not part of the runtime contract.

The metadata is part of the baseline: `published` means every required field
passed its source gate; `review_required` keeps the candidate visible without
presenting it as newly verified calculation pricing.

The Azure baseline generated from the public Azure Retail Prices API is
`publishable`. Former static fallback paths now have reviewed, versioned catalog
evidence:

- Cosmos DB `Data Stored` is selected as `RUs`, `1 GB/Month`, Consumption;
- Blob Storage Cool and Archive select the exact LRS data-stored meters;
- Bandwidth selects `Rtn Preference: MGN` / `Standard Data Transfer Out` as an
  ordered tier series;
- Azure Digital Twins selects the exact Standard Operations, Standard Message, and
  Standard Query Units meters and normalizes each `1K` price to one billable unit.

The live West Europe evidence produced storage values `0.25`, `0.01`, and `0.0018`
USD per GB-month. Transfer thresholds are read from `tierMinimumUnits`; the generated
absolute limits are `100`, `10335`, `51295`, `153695`, `512095`, and `Infinity` GB.
Stable meter/product/SKU identifiers act as drift markers alongside semantic fields;
they are not a cheapest-row heuristic.

### Transfer Catalog Evidence

Transfer pricing is a complete catalog object, not a single `egressPrice`.
Provider fetchers select exact reviewed rows and retain all provider tier
boundaries:

| Provider | Reviewed route | Native unit | Runtime policy |
|---|---|---|---|
| AWS | Frankfurt to `External`, `AWS Outbound` | decimal GB | provider-default public egress and one reviewed aggregate allowance |
| Azure | West Europe, `Rtn Preference: MGN`, Standard Data Transfer Out | decimal GB | Microsoft Premium Global Network |
| GCP | Compute Engine Premium EMEA-to-EMEA SKU `5B70-B2D6-B4FC` | GiB | Premium Tier; Standard Tier is not eligible for the baseline |

The shared workload is converted to bytes first. Each provider catalog then
converts bytes to its native billing quantity before cumulative tier
arithmetic. `per_gib_to_gb` exists only as registry normalization metadata for
cross-provider field contracts; the transfer calculator itself preserves GCP
GiB thresholds and never relabels them as decimal GB.

The committed v2 seeds preserve the v1 manifest and snapshots for audit. The
runtime repository verifies that exact predecessor before a one-time
idempotent upgrade and preserves any newer published pointer.

### GCP Scheduler Job-Month

The two GCP storage transitions each use one source-owned Cloud Function and
one Cloud Scheduler job. Scheduler pricing is a global official-table value,
not a region-specific matching fallback:

```text
transition trigger cost = 1 scheduled job * 0.10 USD/job-month
```

The official three-job free allowance applies to the billing account. The
Optimizer does not assign that shared allowance to a Twin without explicit
account-allocation evidence. The immutable GCP baseline records the official
[Cloud Scheduler pricing](https://cloud.google.com/scheduler/pricing), value,
unit, review date, and allocation rule. The previous daily-fraction value
remains only in its immutable predecessor snapshot.

### Azure Digital Twins Quantities

Azure Digital Twins does not use a device-count tier table. The Optimizer derives
three separate billable quantities from the workload and the active
`five-layer-baseline@1` topology:

```text
telemetry updates
  + logical dashboard queries * ceil(response size in KB)
  = billable ADT operations

logical dashboard queries * average query units per query
  = billable ADT query units

routed ADT messages
  = 0 for five-layer-baseline@1
```

The query-unit and response-size assumptions default to `1.0` for old saved
configurations. Calculation traces mark whether each value was explicitly supplied or
came from that compatibility default. The operation, query-unit, and routed-message
contributions remain separate in the L4 component breakdown. A routed-message price is
still fetched and evidence-backed, even though the baseline currently produces zero
routed messages.

The Optimizer and Management API share the same validated request shape. Management
persists the complete canonical representation; direct downstream forwarding preserves
omitted additive assumptions so their provenance is not lost.

### Executable Error-Handling Boundary

`integrateErrorHandling` is retained only so historical calculation inputs can
be inspected. The current `five-layer-baseline@1` has no matching provider
resource topology, deployment specification dimension, or Terraform path.
Therefore only `false` or omission is valid for a new calculation. The HTTP
schema and direct calculation engine reject `true` with
`UNSUPPORTED_ERROR_HANDLING_TOPOLOGY` before pricing catalogs or provider
calculators are used. This rule is independent of the supported event-checking,
workflow, feedback, and event-action inputs.

[#110 Resolve Azure pricing fallback sources with catalog evidence](https://github.com/TVJunkie724/master-thesis/issues/110)
records this hardening. The broader multi-service fetcher work remains tracked by
[#32 Refresh optimizer pricing schema and provider fetchers for expanded services](https://github.com/TVJunkie724/master-thesis/issues/32).

### Azure IoT Hub Tier Selection

Azure IoT Hub is modeled as provisioned monthly capacity, not as a progressive
usage-price tier. The Optimizer determines the exact F1, S1, S2, or S3 SKU and
capacity needed by the workload. It enforces the provider maximum of one F1
unit, 200 S1 units, 200 S2 units, or 10 S3 units and fails when no registered
combination can satisfy the workload.

The provider bills messages in size blocks. The formula therefore converts
physical workload messages before selecting capacity:

```text
F1 billable messages = physical messages * ceil(message size / 0.5 KB)
S1-S3 billable messages = physical messages * ceil(message size / 4 KB)
```

The selected result retains SKU, capacity, physical messages, billable
messages, included messages per unit, unit price, and total cost under
`details.tierSelection`. The corresponding SKU and capacity are emitted as
deployment selections; billing quantities remain calculation evidence and
never become Terraform variables.

The limits and billing blocks are verified against the official
[Azure IoT Hub scaling documentation](https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-scaling)
and
[Azure service limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits).

## Calculation Model

The calculation engine maps normalized workload quantities and provider pricing to
typed layer/component results. Provider formulas own differing charging models such as
per message, per million operations, GB-second, GiB-month, provisioned units, tier
tables, and transfer brackets. The common result unit is monthly USD, not a claim that
all raw provider units are identical.

```text
usage contract + pricing contract
  -> provider component formula
  -> LayerResult with cost breakdown + deployment selections
  -> provider path total
  -> scoring strategy
  -> cheapest compatible five-layer path
  -> ResolvedDeploymentSpecification v1
  -> trace: profile + bundle + registry + formula + source evidence
```

AWS, Azure, and GCP have provider-specific tier tests. This is calculation coverage,
not a guarantee that every future catalog row remains valid without refresh review.

### Layer Result And Capability Contract

All provider layer calculators return the single
`backend.calculation_v2.layers.LayerResult` model. The model validates provider and
layer identity, owns immutable component-cost and deployment-selection snapshots,
rejects invalid numeric values, and requires a reason whenever a capability is
unsupported.

```text
provider formula inputs
  -> provider component calculators
  -> BaseLayerCalculatorSet._result(...)
  -> canonical LayerResult
  -> cost-result.v1 adapter
  -> supported provider candidates only
  -> scoring strategy
```

AWS and Azure currently support L1 through L5. GCP supports L1 through the three L3
storage tiers; GCP L4/L5 remain explicitly unsupported because the Deployer has no
verified self-hosted path. The engine reads this capability state from each result
instead of maintaining provider-name exceptions. If no provider supports a layer,
calculation fails explicitly; an unsupported zero-cost result cannot win scoring.

The deterministic matrix tests all 21 provider-layer combinations and preserves the
existing `cost-result.v1` fields (`cost`, `components`, `supported`, optional
`dataSizeInGB`, and `unsupportedReason`). The additive
`deploymentSelections` field contains stable component IDs and ordered typed
dimensions only. Every selection must match the canonical component registry
exactly; unknown, missing, duplicated, out-of-range, or contradictory values
fail before scoring can produce a deployable result. The implementation
contract is documented in
`2-twin2clouds/implementation_plans/2026-07-17_layer_result_calculator_contracts.md`.

`GET /capabilities/providers` publishes the complete calculation-side matrix as
`provider-service-capabilities.v1`. It is generated from calculator declarations,
contains no credential or provider calls, and is aggregated with Deployer capability
by the Management API. See [Provider Capabilities](../architecture/provider-capabilities.md).

### Resolved Deployment Output

The Management API creates the calculation run UUID before calling the
Optimizer. After the route-aware winner is known, the Optimizer combines its
registered layer selections with required cross-cloud receiver components and
the exact pricing/formula evidence:

```text
Management calculationRunId
  -> route-aware winning provider slots
  -> registered component selections
  -> optimization and pricing evidence
  -> JSON Schema + semantic registry validation
  -> canonical SHA-256 digest
  -> resolvedDeploymentSpecification
```

The specification is built from canonical USD calculation state before output
currency conversion. Therefore USD and EUR views of the same run have identical
deployment selections and digest. No downstream service may reconstruct SKU,
capacity, storage class, or runtime configuration from defaults.

Management persistence, DeploymentManifest v2, Deployer preflight, and typed
tfvar translation are implemented. AWS, Azure, and GCP resource bindings are
complete. The credential-free gate covers all 27 storage-provider triples and
the Azure F1/S1/S2/S3 capacity cases from formula output to Terraform resource
attributes:

```bash
./thesis.sh test deployment-contract
```

## Optimization Strategy Bundle

Cost is the only currently enabled optimization objective. The executable profile binds:

- metric provider (`cost`);
- pricing intent group;
- calculation model (`cost_model_v1`);
- optimization bundle;
- provider pricing contracts;
- formula set and workload contract;
- scoring strategy;
- result schema version and evidence requirements.

Latency, emissions, and resilience are declarations or future entrypoints, not enabled
features. A future objective must provide real metric acquisition, evidence policy,
calculation model, formulas, scoring, schemas, and tests before it can be enabled.

## AWS TwinMaker Account Pricing

AWS TwinMaker uses two distinct evidence scopes:

| Evidence | Scope | Owner |
|---|---|---|
| regional Price List catalog | public provider/region snapshot | Optimizer |
| current and pending pricing plan | user/account observation | Management API refresh history |

The Optimizer validates Standard dimensions and Tiered Bundle tiers, while Management
binds each successful account observation to the exact user-owned pricing connection,
fingerprint, verified account, region, catalog digest, and refresh run. Basic is
functionally incomplete for the current Five-Layer profile. Pending plan changes and
Tiered Bundle plans without an explicit allocation policy are not comparable.

Calculations retain the plan context even when AWS L4 does not win. Selecting an AWS L4
result for deployment requires the current account evidence to match the persisted
calculation. The Deployer remains read-only with respect to pricing plans.

## API Areas

Internal APIs expose calculation, provider pricing refresh/streaming, pricing registry
metadata, candidate/evidence reports, region acquisition, file freshness, permission
verification, and configuration validation. The Management API is the intended client.
Exact fields are available at `http://localhost:5003/docs`.

## Errors And Security

- provider errors are shaped into explicit responses rather than partial success;
- secrets are redacted from exceptions and validation output;
- credential-file checks require an explicit local-only gate;
- request-body credentials are used for normal Management API calls;
- invalid registries fail before execution;
- non-publishable evidence cannot enter the calculation contract.

## Tests

The suite covers registry validation, all provider fetchers/evidence adapters, candidate
matching, publication rules, currency, formulas, provider tiering, engine consistency,
strategy/profile contracts, API failures, and secret redaction.

```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/ -v
```

Live provider refresh is not part of deterministic default verification.

## Calculation Traceability

Every current cost result contains two versioned, complementary trace structures:

| Structure | Purpose | Authority |
|---|---|---|
| `intentTrace` (`intent-result-trace.v1`) | compact profile, workload, selected path, transfer segments, and publishability summary | selected optimization path |
| `resultTrace` (`intent-to-result-trace.v1`) | provider-field contracts, source and pricing classifications, formulas, evidence references, verification, and result scope | field-level calculation audit |

`resultTrace` derives `selected`, `alternative`, `unsupported`, and
`not_applicable` states from the canonical calculation result. Provider alternatives
are not described as rejected catalog evidence. A rejected evidence ID is emitted only
when a real fetch/review row was rejected.

Current calculators can prove component or layer totals, but generally not an exclusive
amount per pricing field. Such records therefore carry a shared scope and
`cost_contribution_is_additive: false`. Field records must never be summed. Exact
runtime selected-row evidence is also distinguished from a registry contract
reference; the trace does not claim that one is the other.

## Extension Points

### New provider pricing field

Declare intent/mapping/source/normalization/provider contract, implement acquisition,
bind it to a formula, add evidence fixtures plus accepted/rejected/tier tests, and pass
the registry validation gate.

### New optimization objective

Implement and declare metric provider, intent group, calculation model, formula set,
workload/provider contracts, scoring strategy, result schema, profile, traceability,
and broad tests. Only then mark its bundle/profile enabled.

## Evolution And Gaps

The original optimizer matched changing provider catalogs through strings and keywords,
mixed fetched and fallback values, and coupled formulas to loosely structured JSON.
The current registry/evidence/bundle architecture makes selection and calculation
traceable and fail-closed.

Final provider-wide live refresh evidence, historical pricing analytics, remaining
provider charging-model hardening, and non-cost objectives remain explicit
future/evaluation work.
Generated JSON snapshots are evidence artifacts, not proof that a future provider API
will continue returning the same rows.
