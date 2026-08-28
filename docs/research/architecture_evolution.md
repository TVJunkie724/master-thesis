---
title: "Architecture Evolution and Decision Trace"
description: "Traceable evolution from the predecessor architecture to the evaluated Twin2MultiCloud thesis PoC."
tags: [thesis, architecture, decisions, traceability, evaluation]
lastUpdated: "2026-08-28"
version: "1.1"
---

# Architecture evolution and decision trace

Status: active thesis rationale; live validation remains pending.

## Purpose and evidence boundary

The thesis must not present the final implementation as if it had been the
original design. This record separates inherited predecessor behavior,
reasoned architecture changes, offline verification, and later live-cloud
evidence. It complements the
[`development_and_decision_log.md`](../development_and_decision_log.md): that
log states the durable target decisions, while this document explains the
change from the predecessor baseline and the alternatives that were rejected.
Provider-by-provider service additions, replacements, and refinements are
tracked separately in
[`service_selection_evolution.md`](service_selection_evolution.md).

Every material architecture change is recorded before it is implemented or
re-sized. A decision may be supported at four different evidence levels:

1. **inherited** — observed in predecessor code, documents, or fixtures;
2. **reasoned** — justified by the research questions and cited provider facts;
3. **offline-verified** — covered by contracts, deterministic calculations,
   generated manifests, Terraform validation, or non-cloud tests; and
4. **live-validated** — observed in a supervised provider run with
   digest-bound evidence.

Offline evidence is never promoted to a live claim. Git preserves detailed
implementation history, but it is not a substitute for this methodological
decision trace.

## Decision-record fields

Each accepted or superseded change must identify:

| Field | Required content |
|---|---|
| Baseline | Exact predecessor behavior and its source |
| Trigger | Gap, contradiction, deployment blocker, or research need |
| Decision | Retained, changed, or removed behavior |
| Alternatives | Serious options considered, including the simpler option |
| Rationale | Why the decision is proportionate for the thesis PoC |
| Research-question link | RQ1, RQ2, RQ3, RQ3.1, or RQ3.2 |
| Consequence | Capability, cost, complexity, and known limitation |
| Evidence | Contract, test, calculation, provider source, or live record |
| Status | proposed, accepted, offline-verified, live-validated, or superseded |

An open decision remains visibly open. Active documents must not silently
rewrite an unresolved choice into an established fact.

## Evolution overview

| ID | Predecessor or earlier boundary | Current thesis-PoC boundary | Primary reason | RQ | Status |
|---|---|---|---|---|---|
| AE-01 | Five scientific responsibilities with Eventing hidden in processing or provider glue | Five original responsibilities plus an independent, non-linear Event Layer | Make routing, buffering, retry/DLQ, replay, trust boundaries, bridges, and their costs observable | RQ1, RQ2, RQ3.2 | offline-verified; live pending |
| AE-02 | Architecture composition could be interpreted as selectable or inherited profiles | One standalone, hashed `six-layer-eventing@1` deployment contract; Five-layer v1 is an Optimizer-only offline baseline | Reproducibility and a bounded PoC instead of a topology/profile product | RQ1, RQ3.2 | offline-verified |
| AE-03 | Device feedback was represented by optional historical input behavior | Authenticated telemetry plus correlated cloud-to-device command and device-outcome behavior is part of the functional gate | Preserve an actuating Digital Twin path and compare providers by function rather than layer label | RQ2 | offline-verified; live pending |
| AE-04 | GCP device connectivity was not closed by a current, directly comparable managed IoT boundary | BifroMQ provides the MQTT device boundary and Pub/Sub owns durable backend command/event delivery | Preserve bidirectional MQTT semantics without pretending Pub/Sub is a device broker | RQ1, RQ2, RQ3 | capability accepted; live sizing open |
| AE-05 | Theoretical GCP broker capacity used a three-replica GKE allocation, including for Small | The Small live bundle must be measured and explicitly sized as a non-HA PoC before execution; Medium and Large remain theoretical | Three `e2-standard-8` broker nodes are not justified by the 100-device Small workload | RQ2, RQ3 | proposed; blocks GCP-L1 live approval |
| AE-06 | Several potential optimization objectives and public profile choices existed in the implementation surface | Monetary cost is the only active objective behind one small scoring-strategy boundary | Answer RQ3 reproducibly without claiming a generic optimization framework | RQ3, RQ3.1 | offline-verified |
| AE-07 | Mutable deployments implied update, migration, rollback, and replacement semantics | Draft Twins are editable; deployed Twins are immutable; duplicate/import creates an independent draft | Bound lifecycle and cost risk to what the RQs require | RQ1 | offline-verified; live pending |
| AE-08 | External application login and identity-provider integrations expanded the product surface | One local owner profile retains data ownership; external login UI remains dormant behind an adapter boundary | Preserve user-scoped credentials without building an authentication product | RQ1 | offline-verified |
| AE-09 | Broad deployment testing could enumerate many redundant layer permutations | Three provider-local and six directed multi-cloud Small scenarios, preceded by component and identity probes | Cover every provider direction while controlling cost and separating partial from final evidence | RQ1, RQ2, RQ3.1 | planned; live pending |
| AE-10 | Broad provider service labels appeared comparable by layer position | One evidence-backed provider bundle per responsibility, including explicit support services, access paths, and cost owners | Functional equivalence cannot be inferred from product names; service changes must remain thesis-traceable | RQ1, RQ2, RQ3 | offline-verified; live pending |

