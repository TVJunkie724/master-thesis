---
title: "Phase 8 Complete Service-Bundle And Boundary Closure"
description: "Corrective implementation plan that closes complete-provider service, identity, capacity, and workload semantics before new profile activation."
tags: [architecture, services, multicloud, identity, capacity, optimizer, deployer, phase-8]
lastUpdated: "2026-07-20"
version: "1.0"
---

<!-- SOURCES:
- docs/research/phase_08_service_bundle_evaluation.md
- Phase 8.0-8.10 plans and handoff
- Phase 8.8 immutable Eventing decision package
- Current Optimizer, Management, Deployer, Terraform, and Flutter behavior
- User-approved functionality-first PoC selection and mandatory single-cloud/multicloud scenario coverage
EXTRACTED: 2026-07-20 | VERSION: 1.0
-->

# Phase 8 Complete Service-Bundle And Boundary Closure

## 0. Authority And Status

| Field | Value |
|---|---|
| Scope | Cross-cutting corrective gate for Phases 8.4-8.10 |
| Planning branch | `codex/phase-8-service-bundle-closure` |
| Decision evidence | [`phase_08_service_bundle_evaluation.md`](../../research/phase_08_service_bundle_evaluation.md) |
| Historical profile | `five-layer-baseline@1`, immutable read/verify/destroy only |
| New profiles | `five-layer-baseline@2`, then `six-layer-eventing@1` |
| Local environment | OrbStack; no live cloud execution |
| Cost rule | Record complete cost, but do not optimize service admissibility around cost |
| LaTeX | Excluded without separate approval |
| Review status | Two zero-finding plan reviews complete; implementation awaits explicit user approval |

Where an older Phase 8 plan conflicts with this corrective gate, this document
controls new-profile implementation. Historical artifacts, digests, and
completion evidence remain unchanged and are annotated rather than rewritten.

The approved `phase-08-eventing-implementation@1` manifest remains immutable.
It is not widened to pretend that it already contains complete Twin services.
Before runtime implementation, this closure produces a separate immutable
`phase-08-complete-service-bundles@1` decision package. Phase 8.9 consumes both
digests and rejects either package when they disagree about a shared component,
route, identity primitive, provider version, or file owner. The lifecycle
terminology mapping below is an explicit versioned compatibility rule, not an
ignored conflict.

### Activation Vocabulary

Within Phase 8, **profile activation** means that a version is exposed by the
Management API for new selection and may be calculated, resolved, packaged,
and used by the implemented deployment path. Verification in this phase is
repository-controlled and no-apply. Activation does not mean that a real
cloud deployment, provider quota, workload-dependent capacity, or
production-readiness gate has been verified.

Those external claims use the separate terms **live readiness** and
**live-capacity verification**. They remain `live_capacity_pending` until a
supervised, separately approved cloud run supplies the required evidence.
No live cloud apply, deploy, or destroy is authorized by this plan.

The immutable Eventing package predates this vocabulary and stores
`live_gate: required_before_profile_activation`. Its bytes and digest remain
unchanged. The complete-service compatibility table maps that one exact legacy
value to `required_before_live_readiness`; it does not block offline activation
once implementation and no-apply gates pass. Any other unknown or
contradictory gate value fails closed. This mapping is pinned and tested by the
complete-service decision package rather than applied ad hoc by a runtime.

## 1. Problem Statement

The existing Phase 8 chain cannot yet activate an architecture-aware profile:

1. the Optimizer models L4-to-L5 while the current Deployer connects Grafana
   directly to a provider-local L3 hot-reader endpoint;
2. the current cross-cloud Terraform exposes public Function endpoints and
   protects them with one long-lived shared token although profile contracts
   claim workload identity;
3. Phase 8.8 proves asynchronous domain-event bridges, not cross-provider
   storage movement or L4-to-L5 query bindings;
4. current workload inputs conflate Twin entity count with 3D scene entities
   and leave dashboard load semantics ambiguous;
5. the earlier plan rejects all-GCP solely because no managed GCP L4/L5
   equivalent was selected, although the project permits explicit
   provider-hosted bundles;
