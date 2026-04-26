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

Current architecture direction:

- one canonical `LayerResult` model,
- shared layer calculator contracts,
- explicit provider capability modeling,
- visible pricing freshness and fetch errors,
- versioned pricing schema.