## AE-01 — Explicit non-linear Event Layer

### Baseline and trigger

The predecessor Five-layer model remains scientifically useful for Data
Acquisition, Processing, Storage, Twin Management, and Visualization. Its
runtime integrations nevertheless make Eventing appear as incidental glue.
That hides independently placeable and costed behavior: durable acceptance,
fan-out, ordering, retry/dead-letter handling, replay, cross-provider bridges,
and identity exchange.

### Decision and alternatives

The active contract models Eventing as an independent responsibility that can
connect non-adjacent layers. The Five-layer calculation remains a separate,
immutable offline reproduction. Keeping Eventing implicit was rejected because
it prevents a defensible RQ3.2 comparison; turning the PoC into an arbitrary
architecture editor was rejected because it is not required by any RQ.

### Consequence and evidence

The change increases the number of explicit services and edges, but makes cost
attribution and verification possible. Contract, pricing, graph, RDS, and
Terraform checks are offline evidence only. The nine supervised scenarios must
later establish deployability and functional behavior.

## AE-03 — Bidirectional device behavior

### Baseline and trigger

Historical inputs exposed device feedback as optional behavior. The active
functional comparison requires more than one-way telemetry: a command must be
issued from the cloud side, reach the simulated device, produce a correlated
outcome, and become durably queryable. Without this decision the evaluation
would compare telemetry pipelines rather than an actuating Digital Twin path.

### Decision and alternatives

Authenticated telemetry and a correlated command/outcome roundtrip are part of
the common gate for all three providers. A telemetry-only HTTP-to-event-service
path remains a technically simpler alternative, but is rejected while RQ2
claims bidirectional functional comparability.

### Consequence and evidence

AWS and Azure can use their provider IoT boundaries. GCP requires a device-side
MQTT adapter in front of Pub/Sub. This decision justifies the broker capability;
it does not justify production-grade HA or the current Small node size. The
simulator must record both forward telemetry and reverse command/outcome traces
in the live metrics evidence.

## AE-04 and AE-05 — GCP L1 capability versus live sizing

The architecture decision and the capacity decision are intentionally
separate:

- **Capability:** BifroMQ terminates authenticated MQTT device sessions and
  bridges to Pub/Sub; Pub/Sub remains the durable backend owner.
- **Capacity:** the earlier three-replica `e2-standard-8` allocation originates
  from HA and large-capacity reasoning, not from the `core-small` workload of
  100 devices, a two-minute interval, and 0.25 KB messages.

Before any GCP-L1 live authorization, an offline decision must compare at
least:

1. a modest non-HA BifroMQ deployment in the GKE cluster already needed by the
   GCP visualization bundle;
2. a small dedicated broker VM; and
3. the telemetry-only managed-ingress alternative, documented as functionally
   weaker because it removes the MQTT command path.

Only the selected Small bundle is then deployed in one supervised component
probe; the rejected alternatives do not create additional cost-incurring runs.

The selected Small bundle must preserve authentication, telemetry,
command/outcome correlation, and Pub/Sub durability. It must not claim HA. The
decision records provision time, resource count, measured message latency,
success rate, cleanup, and observed cost. Medium and Large remain theoretical
capacity discussions unless separately authorized and executed.

## Measurement-driven validation

The live evaluation uses one versioned metrics document per run. Component
probes and final scenarios remain different datasets and carry different
`run_kind` values. A functional verification message proves reachability; a
small controlled measurement batch supports descriptive latency statistics.

The default protocol is five warm-up messages followed by 50 measured messages
per required direction. Any deviation is recorded in the metrics document.
Each trace uses one correlation identifier and provider/application timestamps
for the relevant stops:

```text
telemetry:
simulator -> L1 -> durable Event Layer -> L2 -> L3 -> L4 -> L5/access

command/outcome:
L4 command -> durable Event Layer -> L1 -> simulator -> outcome -> L3/L4
```

The evaluation reports end-to-end and consecutive-stage latency, success,
timeouts, duplicates, ordering, retries, DLQ observations, deployment/readiness
time, Destroy/cleanup time, resources, and cost. Latency is an evaluation
metric, not an Optimizer objective.

## Thesis placement

| Thesis section | Use of this record |
|---|---|
| Predecessor Analysis | Establish the inherited Five-layer behavior and optional inputs without judging them by the final architecture |
| Method | Explain the decision protocol, evidence levels, functional gate, and controlled measurements |
| System Architecture | Present accepted architecture changes and their bounded alternatives |
| Evaluation | Add only offline-verified or live-validated evidence under the correct label |
| Discussion | Interpret rejected alternatives, unexpected deployment findings, cost/performance trade-offs, and threats to validity |

This document is a rationale source, not final thesis prose. Claims still need
scholarly citations and synthesis in the LaTeX thesis.