6. Phase 8.6 currently appears responsible for profile activation even though
   its scope excludes the service/cost decisions required to make the graph
   truthful.

Finishing a graph compiler does not make an unresolved or unsafe graph
deployable. The compiler may be completed and committed dark, but no profile
is promoted until this plan's complete bundle gates pass.

## 2. Outcome

Implement and activate:

```text
five-layer-baseline@2
  five scientific responsibilities
  + mandatory embedded domain-event behavior
  + complete AWS, Azure, and provider-hosted GCP bundles
  + all six asynchronous event routes
  + all six storage-transition routes
  + co-located provider-native/provider-hosted L4/L5 bundles

six-layer-eventing@1
  the same domain behavior
  + independent Eventing and Messaging responsibility
  + the already approved Event-Layer bundles
```

The user selects a profile and workload. The platform resolves only reviewed
closed-world provider assignments. The user never chooses internal bridge
functions, brokers, datasource plugins, identity-exchange mechanics, or
Terraform resource names.

## 3. Fixed Service Bundles

### 3.1 Shared L1-L3 And Domain-Event Bundles

Use the exact approved Phase 8.8 embedded and Event-Layer selections. Add no
substitute service during implementation.

| Provider | Embedded `five-layer-baseline@2` | Independent Event Layer |
|---|---|---|
| AWS | IoT Core, Lambda, Step Functions Standard, IoT Commands, SQS FIFO, CloudWatch; Kinesis and SNS FIFO only where remote edges require them | Kinesis, SNS FIFO, SQS FIFO, S3 failure destination, Lambda, CloudWatch |
| Azure | IoT Hub, Functions Flex Consumption, Logic Apps Consumption, Service Bus Standard, Azure Monitor; Event Hubs Standard/Dedicated only where remote telemetry requires it | Event Hubs Standard for Small/Medium and Dedicated for Large, Service Bus Standard, Functions Flex Consumption, Azure Monitor |
| GCP | Pub/Sub, Cloud Run, Workflows, GKE Standard, BifroMQ `4.0.0-incubating`, Cloud Load Balancing, Cloud Logging | Pub/Sub, Cloud Run services/worker pools, Cloud Logging |

L3 remains:

| Provider | Hot | Cool | Archive |
|---|---|---|---|
| AWS | DynamoDB on-demand | S3 Standard-IA | S3 Glacier Deep Archive |
| Azure | Cosmos DB NoSQL dynamic autoscale | Blob Cool | Blob Archive |
| GCP | Firestore native mode | Cloud Storage Nearline | Cloud Storage Archive |

### 3.2 L4/L5 Bundles

| Provider | Selected L4 | Selected L5 | Required supporting components |
|---|---|---|---|
| AWS | IoT TwinMaker | Amazon Managed Grafana 12 | External time-series connector Lambda, workspace/entity/scene assets, TwinMaker Grafana plugin `1.3.1`, workspace IAM/service accounts |
| Azure | Azure Digital Twins plus Azure Data Explorer | Azure Managed Grafana Standard X1/X2 on Grafana 12; 3D Scenes viewer when required | Event Hubs/ADX data connection, ADT data history for graph changes, direct time-series ingestion, managed identity, Blob scene assets |
| GCP | Cloud Run Twin API/materializer plus Spanner Graph Enterprise and BigQuery | Grafana OSS 12 on GKE | BigQuery datasource `3.2.0` using `Google Metadata Server` mode, platform Twin/scene backend plugin, Workload Identity for GKE, Cloud Storage assets, dedicated node pool/ingress/configuration |

The GCP bundle is an explicit provider-hosted implementation, not a claim that
Google offers a managed Digital Twin or managed Grafana service.

### 3.3 L4/L5 Placement Constraint

For v1 of both new profiles:

```text
provider(L4) == provider(L5)
```

The resolver emits `PROFILE_L4_L5_BUNDLE_COLOCATION_REQUIRED` before pricing
for every unequal assignment. Positive fixtures cover AWS/AWS, Azure/Azure,
and GCP/GCP. Negative fixtures cover all six directed unequal pairs.

