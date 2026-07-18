# Pricing Catalog Baseline Seeds

This directory contains the read-only, source-controlled seed package for the
Optimizer pricing catalog repository. Runtime refreshes never write here.
`compose.yaml` mounts a separate durable volume at
`/var/lib/twin2multicloud-optimizer/pricing-catalogs`.

Each snapshot is immutable and addressed by the exact reference pinned in
`baseline.json`. Optimizer startup copies missing seed snapshots into an empty
runtime volume, verifies every digest, and never replaces an existing runtime
snapshot or published pointer.

## Provenance

| Provider | Region | Provenance |
|---|---|---|
| AWS | `eu-central-1` | 2026-07-17 provider observation plus a 2026-07-18 reviewed, exact public-egress tier series |
| Azure | `westeurope` | Publishable 2026-07-17 Azure Retail Prices observation with the exact Microsoft Global Network tier series |
| GCP | `europe-west1` | Curated 2026-07-17 service baseline plus reviewed Premium Internet Egress tiers and the official Cloud Scheduler job-month price |

The available GCP service-account files returned `401 UNAUTHENTICATED` during
the bounded read-only Cloud Billing Catalog preflight on 2026-07-17. The GCP
seed therefore still retains explicit `fallback_static` provenance for
non-transfer fields and remains `review_required` overall. Transfer pricing is
no longer one of those fallbacks: it is bound to Compute Engine service
`6F81-5844-456A`, SKU `5B70-B2D6-B4FC`, the Premium EMEA-to-EMEA route, and
native GiB tiers. Replacing the remaining GCP fallback fields with validated
Catalog evidence remains provider-pricing hardening work.

Cloud Scheduler is the exception among the remaining GCP service fields. Its
global official price is stored as `0.10 USD/job-month` with reproducible
documentation evidence. The three-job free allowance is billing-account-wide
and is not allocated to an individual Twin without account allocation
evidence. Each source-owned GCP storage transition therefore contributes one
job-month exactly once. The earlier `0.003225806` value incorrectly represented
a daily fraction and remains visible only in the immutable predecessor
snapshot.

The package was upgraded non-destructively from tracked predecessor seeds.
Every old manifest remains under `history/`, old snapshots remain addressable,
and the active manifest points only to strict
`pricing-provider-schema.v2` snapshots. Reproduce a reviewed transformation
only through:

```bash
cd 2-twin2clouds
PYTHONPATH=. python scripts/upgrade_transfer_pricing_baseline.py \
  --source-root json/pricing_catalog_baselines \
  --output-root /tmp/pricing-catalog-baseline-v2 \
  --registry-root pricing_registry
```

The tool refuses to replace an existing directory. Review the generated
package and its regression evidence before replacing committed seeds. Runtime
startup recognizes only the exact tracked v1 predecessor, verifies every old
snapshot before migration, seeds every v2 snapshot immutably, and never
overwrites a newer published pointer.

## Transfer Contract

All three v2 snapshots contain one strict `transfer-pricing-catalog.v1`
document. It records source region and geography, route and network tier,
billing scope, native billing unit, exact byte divisor, evidence identity, and
contiguous explicit tier ranges. AWS and Azure bill decimal GB
(`1,000,000,000` bytes); GCP bills GiB (`1,073,741,824` bytes). Runtime
calculation validates the complete document and has no scalar
`egressPrice`/`pricePerGB` fallback. Baseline field provenance is `curated`,
while a successful future provider refresh records `fetched`; reviewed seed
data is never mislabeled as a live API observation.

Do not copy account context, credentials, tokens, or client-authored pricing
payloads into this directory.
