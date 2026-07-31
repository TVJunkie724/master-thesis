---
title: "Phase 8.9B: Deferred Six-Layer Eventing Implementation Draft"
description: "Suspended historical draft that must be rewritten after the reviewed five-layer-baseline@2 implementation."
tags: [architecture, eventing, optimizer, management-api, deployer, flutter, issue-140]
lastUpdated: "2026-07-31"
version: "1.12"
---

<!-- SOURCES:
- GitHub issue #140
- Approved Phase 8.8 Eventing decision package
- Phase 8.2-8.7 contracts and implementations
- docs/research/digital_twin_architecture_and_eventing_layer.md
- Existing resolved-deployment-specification, DeploymentManifest, provider, Terraform, and Flutter extension points
- User-approved bounded six-layer profile with no arbitrary graph editor
- User decision to plan and implement Five-layer v2 first and defer Six-layer
  until the committed Five-layer baseline can be inherited without
  reinterpretation
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
EXTRACTED: 2026-07-31 | VERSION: 1.12
-->

# Phase 8.9B: Deferred Six-Layer Eventing Implementation Draft

## Suspension Notice

**Do not implement from this document.**

The service matrix, BigQuery L3 selection, L3-hot/L4/L5 co-location rule, dual
visualization paths, ADX selection, scene requirements, workload fields, tests,
and Definition of Done below describe the superseded pre-2026-07-29
comparison-profile draft. They remain visible only as planning provenance.