### 3.4 Storage-Transition Bundles

Storage transitions use separate platform-event resources. These are
supporting L3 resources, not canonical domain events and not an independent
Eventing responsibility.

| Source provider | Hot-to-cool capture and durable outbox | Batching mover | Cross-provider cool-to-archive mover |
|---|---|---|---|
| AWS | DynamoDB Streams -> Lambda capture with retry/failure destination -> dedicated Kinesis Data Stream | ECS service on Fargate | EventBridge Scheduler -> ECS task on Fargate |
| Azure | Cosmos DB Change Feed Processor in Azure Container Apps with lease container -> dedicated Event Hubs stream | Separate Azure Container Apps app | Scheduled Azure Container Apps Job |
| GCP | Firestore direct Eventarc event -> Cloud Run capture -> dedicated Pub/Sub topic/subscription/dead-letter topic | GKE Standard deployment with Workload Identity | Cloud Scheduler -> Cloud Run Job |

The batching mover emits `telemetry-batch.v1` as gzip NDJSON when either
64 MiB uncompressed or five minutes is reached. Every record preserves its
canonical event ID; object metadata records the schema, route, window, record
count, and SHA-256 checksum. Destination writes are idempotent, and readers
deduplicate by event ID because every source transport is at-least-once.

Same-provider cool-to-archive uses S3 Lifecycle to Glacier Deep Archive, Azure
Blob lifecycle management to Archive on an archive-compatible storage account,
or Cloud Storage Object Lifecycle Management to Archive. A cross-provider
scheduled mover reads the source cool bucket/container with pagination, writes
the destination archive data plane, records its checkpoint in DynamoDB,
Cosmos DB, or Firestore according to source provider, and only then allows
source expiry.

## 4. Boundary And Identity Contracts

### 4.0 Event Taxonomy

The implementation manifest classifies every event-like component as exactly
one of:

- L1 device protocol traffic;
- L1/L2 raw telemetry backbone;
- canonical domain events;
- L3 storage CDC/outbox/schedule events;
- L4 semantic materialization/data-history events;
- provider observability/audit events;
- application-control-plane operation updates.

Only canonical domain-event ownership moves into the independent Eventing
responsibility in `six-layer-eventing@1`. Storage CDC, ADX data-history Event
Hubs, schedulers, lifecycle rules, observability, and Management SSE remain
with their functional owners in both profiles. L4-to-L5 is a synchronous query
contract, not an event bridge. A component without one taxonomy owner fails
validation; a component counted in two responsibility costs also fails.

### 4.1 Asynchronous Domain Events

Reuse `phase-08-cross-cloud-bridge@1` exactly:

- source-owned durable outbox;
- source-provider runtime;
- canonical envelope validation;
- short-lived workload identity;
- destination broker data-plane publish;
- source acknowledgement only after destination durable acceptance;
- all six directed provider pairs;
- no bridge for same-provider edges.

The Eventing decision is sufficient for graph edges whose payload is one of the
approved canonical domain events, including remote persistence and Twin-update
consumers. It is not a generic proof for every cross-cloud operation.

### 4.2 Storage Movement

Add `storage-transition-route.v1` and six directed route classes for each
transition stage. The concrete capture, outbox, worker, scheduler, and
checkpoint services are fixed by Section 3.4:

```text
hot source change stream
  -> source-owned batching mover
  -> destination cool object-store data plane
  -> durable write/checksum acceptance
  -> idempotent checkpoint

cool source inventory/schedule
  -> source-owned batching mover
  -> destination archive object-store data plane
  -> durable write/checksum acceptance
  -> idempotent checkpoint
  -> source expiry according to retention contract
```

Same-provider cool-to-archive uses native lifecycle. Same-provider hot-to-cool
uses the selected source capture/outbox plus batching mover. Cross-provider
routes reuse the approved six workload-identity exchange primitives but have
their own least-privilege object-store permissions:

