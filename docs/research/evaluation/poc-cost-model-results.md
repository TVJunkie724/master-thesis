# Frozen PoC cost comparison

Status: regenerated for the final Managed Grafana bundles on 2026-11-02.
The 2026-10-09 HTML/SVG comparison is historical and preserved in Git.
These are **modeled monthly USD**, not
experiment charges, bills, live capacity results or a new deployment matrix.

`scripts/summarize_poc_cost_model.py --check` reproduces the accompanying
[machine-readable results](poc-cost-model-results.json). It reuses the existing
Optimizer, eight planned complete-profile placements and reviewed baseline
pricing snapshots (fetched 2026-08-25). Workload, plan, candidate and pricing
digests are retained. No provider API or pricing refresh is invoked.

## Comparison and discrete scale sensitivity

The direction labels identify the matrix's focal edge, **not** a placement of
every downstream layer. Exact assignments are in the JSON. For example,
AWS→GCP places Eventing on GCP and the other seven components on AWS.

| Planned placement | Small | Medium | Large |
|---|---:|---:|---:|
| AWS local | 140.84 | 3,461.17 | 117,592.68 |
| Azure local | 219.20 | 7,922.84 | 135,756.95 |
| AWS→Azure | 222.64 | 8,056.31 | 150,237.39 |
| Azure→AWS | 223.99 | 8,122.05 | 137,121.23 |
| AWS→GCP | 114.54 | 3,675.96 | 126,571.68 |
| GCP→AWS | 296.26 | 11,588.13 | Excluded |
| Azure→GCP | 290.79 | 6,264.63 | 131,572.48 |
| GCP→Azure | 301.29 | 7,674.94 | Excluded |

Small's lowest cost among these eight placements is AWS→GCP, **26.30 USD/month
(18.67%) below AWS local**, the cheaper admissible local baseline. AWS local
becomes cheapest among the same planned placements for Medium and Large. This
is a discrete sensitivity to the three immutable workload contracts: multiple
inputs change together, not one isolated parameter. Large GCP-ingress cases
fail the existing admissibility gate and receive neither a cost nor a rank.
This report does not bypass that gate or qualify Medium/Large for live use.

The eight placements are a bounded comparison set, not proof of the global
optimizer minimum. A GCP-local complete profile is excluded by the agreed L4/L5
scope; missing responsibilities are never treated as free services. The nine
successful Core telemetry observations are a different, narrower test matrix.

## Eventing attribution and limits

For Small AWS local, the ledger assigns **105.173677027 USD/month** to Eventing
(of 140.837335030 total), principally Kinesis at 105.171471123. Moving Eventing
also introduces bridge/source/transfer charges elsewhere in the ledger: the
Eventing component subtotal alone is therefore not the total cost of a remote
topology. The report preserves component, edge and service-owner totals rather
than adding or subtracting one broker price to claim savings.

The earlier [Eventing decision evidence](../evidence/phase_08_eventing/README.md)
and its calculator also reproduce byte-identically at this checkpoint. They
are a historical component-level model with their own workload and source
cutoff, not interchangeable complete-profile prices.

- **RQ3/RQ3.1:** provider placement can lower the modeled cost for Small; the
  ordering changes with workload scale. This is conditional on frozen inputs,
  admitted functionality and the specified candidate set.
- **RQ3.2:** Eventing and cross-cloud routing have explicit cost ownership. The
  model and functional observations do not isolate a causal saving from adding
  an Event Layer, nor establish a paired live Five-layer comparison.
- Provider monthly bills, failed-run overhead and live experiment costs remain
  distinct from these monthly projections. No billing attribution is inferred.
