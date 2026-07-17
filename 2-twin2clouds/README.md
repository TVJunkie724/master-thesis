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
- cost-based provider selection for layers L1-L5,
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
       -> cost result + trace evidence
```

The canonical layer model is:

| Layer | Capability |
|---|---|
| L1 | Data ingestion |
| L2 | Processing and orchestration |
| L3 | Hot, cool, and archive storage |
| L4 | Twin management |
| L5 | Visualization |

GCP self-hosted L4/L5 implementations are not available in the Deployer and
therefore fail closed in calculation requests. They are never represented as
zero-cost deployable alternatives.

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
must supply the exact reviewed AWS, Azure, and GCP catalog references under
`providerPricingCatalogs`; the Optimizer resolves all three immutable snapshots
before any formula executes and returns the same references in the result.
Requests may ask for `USD` or `EUR` output. EUR results use the cached
exchange-rate snapshot and expose `currencyConversion` metadata with source
currency, target currency, rate, and retrieval time. Invalid or missing rates
fail closed.

The response also includes:

- selected providers per layer,
- provider and transfer cost breakdowns,
- optimization profile and strategy identifiers,
- registry/evidence references,
- bounded `intentTrace` and `resultTrace` diagnostics.

## Repository Layout

| Path | Purpose |
|---|---|
| `api/` | FastAPI transport adapters |
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