| Direction | Source runtime credential exchange | Destination data-plane operation |
|---|---|---|
| AWS -> Azure | Account-enabled regional AWS STS `GetWebIdentityToken` -> AWS-signed OIDC JWT -> Microsoft Entra federated identity credential | Azure Blob block upload to the landing/Cool tier, followed by the declared Archive transition where applicable |
| AWS -> GCP | AWS role signs the GCP Workload Identity Federation AWS-provider subject token -> GCP STS validates `GetCallerIdentity` and mapped role attributes | Cloud Storage resumable upload to Nearline/Archive |
| Azure -> AWS | User-assigned managed identity obtains an Entra OIDC token for the dedicated AWS audience -> AWS `AssumeRoleWithWebIdentity` | S3 multipart/`PutObject` to Standard-IA/Glacier Deep Archive landing |
| Azure -> GCP | User-assigned managed identity obtains an Entra OIDC token for the GCP provider audience -> GCP Workload Identity Federation OIDC exchange | Cloud Storage resumable upload to Nearline/Archive |
| GCP -> AWS | Google service-account OIDC ID token for the dedicated AWS audience -> AWS `AssumeRoleWithWebIdentity` | S3 multipart/`PutObject` to Standard-IA/Glacier Deep Archive landing |
| GCP -> Azure | Google service-account OIDC ID token with the Azure token-exchange audience -> Microsoft Entra federated identity credential | Azure Blob block upload to the landing/Cool tier, followed by the declared Archive transition where applicable |

These are the exact six identity primitives frozen in the immutable Phase 8.8
`bridge-decision.json`; the storage package reuses their issuer, audience,
subject, expiry, and account/tenant trust rules but grants separate
object-store permissions. In particular, AWS-to-Azure fails preflight when
AWS outbound web identity federation is disabled or a global rather than
regional STS endpoint is selected.

The archive class/tier is selected on the destination object or by a
destination-local lifecycle rule after durable landing. No route writes
directly to an archive tier that cannot accept new objects through its normal
data-plane contract.

Required tests cover partial batches, duplicate delivery, checksum mismatch,
destination outage, source retry, checkpoint loss, redrive, retention, cleanup,
and transfer-cost ownership.

### 4.3 L4 Materialization

Add `twin-materialization-policy.v1`:

- all raw telemetry remains accessible through the L4 query contract;
- raw telemetry is stored in the provider time-series backend;
- model, relationship, scene binding, and explicit materialized-state changes
  update the semantic graph;
- no bundle performs one managed graph mutation for every raw message;
- event IDs provide idempotency;
- stale/out-of-order state changes follow one declared per-device policy;
- every provider exposes the same logical current-state/history query fields.

### 4.4 L4-To-L5

Add `twin-visualization-query.v1` with:

- typed query and scene contracts;
- bounded request and query timeout;
- idempotent read retries only;
- correlation and safe error codes;
- data-source and panel version;
- short-lived/provider-workload identity;
- output bindings from L4 to L5;
- query/scene capacity dimensions;
- dashboard/scene provisioning and cleanup.

Public anonymous endpoints, shared bearer tokens, Grafana API keys on Grafana
12, and direct L3 hot-reader datasources fail preflight.

### 4.5 Legacy Shared Token

`INTER_CLOUD_TOKEN`, `authorization_type = "NONE"` Function URLs, and
`X-Inter-Cloud-Token` are forbidden in all new-profile manifests, packages,
Terraform plans, runtime configuration, and evidence. Historical `@1` records
remain readable and destroyable without being migrated or reactivated.

## 5. Workload Contract V2

Add separate fields:

```text
twinEntityCount
sceneEntityCount
averageSceneAssetSizeMiB
aggregateDashboardRefreshesPerHour
apiCallsPerAggregateDashboardRefresh
dashboardActiveHoursPerDay
monthlyEditorSeats
monthlyViewerSeats
twinStateMaterializationsPerSecond
twinGraphUpdatesPerSecond
```

Remove from new-profile inputs:

```text
useEventChecking
triggerNotificationWorkflow
returnFeedbackToDevice
allowGcpSelfHostedL4
allowGcpSelfHostedL5
```

