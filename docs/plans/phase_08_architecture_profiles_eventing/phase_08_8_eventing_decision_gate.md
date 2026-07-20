---
title: "Phase 8.8: Eventing Parity, Functional, Capacity, And Cost Decision Gate"
description: "Plan for the shared domain-event contract and evidence-backed embedded/Event-Layer decisions that gate five-layer-baseline@2 and six-layer-eventing@1."
tags: [architecture, eventing, pricing, capabilities, evidence, thesis, issue-146]
lastUpdated: "2026-07-20"
version: "1.9"
---

<!-- SOURCES:
- GitHub issue #146
- docs/research/digital_twin_architecture_and_eventing_layer.md
- docs/research/research_questions_and_evaluation_design.md
- docs/research/related_work_multicloud_cost_comparability_eventing.md
- Phase 8.0 graph inventory and Phase 8.1 baseline decision contract
- Current official AWS, Azure, and Google Cloud Eventing documentation to be source-ledger pinned during execution
- User-approved functional-completeness-before-cost and curated-provider-bundle boundaries
- User-approved historical @1, event-enabled five-layer @2, shared domain-event
  behavior, and removal of legacy Eventing flags from both new profiles
EXTRACTED: 2026-07-20 | VERSION: 1.9
-->

# Phase 8.8: Eventing Parity, Functional, Capacity, And Cost Decision Gate

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#146 Complete the Eventing functional and cost decision gate](https://github.com/TVJunkie724/master-thesis/issues/146) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-eventing-decision-gate` |
| Base branch | `master` |
| Evidence status | Approved offline on 2026-07-20 as `phase-08-eventing-decision@1` |
| Implementation ordering | Phase 8.6 / #152, Phase 8.7 / #138, and the immutable complete-service decision still block Phase 8.9 activation; completing this offline evidence early does not bypass them |
| Produces | Shared domain-event contract plus approved or rejected `five-layer-baseline@2` and `six-layer-eventing@1` decision package |
| Live cloud E2E | Forbidden |

Every source, matrix cell, formula input, capability decision, bridge property,
review gate, and Definition of Done item in this plan is mandatory. Phase 8.9
must not begin until this gate concludes with an explicit `approved` decision.

## Corrective Scope Addendum

The completed package proves the shared domain-event behavior, embedded
event-domain bundles, independent Event-Layer bundles, their six directed
broker bridge routes, and Eventing scenario capacity/cost. It does not prove:

- hot-to-cool or cool-to-archive cross-provider data movement;
- native/provider-hosted L4/L5 service and datasource bindings;
- complete Core Twin Small/Medium/Large capacity;
- the predecessor public Function/shared-token runtime safe;
- complete GCP L4/L5 support.