The current executable Five-layer v2 authority is
[`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md). It
keeps Azure Cosmos DB, requires `provider(L3_hot) == provider(L5)`, places L4
independently, implements `L3 hot -> L5` raw visualization and
`L3 hot -> L4` Twin projection, and excludes L4-to-L5/3D behavior.

After Five-layer v2 is implemented, reviewed, and committed, this file must be
rewritten from the committed L1-L5 contract. Only then may a separately
approved 8.9B branch add the independent Eventing responsibility. Until that
gate, every unchecked item and implementation instruction below is
non-authoritative and #140 remains blocked.

The rewrite must inherit the committed guided-cloud-bootstrap and Layer Access
contracts unchanged. Six-layer adds Eventing ownership; it does not introduce
a second credential setup, require manually constructed CloudConnections, or
alter the AWS/Azure/GCP human sign-in prerequisites.

## 0. Metadata

| Field | Value |
|---|---|
| Issues | New `five-layer-baseline@2` implementation issue required before execution; [#140 Implement six-layer-eventing@1 across the platform](https://github.com/TVJunkie724/master-thesis/issues/140) |
| Milestone | Phase 8 - Twin Architecture Profiles & Eventing |
| Recommended branches | 8.9A `codex/phase-8-five-layer-baseline-v2`; 8.9B `codex/phase-8-six-layer-eventing` |
| Branch bases | 8.9A starts from the reviewed Phase 8.7 boundary, which already contains both immutable decision packages and the integrated dark compiler; 8.9B starts from the reviewed 8.9A commit; both ultimately target `master` |
| Blocked by | Phase 8.7 / #138, approved Phase 8.8 / #146, and approved immutable complete-service decision |
| Produces | Executable closed-world `five-layer-baseline@2` and `six-layer-eventing@1` |
| Targets | AWS/Azure/GCP Eventing bundles, admissible whole paths, Web, macOS, Windows, Linux |
| Live cloud E2E | Forbidden |

Every contract, provider bundle, formula, package, permission, Terraform
binding, API field, UI state, test, and Definition of Done item in this plan is
mandatory. The phase must use the exact approved Phase 8.8 bundle and bridge
IDs plus the exact complete-service online-bundle/storage/query IDs; it must not
substitute another service during implementation.

### Corrective Complete-Service Boundary

This plan composes two immutable decisions:

1. `phase-08-eventing-decision@1` for shared domain events, embedded/Event-Layer
   bundles, and asynchronous broker bridges;
2. `phase-08-complete-service-bundles@1` for complete AWS, Azure, and
   provider-hosted GCP L1-L5 bundles, minimal storage transitions, workload
   v2, online-analytics co-location, dual visualization reads,
   materialization, datasource identity, and full-profile capacity.

Phase 8.9 may not reinterpret the first package as proof of the second. The
current public Function/shared-token runtime and the uncontracted historical
L3-hot-to-Grafana binding are forbidden for both new profiles. A corrected,
typed L3-hot-to-L5 raw-history edge is mandatory alongside L4-to-L5 Twin
context.

Phase 8.9 is executed as two independently reviewed branches and commit series.
8.9A implements and closes `five-layer-baseline@2`. 8.9B starts only after
8.9A is clean and implements `six-layer-eventing@1`.

Both boundaries use one fixed regional experiment: AWS `eu-central-1`, Azure
`westeurope`, and GCP `europe-west1`. Region is not an optimization dimension
for these versions. All regional components of a provider stay in its fixed
region, and a missing service/tier/price rejects the bundle instead of causing
an implicit regional fallback.

In this plan, activation is an offline repository state: the Management API
may expose the version for new selection, and the platform may calculate,
resolve, package, and use its implemented deployment path. Verification in
this phase remains no-apply. Activation does not claim a successful live
deployment or measured provider capacity. Those separate live-readiness gates
remain `live_capacity_pending` until a supervised cloud run is explicitly
approved and recorded.

The composed decision validator applies the single pinned legacy mapping
`required_before_profile_activation` ->
`required_before_live_readiness` from the immutable Eventing package. Unknown
gate values or any other cross-package disagreement abort activation.

It also preserves the immutable whole-profile observations
`profile_target_not_implemented` and `unsupported_missing_l4_l5`. The
complete-service package must close them with an exact provider/profile bundle
mapping; GCP closure must specifically prove its selected L4/L5 implementation.
The validator emits both the historical status and the new closure ref/digest.
It never edits the Eventing artifact or treats the old status as the current
runtime result. A missing or provider-mismatched mapping aborts activation.

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
10. the complete-service decision is approved and its implementation manifest
    resolves without conflict against the Eventing manifest;
11. all six storage identity directions and all twelve hot-to-cool/
    cool-to-archive stage route classes resolve;
12. AWS, Azure, and provider-hosted GCP complete-provider capacity gates pass;
13. no native blocker is open.

The implementation must verify these conditions through
both OrbStack-backed commands below before any runtime file is changed:

```bash
docker run --rm -i -v "$PWD:/workspace" -w /workspace \
  2twin2clouds:latest \
  python scripts/phase_08_eventing/validate_decision_package.py --strict

docker run --rm -i -v "$PWD:/workspace" -w /workspace \
  2twin2clouds:latest \
  python scripts/phase_08_service_bundles/validate_decision_package.py --strict
```

A rejected or stale decision aborts the phase.
No builder may substitute a provider service, invent an unlisted file target,
or reinterpret an unresolved manifest entry. Such a finding reopens Phase 8.8
and creates a new immutable decision-package version before implementation
continues.

The reviewed Phase 8.8 inputs are:

| Artifact | Pinned value |
|---|---|
| Decision | `phase-08-eventing-decision@1`, normalized digest `sha256:22aec12d3e3915564d59d6d2ae00ce7fdce375b8d4bfc8c3880762697a02b2a6` |
| Implementation blueprint | `phase-08-eventing-implementation@1`, normalized digest `sha256:7758a81f40d119fec8a61d03d3a8eb36c3825f732129a0edfcc925df26a85ab5` |
| Scenario result | `sha256:64b8059c4bd6a051624802252bd5922b39ba3d1249a388ebd9bf1ef91f59dc27` |
| Decision scope | Offline evidence and non-executable blueprint; live identity and capacity remain live-readiness gates |

The table above is Event-domain evidence only. Phase 8.9 additionally pins the
complete-service decision/package/capacity digests generated by
[`phase_08_service_bundle_closure.md`](phase_08_service_bundle_closure.md).
Missing values abort implementation rather than being filled from memory.

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
When a resolved responsibility edge crosses providers, the producing
responsibility also owns the approved durable source outbox and shared bridge
runtime. Same-provider placements contain neither bridge nor cross-cloud
egress.

Eventing components and edges come only from the approved decision package.
Both profiles must preserve the semantic names of the baseline responsibilities;
numeric labels are display metadata, not primary IDs.

Required topology properties for both profiles:

- producers publish canonical domain events through platform-owned adapters;
- producers do not know consumer function identities or physical destinations;
- the event-rule, action, workflow, and command components are always present;
- runtime rules determine whether a specific message produces an action;
- legacy Eventing feature flags are not accepted for new-profile operations;
- storage lifecycle data movement remains storage-owned;
- L3-hot-to-L5 raw-history and L4-to-L5 Twin-context reads remain separate
  typed synchronous edges;

Additional topology properties for `six-layer-eventing@1`:

- independent consumers subscribe through cataloged edges;
- required buffering, retry, DLQ, and replay/redrive are explicit components;
- L1-L5 components may connect to Eventing where the approved graph requires;
- internal helper calls within one cohesive component remain in-process;
- stateful ordered orchestration uses an approved workflow component rather
  than an accidental topic chain;
- synchronous request/response edges remain typed synchronous edges when the
  functional requirement demands immediate response.

Do not collapse components merely because they use the same provider service
family. In an all-GCP Six-layer graph, L1 device-backbone Pub/Sub resources and
Event-Layer Pub/Sub resources have distinct topics, subscriptions, retention,
permissions, component IDs, and operation costs. They may reuse project/API
enablement and the one L1 BifroMQ/GKE boundary. The equivalent AWS/Azure local
case uses separate declared broker/consumer resources where the approved graph
requires them, but never creates a cross-cloud bridge for a same-provider
edge.

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
responsibility, plus topology-conditional embedded outbox components and
profile-specific bindings to the shared bridge runtimes. The
`six-layer-eventing@1` definitions contain the same domain components plus the
approved Eventing bundle and its own profile-specific bindings to those shared
bridge runtimes.

The positive fixture set must assign the Eventing responsibility to AWS,
Azure, and GCP at least once within an otherwise functionally complete whole
architecture. It must not assume that every provider can implement every other
responsibility. The new complete-service decision makes the provider-hosted
GCP online analytics bundle an implementation target, so all-GCP positive fixtures are
mandatory for both new profiles. Historical `@1` keeps its explicit all-GCP
negative fixture.

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

The user-facing profile workload remains one typed v2 request. In addition to
the core fields below, it has exactly one Eventing field:

```text
profileWorkloadVersion = 2
eventingScenarioId = eventing-small-v1
                   | eventing-medium-v1
                   | eventing-large-v1
```

The immutable `eventing-workload.v1` schema is evidence for bounded synthetic
S/M/L scenarios, not a caller-editable runtime DTO. Management resolves the
selected ID from the approved Phase 8.8 package, verifies the decision and
scenario digests, and transactionally persists the ID, digest, and canonical
20-field snapshot with the Optimizer run. Flutter sends only the ID to
`POST /twins/{twin_id}/optimizer-runs/`; Management sends only the resolved
snapshot to the Optimizer. Inline Eventing objects and custom Eventing scenario
IDs fail closed. A custom workload needs a new contract version.

Both new profiles require the same reference and receive the same exact
snapshot. For `five-layer-baseline@2`, its transport-quality fields are
evaluation probes whose result may show a weaker embedded path; for
`six-layer-eventing@1`, they are mandatory Event-Layer acceptance criteria.
They never cause the five-layer profile to fabricate a sixth responsibility.

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

The profile-detail projection and Dart DTO use these exact JSON keys and
compatible types; decimal shares/rates are JSON numbers and Dart `double`,
while counts remain JSON integers and Dart `int`:

| JSON key | API type | Dart type |
|---|---|---|
| `scenario_id` | string enum of the three approved IDs | `String` |
| `display_name` | string | `String` |
| `schema_version` | const `eventing-workload.v1` | `String` |
| `scenario_digest` | `sha256:` string | `String` |
| `events_per_month`, `publish_requests_per_month`, `average_event_payload_bytes` | integer | `int` |
| `mandatory_processed_consumers`, `extra_processed_consumers` | unique string array | `List<String>` |
| `retry_share`, `dead_letter_share`, `replay_share`, `rule_match_share`, `workflow_start_share_of_matches`, `device_command_share_of_matches` | number `[0,1]` | `double` |
| `retention_hours`, `max_delivery_latency_seconds`, `active_partition_keys`, `concurrent_device_connections` | integer | `int` |
| `ordering_scope` | const `per_device` | `String` enum |
| `required_delivery_semantics` | const `at_least_once` | `String` enum |
| `peak_events_per_second` | non-negative number | `double` |
| `bounded_synthetic_scenario` | const `true` | `bool` |

`ArchitectureProfileDetailResponse` adds
`eventing_scenarios: List<EventingScenarioSummary>` for the two new profiles
and an empty list for historical/read-only profiles. Inside the existing run
request `params`, Flutter sends camel-case `profileWorkloadVersion: 2` and
`eventingScenarioId: String`. `CostCalculationRunDetailResponse` adds the
typed `eventing_scenario_ref` with `scenario_id`, `schema_version`, and
`scenario_digest`; the caller never supplies that digest. Unknown/additional
keys fail at the Management boundary.

`useEventChecking`, `triggerNotificationWorkflow`, and
`returnFeedbackToDevice` are invalid for both new profiles. Unknown, inline,
hidden, or stale Eventing fields fail validation. Switching to historical
`five-layer-baseline@1` is not a silent downgrade; only its historical
read/destroy paths consume legacy records.

The shared workload-v2 core adds these required typed fields:

```text
twinEntityCount
sceneEntityCount
totalSceneAssetSizeMiB
aggregateDashboardRefreshesPerHour
apiCallsPerAggregateDashboardRefresh
dashboardActiveHoursPerDay
monthlyEditorSeats
monthlyViewerSeats
twinStateMaterializationsPerSecond
twinGraphUpdatesPerSecond
```

`totalSceneAssetSizeMiB` is aggregate GLB bytes, while `sceneEntityCount`
counts node/Twin bindings. `needs3DModel=false` requires both to be zero;
`needs3DModel=true` requires both to be positive. Keep the existing three
storage-duration fields in workload v2 but validate `1 <= H < C < A` and
expose the five-minute batch, 24-hour retry, and 48-hour source grace only as
resolved profile constants. Historical workload validation remains unchanged.

It rejects the exact retired-field set from the complete-service closure:
the three legacy Eventing flags, both GCP capability switches, the two old
scene fields, the two old seat fields, the two old dashboard fields, and the
five old Eventing/error workload surrogates. Those fields remain historical
inputs only and never supply v2 Twin, scene, Eventing, or storage capacity.
`numberOfDeviceTypes` remains a valid L2 processor-count input. The three
`core-*-v2` presets and their synthetic state/graph update bounds come from
the complete-service decision; the Phase 8.8 Eventing presets remain separate.

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

1. resolve and digest-check the Management-owned Eventing scenario snapshot;
2. load approved provider profile/catalog versions;
3. map every shared domain-event component and edge;
4. prove mandatory capabilities;
5. validate pricing/formula/specification compatibility;
6. calculate component/edge costs and transfer routes;
7. reject incomplete or unpublishable candidates;
8. rank complete whole-architecture paths;
9. emit RTA v1 and RDS v2 with matching profile/run/digests.

Single-cloud and mixed candidates stay in one result set only when they use the
same exact profile version. `five-layer-baseline@2` and
`six-layer-eventing@1` share domain behavior but remain separate optimizer
runs because the latter has additional mandatory transport semantics.
Historical `five-layer-baseline@1` remains a third, frozen result space.

## 6. Management API And Persistence

The generic Phase 8.4 tables continue to store resolutions and assignments.
Add only:

- v2 deployment-specification persistence/validation;
- required Eventing scenario ID plus immutable digest/snapshot in normalized
  run persistence;
- decision/provider/catalog/bridge digest projections needed for query and
  audit;
- profile-aware run/result summaries;
- Eventing evidence DTOs through existing collapsed evidence endpoints.

Do not add `cheapest_eventing`, provider-specific Eventing columns, raw
pricing JSON fields, or a second Eventing resolution table.

Required API behavior:

- `/architecture-profiles` returns Eventing only after full activation;
- profile detail returns the Eventing graph, provider availability, and the
  three typed immutable `EventingScenarioSummary` projections;
- `POST /twins/{twin_id}/optimizer-runs/` accepts only
  `profileWorkloadVersion=2`, core workload-v2 fields, and one approved
  `eventingScenarioId` for either new profile, then resolves the canonical
  scenario server-side;
- calculation create derives the Eventing bundle from selected profile and the
  workload only from the persisted server-resolved snapshot;
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
| Embedded `five-layer-baseline@2` | IoT Core, Lambda, Step Functions Standard, IoT Commands, SQS FIFO, CloudWatch; Kinesis Data Streams and SNS FIFO only for remote responsibility edges | IoT Hub, Functions Flex Consumption, Logic Apps Consumption, Service Bus Standard, Azure Monitor; Event Hubs Standard for Small/Medium and Event Hubs Dedicated for Large only for remote telemetry edges | Pub/Sub, Cloud Run, Workflows, GKE Standard, Apache BifroMQ `4.0.0-incubating`, Cloud Load Balancing, Cloud Logging |
| `six-layer-eventing@1` Event Layer | Kinesis Data Streams, SNS FIFO, SQS FIFO, S3 failure destination, Lambda, CloudWatch | Event Hubs Standard for Small/Medium, Event Hubs Dedicated for Large, Service Bus Standard, Functions Flex Consumption, Azure Monitor | Pub/Sub, Cloud Run services, Cloud Run worker pools, Cloud Logging |

Provider plugins are pinned by the implementation manifest:

| Provider | Required versions | Binding consequence |
|---|---|---|
| AWS | `hashicorp/aws = 6.53.0`, `hashicorp/awscc = 1.90.0` | `aws_iam_outbound_web_identity_federation` and `awscc_iot_command` are required |
| Azure | `hashicorp/azurerm = 4.81.0`, `Azure/azapi = 2.10.0` | The six-CU Dedicated Event Hubs cluster uses `azapi_resource`; `azurerm_eventhub_cluster` cannot express the reviewed capacity |
| GCP | `hashicorp/google = 7.39.0`, `hashicorp/kubernetes = 3.2.1`, `hashicorp/helm = 3.2.0` | Cloud Run v2 worker pools and the explicit BifroMQ/GKE/Load-Balancer boundary are required |

Every Event-domain service-component instance in the table maps to exactly one
of the 37 records in the immutable Phase 8.8
`implementation-component-manifest.json`. Core online, storage, visualization,
and support components map instead to the separate complete-service manifest.
A selected member absent from its owning manifest is not an implementation
option, and duplicate ownership across the two manifests is invalid.

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

### 7.2 Complete Core Service Bundles

In addition to the Event-domain table above, implement these exact
complete-service selections:

| Provider | L3 hot / cool / archive | L4 | L5 |
|---|---|---|---|
| AWS | DynamoDB on-demand with window-shard GSI / S3 Standard-IA / Glacier Deep Archive | IoT TwinMaker Standard pricing plan plus Lambda external-data connector and scene assets | Amazon Managed Grafana 12 with TwinMaker plugin `1.3.1`, scene viewer, IAM workspace role, and service-account automation |
| Azure | Azure Data Explorer with typed `stored_at` / Blob Cool / Blob Archive | Azure Digital Twins current graph/state and optional 3D scene assets | Azure Managed Grafana Standard X1/X2 on Grafana 12 with ADX datasource, ADT query context, and 3D Scenes viewer when required |
| GCP | BigQuery partitioned on `stored_at` and clustered by device ID / Cloud Storage Nearline / Cloud Storage Archive | Cloud Run Twin API/materializer backed by bounded Firestore Native collections and scene assets | One Grafana OSS 12 pod on GKE with Persistent Disk PVC, paid BigQuery Marketplace datasource `3.2.0` in `Google Metadata Server` mode, and a minimal Twin API/scene datasource-panel |

Cosmos DB and Spanner Graph are not selected. The signed BigQuery plugin
artifact, entitlement, license, digest, and fixed cost must resolve before GCP
activation. GCP Grafana reuses the BifroMQ GKE cluster when present and
otherwise creates one GKE Standard cluster; it
does not receive a dedicated node pool, shared database, or multi-replica HA
setup by default. Scenario-derived CPU/RAM and one Persistent Disk PVC are
priced explicitly. It also adds one priced general-workload node:
`e2-standard-4` for Small/Medium or `e2-standard-8` for Large, whether the
control plane is shared or newly created.

TwinMaker Standard is fixed for every scenario because the selected knowledge
graph is unavailable in Basic. Do not introduce a tiered-bundle choice; price
the Standard entity, data-access, query, connector, scene, and visualization
dimensions.

Build the platform Twin API/scene datasource-panel as the app plugin
`twin2multicloud-twin-app`. Copy its reviewed content digest into the pinned
Grafana image and set `allow_loading_unsigned_plugins` to exactly that one ID.
Do not enable Grafana development mode, list any other unsigned plugin, download
the app at runtime, or enable plugin-admin installation. The paid BigQuery
plugin remains signed and outside this exception. Preflight and image tests
must verify the Grafana image digest, app digest/ID, exact allowlist, disabled
plugin administration, and absence of any additional unsigned artifact.

Implement the bounded GCP Firestore Native model exactly as
`models/{model_id}`, `twins/{twin_id}`,
`twins/{twin_id}/sources/{source_id}`, `relationships/{relationship_id}`, and
`scene_bindings/{twin_id}`, with only `(from_id,type)` and `(to_id,type)`
composite relationship indexes. Per-source transactional last-event/sequence
state supplies materialization idempotency; do not add a global event-ID
collection or arbitrary multi-hop traversal.

Scene deployment is conditional on `needs3DModel`. If false, omit all
scene-specific components. If true, implement only the common GLB asset,
scene-node-to-Twin binding, and latest-value overlay contract. On GCP, the
browser calls an authenticated resource route in the custom Grafana backend
plugin; the backend uses the Grafana workload identity to invoke the Cloud Run
Twin API, whose separate identity reads and streams the exact Cloud Storage
asset. Do not expose a public bucket/Twin API, mint signed asset URLs, or add a
gateway. Gate the reviewed 100-MiB Large asset and overlay refresh on measured
latency and memory before live activation.

`provider(L3_hot) == provider(L4) == provider(L5)` is mandatory. Add three
positive online-bundle fixtures and reject every unequal assignment before
pricing. Exact service/software/provider/Helm versions and digests come from
the complete-service implementation manifest.

Register both typed visualization edges for every online bundle:

```text
L3 hot -- raw_history_query.v1 --> L5
L4 ----- twin_context_query.v1 --> L5
```

Bind L5 readers exactly: AWS Managed Grafana workspace role to TwinMaker/S3;
Azure Managed Grafana managed identity to ADX Viewer and Azure Digital Twins
Data Reader; GKE Grafana Kubernetes service account through Workload Identity
for GKE to dataset-scoped BigQuery Data Viewer, project-scoped BigQuery Job
User, a custom role containing only `resourcemanager.projects.get`, and exact
Cloud Run Invoker. Connector/Twin API runtimes keep separate least-privilege
identities. Static cloud keys, anonymous endpoints, and shared bearer tokens
fail preflight.

Azure live readiness requires a supervised query proving that Managed
Grafana's managed identity authenticates to ADX and is the caller token used
by the ADX ADT-query plugin. The identity needs both ADX Viewer and Azure
Digital Twins Data Reader. Offline activation retains
`live_capacity_pending`; a failed supervised query marks the bundle
`live_readiness_failed` and reopens the decision. Do not substitute an
interactive dashboard-user token or static app secret.

When 3D is selected, provision its Azure path separately: private Blob scene
container, the exact documented 3D Scenes Studio CORS allowlist, and viewer
user/group assignments for Azure Digital Twins Data Reader plus
container-scoped Storage Blob Data Reader. Do not grant edit roles because the
common PoC contract does not include scene editing. This user-scoped viewer is
not a fallback for the Managed Grafana/ADX identity path.

Enable the BigQuery and Cloud Resource Manager APIs for GCP L5. Configure the
datasource with `authenticationType=gce`, bind the Grafana KSA/GSA through
Workload Identity Federation for GKE, and on Standard GKE schedule the pod
only where the GKE metadata server is enabled. GCP live readiness requires
datasource `Save & test` and one bounded BigQuery query under that pod
identity. Offline activation retains `live_capacity_pending`; failure marks
the bundle `live_readiness_failed` and reopens the decision. A service-account
JSON key is not a fallback.

Add separate storage-transition routes for all six directed provider pairs at
hot-to-cool and cool-to-archive. One source-provider scheduled finite job reads
a closed writer-assigned five-minute `stored_at` batch when it reaches the
configured cumulative age boundary and writes deterministic
gzip-NDJSON objects to the
destination object API. Same-provider cool-to-archive uses native object
lifecycle. No storage-specific CDC stream, durable outbox, broker, permanent
worker, DLQ, or checkpoint database is deployed. Window IDs, object keys,
checksums, and immutable manifests provide idempotency and resume. These
components do not reuse Eventing component IDs or broker payloads.

For workload v2, define `H`, `C`, and `A` from the existing hot/cool/archive
duration inputs as cumulative 30-day data-age boundaries: hot `[0,H)`, cool
`[H,C)`, archive `[C,A)`, expiry at `A`, with `1 <= H < C < A`. Historical
`@1` validation and calculation semantics remain byte-stable. Freeze
five-minute batches, a 24-hour retry horizon, and a 48-hour source-expiry
grace as resolved profile dimensions. Native hot
retention and remote cool-source expiry include the grace; a batch incomplete
after 24 hours emits `storage_transition_failed` and fails live readiness.
Same-provider cool-to-archive lifecycle transitions after `C-H` from cool
object creation. Archive expiry is `A-H` after same-provider cool-object
creation or `A-C` after remote archive-object creation.

These offsets are nominal for on-time export. A successful retry may shift
physical lifecycle/cleanup by at most its delay inside the 24-hour horizon,
while `stored_at` still removes the data from logical cool reads at `C` and all
active reads at `A`. Persist scheduled/actual manifest timestamps and emit
`storage_transition_degraded`; do not claim that object lifecycle backdates
creation time.

The storage job and other custom provider containers reuse one
content-addressed registry support component per provider that actually
deploys at least one such image: ECR, ACR Basic, or Artifact Registry. A
managed-services-only provider receives no registry. Registry cost and cleanup
are attributed exactly once outside the scientific responsibilities.

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

The GCP embedded implementation must realize one complete bidirectional device
boundary:

```text
device <-> BifroMQ 4.0.0-incubating on GKE
             |
             +-> persistent QoS 1 $oshare integration adapter
                    -> manual ACK only after ordered Pub/Sub acceptance
```

Small uses three `e2-standard-8` broker nodes and three integration clients;
Medium uses three broker nodes and six clients; Large uses twelve broker nodes,
four dedicated integration-worker nodes, and 30 pods with ten 1-MiB/s clients
each. All scenarios use three inbox replicas. GCP live readiness requires the
approved 64-KiB-payload throughput, backpressure,
reconnect-ordering-degradation, broker/integration-node-loss, and
Pub/Sub-rejection gate against the pinned BifroMQ image. Offline activation
retains `live_capacity_pending`. Pub/Sub, not an MQTT session, remains the
durable cloud backbone for telemetry and command outcomes.

Internal helper functions belonging to one logical component must not be
split into new broker hops. Existing user-function extension slots bind to
approved consumer components through #113 contracts.

## 9. Multi-Cloud Bridge

Implement the exact Phase 8.8 ownership decision as one registered shared
bridge runtime per source provider and six registered directed route classes.
Each route class has separate `five-layer-baseline@2` embedded-component and
`six-layer-eventing@1` Event-Layer component bindings. The runtime mechanics
are shared; ownership, source outbox, destination broker, and cost attribution
remain profile-specific.

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
GCP→AWS, and GCP→Azure; all are capability-admissible, while live testing
remains a future live-readiness gate.

Every bridge runtime must:

- validate the destination allowlist, region-pinned SDK endpoint, normal TLS
  certificate/hostname chain, envelope, schema, route, and size;
- fail AWS-to-Azure preflight unless outbound web identity federation is
  account-enabled and `GetWebIdentityToken` uses a regional STS endpoint;
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

This section governs canonical domain-event routes only. Storage transitions
implement the separate complete-service route contract and may reuse only the
reviewed short-lived identity-exchange primitive. They have independent
payload, checkpoint, permission, failure, observability, and cost owners.

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
- `EVENTING_SCENARIO_REFERENCE_INVALID`
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

The core Twin workload section labels dashboard refreshes as aggregate
workspace load and renders separate controls for Twin entities, 3D scene
entities/assets, monthly editor/viewer seats, state materializations, and
graph/model updates. A change to one field must not mutate or infer another.
The controls are visible for both new profiles and use the exact workload-v2
units; no GCP-support or domain-event enable/disable control is rendered.

### 12.1 Wide Layout

```text
+----------------------+------------------------------------------------------+
| Configuration        | Architecture                                         |
|                      |                                                      |
| Architecture       * | Profile                                              |
|   Select profile   * | ( ) Five-layer v2 (embedded events)                  |
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
|                      | Online bundle: L3 hot + L4 + L5 | AWS/Azure/GCP      |
+----------------------+------------------------------------------------------+
| Back                       Draft saved                         Continue       |
+-----------------------------------------------------------------------------+
```

The following shared domain-event scenario is present for both
`five-layer-baseline@2` and `six-layer-eventing@1`. It contains no
enable/disable switch; profile selection changes architecture ownership, not
whether the domain-event behavior exists. Values come from the Management
projection of the immutable Phase 8.8 package and are read-only.

Domain-event scenario task:

```text
+--------------------------------------------------------------------------+
| Domain-event scenario (required)                                         |
| [ Small v1 ] [ Medium v1 selected ] [ Large v1 ]                         |
|                                                                          |
| Events / month       10,000,000      Average payload  16 KiB              |
| Peak rate            250 events/s    Retention        168 h               |
| Ordering             Per device      Delivery         At least once       |
| Active keys/devices  10,000/10,000   Max latency      10 s                |
| Retry / DLQ / replay 0.5% / 0.05% / 1%                                   |
|                                                                          |
| Derived channels, consumers, fan-out and routes             [Details v]  |
+--------------------------------------------------------------------------+
```

### 12.2 Compact Layout

```text
+------------------------------------------+
| Workload / Domain-event scenario      [v] |
+------------------------------------------+
| [Small] [Medium selected] [Large]         |
| 10,000,000 events/month | 16 KiB          |
| Peak 250/s | Retention 168 h | 10 s max   |
| Per-device | At least once                |
| Retry 0.5% | DLQ 0.05% | Replay 1%        |
| 10,000 keys | 10,000 devices              |
| Derived details                       [v] |
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
        |   `-- EventingScenarioSection [NEW]
        |       |-- SegmentedButton<String> [REUSE Material]
        |       `-- CollapsibleSection [REUSE]
        |-- OptimizerReviewTask [REUSE/MODIFY typed Eventing rows]
        `-- ConfigurationReviewTask [REUSE/MODIFY typed Eventing edges]
```

`EventingScenarioSection` is a dumb, stateless widget under
`lib/features/configuration_workspace/presentation/workload/`. It receives the
three server-returned `EventingScenarioSummary` values, the selected ID, an
enabled flag, and `ValueChanged<String> onSelected`. It uses a Material
`SegmentedButton`, existing theme/spacing tokens, and the existing
`CollapsibleSection`; it contains no numeric editor and no network call. A
missing/unknown selected ID is an inline blocking error, not a default to
Small.

### 12.4 State And Accessibility

- Wizard BLoC owns profile-dependent field visibility, validation, calculation,
  result selection, and profile-change invalidation.
- `WizardEventingScenarioSelected(id)` updates only
  `WizardState.eventingScenarioId`, clears the current calculation/selection,
  and never rewrites core fields. Profile detail supplies the three typed
  summaries; the run request submits only the selected ID.
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
This includes all three shared bridge runtimes, the six directed route classes,
and their `five-layer-baseline@2` embedded outbox/destination bindings because
the five-layer profile must support remote responsibility edges independently
of 8.9B. It also includes workload v2, all three complete L1-L5 provider
bundles, both typed visualization reads, all minimal storage-transition routes,
online-analytics co-location, and removal of the legacy shared-token and
uncontracted visualization paths from new operations.
Run two reviews, fix every finding, and create the clean 8.9A commit before
opening the 8.9B branch. Historical `five-layer-baseline@1` golden evidence
must remain unchanged.

### 8.9B Commit Boundary: `six-layer-eventing@1`

Starting from the reviewed 8.9A commit, add only the independent Eventing
responsibility, approved Event-Layer bundles, and the Event-Layer profile
bindings to the already implemented shared bridge runtimes. Run the same
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
add the shared Eventing scenario selector/read-only details, data-driven
graph/review, profile
invalidation, demo parity, accessibility, and all-platform gates.

### Slice G: Cross-Stack Offline Release Gate

Must prove all-AWS, all-Azure, and provider-hosted all-GCP for each new profile,
plus at least one complete mixed whole path assigning Eventing to each of AWS,
Azure, and GCP, from workload through Optimizer, Management, Manifest v4,
Deployer graph, package, permissions, and Terraform mock plan. The gate also
proves historical `@1` all-GCP rejection, every unequal L3-hot/L4/L5 online
bundle rejection, both query edges, baseline v2, and historical v1/v3
compatibility.

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
- all-AWS, all-Azure, and provider-hosted all-GCP for both new profiles;
- at least one complete whole path assigning Eventing to each of AWS, Azure,
  and GCP;
- historical `@1` all-GCP remains rejected;
- every unequal L3-hot/L4/L5 online-analytics placement rejects before cost;
- `raw_history_query.v1` and `twin_context_query.v1` resolve independently for
  AWS, Azure, and GCP;
- all six directed event bridges, six storage identity directions, and twelve
  directed storage stage routes resolve;
- mandatory capability, ordering, pricing, region, permission, formula, and
  specification rejection;
- exact provider chunk/tier/capacity/retention/transfer boundaries;
- workload-v2 storage volumes use `H`, `C-H`, and `A-C`, while the source
  grace, minimum-duration charges, lifecycle operations, transfers, and
  cross-cloud egress are independently priced;
- exact `core-*-v2` workload fields, scenario values, and storage-batch
  capacity calculations;
- every field in the exact retired-field set is rejected by name for both new
  profiles, while the valid workload-v2 plus approved Eventing-scenario
  reference succeeds;
- shared domain-event paths execute for both new profiles;
- no `five-layer-baseline@2`/`six-layer-eventing@1` cross-ranking;
- historical `five-layer-baseline@1` golden cost/graph remains unchanged;
- deterministic tie-break and trace.

### Management

- migration from baseline-only database;
- profile selection/change preview and exact shared/layer-specific field
  invalidation;
- workload-v2 persistence separates Twin/scene entities, aggregate dashboard
  traffic, seats, semantic update rates, and aggregate scene bytes, and rejects
  every field in the exact retired-field set from the service-bundle closure;
  the test assertion names every field so additions cannot silently bypass the
  gate;
- Eventing run/spec/resolution atomic persistence;
- generic assignment/edge API projections;
- selected-run readiness and invalidation;
- ownership, redaction, audit, OpenAPI, and demo fixtures;
- no provider-specific Eventing column or client-authored architecture field.

### Deployer, Security, And Terraform

- every approved/rejected binding;
- exact envelope behavior across provider adapters;
- duplicate, retry, DLQ, replay, redrive, ordering, and bridge failure;
- scheduled finite storage jobs, deterministic window/object manifests, all
  six destination identity routes, partial objects, duplicate reruns, checksum
  conflict, and resume;
- absence of storage-specific CDC, outbox, broker, permanent worker, DLQ, and
  checkpoint-database resources;
- exact one-ID GCP custom-plugin allowlist, digest-pinned image artifact,
  disabled development/plugin-admin modes, and rejection of any additional
  unsigned plugin;
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
- Twin entities, scene assets, aggregate dashboard load, seats, and
  state/graph rates remain independent and no legacy flag control renders;
- wide/compact layout at 720/960/1200 boundaries;
- 200% text, long labels, keyboard, semantics, light/dark;
- data-driven graph and evidence;
- demo/live parity;
- real Management integration without direct Optimizer/Deployer calls.

Extend `run_frontend_integration_tests()` in `thesis.sh` so the resolved host
device also runs `integration_test/eventing_profile_workflow_test.dart`. The
existing architecture profile test remains in the same credential-free real
Management integration gate.

Focused scenario-selector assertions are mandatory:

| # | Type | Assertion |
|---|---|---|
| 1 | Happy/integration | Selecting Medium sends only `eventing-medium-v1`; the real Management run returns the matching scenario digest and exact canonical summary |
| 2 | Happy/integration | Switching between the two new profiles retains the same supported scenario ID and produces profile-specific ownership without changing scenario values |
| 3 | Unhappy/widget | Missing or unknown selected ID renders one blocking inline error and disables Continue; it never defaults to Small |
| 4 | Unhappy/integration | A stale/unknown scenario or decision digest returns the stable Management error, creates no Optimizer run, and exposes no raw response |
| 5 | Edge/BLoC | Changing the scenario clears the selected calculation and deployment readiness exactly once while leaving all core fields unchanged |
| 6 | Edge/BLoC | Profile-change preview preserves a scenario supported by both new profiles and invalidates it when moving to historical `@1` |
| 7 | Edge/widget | Compact width and 200% text show all three scenario labels and read-only units without overlap; semantics identify selected state |
| 8 | Edge/widget | While profile detail is loading, the selector is disabled and no stale scenario summary is rendered |
| 9 | Edge/integration | Demo and live Management adapters expose the same three IDs, values, units, and ordering |
| 10 | Edge/API | Every retired or inline Eventing field is rejected by name while the valid scenario-reference request succeeds |

### Regression

- complete safe Optimizer, Management, Deployer, Flutter suites;
- historical `five-layer-baseline@1` golden cost and graph remain unchanged;
- `five-layer-baseline@2` uses the intentional workload-v2/RDS-v2/Manifest-v4
  representation;
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
      accepts any field from the exact retired-field set.
- [ ] RDS v2 and Manifest v4 represent generic components and remain
      cross-project drift-gated.
- [ ] Historical RDS v1/Manifest v2 and v3 behavior remains read/destroy
      compatible without enabling new operations.
- [ ] Eventing workload, pricing, formulas, units, tiers, transfer, and
      deployment dimensions are exact and traceable.
- [ ] Each new-profile run stores one approved Eventing scenario ID, digest,
      and canonical snapshot; callers cannot submit inline Eventing values.
- [ ] Functional completeness precedes cost for every provider and mixed path.
- [ ] Baseline and Eventing candidates never share one optimization ranking.
- [ ] L3 hot, L4, and L5 resolve as one of three reviewed online analytics
      bundles, and every unequal placement fails before pricing.
- [ ] `raw_history_query.v1` and `twin_context_query.v1` remain separate,
      implemented, observable, and priced for all three providers.
- [ ] Azure uses ADX plus ADT without an unneeded Cosmos hot-store duplicate.
- [ ] GCP uses BigQuery plus a bounded Firestore Twin API without Spanner Graph
      or a default dedicated Grafana node pool.
- [ ] Storage transitions use finite scheduled jobs and deterministic manifests
      without unproven CDC/outbox/broker/permanent-worker infrastructure.
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
      selection, Eventing scenario-reference submission and server resolution,
      resolved review, invalidation, and safe failure states without mocked
      HTTP.
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
