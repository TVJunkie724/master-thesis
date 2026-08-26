# Twin2Clouds Optimizer

Twin2Clouds is the pricing and cost-optimization service in the
Twin2MultiCloud thesis platform. It evaluates a workload against versioned
pricing, formula, workload, and optimization contracts for AWS, Azure, and GCP.
The Flutter application does not call this service directly; the Management API
owns the user-facing orchestration boundary.

## Responsibility

The Optimizer owns:

- provider pricing acquisition and evidence,
- pricing-source and normalization contracts,
- monthly cost calculation,
- complete-path cost optimization across layers L1-L5,
- profile-bounded candidate construction and functional-completeness admission,
- deterministic, profile-versioned `ResolvedTwinArchitecture v1/v2`
  construction,
- bounded intent-to-result traceability,
- pricing readiness and credential preflight contracts.

It does not persist users or twins and it does not deploy cloud resources.

## Architecture

```text
Management API
  -> Optimizer API
       -> pricing registry
       -> provider fetchers
       -> normalized pricing snapshots
       -> calculation strategy + formulas
       -> fixed Six-layer strategy + completeness gate
       -> cost result + trace evidence
       -> resolved deployment specification + resolved architecture
```

The canonical layer model is:

| Layer | Capability |
|---|---|
| L1 | Data ingestion |
| L2 | Processing and orchestration |
| L3 | Hot, cool, and archive storage |
| L4 | Twin management |
| L5 | Visualization |

The historical `five-layer-baseline@1` remains an Optimizer-only reproduction.
The standalone `six-layer-eventing@1` uses the reviewed complete AWS, Azure,
and provider-hosted GCP bundles plus an independently placed Eventing
component. Missing capability or supervised capacity evidence fails closed and
is never represented as a zero-cost deployable alternative.

## Start

From the repository root:

```bash
./thesis.sh up --no-flutter
```