Those concerns are owned by
[`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md).
The Eventing artifacts and digests remain immutable; a separate complete-service
decision package composes with them before Phase 8.9. “All three providers”
within this completed phase means all three Event-domain providers, not that
every whole-Twin single-cloud path was already complete.

Historical uses of “activation gate” in this completed Event-domain plan mean
a live-readiness or live-capacity claim, not the offline server/profile
activation defined by the complete-service closure. Offline activation is
owned by Phase 8.9 and requires the composed complete-service package.

## 1. Outcome

This phase first freezes the domain-event behavior that both new comparison
profiles must provide. It then decides whether that behavior can be embedded
in a five-layer architecture and whether a bounded Eventing and Messaging
responsibility can be added without false provider equivalence, unowned costs,
or another provider-specific side path.

The result is one immutable decision package containing:

- one versioned Eventing workload contract;
- one versioned common domain-event flow contract;
- one immutable profile-parity decision that preserves
  `five-layer-baseline@1`, defines `five-layer-baseline@2`, and removes the
  legacy Eventing feature flags from both new profiles;
- one mandatory/optional capability contract;
- a source-backed provider capability matrix;
- a pricing-model and unit matrix;
- reproducible fixed-scenario cost results;
- one curated admissible embedded-event bundle and one curated admissible
  Event-Layer bundle per AWS, Azure, and GCP;
- one provider-neutral event envelope and edge contract;
- one explicit multi-cloud bridge decision;
- an approval or rejection record with residual uncertainty.

This is a decision and evidence phase. It creates no Eventing runtime,
Terraform resource, provider package, Management database model, or Flutter
feature.

### Scope Boundary

| Included | Excluded |
|---|---|
| Profile-parity decision, shared domain-event flow, source ledger, workload/capability/pricing/unit contracts, embedded and Event-Layer provider bundle matrices, fixed scenarios, envelope/edge/bridge decisions, rejected alternatives, approval record, and reproducibility checks | Runtime code, DB/API/UI changes, provider packages, Terraform resources, arbitrary topology, paid APIs, credentials, and live E2E |

### 1.1 Fixed Profile And Functional-Parity Decision

The decision package must encode these three distinct roles:

| Profile | Status and purpose | Domain-event behavior | Eventing responsibility |
|---|---|---|---|
| `five-layer-baseline@1` | Immutable historical and paper-compatible profile | Preserves its reviewed omission of optional event-check/action/feedback paths | None |
| `five-layer-baseline@2` | New fair-comparison baseline | Rule evaluation, extension action, notification workflow, and device-command feedback are mandatory embedded L1/L2 behavior | No independent Eventing responsibility; local direct-edge transport and topology-conditional cross-cloud outboxes/forwarders remain owned by the producing and consuming L1/L2 responsibilities |
| `six-layer-eventing@1` | New treatment profile | Exactly the same mandatory domain-event behavior as `five-layer-baseline@2` | Adds independent routing, buffering, fan-out, retry/DLQ, replay, ordering, observability, and cross-cloud transport ownership |

“Exactly the same mandatory domain-event behavior” means the same event types,
rule decisions, invocations, terminal outcomes, and scenario volumes. It does
not erase the treatment variable by requiring the embedded profile to own the
Event-Layer service-quality contract. The embedded profile records the
delivery and ordering behavior its direct edges actually achieve. The
six-layer profile must satisfy the additional Event-Layer guarantees in
Section 7.1. A cross-profile result must therefore report both functional
parity and the achieved quality delta; it must never describe the profiles as
transport-semantics-equivalent.

The shared domain-event flow is:

```text
device telemetry
  -> telemetry.received.v1
  -> processing
  -> telemetry.processed.v1
       +-> historical persistence
       +-> Twin state update
       +-> event-rule evaluation
              -> event.matched.v1
                   +-> extension action
                   +-> notification.requested.v1 -> stateful workflow
                   +-> device.command.requested.v1 -> provider device adapter
```

Storage lifecycle transitions remain storage-owned data-plane operations. They
may emit bounded completion/control events but must not copy object payloads
through an event broker. L4-to-L5 query/read behavior remains synchronous.
Internal wrapper-to-user-function calls may remain in-process when they form
one cohesive deployment component.

The distinction between "always present" and "always invoked" is normative:

- both new profiles always contain the event-rule evaluator, action dispatch,
  notification workflow, and device-command adapter;
- every processed telemetry event is eligible for rule evaluation;
- actions, workflows, and device commands occur only when a typed configured
  rule matches;
- an empty runtime rule set may produce zero actions, but evaluation fixtures
  must contain reviewed non-empty rules that exercise every mandatory path.

`useEventChecking`, `triggerNotificationWorkflow`, and
`returnFeedbackToDevice` are not fields in either new profile. Historical
`five-layer-baseline@1` records retain read/destroy compatibility. New-profile
contracts fail closed on the legacy flags rather than silently translating
them.

## 2. Scientific Boundary

The event responsibility is a logical architecture layer even though its
connections are nonlinear:

```text
                 +---------------------------+
                 | Eventing And Messaging    |
                 | route, buffer, fan-out,   |
                 | retry, DLQ, replay        |
                 +----+----+----+----+-------+
                      |    |    |    |
             +--------+    |    |    +----------+
             v             v    v               v
        ingestion      processing/storage   twin/visualization
```

The layer describes a coherent responsibility and comparison boundary. It does
not imply that every event follows one linear L1-to-L6 path or that one cloud
service implements the entire layer.

Provider comparison is between curated service bundles that satisfy the same
mandatory behavior. Event Grid, Event Hubs, Service Bus, EventBridge, SNS, SQS,
Pub/Sub, Eventarc, Cloud Tasks, or workflow services must not be treated as
equivalent merely because they handle events.

## 3. Required Inputs

The builder must read:

- Phase 8.0 Function-and-Edge Matrix and current graph inventory;
- approved `five-layer-baseline@1` decision record;
- architecture/profile/component contracts from Phases 8.2-8.3;
- resolved graph and deployment evidence from Phases 8.5-8.6;
- `docs/research/digital_twin_architecture_and_eventing_layer.md`;
- `docs/research/research_questions_and_evaluation_design.md`;
- `docs/research/related_work_multicloud_cost_comparability_eventing.md`;
- current pricing evidence/source policies under
  `2-twin2clouds/pricing_registry/`;
- current provider capability and permission contracts.

The baseline matrix determines which direct function edges are candidates for
replacement. The phase must not invent an Eventing edge that has no logical
producer/consumer need.

## 4. Evidence Package

Create:

```text
docs/research/evidence/phase_08_eventing/
  decision.json
  profile-parity-decision.json
  domain-event-flow-contract.json
  mandatory-capabilities.json
  provider-capability-matrix.json
  pricing-model-matrix.json
  scenario-inputs.json
  scenario-cost-results.json
  source-ledger.json
  formula-and-unit-ledger.json
  bridge-decision.json
  implementation-component-manifest.json
  README.md
  schemas/
    eventing-workload.schema.json
    <one schema for every remaining JSON artifact>
```

All JSON files must have repository-owned Draft 2020-12 schemas in that
`schemas/` directory.

Add:

```text
scripts/phase_08_eventing/
  validate_decision_package.py
  calculate_scenarios.py
  verify_sources.py
```

The scripts must run offline against frozen evidence. Online source refresh is
an explicit operation and must not silently mutate reviewed results.

`implementation-component-manifest.json` is the exact, non-executable
implementation blueprint consumed by Phase 8.9. For every selected provider
bundle member, adapter, bridge, and logical edge it must pin:

- logical responsibility, component, edge, and port IDs;
- provider service and resource type;
- planned deployment component and catalog entry IDs/versions;
- planned Terraform resource type, module ownership, input IDs, and output IDs;
- runtime adapter, package artifact, wrapper, and handler IDs;
- permission capability and permission-set refs;
- pricing intent, meter/SKU, formula, unit, tier, and deployment-dimension
  refs;
- envelope, delivery, trust, retry, DLQ, replay, ordering, observability, and
  cleanup contract refs;
- exact provider/region constraints and unsupported combinations;
- repository-relative new/modified file manifest for Optimizer, Management,
  Deployer, Terraform, Flutter, contracts, tests, and documentation.

Every reference must resolve to an existing Phase 8 extension point or be
declared as one exact new ID/path owned by Phase 8.9. The manifest contains no
runtime code, cloud identifier, credential, or Terraform value. Missing,
duplicate, unresolved, or conflicting implementation ownership makes an
`approved` decision invalid.

## 5. Source Protocol

Every provider claim and price field must reference one source-ledger entry:

| Field | Rule |
|---|---|
| `source_id` | Stable repository ID |
| `provider` | `aws`, `azure`, or `gcp` |
| `service_family` | Exact provider service/bundle member |
| `claim_type` | capability, limitation, quota, price, unit, tier, region, security |
| `source_type` | Existing approved pricing source classification |
| `canonical_url` | Direct primary provider documentation/API URL |
| `retrieved_at` | UTC RFC 3339 |
| `effective_at` | Provider effective date when published |
| `region` / `currency` | Explicit or `not_applicable` |
| `content_digest` | Digest of normalized captured evidence |
| `review_status` | `reviewed`, `superseded`, or `unverified` |
| `reviewer_note` | Bounded interpretation, never copied marketing prose |

Execution must verify current primary provider documentation. Search results,
blogs, comparison vendors, generated summaries, and AI output are discovery
 aids only and cannot be cited as evidence.

Candidate families that must be assessed, without presuming equivalence or
requiring one service to satisfy the whole bundle:

- AWS: IoT Core event/device paths, Kinesis Data Streams, EventBridge event
  bus/Pipes, SNS, SQS, Lambda, and Step Functions;
- Azure: IoT Hub/Event Grid ingress, Event Hubs, Service Bus, Functions, and
  Logic Apps or Durable Functions;
- GCP: a complete bidirectional device/telemetry/command boundary, Pub/Sub,
  standalone MQTT brokers on GKE or Compute Engine, Eventarc, Cloud Tasks,
  Cloud Run/Functions, and Workflows.

The matrix may reject all or part of a family. It may add another provider
service only when a mandatory capability cannot otherwise be evaluated and the
rationale is recorded.

The selected service does not have to be identical for telemetry streaming,
durable work, workflow orchestration, and device command delivery. Every
selected member must have one explicit responsibility, capacity proof, cost
owner, deployment mapping, and failure boundary.

Cost is a measured outcome, not an admissibility or selection objective in
this proof of concept. Selection order is:

1. common domain behavior;
2. mandatory profile-specific semantics;
3. deployability and cross-provider compatibility;
4. small/medium/large capacity;
5. security and operational evidence;
6. recorded, but not minimized, estimated cost.

## 6. Eventing Workload Contract

`eventing-workload.v1` must define a channel-aware workload. Aggregate
`consumer_count` and manually entered `cross_cloud_delivery_share` are
insufficient because the actual fan-out and cross-cloud routes follow from the
resolved producer/consumer graph.

| Field | Unit / Rule |
|---|---|
| `events_per_month` | Non-negative integer |
| `average_event_payload_bytes` | Positive integer; raw telemetry payload before the canonical envelope and provider rounding |
| `average_envelope_overhead_bytes` | Positive integer; bounded serialized `eventing-envelope.v1` metadata added to every domain event |
| `average_match_payload_bytes` | Positive integer; rule-match payload before envelope overhead |
| `average_notification_payload_bytes` | Positive integer; notification request payload before envelope overhead |
| `average_device_command_payload_bytes` | Positive integer; device-command request payload before envelope overhead |
| `average_outcome_payload_bytes` | Positive integer; terminal action/workflow/command outcome payload before envelope overhead |
| `publish_requests_per_month` | Non-negative integer |
| `event_channels` | Closed-world channel IDs with exact producer and consumer component refs |
| `channel_delivery_counts` | Derived per channel and per consumer from the resolved graph |
| `cross_cloud_routes` | Derived from differing producer/consumer provider assignments; never a user-entered percentage |
| `retry_share` | Decimal `[0,1]` |
| `dead_letter_share` | Decimal `[0,1]` |
| `replay_share` | Decimal `[0,1]` |
| `retention_hours` | Non-negative integer |
| `ordering_scope` | `none` or `per_device` |
| `max_delivery_latency_seconds` | Positive integer |
| `required_delivery_semantics` | `at_least_once` for v1 |
| `peak_events_per_second` | Non-negative decimal |
| `active_partition_keys` | Positive integer when per-device ordering applies |
| `concurrent_device_connections` | Positive integer; separate from partition-key cardinality and required for device-boundary capacity |
| `rule_match_share` | Decimal `[0,1]`; applies to processed telemetry |
| `extension_actions_per_match` | Positive integer |
| `workflow_start_share_of_matches` | Decimal `[0,1]` |
| `device_command_share_of_matches` | Decimal `[0,1]` |
| `workflow_actions_per_execution` | Positive integer used for workflow quota and cost transformation |
| `workflow_internal_actions_per_execution` | Non-negative integer; provider-local orchestration/control actions |
| `workflow_external_actions_per_execution` | Non-negative integer; external notification/connector actions; internal plus external must equal total workflow actions |
| `terminal_outcome_events_per_invocation` | Closed-world action/workflow/command counts; v1 emits one typed terminal outcome per invocation |
| `component_compute_assumptions` | Closed-world duration, memory, batch-size, and concurrency inputs for new rule/action/Event-Layer-delivery-adapter/workflow-adapter/device-adapter/bridge compute |
| `observability_assumptions` | Closed-world sample share, record size, full-capture channel classes, and retention used to derive log ingestion/storage |
| `provider_region_refs` | Exact AWS, Azure, and GCP region plus immutable pricing-catalog refs |

`provider_region_refs` must pin the same existing comparison regions used by
the current reviewed pricing baseline:

```text
aws.region = eu-central-1
azure.region = westeurope
gcp.region = europe-west1
```

Each entry also carries its immutable pricing catalog snapshot ID and content
digest. A scenario must not resolve "nearest", default, or current regions at
runtime.

Derived quantities must be calculated by one named function each. The contract
must distinguish:

- domain events;
- canonical serialized bytes, including envelope overhead;
- provider-billed request or message chunks;
- deliveries per consumer;
- retries;
- dead-letter writes and storage;
- replay reads and redeliveries;
- inter-region/inter-cloud bytes;
- adapter/workflow invocations; and
- sampled telemetry log records plus fully captured control, outcome, retry,
  dead-letter, replay, and bridge-failure records.

No formula may use `events_per_month` as a substitute for all provider billing
dimensions. `telemetry.received.v1` and `telemetry.processed.v1` each carry the
scenario telemetry payload in v1, so the Event-Layer ingress volume contains
two full telemetry publishes. Bridge and transfer bytes use canonical
serialized envelope bytes. TLS, TCP/IP, and provider-internal replication
overhead are excluded from the base estimate and named as a sensitivity and
construct-validity limitation; they must not be silently approximated as
payload bytes.

The closed-world channel registry must contain at least:

- `telemetry.received.v1`, consumed by processing;
- `telemetry.processed.v1`, consumed by persistence, Twin update, and rule
  evaluation;
- `event.matched.v1`, consumed by action dispatch;
- `notification.requested.v1`, consumed by the workflow adapter;
- `device.command.requested.v1`, consumed by the device-command adapter; and
- typed action/workflow/command outcome events required for retry, audit, or
  terminal failure evidence.

Additional audit or real-time visualization subscribers are separate named
sensitivity variants. They must not be hidden in one generic consumer
multiplier or silently presented as part of the historical five-layer graph.

## 7. Functional Capability Contract

### 7.1 Mandatory Capabilities

Every embedded-event bundle must provide the shared domain behavior from
Section 1.1, typed delivery outcomes, bounded retry/failure handling for its
direct edges, provider-native workflow execution, a complete provider-native
or explicitly provider-hosted bidirectional device boundary, and
topology-conditional source-owned cross-cloud transport for remote
responsibility edges. A hosted device boundary must pin the software
distribution/version/license, compute, load balancing, device identity,
authorization, durable-session, observability, lifecycle, integration adapter,
and cost owners; it cannot be described as though it were a managed provider
service. A same-provider placement creates no bridge. The embedded profile is
not required to pretend that it owns a general replay or fan-out layer.

Every selected Event-Layer bundle must additionally provide:

1. canonical event-envelope ingestion;
2. deterministic routing by event type and bounded metadata;
3. durable buffering until a consumer can process the event;
4. independent fan-out without producer code changes;
5. at-least-once delivery with an explicit retry policy;
6. dead-letter capture after bounded attempts;
7. bounded retention and an explicit replay/redrive mechanism;
8. correlation and trace propagation;
9. consumer idempotency support through stable event/invocation IDs;
10. declared ordering behavior that satisfies the workload requirement;
11. schema/version rejection behavior;
12. encryption, identity, trust, and least-privilege boundaries;
13. metrics/logs for publish, delivery, retry, DLQ, replay, and bridge failure;
14. explicit cross-cloud transport and transfer-cost ownership;
15. deployable provider resources and permission capabilities already
    representable by Phase 8 contracts.

One service need not provide all capabilities. The complete bundle must.

### 7.2 Optional Or Extra Capabilities

Record but do not require:

- exactly-once provider features;
- advanced filtering/enrichment;
- schema registries;
- long-term event archive;
- Kafka compatibility;
- transactional sessions;
- geo-disaster recovery;
- provider-native capture/analytics integrations.

Extra functionality must remain visible and must not be counted as equivalence.
Its unavoidable fixed cost must still be included in the selected bundle.

### 7.3 Admissibility

Each capability cell is one of:

- `native`;
- `composed`;
- `platform_adapter`;
- `unsupported`;
- `unverified`.

Only `native`, `composed`, and `platform_adapter` can satisfy a mandatory
capability. `composed` and `platform_adapter` cells must list every additional
resource, permission, cost field, edge, and failure boundary.

A bundle is admissible only when all mandatory cells pass and all required
costs have evidence. Cost cannot compensate for `unsupported` or `unverified`.

## 8. Capability Matrix

Each row represents a mandatory/optional capability. Each provider bundle
column records:

- status and source IDs;
- exact responsible bundle member;
- relevant tier/SKU/mode;
- delivery and ordering qualification;
- region availability;
- required adapter;
- extra resources;
- limitations;
- executable support status in current Deployer contracts.

The matrix must include rejected alternatives. A rejected service is not
removed; it receives a stable reason such as:

- lacks mandatory durable buffering;
- lacks required replay/redrive behavior;
- ordering does not satisfy the scenario;
- requires an unmodeled paid supporting resource;
- no deployable/permission contract exists;
- evidence is not current or region-compatible.

## 9. Pricing-Model And Unit Matrix

Each selected and rejected bundle member must declare all applicable dimensions:

- request/message/event ingestion;
- payload-size billing chunk;
- delivery/fan-out;
- throughput/capacity units;
- broker/topic/namespace/partition fixed charge;
- retention/storage;
- archive/replay/redrive;
- retry/DLQ operations and storage;
- adapter function/workflow compute;
- observability required for the contract;
- same-region, cross-region, and cross-cloud transfer;
- free quota, minimum allocation, tier threshold, and rounding block.

Required per-field metadata:

```text
intent_id
provider
service_or_bundle_member
provider_meter_or_sku_id
source_type
source_id
raw_unit
normalized_unit
normalization_rule_id
formula_id
tier_schedule
rounding_rule
region
currency
effective_at
fetchability
publishability
```

`fetchability` is one of:

- `dynamic_provider_api`;
- `account_scoped_provider_api`;
- `official_static_documentation`;
- `derived_calculation`;
- `not_applicable`.

An official global/static price is valid evidence when the provider does not
publish it through an API. It must be reviewed, versioned, date-stamped, and
marked non-fetchable. It is never called a fallback. Missing evidence,
emergency fallback data, or stale unreviewed data makes the bundle
non-publishable.

## 10. Scenario Matrix

Freeze three channel-aware sensitivity scenarios:

| Scenario | Telemetry events / publish requests | Raw telemetry payload | Mandatory processed-telemetry consumers | Extra sensitivity consumers | Rule match / workflow / command share | Retry / DLQ / replay | Retention | Peak events/s | Active keys / concurrent devices | Max latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `eventing-small-v1` | 100,000 / 100,000 | 4 KiB | 3 | 0 | 1% / 25% / 25% of matches | 0.1% / 0.01% / 0% | 24 h | 10 | 100 / 100 | 30 s |
| `eventing-medium-v1` | 10,000,000 / 10,000,000 | 16 KiB | 3 | 0 | 1% / 25% / 25% of matches | 0.5% / 0.05% / 1% | 168 h | 250 | 10,000 / 10,000 | 10 s |
| `eventing-large-v1` | 100,000,000 / 100,000,000 | 64 KiB | 3 | 2 | 1% / 25% / 25% of matches | 1% / 0.1% / 2% | 168 h | 2,500 | 100,000 / 100,000 | 5 s |

The following auxiliary payload and execution dimensions are fixed for every
v1 scenario. They are synthetic reference assumptions, not measurements:

| Dimension | v1 value |
|---|---:|
| Canonical envelope overhead | 1 KiB/event |
| Rule-match payload | 1 KiB |
| Notification request payload | 1 KiB |
| Device-command request payload | 1 KiB |
| Terminal outcome payload | 512 B |
| Extension actions per match | 1 |
| Workflow actions per execution | 4 |
| Workflow internal actions per execution | 3 |
| Workflow external notification actions per execution | 1 |
| Terminal outcomes | 1 per extension action, workflow, and command |
| Rule evaluator | 50 ms at 256 MiB |
| Extension action adapter | 100 ms at 256 MiB |
| Event-Layer delivery adapter | 50 ms at 256 MiB, one invocation per delivery; no unapproved batching |
| Workflow start adapter | 50 ms at 256 MiB |
| Device-command adapter | 100 ms at 256 MiB |
| Cross-cloud bridge batch | maximum 10 events, 250 ms at 512 MiB |
| Telemetry observability sample | 1% of received and processed publications |
| Fully captured observability records | Every match, notification request, command request, terminal outcome, retry, DLQ, replay, and bridge terminal failure |
| Average observability record | 1 KiB after safe-field projection |
| Observability retention | 30 days |

For the Event-Layer treatment, all three scenarios require at-least-once
delivery and per-device ordering. For the embedded baseline, the same fields
are evaluation probes: the evidence records whether each direct provider path
achieves them, but failure does not fabricate a sixth responsibility inside
the five-layer profile. The input file must pin the three provider-region
catalog refs above and state that these are bounded evaluation scenarios, not
observed production traffic. Publish request counts intentionally equal event
counts in v1 so batching is not silently assumed for domain publishers;
provider billing chunks are derived later from the serialized envelope and
provider rules. The four-step notification workflow has three provider-local
orchestration/control steps and one external notification delivery step. This
keeps the observable behavior identical while preserving the providers'
different workflow and connector meters. The observability sample is a
synthetic cost/capacity assumption, not a production-recommended logging
policy: telemetry is sampled, while low-volume control, outcome, and failure
records are retained completely. Only the bridge has the explicit bounded
batch assumption above. If existing thesis workload fixtures justify different
values, the change must be made before calculation, documented in the decision
record, and versioned as new scenario IDs.

The three mandatory `telemetry.processed.v1` consumers are historical
persistence, Twin-state update, and rule evaluation. The Large scenario adds
two explicitly named audit/real-time sensitivity subscribers; it does not
pretend that the original five-layer graph had five anonymous consumers.
Workflow and command shares are applied after the 1% rule-match share. At the
Large peak this means 2,500 rule checks/s, 25 matches/s, and 6.25 workflow
starts/s plus 6.25 command requests/s. Every match also starts one extension
action. Each extension action, workflow, and command emits one typed terminal
outcome. Device-boundary capacity must use `concurrent_device_connections`,
not infer connection count from monthly event volume.

Cross-cloud volume is calculated separately for every resolved event-domain
placement:

- the single-cloud AWS, Azure, and GCP event-domain cases;
- every admissible directed AWS/Azure/GCP provider pair;
- admissible three-provider placements; and
- each possible Eventing-responsibility provider in the six-layer profile.

Same-cloud edges create no bridge. A provider pair is not assumed symmetric:
AWS-to-Azure and Azure-to-AWS are separate capacity, identity, egress, and
failure cases. These Phase 8.8 totals cover the event-domain scope, not the
complete Twin. Unsupported whole-Twin paths remain visible and receive no
fabricated total in Phase 8.9/8.10 evaluation.

For every admissible provider bundle and scenario, output:

- every normalized quantity;
- every tier/rounding step;
- each service/member contribution;
- transfer and adapter contributions;
- total monthly estimate;
- extra functionality;
- evidence and formula references;
- unsupported/unverified state where applicable.

Do not rank the two profiles together in this phase. This phase calculates the
embedded domain-event cost for `five-layer-baseline@2` and the Event-Layer plus
bridge cost for `six-layer-eventing@1` from the same channel workload. Full
profile totals and the fair cross-profile delta are Phase 8.10 evidence.

## 11. Canonical Event And Edge Decision

`bridge-decision.json` must pin:

- `eventing-envelope.v1` fields and maximum sizes;
- event ID, type, schema version, occurred time, correlation ID, producer
  component, Twin ID, device ID, partition key, trace context, and payload;
- which metadata may be used for routing;
- duplicate/idempotency handling;
- retryable versus terminal errors;
- retry schedule and maximum attempts;
- DLQ envelope and redrive audit;
- replay semantics and replay marker;
- ordering scope and degradation behavior;
- retention and deletion behavior;
- producer acknowledgement boundary;
- consumer acknowledgement boundary;
- observability events and bounded safe fields.

The envelope must not include provider resource IDs, credentials, deployment
URLs, Terraform names, raw exception text, or arbitrary headers.

## 12. Multi-Cloud Bridge Decision

The bridge is an explicit deployment component and cost owner, not hidden glue.
The decision must define:

- source and destination ownership;
- push/pull direction;
- trust establishment and credential lifetime;
- transport encryption and endpoint validation;
- schema validation before forwarding;
- delivery acknowledgement boundary;
- duplicate and idempotency behavior;
- retry, circuit-break, backpressure, DLQ, and redrive;
- ordering behavior across the bridge;
- trace/correlation propagation;
- transfer byte calculation and provider egress owner;
- adapter compute and destination-ingress cost owner;
- outage and partial-failure behavior;
- secret-free logs, metrics, and audit evidence.

The decision must compare at least:

1. source-owned bridge adapter;
2. destination-owned bridge adapter.

It must select one ownership rule for v1 or reject Eventing implementation.
Direct provider-specific function-to-function invocation cannot be the selected
bridge.

The selected topology must be hub-and-spoke around the resolved Eventing
provider, not an arbitrary mesh:

- same-cloud producer/consumer edges use the selected local bundle and no
  bridge;
- a remote producer writes through one source-side durable outbox/stream and a
  source-owned bridge publishes to the Eventing provider;
- a remote consumer receives through one Eventing-owned subscription and a
  source-owned bridge publishes to the destination landing queue/topic;
- the source delivery is acknowledged only after the destination durable
  endpoint accepts the canonical envelope;
- short-lived workload identity federation is preferred; every trust must
  constrain the workload through a token subject claim or through a
  single-workload token-issuance assignment plus issuer/audience checks; any
  provider direction that cannot establish reviewed secretless trust is
  unsupported.

The matrix must test all six directed provider pairs. A generic statement that
"HTTPS works cross-cloud" is not sufficient evidence.

## 13. Decision Record

`decision.json` must contain:

```text
schema_version
decision_id
decision_status: approved | rejected
profile_candidates:
  - five-layer-baseline@2
  - six-layer-eventing@1
historical_profile: five-layer-baseline@1
profile_parity_decision_ref
domain_event_flow_contract_ref
input_digests
selected_embedded_event_bundle_refs
selected_event_layer_bundle_refs
bridge_decision_ref
implementation_component_manifest_ref
mandatory_capability_result
pricing_completeness_result
scenario_result_digest
known_differences
residual_risks
approved_at
reviewers
```

Approval requires the common domain-event contract to be complete, the
embedded and Event-Layer bundles for all three Eventing providers to be
functionally admissible and pricing-complete, and the implementation component
manifest to have complete, non-conflicting ownership and exact file/contract
targets. A provider cannot be silently omitted. Whole-profile paths may still
be explicitly unsupported when a non-Eventing responsibility is missing. If
one required Eventing provider or implementation mapping fails, the correct
outcome is `rejected` with evidence; Phase 8.9 remains blocked.

## 14. Implementation Slices

### Slice A: Profile Parity And Domain-Event Contract

Must freeze the three profile roles, mandatory shared domain behavior, typed
event flow, legacy-flag compatibility boundary, and fair-comparison rule before
provider evaluation begins.

Slice A is committed and reviewed as a standalone planning boundary. Slices
B-H are the subsequent evaluation branch and may not change the profile-parity
contract implicitly; a required change creates a new reviewed contract version.

### Slice B: Evidence Schemas And Source Ledger

Must create schemas, source protocol, validator, primary-source inventory, and
positive/negative fixtures.

### Slice C: Functional Matrix

Must evaluate embedded and Event-Layer candidates, rejected alternatives,
composed resources, limitations, executable support, single-cloud paths, all
six directed provider pairs, and mandatory capability completeness.

### Slice D: Capacity, Pricing, And Formula Matrix

Must prove Small/Medium/Large capacity before cost, enumerate every cost
dimension, classify source/fetchability, normalize units without losing
provider semantics, and implement offline formulas.

### Slice E: Scenario Calculation

Must freeze scenario inputs, calculate every admissible provider bundle,
produce field-level traces, and fail closed on missing evidence or dimensions.

### Slice F: Envelope And Bridge Decision

Must produce the canonical envelope/edge contract and select or reject a
multi-cloud bridge ownership model.

### Slice G: Implementation Component Manifest

Must translate every approved bundle/bridge decision into the exact
cross-project IDs, resource types, adapters, packages, permissions, bindings,
file targets, and test ownership required by Phase 8.9. Must run reference,
duplicate-ownership, and extension-point compatibility checks.

### Slice H: Independent Review And Approval

Must review the complete package from architecture, provider, pricing,
security, reproducibility, and thesis-validity perspectives. Approval is a
committed decision record, not a chat statement.

## 15. Test Plan

### Schema And Referential Integrity

- every required field missing;
- additional properties;
- duplicate capability/source/formula IDs;
- unresolved source/formula/service references;
- unsupported schema versions;
- digest mutation;
- non-canonical decimal and timestamp values.
- implementation-manifest missing file ownership, duplicate component IDs,
  unresolved extension points, or conflicting Terraform/port bindings.

### Functional Gate

- historical `five-layer-baseline@1` digest or behavior changes;
- a legacy Eventing feature flag is accepted by either new profile;
- one mandatory shared domain-event path is absent from either new profile;
- an empty evaluation fixture fails to exercise action, workflow, or command;
- one mandatory cell `unsupported`;
- one mandatory cell `unverified`;
- composed cell missing supporting resource;
- adapter missing permission/deployment support;
- ordering mismatch;
- replay/DLQ capability omitted;
- extra capability preserved but not counted as equivalence.

### Pricing Gate

- provider unit chunks at exact boundary and boundary plus one byte;
- free quota and tier boundary values;
- minimum capacity/partition rounding;
- fan-out multiplier;
- retry/DLQ/replay quantities;
- retention/storage;
- adapter compute;
- same-cloud/cross-cloud transfer;
- official-static evidence accepted only by explicit field policy;
- fallback/stale/unreviewed evidence rejected;
- no double counting of bundled dimensions.

### Scenario And Reproducibility

- all three scenarios for all three providers;
- all three single-cloud event-domain cases and all six directed provider
  pairs;
- cross-cloud routes and fan-out derived from graph assignments;
- same-cloud edges produce no bridge invocation or egress charge;
- the Large peak proves each selected member's documented capacity or records
  the exact shard/partition/namespace/capacity configuration;
- identical offline inputs produce byte-identical result JSON and digest;
- shuffled source/matrix order produces the same digest;
- one evidence value mutation changes dependent field and package digest;
- rejected bundle never receives a publishable total.

### Security And Documentation

- source ledger contains no credentials or copied private identifiers;
- event envelope fixtures reject secret/provider infrastructure fields;
- bridge logs/audit schema permits only bounded safe fields;
- research files do not leak into current product/user instructions.

Safe verification:

```bash
docker run --rm -i -v "$PWD:/workspace" -w /workspace \
  2twin2clouds:latest \
  sh -lc '
    python scripts/phase_08_eventing/verify_sources.py --offline --strict &&
    python scripts/phase_08_eventing/calculate_scenarios.py --check &&
    python scripts/phase_08_eventing/validate_decision_package.py --strict &&
    python -m pytest \
      scripts/phase_08_eventing/tests/test_calculate_scenarios.py \
      scripts/phase_08_eventing/tests/test_validate_decision_package.py -q
  '
```

The online source-refresh mode may perform read-only public documentation and
pricing queries. It must not use cloud admin credentials, create resources, or
replace reviewed evidence automatically.

## 16. Documentation

Update only research/planning material:

- `docs/research/digital_twin_architecture_and_eventing_layer.md`;
- `docs/research/research_questions_and_evaluation_design.md`;
- source/evidence README in this phase package;
- Phase 8 roadmap and #146 with named bundle/matrix/digest results.

Current product documentation must not describe Eventing as implemented.
Do not edit `twin2multicloud-latex`.

## 17. Rollback

This phase is additive evidence only. Rollback means:

- mark a decision `superseded` through a new immutable decision version;
- preserve all prior evidence and digests;
- keep Phase 8.9 blocked;
- never delete inconvenient rejected candidates or failed source checks.

## 18. Definition Of Done

- [x] `five-layer-baseline@1` remains immutable historical evidence.
- [x] `five-layer-baseline@2` and `six-layer-eventing@1` share one exact,
      versioned domain-event behavior contract.
- [x] Rule evaluation, extension action, notification workflow, and
      device-command feedback are mandatory components in both new profiles,
      while action invocations remain match-driven.
- [x] The three legacy Eventing feature flags are absent from new-profile
      contracts and retained only for historical read/destroy compatibility.
- [x] The Eventing workload and capability contracts are channel-aware, exact,
      and versioned; fan-out and cross-cloud routes are graph-derived.
- [x] Primary-source evidence is current, direct, digest-pinned, and classified.
- [x] AWS, Azure, and GCP candidate families and rejected alternatives are
      represented without assumed one-to-one equivalence.
- [x] Embedded-event and Event-Layer bundles are evaluated separately for
      single-cloud, all six directed provider pairs, and admissible
      three-provider paths.
- [x] The embedded profile owns topology-conditional source outboxes and bridge
      bindings for remote responsibility edges without introducing an
      independent Eventing responsibility.
- [x] GCP uses one complete bidirectional BifroMQ/GKE device boundary with an
      explicit MQTT-to-Pub/Sub integration adapter; reconnect ordering
      degradation and selected-version capacity remain activation gates.
- [x] Small, Medium, and Large theoretical capacity is proven before cost is
      reported; supervised live capacity remains an activation gate.
- [x] Cost is recorded as an outcome and is not used to reject an otherwise
      valid PoC bundle.
- [x] Every mandatory capability is supplied by a named, deployable bundle
      member or the candidate is rejected.
- [x] Every fixed, variable, tiered, transfer, adapter, retention, replay, DLQ,
      and observability cost has one owner and evidence/formula references.
- [x] Official non-fetchable prices are reviewed static evidence, never hidden
      fallbacks.
- [x] All three scenario calculations are field-traceable and reproducible.
- [x] The canonical event envelope, edge semantics, and bridge ownership are
      fully decided.
- [x] The implementation component manifest pins exact cross-project IDs,
      resource types, adapters, packages, permissions, ports, bindings, file
      targets, and verification ownership for every selected bundle member.
- [x] Trust, retry, DLQ, replay, idempotency, ordering, observability, transfer,
      and failure behavior are explicit.
- [x] `decision.json` is approved only if all three embedded-event and all
      three Event-Layer provider bundles pass their applicable contracts.
- [x] Schema, reference, capability, pricing, formula, unit, scenario,
      reproducibility, security, and documentation tests pass.
- [x] No runtime code, Terraform, cloud credential, cloud resource, paid API,
      or live E2E operation is introduced.
- [x] Research notes, source ledger, and roadmap are updated; the revised
      digests are queued for #146 when this local commit is published.
- [x] Two reviews find no unresolved issue.
- [x] The structured commit references #146.

## 19. Completion Evidence

- Approved decision: `phase-08-eventing-decision@1`, normalized digest
  `sha256:22aec12d3e3915564d59d6d2ae00ce7fdce375b8d4bfc8c3880762697a02b2a6`.
- Exact non-executable blueprint:
  `phase-08-eventing-implementation@1`, normalized digest
  `sha256:7758a81f40d119fec8a61d03d3a8eb36c3825f732129a0edfcc925df26a85ab5`.
- Scenario result digest:
  `sha256:64b8059c4bd6a051624802252bd5922b39ba3d1249a388ebd9bf1ef91f59dc27`.
- Strict offline verification covers 12 decision artifacts, 66 frozen
  primary-source records, all three single-cloud event-domain cases, all six
  directed pairs, six closed-world three-provider placements, three workloads,
  37 selected service components, ten adapters, eight domain edges, six bridge
  route classes with two profile bindings each, and exact file/test ownership.
- Thirty focused calculator and package-validator tests pass, including
  negative formula, digest, capacity, route, profile-binding, source-adapter,
  identity-preflight, ownership, contract, and secret cases.
- Two separate reviews recorded in `decision.json` report `zero_findings`:
  architecture/provider/security/ownership and
  pricing/reproducibility/thesis/documentation.
- Commit `28a76ea6` remains provenance for the earlier approval; this reviewed
  revision supersedes its service-boundary, ownership, and digest details.
  Runtime, Terraform, live identity exchange, and supervised capacity remain
  outside this completed evidence phase.
- GitHub issue #146 must receive the revised decision, blueprint, scenario, and
  strict OrbStack evidence when this local commit is published; it remains open
  until the evidence is published or merged.
