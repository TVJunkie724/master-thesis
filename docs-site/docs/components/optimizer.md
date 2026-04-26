# Twin2Clouds Optimizer

The Optimizer is the cost calculation engine.

Responsibilities:

- evaluate Digital Twin scenario parameters,
- fetch or consume cloud pricing data,
- apply the EDTConf'25 cost formulas,
- recommend provider placement across the five Digital Twin layers.

It should not deploy infrastructure or persist user/twin lifecycle state.

## Provider Service Mapping

The original Twin2Clouds documentation mapped each Digital Twin layer to comparable services across AWS, Azure, and GCP. That mapping is central to the optimizer because the cost engine compares provider choices layer by layer.

![Provider service mapping](../references/diagrams/provider_service_mapping_v6.png)

## Provider Layer Mapping

The provider-layer mapping is used to reason about which services can satisfy each layer and which combinations create cross-cloud transfer costs.

![Provider layer mapping](../references/diagrams/provider_layer_mapping_1763756000144.png)

## Cost Optimization Flow

The optimizer evaluates possible provider assignments for the five Digital Twin layers. It combines layer-specific service mappings, provider capability rules, pricing data, and cross-cloud transfer assumptions. The important thesis behavior is not only the final cheapest provider, but the explanation of why a layer was mapped to a provider.

The original docs describe the optimizer as a decision graph: each layer/provider choice becomes a candidate node, edges represent valid transitions and transfer costs, and the cheapest path through the graph becomes the recommendation. That model is still the right mental model for the thesis platform.

## Pricing Data

| Provider | Pricing source | Credential behavior |
|----------|----------------|---------------------|
| AWS | AWS Price List API | read-only pricing credentials are enough for optimizer pricing fetches |
| Azure | Azure Retail Prices API | public pricing data can be fetched without the same credential burden |
| GCP | Cloud Billing Catalog API | service account/project setup may be required depending on fetch path |

Pricing freshness and fetch errors must be visible because stale or partial pricing data changes the quality of the recommendation.

## Implementation Notes

- one canonical `LayerResult` model,
- shared layer calculator contracts,
- explicit provider capability modeling,
- visible pricing freshness and fetch errors,
- versioned pricing schema.

The optimizer remains a calculation service. It should not deploy resources, own user state, or assume that a recommendation has already been accepted by the user.