The host API is available at
[http://localhost:5003/docs](http://localhost:5003/docs). Normal application
traffic goes through the Management API on port 5005.

A standalone development container can be started with:

```bash
docker compose up -d 2twin2clouds
```

## Pricing Refresh

The default runtime does not read local credential files. The Management API
forwards user-scoped credentials for AWS and GCP refreshes; Azure pricing uses
the public Retail Prices API.

Canonical endpoints include:

| Method | Endpoint | Purpose |
|---|---|---|
| `PUT` | `/calculate` | Execute the enabled cost optimization profile |
| `POST` | `/fetch_pricing_with_credentials/{provider}` | Refresh provider pricing with explicit credential context |
| `POST` | `/stream/fetch_pricing/{provider}` | Stream one operation-scoped refresh |
| `GET` | `/pricing/source_inventory` | Read pricing source governance |
| `GET` | `/pricing/catalogs/baseline/{provider}` | Read the pinned reviewed baseline reference |
| `GET` | `/pricing/catalogs/{provider}/{region}/published` | Read the active regional reference and freshness |
| `GET` | `/pricing/catalogs/{provider}/{region}/snapshots/{snapshot_id}/reference` | Verify one exact reference without loading pricing |
| `GET` | `/pricing/catalogs/{provider}/{region}/snapshots/{snapshot_id}` | Inspect one explicitly identified immutable snapshot |
| `POST` | `/permissions/verify/{provider}` | Validate pricing-access credentials |
| `POST` | `/fetch_currency` | Refresh the USD/EUR conversion snapshot |

The local-file endpoints under `/fetch_pricing/{provider}` and
`GET /permissions/verify/{provider}` are disabled unless
`ENABLE_LOCAL_CREDENTIAL_FILE_CHECKS=true`. That switch is reserved for the
explicit local cloud overlay.

Provider refreshes are isolated by provider and canonical pricing region.
Duplicate same-region refreshes are rejected, immutable snapshots are written
to the durable `optimizer_pricing_catalogs` volume, and reviewed references are
published atomically. Review-required candidates never replace the regional
last-known-good pointer.

## Calculation Contract

Provider prices are normalized to canonical USD inputs. Calculation requests
must supply a Management-owned UUID under `calculationRunId` and the exact
reviewed AWS, Azure, and GCP catalog references under
`providerPricingCatalogs`; the Optimizer resolves all three immutable snapshots
before any formula executes and returns the same run ID and references in the
result.
Requests may ask for `USD` or `EUR` output. EUR results use the cached
exchange-rate snapshot and expose `currencyConversion` metadata with source
currency, target currency, rate, and retrieval time. Invalid or missing rates
fail closed.

The response also includes:

- selected providers per layer,
- provider and transfer cost breakdowns,
- all six evaluated baseline edges from L1-to-L2 through L4-to-L5,
- exact route, tier, billing-pool, and immutable catalog evidence for the
  winning complete path,
- bounded complete-path diagnostics with evaluated and rejected candidate
  counts,
- optimization profile and strategy identifiers,
- registry/evidence references,
- bounded `intentTrace` and `resultTrace` diagnostics,
- one schema-valid `resolvedDeploymentSpecification` with exact component,
  tier, SKU, capacity, storage-class, and runtime selections for the winning
  path.

Selection is not greedy per layer. The Optimizer enumerates every executable
provider assignment for the closed Five-Layer baseline, calculates layer and
route costs as one candidate total, applies each transfer allowance once per
source-provider billing pool, and passes those totals to the active scoring
strategy. Unsupported routes and capabilities fail closed rather than entering
selection as zero-cost alternatives.

### Six-Layer Resolution

The closed Six-layer resolver lives under `backend/architecture_profiles/`.
When
`ARCHITECTURE_PROFILE_RESOLUTION_ENABLED=true`, `PUT /calculate` additionally
requires the exact Management-owned `architectureProfile` reference and the
complete immutable `extensionBindings` set. The Optimizer:

1. resolves only the exact repository profile digest;
2. constructs the bounded provider/component candidates;
3. rejects incomplete components, capabilities, ports, edges, regions,
   pricing/formula evidence, deployment mappings, or extension coverage before
   cost ranking;
4. ranks only admissible complete paths with exact decimal totals and a
   canonical tie-break key;
5. emits one contract-validated RTA v2/RDS v2 pair for the standalone Six-layer
   calculation path.

The gate defaults to `true` for the reviewed `six-layer-eventing@1` path. An
explicit `false` remains the fail-closed operational rollback; it rejects
architecture fields and never falls back to a legacy result. The activated
provider definitions are contract-complete for offline calculation, while each
unresolved supervised capacity gate remains embedded in RDS v2 and prevents
deployment selection. Activation therefore does not claim a live-cloud E2E.

Six-layer calculation reads immutable repository-published provider rate
cards. `scripts/publish_six_layer_rate_cards.py` validates the source
manifest, publishes content-addressed AWS/Azure/GCP snapshots, archives the
predecessor baseline, and supports the pinned USD and EUR calculation
currencies. The rate cards are bounded to the frozen thesis Small, Medium, and
Large workloads; they are reproducible pricing evidence, not a general cloud
price catalogue. AWS IoT Commands uses the regional Commands execution SKU,
not the more expensive Device Jobs remote-action meter. Cloud Run services use
the request-based Tier-1 CPU, memory, and request rates. Account-wide free-tier
grants are deliberately excluded from both models so one allowance cannot be
counted independently for multiple architecture components. Azure Large uses a
108,000-RU/s offline comparison proxy: the
rounded maximum of the storage floor and the documented 10-RU write / 1-RU
read operation estimates for the frozen workload. Its supervised request-charge
and capacity gates remain mandatory before deployment, so the proxy cannot be
mistaken for measured capacity.

Hot-storage ownership follows the PoC data path exactly: each accepted
telemetry message creates one raw record and updates its hourly rollup in the
same provider-native transaction. Stored rollup documents remain bounded to
one per device/metric/hour, but billed reads and transactional writes count
actual operations rather than distinct documents. The combined
Cosmos/Firestore components own both operation streams; the two DynamoDB
tables keep raw and rollup meters separate. L4 bounded-twin operations remain
independent of both.

Azure IoT Hub sizing returns the selected F1/S1/S2/S3 SKU and unit capacity
rather than only a cost. Physical workload messages are normalized to the
provider billing blocks first: 0.5 KB for F1 and 4 KB for paid Standard tiers.
The result keeps physical messages, billable messages, included messages per
unit, SKU, and capacity together under `details.tierSelection`, making the
formula and deployable selection directly auditable.

## Frozen Phase 8 Evidence

The `phase_08_eventing` and `phase_08_service_bundles` packages freeze the
standalone Six-layer capability, topology, workload, pricing ownership, and
capacity assumptions. They cover three single-cloud placements, all nine
L3/L5-to-L4 placements, all six directed Event-provider pairs, and
representative three-provider graphs. This is offline estimation evidence, not
a provider invoice or live-capacity result.

## Repository Layout

| Path | Purpose |
|---|---|
| `api/` | FastAPI transport adapters |
| `backend/architecture_profiles/` | Fixed Six-layer candidate/completeness strategy, diagnostics, and resolution builder; historical Five-layer adapter |
| `backend/calculation_v2/` | Calculation engine, formulas, layer contracts, traceability |
| `backend/optimization/` | Metrics, profiles, scoring, and extension points |
| `backend/fetch_data/` | Provider pricing adapters and refresh orchestration |
| `pricing_registry/` | Versioned pricing and optimization contracts |
| `json/pricing_catalog_baselines/` | Pinned reviewed regional pricing seed snapshots |
| `json/fetched_data/` | Region lists and currency snapshots only |
| `/var/lib/twin2multicloud-optimizer/pricing-catalogs/` | Durable immutable runtime catalogs and regional published pointers |
| `tests/` | Unit and API integration tests |
| `implementation_plans/` | Approved and completed implementation records |

The integrated documentation is served from `docs-site/`. Historical HTML
under this service remains reference material and is not the canonical project
entrypoint.

## Verification

Run the complete offline quality gate from the repository root:

```bash
docker compose run --rm --no-deps 2twin2clouds sh -lc \
  'python -m pytest tests -q && \
   ruff check api backend rest_api.py && \
   python -m bandit -r api backend rest_api.py -q && \
   python -m compileall -q api backend rest_api.py && \
   python -m pip check'
```

Provider API fixture tests are safe and do not create cloud resources. Live
pricing refreshes require intentional credentials and network access.

Backlog and future work are tracked in
[GitHub Issues](https://github.com/TVJunkie724/master-thesis/issues), not in
service-local TODO files.