The first three are always-present profile behavior. GCP L4/L5 availability is
a provider-profile fact, not a user feature flag.

Freeze `core-small-v2`, `core-medium-v2`, and `core-large-v2` exactly as
specified by the research evaluation. Preserve the Phase 8.8 Eventing
scenarios unchanged and pair scenario sizes only in Phase 8.10.

Freeze the synthetic semantic-update bounds separately from raw telemetry:

| Field | Small | Medium | Large |
|---|---:|---:|---:|
| `twinStateMaterializationsPerSecond` | 0.1 | 2.5 | 50 |
| `twinGraphUpdatesPerSecond` | 0.01 | 0.1 | 1 |

State materialization updates current operational state. Graph updates change
models, entities, relationships, or scene bindings. Neither field is inferred
from every raw telemetry record.

Migration rules:

- historical requests preserve all legacy fields verbatim;
- a new-profile request rejects legacy flags;
- `entityCount` maps only to `sceneEntityCount` for historical display;
- no migration invents `twinEntityCount`;
- new profile selection requires an explicit v2 workload or a named reviewed
  preset.

## 6. Capacity And Deployment Dimensions

Every resolved component records exact scenario-derived capacity rather than
one display tier:

| Bundle | Small | Medium | Large |
|---|---|---|---|
| AWS TwinMaker | 100 entities, external telemetry, 0.0033 query/s | 4,000 entities, external telemetry, 0.1667 query/s | 30,000 entities, external telemetry, 3.3333 query/s |
| AWS Grafana | Grafana 12, workspace/service accounts | Same | Same; 400 monthly seats remain below the 500 concurrent quota but are not claimed as observed concurrency |
| Azure ADX | `Standard_E8ads_v5`, capacity 2, streaming eligible | `Standard_E8ads_v5`, capacity 2, queued ingestion | `Standard_E8ads_v5`, capacity 4, queued ingestion |
| Azure Grafana | Standard X1, Grafana 12 | Standard X1, Grafana 12 | Standard X2, Grafana 12 |
| GCP Spanner Graph | Enterprise regional SSD, 1 node | Enterprise regional SSD, 1 node | Enterprise regional SSD, 2 nodes |
| GCP Grafana | Grafana 12 on dedicated GKE node pool | Scaled replicas/node pool | Scaled replicas/node pool plus 3D panel |
| Storage outbox/mover | AWS 1 Kinesis shard + 1 Fargate task; Azure Event Hubs Standard 1 TU + 1 Container Apps replica; GCP Pub/Sub + 1 GKE replica | Same initial units; five-minute batch flush | AWS 8 Kinesis shards + 3 Fargate tasks; Azure Event Hubs Standard 8 TUs/auto-inflate max 16 + 3 Container Apps replicas; GCP Pub/Sub + 3 GKE replicas |

The Large core stream is 5,000 records/s and approximately 3.91 MiB/s before
transport overhead. Eight Kinesis shards and eight Event Hubs TUs therefore
avoid treating their per-shard/per-TU record and byte ceilings as a perfect
no-headroom fit. Pub/Sub's regional defaults are higher, but the GKE consumer
still needs explicit replica, acknowledgement, backlog, and egress tests.
At the 64-MiB batch threshold, the Large mover emits about one object every
16.4 seconds (roughly 5,273/day); Small and Medium reach the five-minute flush
first. These are deterministic planning inputs, not observed throughput.

The exact Kinesis/Event Hubs/Pub/Sub/BifroMQ capacities remain pinned by Phase
8.8. Database RU, partition, BigQuery connection/throughput, Cloud Run
instance/concurrency, GKE replica/node, transition batch, retry, and storage
dimensions must be emitted into RDS v2 and priced.

Published quotas establish theoretical admissibility. Workload-dependent ADX,
Spanner, database partitioning, plugin, bridge, and scene behavior remains
`live_capacity_pending`; it may not be relabeled verified by an offline test.

## 6.1 Immutable Decision Package

Before any Phase 8.9 runtime file changes, create:

