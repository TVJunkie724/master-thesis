# Pricing and Cost Optimization

## Frozen evidence boundary

The thesis runtime uses one reviewed, dated, cited, and content-hashed price
snapshot for each selected provider region. Those snapshots are repository
evidence, not mutable application state.

The PoC deliberately has no provider price refresh, mapping review center,
approval workflow, pricing credential, account-plan administration, or live
catalog scheduler. Price drift is handled through provenance, sensitivity
analysis, and limitations in the thesis.

## Calculation flow

```text
typed Six-layer workload
  + fixed architecture contract
  + exact AWS/Azure/GCP snapshot references
  + provider capability contracts
  + cost formulas and transfer policy
        |
        v
admissible complete provider assignments
        |
        v
component + edge + transfer cost contributions
        |
        v
minimum monthly monetary cost
        |
        v
result trace + resolved graph + deployment specification
```

Only estimated monetary cost participates in scoring. Latency,
sustainability, resilience, weighted scoring, and strategy selection are not
runtime inputs.

## Reproducibility

Every successful result identifies:

- the canonical architecture and workload digests;
- each provider snapshot ID, region, timestamp, source and digest;
- formula and pricing-model references;
- component, edge, transfer, and billing-pool contributions;
- evaluated and rejected candidate counts with bounded reasons; and
- the exact resolved architecture and deployment-specification digests.

Provider-native units are normalized by reviewed formulas before totals are
compared. The Optimizer evaluates complete functionally admissible paths rather
than choosing the cheapest provider independently for each responsibility.

The historical Five-layer v1 calculation is an offline baseline only. It does
not enter the normal API/UI workflow and cannot produce a deployable result.
