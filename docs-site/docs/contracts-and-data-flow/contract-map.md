# Cross-Project Contract Map

```text
Twin intent
   |
   v
Management ---- exact calculation request ----> Optimizer
   |                                             |
   |<-- result + cost trace + immutable graph ---+
   |
   +---- readiness/package/operation ----------> Deployer
   |                                             |
   |<-- progress + verification + cleanup -------+
   |
   v
Flutter read models and confirmations
```

| Contract | Owner | Required consumers | Purpose |
|---|---|---|---|
| `six-layer-eventing@1` definition | shared repository source | Optimizer, Management, Deployer, Flutter | fixed responsibilities, components and edges |
| Six-layer workload v1 | shared repository source | Flutter, Management, Optimizer | typed comparable experiment input |
| pricing snapshots and formula registry | Optimizer | Optimizer; Management verifies references | reproducible cost input and trace |
| resolved architecture v2 | Optimizer, validated by Management | Management, Deployer, Flutter | immutable placement and edge evidence |
| resolved deployment specification v2 | Optimizer, validated by Management | Deployer, Flutter | exact deployable dimensions and readiness gates |
| deployment manifest v4 | Management | Deployer | package identity and integrity |
| deployment access v1 | shared repository source | Management, Deployer, Flutter | provider-accurate L4/L5 handoff |
| cleanup evidence v1 | Deployer, persisted by Management | Flutter and evaluation | removed, retained-shared, and residual resources |

Generated copies are synchronized into service-specific runtime locations and
checked for digest drift. Schema version numbers do not imply multiple
user-selectable architectures.

## Boundary rules

- `architectureProfile` fields inside internal evidence identify the fixed
  contract; they are not a public choice.
- `providerPricingContexts` and account-specific pricing plans are not part of
  calculation requests.
- credentials are absent from all portable and persisted cross-service
  evidence.
- a deployment package is valid only for the exact calculation, graph,
  connection bindings, and readiness digest for which it was created.
