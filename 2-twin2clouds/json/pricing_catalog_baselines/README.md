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
| AWS | `eu-central-1` | Migrated from the 2026-07-17 provider observation, including explicit quality/evidence metadata |
| Azure | `westeurope` | Migrated from the publishable 2026-07-17 Azure Retail Prices observation |
| GCP | `europe-west1` | Curated review of the legacy calculation baseline on 2026-07-17; not represented as a successful Billing Catalog fetch |

The available GCP service-account files returned `401 UNAUTHENTICATED` during
the bounded read-only Cloud Billing Catalog preflight on 2026-07-17. The GCP
seed therefore retains explicit `fallback_static` field provenance and
`curated_legacy_review` metadata. It is an emergency reviewed baseline, not
fresh provider evidence. Replacing those fields with validated Catalog
evidence remains part of provider pricing fetcher/mapping hardening.

Regenerate the package only through the reviewed migration tool:

```bash
cd 2-twin2clouds
PYTHONPATH=. python scripts/migrate_pricing_catalog_baselines.py \
  --output-root /tmp/reviewed-pricing-catalog-baselines \
  --gcp-reviewed-at 2026-07-17T17:54:56Z
```

The tool refuses to replace an existing directory. Review the generated
package and its regression evidence before replacing the committed seeds in a
separate, explicit repository change.

Do not copy account context, credentials, tokens, or client-authored pricing
payloads into this directory.
