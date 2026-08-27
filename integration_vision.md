# Twin2MultiCloud Integration Vision

Status: current thesis-PoC boundary

## Research objective

Twin2MultiCloud demonstrates how a theoretical layer-based cost model can be
operationalized as a functionally gated, traceable and reproducibly deployable
Digital Twin across AWS, Azure and Google Cloud.

The contribution is not a general cloud-management product. It is the method
and evidence chain used to answer:

- how typed Twin intent becomes a cloud deployment and verification result;
- how provider implementations can be compared under the same functional
  responsibilities;
- how provider-local and multi-cloud placement affects estimated cost; and
- how Eventing topology, delivery responsibility and cost become explicit.

## Canonical architecture

The original five responsibilities—acquisition, processing, storage, Twin
management and visualization/access—remain. `six-layer-eventing@1` adds
Eventing as an independent responsibility because it owns placement, trust,
delivery semantics, directed cross-cloud edges, verification and cost.

This is the only deployable architecture. Five-layer v1 remains an isolated
Optimizer-side offline baseline.

## Integrated system

```text
Flutter
   |
   v
Management API
   |--------------------|
   v                    v
Cost Optimizer      Cloud Deployer
   |                    |
   +---- immutable -----+
        result, graph,
        operation and evidence
```

Management owns users, Twins, encrypted deployment connections, immutable
calculation evidence, readiness, operations, verification, cleanup and public
errors. Optimizer owns frozen pricing/formulas, capability admission, monetary
ranking and graph resolution. Deployer owns provider readiness, bounded
preparation, packages, Terraform/provider execution and probes.

## Supported workflow

1. Create, import or duplicate a unique Twin draft.
2. Configure typed workload and bounded university user functions.
3. Calculate one cost-only result from exact frozen pricing snapshots.
4. Review placement, exclusions, assumptions, trace and immutable graph.
5. Select existing named deployment CloudConnections.
6. Run graph readiness and confirmed bounded preparation or manual repair.
7. Confirm Deploy and follow durable/replayable progress.
8. Verify the telemetry roundtrip and open provider-owned L4/L5 surfaces.
9. Confirm Destroy and record post-destroy inventory/residual evidence.

Deployed definitions are immutable; a changed experiment becomes a new draft.

## Evaluation boundary

Offline suites prove deterministic contracts and logic. Live evaluation first
uses low-cost identity/API/capacity/image probes, then three provider-local and
six directed multi-cloud Small scenarios. Every live run has budget/duration
guardrails, immediate verification, a guaranteed Destroy attempt and residual
inventory.

Results must distinguish estimated cost, contract-tested functionality and
live-verified behavior. Limitations, sensitivity, threats to validity and the
distance to product maturity are first-class thesis outputs.
