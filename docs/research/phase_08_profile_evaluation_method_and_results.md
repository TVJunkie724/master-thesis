---
title: "Phase 8 Architecture-Profile Evaluation Method And Results"
description: "Reproducible offline evaluation protocol and bounded interpretation for the historical Five-layer v1, Five-layer v2, and Six-layer v1 profiles."
tags: [architecture, digital-twin, eventing, evaluation, reproducibility, phase-8]
lastUpdated: "2026-08-14"
version: "1.0"
---

# Phase 8 Architecture-Profile Evaluation Method And Results

## Research Boundary

Phase 8.10 evaluates three deliberately different profile roles:

| Profile | Experimental role | Admissible interpretation |
|---|---|---|
| `five-layer-baseline@1` | Historical reconstruction | Reproduce the inherited implementation and its limitations; do not repair or rank it with the active profiles. |
| `five-layer-baseline@2` | Functionally aligned control | Estimate complete profile-local alternatives with mandatory event behavior embedded in L1/L2. |
| `six-layer-eventing@1` | Treatment | Estimate the same L1-L5 functionality plus a separately owned and separately costed Event Layer. |

The active profiles are not placed into one Optimizer result set. Their
mandatory contracts and ownership structures differ, so a numerically lower
total is not a universal recommendation for Five or Six layers. The valid
comparison is a reported delta for a matched L1-L5 context, with the
independent Event Layer amount shown separately.

The generated evidence is the numeric source of truth. This document explains
the method and interpretation without duplicating exact totals that could
drift from the machine-readable package.

## Evaluation Protocol

Every candidate passes the following ordered gates:

1. **Functional completeness.** The profile, provider bundles, mandatory
   capabilities, required edges, and ownership constraints must match.
2. **Theoretical capacity.** The frozen Small, Medium, or Large workload must
   remain within the documented formula and service-bundle bounds. A capacity
   requirement that needs supervised provider evidence remains live-unverified.
3. **Estimated cost.** Only candidates that pass the preceding gates receive a
   publishable estimated USD/month total.

Unsupported and live-unverified candidates remain evidence rows with stable
reasons. They do not receive placeholder, partial, or zero totals. This avoids
letting an incomplete architecture appear cheaper.

The generator uses frozen repository inputs, exact profile and workload
digests, the Phase 8 European region set, and immutable pricing catalog
references. It does not refresh prices, access a provider account, execute
Terraform, or create a cloud resource.

## Frozen Scenario And Placement Coverage

The active-profile matrix contains paired Small, Medium, and Large scenarios.
For each size both profiles cover:

- all nine L3-hot/L5-to-L4 placements, including the three single-cloud
  placements.

For each size Six-layer v1 additionally covers all six directed cross-provider
Event routes, all three same-provider Event routes (which correctly require
neither a bridge nor cross-cloud transfer), and one representative admissible
three-provider graph. Five-layer v2 has no independent Event placement or
Event-provider-pair result.

Five-layer v2 costs 729 admissible candidates per size. Six-layer v1 costs
2,187 per size because the independently placed Event Layer adds a provider
dimension. The package additionally reconstructs the two frozen historical v1
scenarios and preserves rejected all-GCP historical resolutions without totals.

## Exact-Once Ownership And Attribution

The evaluation records cost by explicit owner and category before summing it:

- profile-local component cost;
- provider-local support resources;
- storage-tier transitions;
- source-owned forwarder or bridge processing;
- destination-broker landing work;
- cross-cloud data transfer; and
- the independent Six-layer Event scope.

Shared fixed resources are charged once to their declared owner and are not
divided heuristically among consumers. A same-provider route has zero bridge
and zero cross-cloud transfer. Five-layer v2 internal event adapters remain in
their owning L1/L2 bundles and are not relabeled as an independent bridge.

## Result Interpretation

Within Five-layer v2, the profile-local estimate selects an all-AWS placement
for Small and Medium and an all-Azure placement for Large. Within Six-layer v1,
the profile-local estimate selects a multi-cloud placement at each frozen
size. These are outcomes of the frozen formulas, evidence, service bundles,
and scenarios—not general provider rankings.

