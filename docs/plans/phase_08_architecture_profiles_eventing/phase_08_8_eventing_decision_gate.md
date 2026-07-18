---
title: "Phase 8.8: Eventing Functional And Cost Decision Gate"
description: "Implementation plan for the evidence-backed capability, pricing, and bridge decision that gates six-layer-eventing@1."
tags: [architecture, eventing, pricing, capabilities, evidence, thesis, issue-146]
lastUpdated: "2026-07-19"
version: "1.0"
---

<!-- SOURCES:
- GitHub issue #146
- docs/research/digital_twin_architecture_and_eventing_layer.md
- docs/research/research_questions_and_evaluation_design.md
- docs/research/related_work_multicloud_cost_comparability_eventing.md
- Phase 8.0 graph inventory and Phase 8.1 baseline decision contract
- Current official AWS, Azure, and Google Cloud Eventing documentation to be source-ledger pinned during execution
- User-approved functional-completeness-before-cost and curated-provider-bundle boundaries
EXTRACTED: 2026-07-19 | VERSION: 1.0
-->

# Phase 8.8: Eventing Functional And Cost Decision Gate

## 0. Metadata

| Field | Value |
|---|---|
| Issue | [#146 Complete the Eventing functional and cost decision gate](https://github.com/TVJunkie724/master-thesis/issues/146) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branch | `codex/phase-8-eventing-decision-gate` |
| Base branch | `master` |
| Blocked by | Phase 8.6 / #152 |
| Produces | Approved or rejected `six-layer-eventing@1` decision package |
| Live cloud E2E | Forbidden |

Every source, matrix cell, formula input, capability decision, bridge property,
review gate, and Definition of Done item in this plan is mandatory. Phase 8.9
must not begin until this gate concludes with an explicit `approved` decision.

## 1. Outcome

This phase decides whether a bounded Eventing and Messaging responsibility can
be added to the thesis architecture without false provider equivalence,
unowned costs, or another provider-specific side path.

The result is one immutable decision package containing:

- one versioned Eventing workload contract;
- one mandatory/optional capability contract;
- a source-backed provider capability matrix;
- a pricing-model and unit matrix;
- reproducible fixed-scenario cost results;
- one curated admissible implementation bundle per AWS, Azure, and GCP;
- one provider-neutral event envelope and edge contract;
- one explicit multi-cloud bridge decision;
- an approval or rejection record with residual uncertainty.

This is a decision and evidence phase. It creates no Eventing runtime,
Terraform resource, provider package, Management database model, or Flutter
feature.

### Scope Boundary

| Included | Excluded |
|---|---|
| Source ledger, workload/capability/pricing/unit contracts, provider bundle matrix, fixed scenarios, envelope/edge/bridge decisions, rejected alternatives, approval record, and reproducibility checks | Runtime code, DB/API/UI changes, provider packages, Terraform resources, arbitrary topology, paid APIs, credentials, and live E2E |

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
  eventing-workload.schema.json
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
```

All JSON files must have repository-owned Draft 2020-12 schemas under:

```text
docs/research/evidence/phase_08_eventing/schemas/
```

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

Candidate families that must be assessed, without presuming equivalence:

- AWS: EventBridge event bus/Pipes, SNS, SQS, and only supporting workflow or
  compute resources required by a candidate bundle;
- Azure: Event Grid, Service Bus, Event Hubs, and only supporting workflow or
  compute/storage resources required by a candidate bundle;
- GCP: Pub/Sub, Eventarc, Cloud Tasks, and only supporting workflow or compute
  resources required by a candidate bundle.

The matrix may reject all or part of a family. It may add another provider
service only when a mandatory capability cannot otherwise be evaluated and the
rationale is recorded.

## 6. Eventing Workload Contract

`eventing-workload.v1` must define:

| Field | Unit / Rule |
|---|---|
| `events_per_month` | Non-negative integer |
| `average_event_payload_bytes` | Positive integer; pre-provider rounding |
| `publish_requests_per_month` | Non-negative integer |
| `consumer_count` | Positive integer |
| `fanout_deliveries_per_month` | Derived and separately auditable |
| `cross_cloud_delivery_share` | Decimal `[0,1]` |
| `retry_share` | Decimal `[0,1]` |
| `dead_letter_share` | Decimal `[0,1]` |
| `replay_share` | Decimal `[0,1]` |
| `retention_hours` | Non-negative integer |
| `ordering_scope` | `none` or `per_device` |
| `max_delivery_latency_seconds` | Positive integer |
| `required_delivery_semantics` | `at_least_once` for v1 |
| `peak_events_per_second` | Non-negative decimal |
| `active_partition_keys` | Positive integer when per-device ordering applies |
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
- provider-billed request or message chunks;
- deliveries per consumer;
- retries;
- dead-letter writes and storage;
- replay reads and redeliveries;
- inter-region/inter-cloud bytes;
- adapter/workflow invocations.

No formula may use `events_per_month` as a substitute for all provider billing
dimensions.

## 7. Functional Capability Contract

### 7.1 Mandatory Capabilities

Every selected bundle must provide:

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

Freeze three sensitivity scenarios:

| Scenario | Events / publish requests | Payload | Consumers | Cross-cloud | Retry / DLQ / replay | Retention | Peak events/s | Active partition keys | Max latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `eventing-small-v1` | 100,000 / 100,000 | 4 KiB | 1 | 0% | 0.1% / 0.01% / 0% | 24 h | 10 | 100 | 30 s |
| `eventing-medium-v1` | 10,000,000 / 10,000,000 | 16 KiB | 3 | 5% | 0.5% / 0.05% / 1% | 168 h | 250 | 10,000 | 10 s |
| `eventing-large-v1` | 100,000,000 / 100,000,000 | 64 KiB | 5 | 20% | 1% / 0.1% / 2% | 168 h | 2,500 | 100,000 | 5 s |

All three use at-least-once delivery and per-device ordering. The input file
must pin the three provider-region catalog refs above and state that these are
bounded evaluation scenarios, not observed production traffic. Publish request
counts intentionally equal event counts in v1 so batching is not silently
assumed; provider billing chunks are derived later from payload and provider
rules. If existing thesis workload fixtures justify different values, the
change must be made before calculation, documented in the decision record, and
versioned as new scenario IDs.

For every admissible provider bundle and scenario, output:

- every normalized quantity;
- every tier/rounding step;
- each service/member contribution;
- transfer and adapter contributions;
- total monthly estimate;
- extra functionality;
- evidence and formula references;
- unsupported/unverified state where applicable.

Do not blend five-layer and six-layer totals in this phase. This phase
calculates the incremental Eventing responsibility and its bridge costs. Full
profile totals are Phase 8.10 evidence.

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

## 13. Decision Record

`decision.json` must contain:

```text
schema_version
decision_id
decision_status: approved | rejected
profile_candidate: six-layer-eventing@1
input_digests
selected_provider_bundle_refs
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

Approval requires all three provider bundles to be functionally admissible and
pricing-complete, and the implementation component manifest to have complete,
non-conflicting ownership and exact file/contract targets. A provider cannot
be silently omitted. If one provider or implementation mapping fails, the
correct outcome is `rejected` with evidence; Phase 8.9 remains blocked.

## 14. Implementation Slices

### Slice A: Evidence Schemas And Source Ledger

Must create schemas, source protocol, validator, primary-source inventory, and
positive/negative fixtures.

### Slice B: Functional Matrix

Must evaluate all candidates, rejected alternatives, composed resources,
limitations, executable support, and mandatory capability completeness.

### Slice C: Pricing And Formula Matrix

Must enumerate every cost dimension, classify source/fetchability, normalize
units without losing provider semantics, and implement offline formulas.

### Slice D: Scenario Calculation

Must freeze scenario inputs, calculate every admissible provider bundle,
produce field-level traces, and fail closed on missing evidence or dimensions.

### Slice E: Envelope And Bridge Decision

Must produce the canonical envelope/edge contract and select or reject a
multi-cloud bridge ownership model.

### Slice F: Implementation Component Manifest

Must translate every approved bundle/bridge decision into the exact
cross-project IDs, resource types, adapters, packages, permissions, bindings,
file targets, and test ownership required by Phase 8.9. Must run reference,
duplicate-ownership, and extension-point compatibility checks.

### Slice G: Independent Review And Approval

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
python scripts/phase_08_eventing/validate_decision_package.py --strict
python scripts/phase_08_eventing/calculate_scenarios.py --check
python scripts/phase_08_eventing/verify_sources.py --offline --strict
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/unit/pricing tests/unit/calculation_v2 -v
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

- [ ] The Eventing workload and capability contracts are exact and versioned.
- [ ] Primary-source evidence is current, direct, digest-pinned, and classified.
- [ ] AWS, Azure, and GCP candidate families and rejected alternatives are
      represented without assumed one-to-one equivalence.
- [ ] Every mandatory capability is supplied by a named, deployable bundle
      member or the candidate is rejected.
- [ ] Every fixed, variable, tiered, transfer, adapter, retention, replay, DLQ,
      and observability cost has one owner and evidence/formula references.
- [ ] Official non-fetchable prices are reviewed static evidence, never hidden
      fallbacks.
- [ ] All three scenario calculations are field-traceable and reproducible.
- [ ] The canonical event envelope, edge semantics, and bridge ownership are
      fully decided.
- [ ] The implementation component manifest pins exact cross-project IDs,
      resource types, adapters, packages, permissions, ports, bindings, file
      targets, and verification ownership for every selected bundle member.
- [ ] Trust, retry, DLQ, replay, idempotency, ordering, observability, transfer,
      and failure behavior are explicit.
- [ ] `decision.json` is approved only if all three provider bundles pass.
- [ ] Schema, reference, capability, pricing, formula, unit, scenario,
      reproducibility, security, and documentation tests pass.
- [ ] No runtime code, Terraform, cloud credential, cloud resource, paid API,
      or live E2E operation is introduced.
- [ ] Research notes, source ledger, roadmap, and #146 are updated.
- [ ] Two reviews find no unresolved issue.
- [ ] The structured commit references #146.