```text
docs/research/evidence/phase_08_service_bundles/
  decision.json
  common-functional-contract.json
  complete-provider-bundles.json
  boundary-route-matrix.json
  workload-scenarios.json
  capacity-matrix.json
  pricing-ownership-matrix.json
  source-ledger.json
  implementation-component-manifest.json
  README.md
  schemas/
    <one Draft 2020-12 schema per JSON artifact>

scripts/phase_08_service_bundles/
  validate_decision_package.py
  calculate_capacity.py
  verify_sources.py
  tests/
```

`implementation-component-manifest.json` pins every new logical/deployment
component, service/software version, image digest, license, Terraform
resource/module, runtime/package/plugin, port, output/input, permission,
formula, capacity dimension, file target, and test owner. Version-dependent
software such as Grafana OSS, the GCP backend/panel plugin toolchain, Helm
charts, provider plugins, and Azure 3D viewer dependencies must have exact
versions and content digests here; this plan deliberately does not invent a
future patch version before the source refresh.

The validator rejects:

- unresolved or duplicate ownership;
- a component already owned incompatibly by the immutable Eventing manifest;
- missing provider/region/version/license/capacity/cost data;
- a shared identity primitive with different issuer/audience/subject rules;
- a scenario or provider bundle absent from the decision;
- a selected service with `unsupported` or `unverified` mandatory capability;
- a historical `@1` digest change;
- any secret-like or physical cloud identifier.

Decision status is `approved` only after source refresh, deterministic
capacity calculation, schema/reference validation, and two zero-finding
reviews. Phase 8.9 preflight consumes the two immutable package digests.

## 7. Optimizer Changes

The Optimizer must:

1. load only the complete new-profile provider bundles;
2. enforce mandatory functionality before pricing;
3. treat L4/L5 as one provider bundle selection;
4. derive all event and storage routes from component assignments;
5. select no bridge for same-provider edges;
6. include every source mover, destination landing, identity, transfer,
   time-series, graph, Grafana, 3D, compute, fixed-capacity, observability, and
   cleanup cost exactly once;
7. calculate AWS, Azure, and GCP single-cloud candidates;
8. calculate all otherwise admissible mixed candidates;
9. reject incomplete evidence and capacity dimensions;
10. keep `@2` and six-layer candidates in separate runs;
11. retain `@1` only in the historical reproduction path.

No candidate is complete merely because every seven-slot provider price exists.

## 8. Management And Flutter Changes

Management:

- does not auto-select `five-layer-baseline@1` for a newly created Twin;
- retains migrated `@1` selections as historical records;
- exposes no active selectable profile until a new profile is fully activated;
- persists workload v2 and generic component/edge/capacity evidence;
- atomically switches the default new-Twin profile to `@2` only at activation;
- returns stable unsupported/retired/activation-pending reason codes.

Flutter Phase 8.7:

- implements the profile workflow against typed Management APIs while the
  backend may return the required no-active-profile state;
- does not advertise "`AWS | Azure | Mixed supported`" generically;
- displays AWS/Azure/GCP provider-bundle availability and the L4/L5
  co-location constraint from DTOs;
- labels dashboard refreshes as aggregate workspace load;
- separates Twin entity count from 3D scene entity count;
- shows `@1` only on historical Twins/runs, never as a new selection;
- exposes `@2` and six-layer only after server activation.

## 9. Deployer And Terraform Changes

Add exact catalog components, ports, outputs, permissions, packages, and static
Terraform for:

- AWS TwinMaker connector, Grafana 12 datasource/service account, and scene
  assets;
- Azure ADT, Event Hubs/ADX ingestion, ADX/ADT query permissions, Managed
  Grafana 12 datasource/identity, and 3D scene assets;
- GCP Cloud Run Twin API/materializer, Spanner Graph, BigQuery, GKE Grafana,
  plugins, Workload Identity, scene assets, networking, backup, and cleanup;
- same-provider and six directed storage-transition routes;
- every new pricing and capacity dimension.

Graph resolution must prove:

