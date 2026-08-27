# Provider Capabilities

Provider capability evidence is a fail-closed gate between price comparison and
deployment. A service is not admissible merely because it has a price or a
Terraform template.

## Two boundaries

The generic provider-layer capability endpoints report what the legacy
layer-neutral Optimizer and Deployer paths can execute. Each entry contains:

- `available`, `disabled`, or `unsupported` availability;
- a stable reason code and reason when unavailable; and
- `not_verified`, `contract_tested`, or `live_verified` evidence level.

They contain no roadmap or future-delivery marker.

The canonical Six-layer resolver uses the stricter provider implementation and
component/edge catalogs. All three providers have complete reviewed bundles for
the closed architecture, including the GCP L4/L5 implementations that are not
part of the generic historical layer path.

## Admission rule

```text
workload + fixed architecture
  -> provider implementation bundle
  -> required capabilities, components and directed edges
  -> pricing/formula/package/Terraform evidence
  -> functional completeness
  -> candidate cost ranking
```

Missing capability or evidence excludes the candidate with a bounded reason.
It never enters scoring at zero cost.

`contract_tested` means deterministic source/fixture/package evidence exists.
Only recorded provider execution may upgrade a claim to `live_verified`.
Supervised capacity and identity gates therefore remain separate from offline
candidate admission.