The useful cross-profile evidence is the set of 27 exact matched-context
deltas: three sizes multiplied by the nine L3/L5-to-L4 placements. Each row
keeps the L1-L5 context fixed and reports both the whole-architecture delta and
the independently attributed Event scope. The comparison therefore exposes
what changes when Eventing becomes an architectural responsibility without
pretending that the two profiles are interchangeable candidates.

The historical v1 results remain a separate reconstruction. They document the
inherited model and implementation boundary, including unsupported GCP paths,
and are not evidence that v1, v2, and Six-layer v1 form one comparable ranking.

Exact totals, winner assignment vectors, and delta rows are available in the
[generated cost summary](evidence/phase_08_profile_evaluation/cost-summary.md)
and [machine-readable delta package](evidence/phase_08_profile_evaluation/architecture-deltas.json).

## Research-Question Mapping

| Research question | Phase 8.10 evidence |
|---|---|
| RQ1 | Frozen inputs, strict contracts, resolved-architecture wrappers, result digests, reproducibility verification, and implementation-freeze identity show how the model is operationalized reproducibly. |
| RQ2 | The functional matrix, provider-bundle capability rows, ordered admission gates, and explicit rejections separate complete from incomplete alternatives. |
| RQ3 | Profile-local result sets, exact-once cost categories, immutable pricing references, and published limitations provide traceable monetary estimates. |
| RQ3.1 | The three single-cloud cases and all admissible multicloud placements are present for every active-profile size. |
| RQ3.2 | Six-layer Event ownership, all six directed provider pairs, same-provider bridge elision, and the 27 matched-context deltas isolate the bounded Event-Layer experiment. |

The authoritative structured mapping is
[`rq-mapping.json`](evidence/phase_08_profile_evaluation/rq-mapping.json).

## Limitations And Non-Claims

This is deterministic offline PoC evidence for a Master thesis. It does not
claim:

- observed invoices or billing reconciliation;
- live throughput, latency, resilience, or quota approval;
- real cross-cloud workload-identity exchange;
- successful provider-console or Grafana browser sign-in;
- semantic equivalence of every provider-native feature beyond the frozen
  mandatory capability contract;
- sensitivity outside the three frozen workload sizes and regions;
- an exhaustive service catalog or globally optimal cloud architecture; or
- a universal winner between Five-layer v2 and Six-layer v1.

Supervised deployment, live-capacity evidence, provider identity federation,
and browser access remain separate future evidence. The detailed limitation
ledger is
[`limitations.json`](evidence/phase_08_profile_evaluation/limitations.json).

## Reproduction

From the repository root, use the frozen Optimizer image and the local
OrbStack context. The repository remains read-only during validation and the
two clean regenerations:

```bash
python3 scripts/phase_08_profile_evaluation/verify_runtime_images.py \
  --project master-thesis-deployment-contract

docker --context orbstack run --rm \
  -e RUFF_CACHE_DIR=/tmp/phase-8-profile-evaluation-ruff-cache \
  -v "$PWD:/workspace:ro" -w /workspace 2twin2clouds \
  sh -lc 'python scripts/phase_08_profile_evaluation/validate.py \
    && python -m pytest -q -p no:cacheprovider \
      scripts/phase_08_profile_evaluation/tests \
    && ruff check scripts/phase_08_profile_evaluation \
    && ruff format --check scripts/phase_08_profile_evaluation'

docker --context orbstack run --rm \
  -v "$PWD:/workspace:ro" -w /workspace 2twin2clouds \
  python scripts/phase_08_profile_evaluation/verify_reproducibility.py
```

The reproducibility verifier regenerates the package twice in clean temporary
directories and requires byte-identical artifact sets. The generated
[`evaluation-manifest.json`](evidence/phase_08_profile_evaluation/evaluation-manifest.json)
pins the implementation freeze and all evaluated inputs; the generated
[`verification.json`](evidence/phase_08_profile_evaluation/verification.json)
records artifact digests, executed safe gates, and zero cloud activity.

The whole package is indexed by
[`evidence/phase_08_profile_evaluation/README.md`](evidence/phase_08_profile_evaluation/README.md).

## Thesis Use

These notes and generated artifacts are research inputs, not final thesis
prose. Any claim moved into LaTeX must preserve the profile roles, gate order,
frozen scenario context, exact evidence citation, and limitations above. Exact
numeric values should be sourced from the generated package at synthesis time
rather than copied from this interpretation document.
