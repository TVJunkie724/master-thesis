---
title: "Phase 8.9: Implement The Event-Enabled Comparison Profiles"
description: "Implementation plan for five-layer-baseline@2 and six-layer-eventing@1 using one approved domain-event contract and separate architecture ownership."
tags: [architecture, eventing, optimizer, management-api, deployer, flutter, issue-140]
lastUpdated: "2026-07-20"
version: "1.4"
---

<!-- SOURCES:
- GitHub issue #140
- Approved Phase 8.8 Eventing decision package
- Phase 8.2-8.7 contracts and implementations
- docs/research/digital_twin_architecture_and_eventing_layer.md
- Existing resolved-deployment-specification, DeploymentManifest, provider, Terraform, and Flutter extension points
- User-approved bounded six-layer profile with no arbitrary graph editor
- User-approved event-enabled five-layer @2 comparison profile, shared
  domain-event behavior, and separate 8.9A/8.9B implementation boundaries
EXTRACTED: 2026-07-20 | VERSION: 1.4
-->

# Phase 8.9: Implement The Event-Enabled Comparison Profiles

## 0. Metadata

| Field | Value |
|---|---|
| Issues | New `five-layer-baseline@2` implementation issue required before execution; [#140 Implement six-layer-eventing@1 across the platform](https://github.com/TVJunkie724/master-thesis/issues/140) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branches | 8.9A `codex/phase-8-five-layer-baseline-v2`; 8.9B `codex/phase-8-six-layer-eventing` |
| Branch bases | 8.9A starts from the reviewed Phase 8.7 boundary plus the approved Phase 8.8 package; 8.9B starts from the reviewed 8.9A commit; both ultimately target `master` |
| Blocked by | Phase 8.7 / #138 and approved Phase 8.8 / #146 |
| Produces | Executable closed-world `five-layer-baseline@2` and `six-layer-eventing@1` |
| Targets | AWS/Azure/GCP Eventing bundles, admissible whole paths, Web, macOS, Windows, Linux |
| Live cloud E2E | Forbidden |

Every contract, provider bundle, formula, package, permission, Terraform
binding, API field, UI state, test, and Definition of Done item in this plan is
mandatory. The phase must use the exact approved Phase 8.8 bundle and bridge
IDs; it must not substitute another service during implementation.

Phase 8.9 is executed as two independently reviewed branches and commit series.
8.9A implements and closes `five-layer-baseline@2`. 8.9B starts only after
8.9A is clean and implements `six-layer-eventing@1`.

## 1. Outcome

Add two executable, versioned comparison profiles through the same generic
extension points used by the hardened historical baseline:

```text
shared domain-event contract
  -> five-layer-baseline@2
       event behavior embedded in L1/L2
  -> six-layer-eventing@1
       same event behavior through independent Eventing responsibility
  -> profile and provider catalogs
  -> functionally complete Optimizer candidates
  -> immutable Management resolution
  -> DeploymentManifest v4
  -> deterministic Deployer graph
  -> explicit Terraform resources and provider packages
  -> compact Flutter selection and review
```

Both profiles always include rule evaluation, extension actions, notification
workflows, and device-command feedback. The six-layer profile additionally
adds Eventing and Messaging as a nonlinear responsibility with explicit
routing, buffering, fan-out, retry, DLQ, replay/redrive, observability, and
cross-cloud transport. Neither profile adds a broker between every helper
function or creates a general event-topology editor.

### Scope Boundary

| Included | Excluded |
|---|---|
| The exact approved shared domain-event contract, five-layer v2 and six-layer profiles, RDS v2/Manifest v4, Eventing workload/pricing/formulas, normalized persistence, provider bundles, packages, permissions, static Terraform, bridge, failure semantics, compact Flutter workflow, and broad offline gates | Changes to historical `five-layer-baseline@1`, unapproved provider substitutions, arbitrary profiles/topologies, unrelated optimization strategies, dynamic Terraform, all-provider-path claims not proven by capabilities, and live provider execution |

## 2. Activation Preconditions

Implementation may start only when:

1. Phase 8.8 `decision.json` is `approved`;
2. the profile-parity and domain-event flow decisions resolve;
3. all three selected embedded-event and Event-Layer provider bundle refs
   resolve;
4. every mandatory capability is complete;
5. every pricing/formula field is publishable;
6. the canonical envelope and bridge ownership are approved;
7. the Phase 8.8 implementation component manifest resolves every exact
   cross-project ID, resource type, adapter, package, permission, port,
   binding, file target, and test owner without duplicates;
8. the new 8.9A issue exists with reviewed native blockers;
9. Phase 8.7 all-platform and real-Management integration gates pass;
10. no native blocker is open.

The implementation must verify these conditions through
the OrbStack-backed command below before any runtime file is changed:

```bash
docker run --rm -i -v "$PWD:/workspace" -w /workspace \
  2twin2clouds:latest \
  python scripts/phase_08_eventing/validate_decision_package.py --strict
```

A rejected or stale decision aborts the phase.
No builder may substitute a provider service, invent an unlisted file target,
or reinterpret an unresolved manifest entry. Such a finding reopens Phase 8.8
and creates a new immutable decision-package version before implementation
continues.

The reviewed Phase 8.8 inputs are:

| Artifact | Pinned value |
|---|---|
| Decision | `phase-08-eventing-decision@1`, normalized digest `sha256:cf9a9bd7b9d385794747bd0b564a58019fb395b8daf128977aa728f6d84a7e6c` |
| Implementation blueprint | `phase-08-eventing-implementation@1`, normalized digest `sha256:cfaa4459f6d06ff920d5d1ed5295ee21448329754071d024753ef318dd0eb7eb` |
| Scenario result | `sha256:bc4102c52f4f759b0726f73b7dd8587689eb4fb09d0a707dba0baec9896308c5` |
| Decision scope | Offline evidence and non-executable blueprint; live identity and capacity remain activation gates |

## 3. Fixed Architecture

Add both:

```text
ArchitectureProfile: five-layer-baseline@2

Responsibilities:
  Data acquisition
  Data processing
  Historical storage
  Digital Twin state
  Visualization

ArchitectureProfile: six-layer-eventing@1

Responsibilities:
  Data acquisition
  Data processing
  Historical storage
  Digital Twin state
  Visualization
  Eventing and messaging
```

`five-layer-baseline@2` assigns the event-rule evaluator, action dispatch, and
notification workflow to Data Processing and the device-command adapter to
Data Acquisition. Direct/provider-native event transport remains supporting
behavior of those responsibilities and is not mislabeled as a sixth layer.

Eventing components and edges come only from the approved decision package.
Both profiles must preserve the semantic names of the baseline responsibilities;
numeric labels are display metadata, not primary IDs.

Required topology properties for both profiles:

- producers publish canonical domain events through platform-owned adapters;
- producers do not know consumer function identities or physical destinations;
- the event-rule, action, workflow, and command components are always present;
- runtime rules determine whether a specific message produces an action;
- legacy Eventing feature flags are not accepted for new-profile operations;
- storage lifecycle data movement remains storage-owned and L4-to-L5 reads
  remain synchronous;

Additional topology properties for `six-layer-eventing@1`:

- independent consumers subscribe through cataloged edges;
- required buffering, retry, DLQ, and replay/redrive are explicit components;
- L1-L5 components may connect to Eventing where the approved graph requires;
- internal helper calls within one cohesive component remain in-process;
- stateful ordered orchestration uses an approved workflow component rather
  than an accidental topic chain;
- synchronous request/response edges remain typed synchronous edges when the
  functional requirement demands immediate response.

## 4. Contract Evolution

### 4.1 Architecture Contracts

Retain schema v1 and add new semantic definitions/fixtures:

```text
contracts/architecture-profiles/definitions/
  profiles/five-layer-baseline/2/profile.json
  provider-implementations/five-layer-baseline/2/
    aws/1.json
    azure/1.json
    gcp/1.json
  profiles/six-layer-eventing/1/profile.json
  provider-implementations/six-layer-eventing/1/
    aws/1.json
    azure/1.json
    gcp/1.json
  component-catalogs/eventing/1/catalog.json
  fixtures/resolved/
    all-aws-five-layer-v2-resolved-architecture.json
    all-azure-five-layer-v2-resolved-architecture.json
    mixed-five-layer-v2-resolved-architecture.json
    all-aws-eventing-resolved-architecture.json
    all-azure-eventing-resolved-architecture.json
    mixed-eventing-on-gcp-resolved-architecture.json
    mixed-eventing-resolved-architecture.json
  fixtures/unsupported/
    unsupported-single-provider-path.json
```

`ResolvedTwinArchitecture v1` is already responsibility/component based and
remains valid. Its profile, provider profile, catalog, formula, evidence,
extension, and graph refs pin the embedded-event or Event-Layer
implementation.

The `five-layer-baseline@2` provider definitions contain the mandatory
event-rule/action/workflow/command components without an Eventing
responsibility. The `six-layer-eventing@1` definitions contain the same domain
components plus the approved Eventing bundle and bridge components.

The positive fixture set must assign the Eventing responsibility to AWS,
Azure, and GCP at least once within an otherwise functionally complete whole
architecture. It must not assume that every provider can implement every other
responsibility. An all-GCP whole path is positive only when the Phase 8.5
capability gate proves all six responsibilities complete; otherwise it remains
an explicit negative fixture with exact unsupported reasons.

### 4.2 `ResolvedDeploymentSpecification v2`

Create:

```text
contracts/resolved-deployment-specification/v2/
  schema.json
  deployment-dimensions.json
  verification-matrix.json
  verification-matrix.schema.json
  fixtures/
```

V2 replaces the fixed `slot_id` enum with:

- `responsibility_id`;
- `logical_component_id`;
- `deployment_component_id` and version;
- `provider`;
- `service_id`;
- `required`;
- typed deployment `dimensions`.

It accepts only profile/catalog-declared component IDs. It does not accept
arbitrary client-authored layer names. The dimension registry maps each
deployment component to exact required/optional dimensions, formulas,
classification, type, range, allowed values, and Terraform bindings.

Both active profiles emit v2 for new calculations after activation. V1 remains
readable for historical five-layer runs and is never widened or rewritten.
There is no automatic conversion of a frozen v1 run to v2.

### 4.3 DeploymentManifest v4

Create Manifest v4 because Manifest v3 pins deployment specification v1:

```text
contracts/deployment-manifest/v4/
  schema.json
  fixtures/
```

V4 carries:

- full secret-free `ResolvedTwinArchitecture v1`;
- full `ResolvedDeploymentSpecification v2`;
- exact decision/profile/provider/catalog/bridge digests;
- the existing package, Twin, calculation, credential-source, and
  compatibility metadata.

Manifest v2 remains historical for pre-architecture-profile operations, and
Manifest v3 remains historical for frozen profile-driven baseline operations.
Both remain readable and destroyable. New five-layer and Eventing operations
require v4 after activation. Invalid v4 never falls back to v3 or v2.

### 4.4 Sync And Compatibility

Extend existing sync scripts and `.github/workflows/deployment-contract.yml`.
Optimizer, Management, and Deployer generated copies must be byte-identical.
Compatibility tests must prove:

- v1 specification + Manifest v2 pre-profile historical read/destroy;
- v1 specification + Manifest v3 historical read/destroy;
- v2 specification + Manifest v4 new baseline deploy;
- v2 specification + Manifest v4 new Eventing deploy;
- new deploy/redeploy/verify/package rejects Manifest v2 and v3 after v4
  activation while their historical read/destroy paths remain available;
- every cross-version mismatch fails closed.

## 5. Eventing Workload And Optimization

### 5.1 Workload Contract

Add the approved `eventing-workload.v1` fields to the profile-bound workload
bundle. The user-facing workload remains one typed object. Shared
domain-event traffic fields are required by both new profiles; fields that
describe Event-Layer-only retention/replay policy are required only by
`six-layer-eventing@1`.

The Management API, Optimizer, and Flutter must share exact constraints for:

- events/month and payload bytes;
- closed-world event channel IDs;
- rule-match, workflow-start, and device-command shares;
- graph-derived per-channel consumers and fan-out deliveries;
- retry, DLQ, replay shares;
- retention;
- ordering scope;
- required delivery semantics;
- peak throughput and partition-key count;
- graph-derived directed cross-cloud routes;
- exact provider-region pricing catalog references.

`useEventChecking`, `triggerNotificationWorkflow`, and
`returnFeedbackToDevice` are invalid for both new profiles. Unknown, hidden,
or stale Eventing fields fail validation. Switching to historical
`five-layer-baseline@1` is not a silent downgrade; only its historical
read/destroy paths consume legacy records.

### 5.2 Pricing Registry

For every approved bundle member, register:

- `PricingIntent` fields;
- exact dynamic/account-scoped/static-official source policy;
- meter/SKU/product selectors and rejected alternatives;
- normalization rule;
- formula ID/version;
- free quota, tier, minimum capacity, and rounding behavior;
- transfer and adapter cost ownership;
- evidence freshness/review policy.

Official-static fields use the current reviewed evidence path. They are never
loaded through an emergency fallback or represented as fetched.

### 5.3 Formula Set And Strategy Bundle

Add one shared domain-event formula set plus the approved transport-specific
formula sets. Bind embedded-event formulas to `five-layer-baseline@2` and
Event-Layer formulas to `six-layer-eventing@1`:

```text
optimization strategy
  + calculation strategy
  + Eventing formula set
  + pricing registry version
  + workload contract
  + deployment specification v2
  + profile/provider catalogs
```

Formulas must expose:

- provider-billed request/message chunks;
- ingestion, delivery, fan-out, retry, DLQ, retention, replay;
- fixed capacity/partition resources;
- adapter/workflow compute;
- same-region, cross-region, and cross-cloud transfer;
- total and field-level evidence references.

No formula may infer a provider tier from a display string.

### 5.4 Candidate Resolution

Extend the Phase 8.5 profile resolver; do not add an Eventing-only optimizer
endpoint.

For each candidate:

1. load approved provider profile/catalog versions;
2. map every shared domain-event component and edge;
3. prove mandatory capabilities;
4. validate pricing/formula/specification compatibility;
5. calculate component/edge costs and transfer routes;
6. reject incomplete or unpublishable candidates;
7. rank complete whole-architecture paths;
8. emit RTA v1 and RDS v2 with matching profile/run/digests.

Single-cloud and mixed candidates stay in one result set only when they use the
same exact profile version. `five-layer-baseline@2` and
`six-layer-eventing@1` share domain behavior but remain separate optimizer
runs because the latter has additional mandatory transport semantics.
Historical `five-layer-baseline@1` remains a third, frozen result space.

## 6. Management API And Persistence

The generic Phase 8.4 tables continue to store resolutions and assignments.
Add only:

- v2 deployment-specification persistence/validation;
- Eventing workload fields in normalized Twin workload persistence;
- decision/provider/catalog/bridge digest projections needed for query and
  audit;
- profile-aware run/result summaries;
- Eventing evidence DTOs through existing collapsed evidence endpoints.

Do not add `cheapest_eventing`, provider-specific Eventing columns, raw
pricing JSON fields, or a second Eventing resolution table.

Required API behavior:

- `/architecture-profiles` returns Eventing only after full activation;
- profile detail returns the Eventing graph and provider availability;
- calculation create derives the Eventing bundle from selected profile;
- run/resolution endpoints return typed Eventing assignments and edges;
- deployment requires matching RTA v1 + RDS v2;
- profile-change preview includes Eventing workload/binding invalidation;
- unsupported or incomplete provider/profile combinations fail with stable
  safe codes.

All writes remain owner-scoped and transactional. Flutter cannot author
provider bundles, Eventing service IDs, formulas, cost values, graph edges,
tiers, or deployment dimensions.

## 7. Deployer Catalog And Graph

Register only the three approved provider bundles. Each selected bundle member
must have:

- deployment component and version;
- provider service and approved tier/mode;
- package/runtime adapter where required;
- explicit Terraform module/resource address;
- allowlisted inputs and outputs;
- permission capabilities and permission-set version;
- input/output ports and envelope version;
- delivery/retry/DLQ/replay contract refs;
- error/observability/cleanup refs;
- pricing/formula/specification dimension refs;
- dependency and lifecycle stages.

### 7.1 Exact Selected Bundles And Provider Versions

The implementation must use these bundle members exactly:

| Scope | AWS | Azure | GCP |
|---|---|---|---|
| Embedded `five-layer-baseline@2` | IoT Core, Lambda, Step Functions Standard, IoT Commands, SQS FIFO, CloudWatch | IoT Hub, Functions Flex Consumption, Logic Apps Consumption, Service Bus Standard, Azure Monitor | Pub/Sub, Cloud Run, Workflows, GKE Standard, Apache BifroMQ `4.0.0-incubating`, Cloud Load Balancing, Cloud Logging |
| `six-layer-eventing@1` Event Layer | Kinesis Data Streams, SNS FIFO, SQS FIFO, S3 failure destination, Lambda, CloudWatch | Event Hubs Standard for Small/Medium, Event Hubs Dedicated for Large, Service Bus Standard, Functions Flex Consumption, Azure Monitor | Pub/Sub, Cloud Run services, Cloud Run worker pools, Cloud Logging |

Provider plugins are pinned by the implementation manifest:

| Provider | Required versions | Binding consequence |
|---|---|---|
| AWS | `hashicorp/aws = 6.53.0`, `hashicorp/awscc = 1.90.0` | `aws_iam_outbound_web_identity_federation` and `awscc_iot_command` are required |
| Azure | `hashicorp/azurerm = 4.81.0`, `Azure/azapi = 2.10.0` | The six-CU Dedicated Event Hubs cluster uses `azapi_resource`; `azurerm_eventhub_cluster` cannot express the reviewed capacity |
| GCP | `hashicorp/google = 7.39.0`, `hashicorp/kubernetes = 3.2.1`, `hashicorp/helm = 3.2.0` | Cloud Run v2 worker pools and the explicit BifroMQ/GKE/Load-Balancer boundary are required |

Every selected service-component instance maps to exactly one of the 33
service-component records in `implementation-component-manifest.json`. A
bundle member absent from that manifest is not an implementation option.

The existing generic `ResolvedDeploymentGraph v1` remains valid. Add Eventing
nodes and edges through catalog data, not switch statements on `eventing`.

Preflight must reject:

- missing/extra Eventing component;
- unsupported provider/region/tier;
- envelope or port mismatch;
- unresolved destination/topic/queue/subscription/output;
- permission-set gap;
- illegal producer-to-consumer identity construction;
- missing retry/DLQ/replay/observability resource;
- bridge direction/trust mismatch;
- RDS v2 dimension mismatch;
- catalog/decision digest drift.

## 8. Runtime Adapters And Packages

Implement `eventing-envelope.v1` in platform-owned adapters for all three
provider bundles.

Adapter requirements:

- validate size/schema/version before routing or invoking user logic;
- preserve event, correlation, trace, Twin/device, and partition IDs;
- distinguish retryable, rejected, and terminal failures;
- never log payloads, credentials, endpoints, or provider responses;
- propagate original typed failure without false success;
- expose bounded publish/delivery/retry/DLQ/replay metrics;
- preserve idempotency keys across redelivery and bridge forwarding.

Producer code depends on one platform publisher interface. Consumer wrappers
depend on one platform envelope interface. Provider SDK calls, physical names,
and trigger shapes remain inside adapters.

Internal helper functions belonging to one logical component must not be
split into new broker hops. Existing user-function extension slots bind to
approved consumer components through #113 contracts.

## 9. Multi-Cloud Bridge

Implement the exact Phase 8.8 ownership decision as one registered bridge
component per cross-provider route class.

The bridge is not a public function endpoint and is not destination-owned
pulling. Its fixed flow is:

```text
source durable outbox/broker
  -> source-provider runtime trigger
  -> envelope and route validation
  -> short-lived destination credential
  -> destination broker data-plane publish
  -> wait for durable destination acceptance
  -> acknowledge/checkpoint the source
```

The source runtime and destination APIs are exact:

| Source provider | Source trigger and runtime | Cross-provider destination APIs used by that runtime | Source acknowledgement |
|---|---|---|---|
| AWS | Kinesis event-source mapping for telemetry; SNS FIFO archive plus bridge-owned SQS FIFO subscription and Lambda SQS mapping for control; batch maximum 10, Kinesis `ParallelizationFactor=1` | Azure: Event Hubs or Service Bus producer SDK; GCP: ordered Pub/Sub publisher | Kinesis checkpoint/partial batch success or SQS delete only after destination acceptance |
| Azure | Event Hubs or session-enabled Service Bus trigger on Functions Flex Consumption; batch maximum 10 | AWS: Kinesis `PutRecord` or SNS FIFO `Publish`; GCP: ordered Pub/Sub publisher | Event Hubs checkpoint or Service Bus manual completion only after destination acceptance |
| GCP Small/Medium and Large control | IAM-authenticated Pub/Sub push invokes a Cloud Run service with one message per request | AWS: Kinesis `PutRecord` or SNS FIFO `Publish`; Azure: Event Hubs or Service Bus producer SDK | HTTP success only after destination acceptance |
| GCP Large telemetry | Pub/Sub ordered StreamingPull subscription consumed by a Cloud Run worker pool; 21 workers per telemetry channel in the reviewed bridge scenario | AWS: Kinesis `PutRecord`; Azure: Event Hubs producer SDK | Per-message StreamingPull acknowledgement only after destination acceptance |

A same-provider edge publishes and consumes through the selected local broker
path. It creates no bridge forwarder, workload-identity exchange, or
cross-cloud egress contribution.

Telemetry lands in Kinesis, Event Hubs, or Pub/Sub with `device_id` as the
partition/ordering key. Control/action/command traffic lands in SNS/SQS FIFO,
Service Bus sessions, or ordered Pub/Sub. The six directed route classes and
their exact trust paths are AWS→Azure, AWS→GCP, Azure→AWS, Azure→GCP,
GCP→AWS, and GCP→Azure; all are capability-admissible but remain live-tested
activation gates.

Every bridge runtime must:

- validate the destination allowlist, region-pinned SDK endpoint, normal TLS
  certificate/hostname chain, envelope, schema, route, and size;
- cache only short-lived credentials in memory, discarding them at expiry
  minus five minutes or after one hour, whichever occurs first;
- enforce retry, backoff, circuit-break, backpressure, terminal source DLQ,
  and audited redrive;
- preserve `event_id`, `invocation_id`, correlation, trace, device key, and
  replay identity; explicit redrive uses `event_id + replay_id_or_live` for
  FIFO transport deduplication;
- resume GCP ordering keys after publish errors and emit an ordering-degraded
  terminal outcome when a key cannot progress;
- emit only bounded payload/credential/endpoint-free evidence; and
- account for source outbox/read, forwarder compute, source egress,
  destination ingress/landing, and observability exactly once.

Static shared secrets are forbidden. If the approved trust mechanism cannot be
implemented using the current credential/permission contracts, the provider
route remains unsupported and the profile cannot activate.

## 10. Terraform Implementation

Add explicit, reviewed Terraform modules/resources for every selected bundle.
Terraform remains static HCL.

Requirements:

- one module/resource implementation per catalog entry;
- direct resource/output references for topics, queues, subscriptions,
  endpoints, roles, DLQs, archives, and bridge inputs;
- no duplicated name reconstruction in tfvars or function code;
- exact tier/capacity/retention/retry/DLQ values from RDS v2;
- provider-native dependency graph;
- lifecycle, encryption, logging, and deletion behavior;
- least-privilege permission capabilities;
- deterministic outputs consumed by graph bindings;
- no provider default relied upon when it changes functionality, cost,
  retention, delivery, or security.

Defaults may remain implicit only when the approved provider contract proves
they are stable, equivalent to the selected dimension, and covered by drift
tests. Otherwise the value must be explicit.

## 11. Failure And Observability Contract

Add stable codes:

- `EVENTING_PROFILE_DECISION_INVALID`
- `EVENTING_BUNDLE_UNSUPPORTED`
- `EVENTING_CAPABILITY_INCOMPLETE`
- `EVENTING_PRICING_UNPUBLISHABLE`
- `EVENTING_ENVELOPE_INVALID`
- `EVENTING_SCHEMA_UNSUPPORTED`
- `EVENTING_DELIVERY_RETRY_EXHAUSTED`
- `EVENTING_DLQ_UNAVAILABLE`
- `EVENTING_REPLAY_UNAVAILABLE`
- `EVENTING_ORDERING_UNSUPPORTED`
- `EVENTING_BRIDGE_TRUST_INVALID`
- `EVENTING_BRIDGE_DESTINATION_INVALID`
- `EVENTING_BRIDGE_BACKPRESSURE`
- `EVENTING_DEPLOYMENT_BINDING_INVALID`

Management and Deployer translate errors through their existing centralized
boundaries. Errors expose safe profile/component/edge IDs and correlation ID
only.

Structured operation evidence includes:

- profile/decision/catalog/formula/specification/graph digests;
- provider bundle and safe component/edge IDs;
- stage, status, duration, counts, and safe result code;
- no event payload, source, credential, physical destination, tfvars, or raw
  provider error.

## 12. Flutter Workflow

Extend the existing Phase 8.7 Architecture and Workload tasks. Do not add a
second Eventing wizard.

### 12.1 Wide Layout

```text
+----------------------+------------------------------------------------------+
| Configuration        | Architecture                                         |
|                      |                                                      |
| Architecture       * | Profile                                              |
|   Select profile   * | ( ) Five-layer baseline                              |
|   Understand       o | (o) Six-layer Eventing                               |
| Workload           l |                                                      |
| User Logic         l | Eventing and messaging                               |
| Optimize...        l | route | buffer | fan-out | retry | DLQ | replay      |
| Deployment...      l |                                                      |
|                      | Ingestion ---> Eventing ---> Processing               |
|                      |                  |    |                                |
|                      |                  v    +--> Twin ---> Visualization     |
|                      |               Storage                                 |
|                      |                                                      |
|                      | Functional coverage: Complete                         |
|                      | Provider bundles: AWS | Azure | GCP | Mixed           |
+----------------------+------------------------------------------------------+
| Back                       Draft saved                         Continue       |
+-----------------------------------------------------------------------------+
```

The following shared domain-event workload is present for both
`five-layer-baseline@2` and `six-layer-eventing@1`. It contains no
enable/disable switch; profile selection changes architecture ownership, not
whether the domain-event behavior exists.

Domain-event workload task:

```text
+--------------------------------------------------------------------------+
| Domain-event workload                                                    |
| Events / month       [ 10,000,000 ]  Average payload [ 16 ] KiB           |
| Channels             [ 8 derived  ]  Peak rate       [ 250 ] events/s     |
| Retention            [ 168        ]h Ordering        [ Per device      v ] |
| Retry share          [ 0.5        ]% DLQ share       [ 0.05           ]%  |
| Replay share         [ 1.0        ]% Routes          [ Graph-derived   ]  |
|                                                                          |
| Derived base deliveries: 40,300,000                       [Details v]     |
+--------------------------------------------------------------------------+
```

### 12.2 Compact Layout

```text
+------------------------------------------+
| Workload / Domain events              [v] |
+------------------------------------------+
| Events / month                           |
| [ 10,000,000                          ]  |
| Payload [ 16 ] KiB   Rule matches [1]%   |
| Peak    [ 250 ]/s    Retention [ 168 ]h  |
| Ordering [ Per device                 v]  |
| Retry [0.5]%  DLQ [0.05]%  Replay [1]%   |
| Workflow [25]%  Device command [25]%     |
|                                          |
| Derived channels, fan-out, routes   [v]  |
+------------------------------------------+
| Back                         Continue     |
+------------------------------------------+
```

The resolved review reuses `ArchitectureProfileGraph`,
`ResolvedArchitectureSummary`, evidence disclosures, and deployment review.
It adds Eventing rows/edges through typed data; graph widgets must not test the
profile ID.

### 12.3 Widget Tree

```text
WizardView [MODIFY]
`-- ConfigurationWorkspaceShell [REUSE]
    `-- selected task child from WizardView [MODIFY]
        |-- ArchitectureProfileTask [REUSE/MODIFY new profiles]
        |   `-- ArchitectureProfileGraph [REUSE]
        |-- WorkloadTasks [MODIFY]
        |   `-- EventingWorkloadSection [NEW]
        |       |-- ValidatedNumberInput [REUSE]
        |       |-- ValidatedDecimalInput [REUSE]
        |       |-- OrderingScopeSelector [NEW]
        |       `-- CollapsibleSection [REUSE]
        |-- OptimizerReviewTask [REUSE/MODIFY typed Eventing rows]
        `-- ConfigurationReviewTask [REUSE/MODIFY typed Eventing edges]
```

`OrderingScopeSelector` is new because the current workload controls have no
closed semantic ordering enum. All other fields must reuse current form and
evidence primitives.

### 12.4 State And Accessibility

- Wizard BLoC owns profile-dependent field visibility, validation, calculation,
  result selection, and profile-change invalidation.
- Riverpod retains runtime/demo/API composition.
- `ApiService` talks only to Management API.
- demo/live interfaces remain identical.
- all controls use theme tokens and Material icons.
- labels include units and semantic purpose; color is never the only status.
- wide and compact layouts support keyboard operation and 200% text scale.
- raw provider meters, tfvars, bridge endpoints, credentials, and event
  payloads remain hidden.

## 13. Implementation Slices

### 8.9A Commit Boundary: `five-layer-baseline@2`

Implement shared contracts and the complete embedded-event profile across
Optimizer, Management, Deployer, Terraform, Flutter, tests, and documentation.
Run two reviews, fix every finding, and create the clean 8.9A commit before
opening the 8.9B branch. Historical `five-layer-baseline@1` golden evidence
must remain unchanged.

### 8.9B Commit Boundary: `six-layer-eventing@1`

Starting from the reviewed 8.9A commit, add only the independent Eventing
responsibility, approved Event-Layer bundles, and bridge behavior. Run the same
two-review/fix cycle before the 8.9B commit.

### Slice A: V2/V4 Contracts

Must implement RDS v2, Manifest v4, new fixtures, byte-identical generated
copies, compatibility readers, sync gates, and negative cross-version tests.

### Slice B: Profile, Provider, And Catalog Definitions

Must add `five-layer-baseline@2` first and `six-layer-eventing@1` second,
including their approved provider bundles/component/edge definitions, and
prove every reference, capability, permission, package, Terraform, formula,
and specification binding.

### Slice C: Optimizer

Must add workload intents, pricing sources, formula set, functional gate,
whole-path calculation, RTA/RDS output, golden scenarios, and fail-closed
evidence handling.

### Slice D: Management API

Must add workload persistence/validation, v2 specification handling, generic
Eventing projections, profile activation, errors, audit, migration, and API
tests without provider-specific columns.

### Slice E: Deployer And Runtime

Must add graph nodes/edges, adapters, packages, bridge, permissions, static HCL,
typed bindings, preflight, operation evidence, and offline provider tests.

### Slice F: Flutter

Must expose `five-layer-baseline@2` and `six-layer-eventing@1` as the two new
selectable profiles, keep `five-layer-baseline@1` historical/read-only, and
add shared Eventing workload fields, data-driven graph/review, profile
invalidation, demo parity, accessibility, and all-platform gates.

### Slice G: Cross-Stack Offline Release Gate

Must prove every currently admissible single-provider path and at least one
complete whole path assigning Eventing to each of AWS, Azure, and GCP from
workload through Optimizer, Management, Manifest v4, Deployer graph, package,
permissions, and Terraform mock plan. Explicitly unsupported single-provider
paths must remain negative fixtures. The gate must also prove baseline v2 and
historical v1/v3 compatibility.

## 14. Test Plan

### Contracts

- every required/additional field for RDS v2 and Manifest v4;
- v1/v2 and v3/v4 compatibility/mismatch matrix;
- Eventing profile/provider/catalog positive and negative references;
- decision/catalog digest drift;
- canonical digest stability.

### Optimizer

- Phase 8.8 small/medium/large scenarios for each embedded-event and
  Event-Layer provider bundle;
- every currently admissible single-provider whole path;
- at least one complete whole path assigning Eventing to each of AWS, Azure,
  and GCP;
- explicitly unsupported single-provider paths remain rejected;
- mandatory capability, ordering, pricing, region, permission, formula, and
  specification rejection;
- exact provider chunk/tier/capacity/retention/transfer boundaries;
- no legacy Eventing feature flag in either new profile;
- shared domain-event paths execute for both new profiles;
- no `five-layer-baseline@2`/`six-layer-eventing@1` cross-ranking;
- historical `five-layer-baseline@1` golden cost/graph remains unchanged;
- deterministic tie-break and trace.

### Management

- migration from baseline-only database;
- profile selection/change preview and exact shared/layer-specific field
  invalidation;
- Eventing run/spec/resolution atomic persistence;
- generic assignment/edge API projections;
- selected-run readiness and invalidation;
- ownership, redaction, audit, OpenAPI, and demo fixtures;
- no provider-specific Eventing column or client-authored architecture field.

### Deployer, Security, And Terraform

- every approved/rejected binding;
- exact envelope behavior across provider adapters;
- duplicate, retry, DLQ, replay, redrive, ordering, and bridge failure;
- trust/destination allowlist, TLS, idempotency, and backpressure;
- package determinism and secret/payload-free evidence;
- permission contract and Terraform symbol drift;
- explicit provider tier/capacity/retention values;
- native Terraform validate/test and offline mock plan for every provider and
  mixed fixture;
- no source/target name reconstruction in function code or tfvars.

### Flutter

- strict model parsing and unknown version;
- BLoC happy/error/stale/invalidation/retry states;
- profile selection and profile-specific workload fields;
- wide/compact layout at 720/960/1200 boundaries;
- 200% text, long labels, keyboard, semantics, light/dark;
- data-driven graph and evidence;
- demo/live parity;
- real Management integration without direct Optimizer/Deployer calls.

Extend `run_frontend_integration_tests()` in `thesis.sh` so the resolved host
device also runs `integration_test/eventing_profile_workflow_test.dart`. The
existing architecture profile test remains in the same credential-free real
Management integration gate.

### Regression

- complete safe Optimizer, Management, Deployer, Flutter suites;
- five-layer baseline golden cost and graph remain unchanged except intentional
  RDS v2/Manifest v4 representation for new runs;
- historical operations remain readable/destroyable from frozen evidence;
- docs strict build and links.

Safe verification:

```bash
docker compose up -d 2twin2clouds 3cloud-deployer management-api
docker run --rm -i -v "$PWD:/workspace" -w /workspace \
  2twin2clouds:latest \
  python scripts/phase_08_eventing/validate_decision_package.py --strict
python scripts/sync_architecture_profile_contracts.py --check
python scripts/sync_resolved_deployment_contract.py --check
python scripts/sync_deployment_manifest_contract.py --check
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 \
  python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 \
  python -m pytest tests/ --ignore=tests/e2e -v
./thesis.sh test deployment-contract
./thesis.sh test frontend
./thesis.sh test frontend-integration
```

Windows runs in the existing GitHub Actions job. No command may refresh paid
pricing, plan/apply against live provider credentials, deploy, or destroy.
Before `docker compose up`, record which named services are already running.
After verification, stop only services that this test invocation started.
Never use `docker compose down` against a shared developer stack as test
cleanup.

## 15. Documentation

Update current product/developer docs only after activation:

- profile selection and Eventing workload user guide;
- architecture profile, provider bundle, catalog, envelope, bridge, and
  extension procedure;
- contracts/data-flow diagrams for RDS v2, Manifest v4, Eventing flow, and
  bridge ownership;
- Deployer Terraform/permission/troubleshooting references;
- demo handbook/scenarios;
- Phase 8 roadmap and #140 with named provider/platform evidence.

Update research evidence with implementation deviations and limitations.
Keep cost interpretation for Phase 8.10. Do not edit LaTeX.

## 16. Rollout And Rollback

Rollout:

1. ship RDS v2/Manifest v4 readers and profile definitions dark;
2. run all offline cross-stack gates;
3. enable `five-layer-baseline@2` v2/v4 calculation and deployment, publish it
   through the Management profile list, and expose it through the existing
   compact Flutter/demo workflow;
4. verify shared event behavior and historical `five-layer-baseline@1`
   compatibility;
5. commit and review the 8.9A boundary;
6. implement and verify the independent Eventing responsibility from the
   reviewed 8.9A base, then activate `six-layer-eventing@1`
   calculation/deployment server-side;
7. publish `six-layer-eventing@1` through the same Management profile list and
   existing Flutter/demo workflow without changing the already active
   five-layer v2 contract;
8. monitor stable errors and operation evidence;
9. commit and review the 8.9B boundary.

Activation is atomic at the repository/server profile lifecycle boundary. Do
not expose a profile whose provider bundles are only partially implemented.

Rollback retires `six-layer-eventing@1` from new selection and blocks new
Event-Layer operations. `five-layer-baseline@2` has an independent activation
and rollback switch. Existing resolutions and frozen operations remain
readable/destroyable. Neither rollback may silently fall back to another
profile or rewrite a Twin's selected profile.

## 17. Definition Of Done

- [ ] The Phase 8.8 approved decision and exact bundle/bridge refs are enforced.
- [ ] Every implementation component manifest entry maps one-to-one to the
      implemented cross-project IDs, files, resources, packages, permissions,
      ports, bindings, and tests.
- [ ] `five-layer-baseline@1` remains immutable and historical.
- [ ] `five-layer-baseline@2` is a closed-world five-responsibility profile
      with mandatory embedded rule/action/workflow/command behavior.
- [ ] `six-layer-eventing@1` is a closed-world, nonlinear, versioned profile.
- [ ] Both new profiles implement the same domain-event flow, and neither
      accepts the three legacy Eventing feature flags.
- [ ] RDS v2 and Manifest v4 represent generic components and remain
      cross-project drift-gated.
- [ ] Historical RDS v1/Manifest v2 and v3 behavior remains read/destroy
      compatible without enabling new operations.
- [ ] Eventing workload, pricing, formulas, units, tiers, transfer, and
      deployment dimensions are exact and traceable.
- [ ] Functional completeness precedes cost for every provider and mixed path.
- [ ] Baseline and Eventing candidates never share one optimization ranking.
- [ ] Management stores generic immutable assignments/edges without new fixed
      provider/Eventing columns.
- [ ] Every approved Eventing component, package, permission, output/input,
      Terraform resource, and cleanup behavior is cataloged.
- [ ] Producers and user code do not reference consumer or provider resource
      identities.
- [ ] Retry, DLQ, replay/redrive, idempotency, ordering, observability, trust,
      bridge, transfer, and failure semantics are implemented and tested.
- [ ] Terraform uses explicit resources/outputs and exact selected
      tier/capacity/retention values.
- [ ] Flutter offers compact profile-aware workload and read-only review on
      Web, macOS, Windows, and Linux through Management only.
- [ ] The real-Management `eventing_profile_workflow_test.dart` proves profile
      selection, Eventing workload submission, resolved review, invalidation,
      and safe failure states without mocked HTTP.
- [ ] Every admissible single-provider path, one complete path per Eventing
      provider, all explicit unsupported paths, mixed, negative, compatibility,
      package, permission, Terraform mock-plan, API, demo, UI, and
      documentation gates pass.
- [ ] No live provider credential, resource, paid API, apply, destroy, or E2E
      action occurs.
- [ ] 8.9A and 8.9B use separate branches, reviews, and clean commits.
- [ ] Product/developer/research docs, roadmap, the new 8.9A issue, and #140
      are updated.
- [ ] Two reviews find no unresolved issue.
- [ ] Each structured commit references its own implementation issue.
