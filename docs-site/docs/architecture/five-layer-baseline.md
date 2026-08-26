---
title: "Historical Five-Layer Baseline"
description: "Optimizer-only paper-compatible baseline retained for reproduction."
tags: [architecture, baseline, optimizer, historical]
lastUpdated: "2026-08-26"
---

# Historical Five-Layer Baseline

`five-layer-baseline@1` is retained only inside the Optimizer so the original
Twin2Clouds calculation space can be reproduced. It is not an active runtime
profile and is not exposed through Management, Deployer, Terraform, or Flutter.

The historical model contains five scientific responsibilities:

1. ingestion;
2. processing;
3. hot, cool, and archive storage;
4. Twin state; and
5. visualization.

Its frozen limitations remain part of the historical result: incomplete GCP
L4/L5 realization, legacy feature inputs, and the original edge decisions. No
new runtime work should extend this model.

The standalone `six-layer-eventing@1` profile owns the current PoC service
bundles, mandatory domain behavior, provider mappings, workload, costs, and
deployment path. It does not inherit from this baseline.

Historical rationale remains available in
`docs/research/five_layer_baseline_target_decision.md`.
