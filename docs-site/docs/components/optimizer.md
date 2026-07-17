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
| `json/fetched_data/` | generated provider results and region/currency snapshots |

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

The loader rejects duplicate keys, schema/version mismatches, missing coverage,
invalid references, non-publishable source types, and incoherent strategy bundles.
Reviewed decisions may select mappings but may not store price overrides.

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

### Versioned Pricing Baselines

The tracked files under `2-twin2clouds/json/fetched_data/pricing_dynamic_*.json`
provide inspectable offline and last-known-good baselines. A live refresh may update
these generated files, but a changed snapshot is committed only after its values,
schema metadata, and source classifications have been reviewed. The metadata is part
of the baseline: `publishable` means every required field passed its source gate;
`review_required` keeps usable last-known-good values visible without presenting them
as newly verified pricing.

The Azure baseline generated on 2026-07-16 is reproducible against the public Azure
Retail Prices API and is `publishable`. Four former static fallback paths now have
reviewed, versioned catalog evidence:

- Cosmos DB `Data Stored` is selected as `RUs`, `1 GB/Month`, Consumption;
- Blob Storage Cool and Archive select the exact LRS data-stored meters;
- Bandwidth selects `Rtn Preference: MGN` / `Standard Data Transfer Out` as an
  ordered tier series;
- Cosmos-to-Blob transfer cost derives from the first paid fetched egress tier.

The live West Europe evidence produced storage values `0.25`, `0.01`, and `0.0018`
USD per GB-month. Transfer thresholds are read from `tierMinimumUnits`; the generated
absolute limits are `100`, `10335`, `51295`, `153695`, `512095`, and `Infinity` GB.
Stable meter/product/SKU identifiers act as drift markers alongside semantic fields;
they are not a cheapest-row heuristic.

[#110 Resolve Azure pricing fallback sources with catalog evidence](https://github.com/TVJunkie724/master-thesis/issues/110)
records this hardening. The broader multi-service fetcher work remains tracked by
[#32 Refresh optimizer pricing schema and provider fetchers for expanded services](https://github.com/TVJunkie724/master-thesis/issues/32).

## Calculation Model

The calculation engine maps normalized workload quantities and provider pricing to
typed layer/component results. Provider formulas own differing charging models such as
per message, per million operations, GB-second, GiB-month, provisioned units, tier
tables, and transfer brackets. The common result unit is monthly USD, not a claim that
all raw provider units are identical.

```text
usage contract + pricing contract
  -> provider component formula
  -> LayerResult with component breakdown
  -> provider path total
  -> scoring strategy
  -> cheapest compatible five-layer path
  -> trace: profile + bundle + registry + formula + source evidence
```

AWS, Azure, and GCP have provider-specific tier tests. This is calculation coverage,
not a guarantee that every future catalog row remains valid without refresh review.

### Layer Result And Capability Contract

All provider layer calculators return the single
`backend.calculation_v2.layers.LayerResult` model. The model validates provider and
layer identity, owns an immutable component-cost snapshot, rejects invalid numeric
values, and requires a reason whenever a capability is unsupported.

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
`dataSizeInGB`, and `unsupportedReason`). The implementation contract is documented
in `2-twin2clouds/implementation_plans/2026-07-17_layer_result_calculator_contracts.md`.

`GET /capabilities/providers` publishes the complete calculation-side matrix as
`provider-service-capabilities.v1`. It is generated from calculator declarations,
contains no credential or provider calls, and is aggregated with Deployer capability
by the Management API. See [Provider Capabilities](../architecture/provider-capabilities.md).

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

Final provider-wide live refresh evidence, historical pricing analytics, additional
service tiering, and non-cost objectives remain explicit future/evaluation work.
Generated JSON snapshots are evidence artifacts, not proof that a future provider API
will continue returning the same rows.
