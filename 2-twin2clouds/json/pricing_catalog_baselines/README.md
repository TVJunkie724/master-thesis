# Frozen Optimizer pricing baseline

This directory is the source-controlled, read-only pricing input for the thesis
Optimizer. `baseline.json` pins exactly one immutable snapshot per provider:

| Provider | Pricing region |
|---|---|
| AWS | `eu-central-1` |
| Azure | `westeurope` |
| GCP | `europe-west1` |

`backend/pricing_catalog_repository.py` reads this directory directly, validates
the manifest and snapshot identities/digests, and rejects unpinned references.
`backend/pricing_catalog_resolver.py` supplies the three resolved provider
payloads to calculation. There is no runtime refresh, startup migration, seed
copy, or writable catalog volume. `PRICING_CATALOG_BASELINE_ROOT` can select a
different complete, reviewed package; it does not enable fetching.

## Active Six-layer prices and provenance

The pinned snapshots use `pricing-provider-schema.v2`. Their `sixLayer` rate
cards cover registered component capacity dimensions, directed route prices,
meter units, tiers, minimum charges, and frozen currency conversions. The
supplemental source manifest is
`../../pricing_registry/six_layer_rate_card_sources.v1.json`; its review date
is 2026-08-25. Each snapshot binds that source manifest and its rate card by
digest. All three active references are marked `reviewed_baseline` / `reviewed`.
The compatibility field `fetched_at` records the publication's review timestamp,
not a new live API observation for every constituent price.

Event-layer topology costs also use the frozen generated contract
`backend/contracts/generated/architecture-profiles/definitions/six-layer-eventing-v1-cost-registry.json`
(relative to the Optimizer root). Calculation reconciles its component and
route allocations against the selected topology; the regression suite checks
all 243 registered topology/scenario combinations.

These are reproducible model inputs, not a claim of today's market prices or
an account-specific billing quote. Source dates, service editions, allowances,
regional applicability, and minimum billing periods still limit interpretation.
Currency conversions are frozen too; they are not today's exchange rates.

Earlier provider observations and curated fields remain in the payloads for
reconstruction and the offline five-layer baseline. In particular, retained GCP
fields marked `fallback_static` are not retroactively validated live Catalog
observations. The reviewed Six-layer overlay does not erase their provenance.

## Transfer contract

Each provider snapshot contains a strict `transfer-pricing-catalog.v1` document:
source region/geography, route, network tier, billing scope, native unit, exact
byte divisor, evidence identity, and contiguous explicit tiers. AWS and Azure
use decimal GB (`1,000,000,000` bytes); GCP uses GiB (`1,073,741,824` bytes).
The transfer calculator validates this document without a scalar
`egressPrice` / `pricePerGB` fallback.

## Offline verification and retained history

From `2-twin2clouds`, using the project test dependencies:

```bash
PYTHONPATH=. python -m pytest -q tests/unit/pricing \
  tests/unit/architecture_profiles/test_six_layer_optimizer.py \
  tests/integration/test_pricing_catalog_api.py
```

These checks cover snapshot integrity, deterministic rate-card reconstruction,
meter coverage, real frozen-price calculations, and read-only API resolution.
They do not contact provider pricing APIs or deploy cloud resources.

`history/` and predecessor snapshots are retained as scientific provenance and
inputs to the offline transformation/publication tests. They are not selectable
through the runtime repository. The offline scripts
`scripts/upgrade_transfer_pricing_baseline.py` and
`scripts/publish_six_layer_rate_cards.py` reconstruct reviewed packages; they
are not live fetchers. Any future price change requires review, explicit
publication of a new versioned package, and calculation regression checks.

Never store account context, credentials, tokens, or client-authored pricing
payloads here.