```text
logical edge
  -> catalog edge implementation
  -> source output
  -> optional trust/route component
  -> destination input
  -> exact Terraform resource/output reference
```

No post-deploy name reconstruction, mutable datasource discovery, public
ingestion endpoint, or secret injection is permitted.

## 10. Phase Corrections

### 8.0-8.3

Keep inventories, historical decisions, contracts, digests, and dark catalogs
unchanged. Add an explicit supersession note: their `@1` implementation
mappings are historical/read-only and do not prove new-profile service
admissibility.

### 8.4

Preserve migration 022 and existing historical selections. Correct new-Twin
default behavior during 8.9A activation; do not rewrite old records.

### 8.5

Keep the generic resolver and default-off output. It remains non-activatable
until complete provider bundles and routes are present.

### 8.6

Complete Manifest v3/graph compiler/preflight as a dark generic foundation.
Do not promote `five-layer-baseline@1` or claim the current L4-to-L5/shared
token runtime is fixed. Record the compiler commit separately.

### 8.7

Implement typed Flutter workflow and the no-active-profile/historical-profile
states. Activation remains server-driven by 8.9A.

### 8.8

Preserve the approved Eventing evidence package. Clarify that its capacity and
bridge proof cover the domain-event scope only. This closure owns complete
Twin services, storage movement, workload v2, and L4/L5.

### 8.9A

Implement workload v2, RDS v2/Manifest v4, complete AWS/Azure/GCP bundles,
storage routes, corrected identity, and `five-layer-baseline@2`. Activate
`@2` for offline selection, calculation, resolution, and packaging only after
all offline gates; supervised live-readiness and live-capacity gates remain
honestly pending in evidence.

### 8.9B

Add the independent Eventing responsibility using the unchanged approved
Phase 8.8 bundle/bridge decisions. Do not duplicate core storage or L4/L5
resources.

### 8.10

Evaluate three single-cloud paths, admissible mixed paths, all explicit
rejections, both scenario families, provider-hosted GCP costs, and the fair
`@2` versus six-layer delta. Report live-capacity uncertainty as a threat to
validity.

## 11. Implementation Order And Clean Commit Boundaries

1. Commit this reviewed planning/evaluation closure.
2. Build, review, and commit the immutable complete-service decision package.
3. Return to the Phase 8.6 implementation worktree; finish the generic
   compiler dark, review twice, and commit one clean 8.6 boundary.
4. Create `codex/phase-8-profile-foundation` from the complete-service
   decision-package commit and cherry-pick the clean Phase 8.6 compiler commit.
   Resolve overlap by preserving this corrective plan and the implemented dark
   compiler, rerun both review suites, and commit no unrelated change.
5. Create `codex/phase-8-flutter-profile-workflow` from the reviewed integrated
   foundation; implement/review/commit 8.7.
6. Create `codex/phase-8-five-layer-baseline-v2` from reviewed 8.7; the
   planning and both immutable decision packages are already ancestors.
   Implement/review/commit the complete 8.9A boundary.
7. Create `codex/phase-8-six-layer-eventing` from reviewed 8.9A;
   implement/review/commit 8.9B.
8. Create `codex/phase-8-evaluation-package` from reviewed 8.9B; generate and
   review 8.10.

Each step uses understandable intermediate commits. A later branch never
starts from an unreviewed dirty boundary.

## 12. Verification

### Contract And Evidence

- schema/version/additional-field/duplicate/reference/digest tests;
- all profile/provider/catalog/RDS/Manifest generated-copy drift gates;
- historical `@1` byte-stability and read/destroy fixtures;
- three positive L4/L5 bundles and six co-location rejection fixtures;
- complete source/formula/unit/capacity refs.

### Identity And Security

- all six event and all six storage identity exchanges;
- no shared token, cloud key, public Function ingestion URL, API key, payload,
  endpoint, physical resource name, or raw provider error in artifacts;
- exact issuer/audience/subject/expiry and least-privilege destination roles;
- source acknowledgement only after durable destination acceptance.

### Capacity

