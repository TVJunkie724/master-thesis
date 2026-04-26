# Twin2Clouds Optimizer

The Optimizer is the cost calculation engine.

Responsibilities:

- evaluate Digital Twin scenario parameters,
- fetch or consume cloud pricing data,
- apply the EDTConf'25 cost formulas,
- recommend provider placement across the five Digital Twin layers.

It should not deploy infrastructure or persist user/twin lifecycle state.

Current architecture direction:

- one canonical `LayerResult` model,
- shared layer calculator contracts,
- explicit provider capability modeling,
- visible pricing freshness and fetch errors,
- versioned pricing schema.
