# Twin2Clouds Optimizer

The pricing and cost engine of the Twin2MultiCloud PoC. The Management API
supplies workload inputs and exact pricing-catalog references; the Optimizer
returns a costed provider path, evidence and a resolved deployment specification.

## Run

From the repository root:

```bash
./thesis.sh up --no-flutter
```

The internal API reference is at [localhost:5003/docs](http://localhost:5003/docs).
Application clients use the Management API on port 5005.

## What it does

- Fetches and reviews provider pricing without silently publishing ambiguous rows.
- Compares complete five-layer provider paths, including transfer, glue and storage-transition runtime costs.
- Retains immutable catalog references and bounded calculation evidence.
- Excludes unsupported GCP L4/L5 choices.

Selection is not an independent minimum per layer. Results are estimates under
the recorded workload and pricing assumptions, not reconciled provider bills.

Architecture-aware calculation is implemented behind
`ARCHITECTURE_PROFILE_RESOLUTION_ENABLED`, default `false` in both Optimizer
and Management API. With it enabled, Management supplies the pinned profile
and extension references; incomplete candidates are rejected before ranking.
AWS/Azure profile definitions have `supported: true`, but this does not imply
default activation or live-cloud verification. See
[Architecture Profiles](../docs-site/docs/contracts-and-data-flow/architecture-profiles.md).

## Code and reference

| Path | Purpose |
|---|---|
| `api/` | HTTP adapters |
| `backend/calculation_v2/` | formulas, complete-path scoring and traceability |
| `backend/architecture_profiles/` | profile resolution and completeness checks |
| `backend/fetch_data/` | provider pricing acquisition |
| `pricing_registry/` | versioned pricing and optimization definitions |
| `json/pricing_catalog_baselines/` | reviewed baseline snapshots |
| `tests/` | unit and API contract tests |

- [Optimizer reference](../docs-site/docs/components/optimizer.md)
- [Pricing and optimization flow](../docs-site/docs/contracts-and-data-flow/pricing-optimization.md)
- [Pricing Review](../docs-site/docs/user-guide/pricing-review.md)
- [Testing](../docs-site/docs/developer-guide/testing.md)