- both Small/Medium/Large scenario families;
- AWS TwinMaker/Grafana quotas;
- Azure ADT/ADX/Grafana/3D limits and ingestion mode;
- GCP Spanner/BigQuery/Cloud Run/GKE/Grafana/plugin limits;
- hot database partitioning, storage batching, backpressure, retry, and DLQ;
- `live_capacity_pending` remains visible until supervised execution.

### Cross-Stack

- Optimizer complete-path and rejection traces;
- Management atomic persistence/ownership/redaction;
- Deployer graph/package/permission/Terraform validate and no-apply mock plan;
- Flutter unit/widget/visual/accessibility and real-Management integration;
- Web, macOS, Windows, Linux, docs strict, link, secret, and compatibility
  gates;
- no live cloud resource, paid operation, apply, deploy, or destroy.

Use OrbStack and existing project commands. Record services running before a
test and stop only services started by that invocation.

## 13. Failure Codes

Add:

```text
PROFILE_HISTORICAL_READ_ONLY
PROFILE_NO_ACTIVE_VERSION
PROFILE_COMPLETE_BUNDLE_MISSING
PROFILE_L4_L5_BUNDLE_COLOCATION_REQUIRED
PROFILE_WORKLOAD_V2_REQUIRED
PROFILE_TWIN_ENTITY_COUNT_MISSING
PROFILE_CAPACITY_EVIDENCE_INCOMPLETE
STORAGE_TRANSITION_ROUTE_UNSUPPORTED
STORAGE_TRANSITION_IDENTITY_INVALID
TWIN_MATERIALIZATION_POLICY_INVALID
TWIN_VISUALIZATION_BINDING_INVALID
TWIN_VISUALIZATION_IDENTITY_INVALID
LEGACY_SHARED_TOKEN_FORBIDDEN
LIVE_CAPACITY_GATE_PENDING
```

Errors expose only safe logical IDs, profile/version, scenario, stable reason,
and correlation ID.

## 14. Rollout And Rollback

Rollout is dark-first:

1. ship readers/contracts/catalogs;
2. run all offline gates;
3. activate `@2` atomically;
4. later activate six-layer atomically.

Rollback retires the affected new profile from new selection and operations.
It never falls back to `@1`, rewrites an existing selection, changes a frozen
resolution, or discards destroy support.

## 15. Definition Of Done

- [ ] The complete service evaluation is source-backed and versioned.
- [ ] Cost is recorded but never used as the service-admissibility objective.
- [ ] `@1` is immutable historical/read/verify/destroy only.
- [ ] `@2` and six-layer share the mandatory domain-event behavior without
      feature flags.
- [ ] AWS, Azure, and provider-hosted GCP have complete L1-L5 bundles.
- [ ] Three single-cloud paths and admissible mixed paths are represented.
- [ ] L4/L5 co-location is enforced and all six unequal pairs fail clearly.
- [ ] Event bridges and storage movers have separate exact contracts.
- [ ] All six directed event and storage identity paths use short-lived
      workload identity.
- [ ] New profiles contain no public Function ingestion endpoint or shared
      inter-cloud token.
- [ ] Raw telemetry, semantic graph state, and 3D scene state have distinct
      storage/update semantics.
- [ ] Twin entities, scene entities, dashboard traffic, and seat counts are
      separate workload dimensions.
- [ ] Both scenario families pass theoretical Small/Medium/Large capacity or
      receive an explicit unsupported result.
- [ ] Workload-dependent live gates remain visible and block any live-capacity
      claim.
- [ ] Every supporting component has one deployment, permission, cost,
      observability, failure, cleanup, and verification owner.
- [ ] Phase 8.6 remains dark; 8.7 is server-driven; activation occurs in 8.9A
      and 8.9B only.
- [ ] Optimizer, Management, Deployer, Terraform, Flutter, research, and
      product-documentation responsibilities are exact.
- [ ] Historical compatibility, security, capacity, cross-stack, platform,
      documentation, and no-live-cloud gates pass.
- [ ] Two independent reviews find zero unresolved findings.
- [ ] The planning boundary is committed cleanly before implementation.
