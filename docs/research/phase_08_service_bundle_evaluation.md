---
title: "Phase 8 Complete Twin Service-Bundle Evaluation"
description: "PoC-focused functional, compatibility, identity, and capacity evaluation for five-layer-baseline@2 and six-layer-eventing@1."
tags: [architecture, digital-twin, eventing, multicloud, services, capacity, phase-8]
lastUpdated: "2026-07-21"
version: "1.2"
---

<!-- SOURCES:
- Current Phase 8 plans and versioned architecture/Eventing evidence
- Current Optimizer workload presets and calculation semantics
- Current Deployer Terraform/provider/runtime implementation
- Primary AWS, Microsoft Azure, Google Cloud, and Grafana documentation linked below
- User-approved functionality-first PoC rule and Small/Medium/Large evaluation
EXTRACTED: 2026-07-21 | VERSION: 1.2
-->

# Phase 8 Complete Twin Service-Bundle Evaluation

## Evaluation Question

Select one implementable service bundle per provider for two functionally
aligned architecture profiles:

- `five-layer-baseline@2`: five scientific responsibilities with mandatory
  domain-event behavior embedded in their owners;
- `six-layer-eventing@1`: the same L1-L5 behavior and workloads, with the same
  domain-event contract owned by an independent Eventing responsibility.

The proof of concept is not a cost-minimization exercise. A service is selected
when it closes the required function and has a credible theoretical
Small/Medium/Large capacity path. Its complete cost still enters the Optimizer
so the evaluation can expose structural cost differences.

The design deliberately excludes production-only machinery without a measured
need. High availability, CDC, extra brokers, outboxes, dedicated node pools,
and operational control planes are not added merely because they could be
useful in a production system.

## Decision Summary

The evaluated region set is fixed, not optimized: AWS `eu-central-1`, Azure
`westeurope`, and GCP `europe-west1`. It is identical to the immutable Eventing
scenarios. All regional components owned by a provider stay in that region;
only declared remote edges incur cross-cloud transfer. The later immutable
complete-service package must prove availability and pricing of every selected
member in its fixed region and fail closed rather than substitute a region.

### Common L1-L5 Service Matrix

| Layer | AWS | Azure | GCP |
|---|---|---|---|
| L1 acquisition | IoT Core and IoT Commands | IoT Hub | BifroMQ `4.0.0-incubating` on GKE Standard, load balancer, ordered MQTT-to-Pub/Sub adapter |
| L2 processing | Lambda and Step Functions Standard | Functions Flex Consumption and Logic Apps Consumption | Cloud Run and Workflows |
| L3 hot/raw history | DynamoDB on-demand with a window-shard GSI | Azure Data Explorer with `stored_at` | BigQuery partitioned on `stored_at` and clustered by device ID |
| L3 cool | S3 Standard-IA | Blob Cool | Cloud Storage Nearline |
| L3 archive | S3 Glacier Deep Archive | Blob Archive | Cloud Storage Archive |
| L4 semantic Twin | IoT TwinMaker Standard pricing plan with Lambda external-data connector | Azure Digital Twins | Cloud Run Twin API/materializer with Firestore Native |
| L5 visualization | Amazon Managed Grafana 12 with TwinMaker plugin/scene viewer | Azure Managed Grafana 12 with ADX datasource plus ADT context; 3D Scenes viewer when needed | One Grafana OSS 12 pod on GKE with Persistent Disk PVC, paid BigQuery Marketplace datasource, and minimal Twin API/scene panel |

The selected GCP bundle is provider-hosted. It does not claim that Google
offers a managed Digital Twin equivalent to TwinMaker or ADT. The implementation
and cost model therefore include the Twin API, Firestore schema/indexes,
Grafana deployment, plugin/panel, images, identity, logging, upgrades, and
cleanup.

TwinMaker Standard is selected for Small, Medium, and Large because the Basic
plan does not provide the required knowledge graph. Tiered bundles add a
commitment/selection variable without adding PoC functionality, so they are
not candidates. Standard-plan entities, data-access calls, queries, connector,
scenes, and Grafana are all priced.

### Profile Lifecycle

| Profile | Role | Lifecycle |
|---|---|---|
| `five-layer-baseline@1` | Historical paper-compatible reference | Immutable; read, reproduce, verify, and destroy only |
| `five-layer-baseline@2` | New five-responsibility control with mandatory embedded events | Implement first; offline activation only after complete-service gates |
| `six-layer-eventing@1` | Treatment profile with an independent Event Layer | Branch from reviewed `@2`; activate only after its own gates |

No implementation silently repairs `@1`. Its current public
Function/shared-token boundary and L3/Grafana mismatch remain historical debt,
not a target implementation.

## Why The Online Analytics Bundle Is Co-Located

The corrected common contract exposes two distinct visualization dependencies:

```text
L3 hot -> L5: raw telemetry and historical aggregates
L4     -> L5: Twin model, current state, relationships, and scenes
```

Direct L3 visualization is therefore not an architectural error. The error in
the predecessor was that the Optimizer modeled only L4-to-L5 while the Deployer
bound Grafana to L3 without a corresponding contract or cost edge.

For v1, both profiles enforce:

```text
provider(L3_hot) == provider(L4) == provider(L5)
```

This yields three reviewed online bundles. It avoids claiming twelve unproven
cross-provider datasource paths: six directed L3-to-L5 combinations and six
directed L4-to-L5 combinations. Managed Grafana plugin installation,
short-lived cross-cloud authentication, query semantics, and 3D assets differ
by provider; treating all pairings as interchangeable would be a separate
integration study.

The restriction does not turn the profiles into single-cloud architectures.
L1, L2, L3 cool, L3 archive, and the Six-layer Eventing responsibility remain
independently assignable. Three complete single-cloud cases and all otherwise
admissible mixed cases remain in Phase 8.10.

The provider-local query identities are part of each bundle: Amazon Managed
Grafana uses a workspace role for TwinMaker/S3; Azure Managed Grafana uses its
managed identity with ADX Viewer and Azure Digital Twins Data Reader; GKE
Grafana uses Workload Identity for GKE with dataset-scoped BigQuery Data
Viewer, project-scoped BigQuery Job User, a custom role containing only
`resourcemanager.projects.get`, and exact Cloud Run Invoker. Connector and
Twin API runtimes use separate least-privilege identities. No cloud key or
anonymous query endpoint is selected.

The Azure identity composition remains an explicit live gate. Microsoft
documents Managed Grafana managed-identity access to ADX and separately states
that the ADX ADT-query plugin uses the caller's Entra token. The plan infers
that the workspace identity can be that caller, but activation requires one
supervised ADX query that reaches ADT with the workspace identity. A failure
rejects/reopens the bundle rather than introducing an interactive user token
or static client secret.

Azure 3D Scenes is a separate, intentionally user-scoped path rather than an
ADT-query fallback. If `needs3DModel=true`, the private scene container uses
the documented Studio CORS allowlist and viewer users/groups receive Azure
Digital Twins Data Reader plus container-scoped Storage Blob Data Reader.
Scene editing is not a PoC requirement, so no Blob Contributor/Owner role is
granted. Preview status and interactive Entra sign-in remain visible
limitations.

For GCP, the BigQuery and Cloud Resource Manager APIs are enabled. The plugin
uses authentication type `gce`; the Grafana pod is constrained to a Standard
GKE node with the GKE metadata server enabled. Google documents compatibility
for existing Compute Engine metadata-server clients through Workload Identity
Federation for GKE, while Grafana documents metadata authentication and the
project-read permission. The composed path is nevertheless verified with
plugin `Save & test` and one bounded query before live readiness. Offline
activation keeps the bundle `live_capacity_pending`; a failed supervised query
reopens the bundle rather than allowing a JSON service-account key.

## Provider Evaluation

### AWS

The selected AWS path is the smallest change from the existing target:

```text
IoT Core -> Lambda/Step Functions -> DynamoDB
                                  -> S3 Standard-IA -> Glacier Deep Archive

DynamoDB -- TwinMaker Lambda connector --+
TwinMaker entity/component/scene APIs ----+-> Managed Grafana
```

TwinMaker explicitly supports Lambda data connectors for external stores such
as DynamoDB. The TwinMaker Grafana plugin supplies a datasource and scene
viewer. Raw data stays in L3; the connector does not imply one TwinMaker graph
write per telemetry message.

Selected supporting components are the connector Lambda, TwinMaker workspace
and entities, S3 scene assets, Grafana workspace, plugin, datasource, IAM role,
and Grafana 12 service-account automation. A separate AWS raw-query gateway or
second Grafana datasource is not required.

### Azure

The earlier bundle used both Cosmos DB and ADX for online data. That duplicated
storage for the PoC without a functional requirement. The corrected bundle is:

```text
IoT Hub -> ADX raw time-series tables -> Managed Grafana
             + ADT query context

selected state/model changes -> ADT -> 3D Scenes/current Twin context
```

ADX is the L3 hot time-series store and Grafana datasource. ADT owns the L4
current graph and state. The ADX Azure Digital Twins query plugin can combine
Twin context with time series. Optional 3D Scenes reads the ADT model and scene
assets. Cosmos DB is not selected.

ADT data history through a dedicated Event Hub is not enabled by default.
The common contract requires raw telemetry history and current Twin context,
not a complete historical log of every graph mutation. If graph-history
analysis becomes a research requirement, it is added as a versioned optional
capability with its Event Hub and ADX tables priced explicitly.

This separation also answers why Azure still uses both Event Hubs and Service
Bus in the independent Event Layer: ADX is the L3 database; Event Hubs is the
retained high-volume Event-Layer stream; Service Bus is the ordered control,
action, notification, and command queue. They serve different contracts.

### GCP

GCP has two different event-facing services because they close different
boundaries:

```text
device <-> BifroMQ on GKE <-> ordered adapter <-> Pub/Sub
                                                |
                                                +-> Cloud Run/Workflows
                                                +-> BigQuery raw history

selected state/model changes -> Cloud Run Twin API -> Firestore

Grafana on GKE -> BigQuery datasource
               -> Twin API/scene datasource-panel
```

BifroMQ is the MQTT device boundary. Pub/Sub is the durable cloud backbone; it
does not expose a general MQTT device interface. The pair is shared by Five-
layer v2 and Six-layer v1 whenever GCP owns L1, so BifroMQ is not a Six-layer
addition.

BigQuery is selected for L3 hot because it supports streaming writes and the
official Grafana datasource. Firestore is selected for L4 because the PoC
query set is bounded to Twin/model lookup, current state, direct relationships,
scene bindings, and idempotent materialization. Documents and indexed
relationship collections are sufficient for 30,000 Twin entities and one-hop
queries.

The frozen document model uses `models/{model_id}`, `twins/{twin_id}`,
`twins/{twin_id}/sources/{source_id}`, `relationships/{relationship_id}`, and
`scene_bindings/{twin_id}`. Only `(from_id, type)` and `(to_id, type)` composite
relationship indexes are required. Per-source state stores the last accepted
event ID/sequence and updates transactionally, avoiding an unbounded global
idempotency collection.

Scene behavior is conditional and bounded across providers. With
`needs3DModel=false`, no scene resource is created. When true, the PoC requires
GLB assets, stable node-to-Twin bindings, and current-value overlays, not a
scene editor. For GCP, the authenticated browser calls a Grafana
backend-plugin resource route; that backend invokes the Cloud Run Twin API
under the Grafana workload identity, and the Twin API streams the exact Cloud
Storage asset using its own identity. No public bucket, signed URL, or separate
gateway is selected. The 100-MiB Large asset and overlay refresh remain live
latency/memory gates.

Spanner Graph is rejected. It would add an Enterprise database and graph
capacity model for graph algorithms and traversal requirements the PoC does
not have. The decision must be reopened if arbitrary multi-hop traversal or
graph analytics becomes mandatory.

Grafana runs on the BifroMQ GKE cluster when that cluster already exists.
Otherwise the GCP online bundle creates one GKE Standard cluster. Grafana and
BifroMQ remain separate deployments/namespaces. Grafana uses one pod with
scenario-derived CPU/RAM and a ReadWriteOnce Persistent Disk PVC for its
minimal SQLite state; dashboards/datasources are provisioned declaratively. A
dedicated Grafana node pool, shared database, or multi-replica HA setup is not
selected by default.

Cluster reuse does not make Grafana compute free. The bundle adds one
incremental general-workload node to an existing BifroMQ cluster, or creates a
one-node zonal cluster when no GCP L1 cluster exists. The initial allocation is
`e2-standard-4` for Small/Medium and `e2-standard-8` for Large; both the node
and Persistent Disk are priced.

The BigQuery datasource uses `Google Metadata Server` authentication backed by
Workload Identity for GKE. The plugin's separately named Workload Identity
Federation mode is Grafana-Cloud-only and is not selected. No service-account
JSON key is generated. Version `3.2.0` is a paid Marketplace plugin; its
entitlement/license is frozen and priced as a fixed GCP L5 component instead of
being hidden behind the open-source Grafana runtime. The signed self-hosted
artifact and entitlement are mandatory activation evidence. If they are not
obtainable, the all-GCP target fails closed and the datasource decision must be
reopened; no unsigned or unlicensed BigQuery-plugin binary is accepted.

The platform-owned Twin API/scene app plugin is different from that commercial
datasource. Grafana does not load unsigned plugins by default. For this PoC,
the reviewed custom artifact has the fixed ID
`twin2multicloud-twin-app`, is copied into the content-addressed Grafana image,
and is the only ID in `allow_loading_unsigned_plugins`. Development mode,
general unsigned loading, runtime download, and UI plugin installation are
disabled; a modified signed plugin is not accepted. This is a visible
provider-hosted GCP risk and live-readiness gate, not a claim equivalent to a
managed vendor plugin. A later version may replace the exact exception with a
private signature.

## Event Inventory And Profile Ownership

The analysis covers every planned event-like mechanism but does not call every
mechanism the scientific Event Layer:

| Event class | Purpose | Five-layer v2 | Six-layer v1 |
|---|---|---|---|
| Device traffic | Telemetry and bidirectional commands | L1 | L1 |
| Raw telemetry backbone | Delivery into processing and L3 hot | L1/L2 | L1/L2 |
| Canonical domain events | Rules, actions, workflows, notifications, commands, outcomes, persistence, Twin updates | Embedded in existing owners | Independent Eventing responsibility |
| Storage schedule/manifest | Finite hot/cool/archive batch movement | L3 | L3 |
| Twin materialization | Selected current-state/model/relationship changes | L4 | L4 |
| Provider logs/audit | Metrics and bounded failures | Component owner | Component owner |
| Management SSE | Optimizer/deployer operation progress | Application control plane | Application control plane |

Both new profiles always include the domain behavior. The legacy flags
`useEventChecking`, `triggerNotificationWorkflow`, and
`returnFeedbackToDevice` are invalid for their requests. A rule may evaluate
to no action at runtime, but the architectural capability is never removed.

The immutable Phase 8.8 bundle decision remains unchanged:

| Scope | AWS | Azure | GCP |
|---|---|---|---|
| Embedded Five-layer v2 | IoT Core, Lambda, Step Functions Standard, IoT Commands, SQS FIFO, CloudWatch; Kinesis/SNS FIFO for reviewed remote edges | IoT Hub, Functions Flex, Logic Apps, Service Bus Standard, Azure Monitor; Event Hubs for reviewed remote telemetry edges | Pub/Sub, Cloud Run, Workflows, BifroMQ/GKE, load balancer, Cloud Logging |
| Independent Six-layer | Kinesis, SNS FIFO, SQS FIFO, S3 failure destination, Lambda, CloudWatch | Event Hubs Standard/Dedicated, Service Bus Standard, Functions Flex, Azure Monitor | Pub/Sub, Cloud Run services/worker pools, Cloud Logging |

The table lists the service family composition. Topology-conditional bridge
resources are created only for remote edges. A same-provider event path stays
inside the local bundle and has no bridge or cross-cloud identity exchange.

Service-family reuse does not merge architecture ownership. For all-GCP Six
Layer, the L1 MQTT/Pub/Sub device backbone and the independent Event Layer use
separate Pub/Sub topics, subscriptions, permissions, retention, component IDs,
and operation-cost records; they reuse project/API enablement and one L1
BifroMQ/GKE boundary. BifroMQ is not duplicated into the Event Layer. The same
principle applies when AWS or Azure is both producer and consumer: local
broker/trigger bindings replace the bridge, while logical component and cost
ownership remains explicit.

## Domain-Event Cross-Cloud Compatibility

The approved bridge remains:

```text
source durable outbox/broker
  -> source-provider runtime
  -> short-lived destination identity
  -> destination broker data-plane publish
  -> durable acceptance
  -> source acknowledgement
```

It supports AWS→Azure, AWS→GCP, Azure→AWS, Azure→GCP, GCP→AWS, and
GCP→Azure. Source runtimes consume Kinesis/SNS-SQS, Event Hubs/Service Bus, or
Pub/Sub and publish through the destination service SDK. A provider may be
sender on one resolved edge and receiver on another. The bridge is not a
public destination Function and never uses one shared token.

The Eventing package is immutable because this complete-service correction
does not change its domain-event semantics, selected service bundles, capacity
allocations, or route identities.

## Minimal Storage Transition Design

Storage transitions move immutable telemetry batches, not canonical domain
events. The selected implementation is one portable container image with
provider source and object-store adapters:

| Source | Scheduled finite runtime | Hot source |
|---|---|---|
| AWS | EventBridge Scheduler starts an ECS/Fargate task; ECR stores the image | DynamoDB bounded time-window query |
| Azure | Scheduled Container Apps Job; ACR Basic stores the image | ADX bounded time-window query/export |
| GCP | Cloud Scheduler starts a Cloud Run Job; Artifact Registry stores the image | BigQuery bounded partition query/export |

One content-addressed registry support component is reused by all selected
container images in a provider deployment and priced once. A provider with no
selected platform-owned container receives no registry. It is supporting
deployment infrastructure, not another scientific responsibility.

For both new profiles, the three existing duration inputs are cumulative data
age boundaries measured from provider-assigned `stored_at`: hot `[0,H)`, cool
`[H,C)`, archive `[C,A)`, then expiry. Historical `@1` retains its frozen
calculation and non-strict validation; workload v2 requires
`1 <= H < C < A`. It therefore prices steady-state bytes as monthly ingest
times `H`, `C-H`, and `A-C`, rather than pricing three overlapping complete
histories.

For hot-to-cool, the L3 writer assigns a `stored_at` ingestion timestamp while
preserving the device `event_time`. It assigns the record to a deterministic
five-minute batch. Once that batch reaches age `H`, the job partitions it
deterministically and writes gzip NDJSON objects of at most
64 MiB uncompressed. Object names contain route, window, and partition. Object
metadata contains schema, count, event-ID range, and SHA-256 checksum. Reruns
use provider conditional-create operations, write the immutable window
manifest last, and are idempotent: an identical object succeeds; a different
checksum for the same key fails visibly. A late device event receives a later
`stored_at` value and enters a later batch without rewriting a closed object.

The source query is not an unbounded scan. AWS derives a `stored_at`
window-shard GSI count from the scenario and prices its writes/storage/reads;
ADX filters its typed `stored_at` column; BigQuery prunes its `stored_at`
partition. Device ID remains the operational ordering/lookup dimension.

At age `C`, same-provider cool-to-archive uses the provider's native lifecycle
rule, configured as `C-H` after cool-object creation. For a different archive
provider, the same finite source-provider job copies only manifest-complete,
immutable cool objects conditionally to the destination object API.
Destination lifecycle performs a required landing-to-archive transition and
expires the data at age `A` (`A-H` after same-provider cool-object creation or
`A-C` after remote archive-object creation).

These object-age offsets are exact only when the preceding export is on time.
A retry that succeeds within 24 hours shifts physical lifecycle/cleanup by the
same bounded delay. Logical query eligibility remains based on `stored_at` and
ends at `C`/`A`; manifests record scheduled/actual timestamps and the delayed
cleanup as a degraded transition. Native lifecycle is not represented as if it
could backdate object creation.

The deliberately bounded PoC recovery policy is a 24-hour retry horizon and a
48-hour source-expiry grace. Hot-store retention and remote cool-source expiry
include that grace, and the overlap is priced. A still-incomplete window at 24
hours becomes a visible `storage_transition_failed` live-readiness failure; no
CDC service or conditional-retention database is added speculatively.

This design deliberately has no storage-specific DynamoDB Streams/Lambda/
Kinesis path, Cosmos Change Feed/Event Hubs path, Firestore Eventarc/Pub/Sub
path, permanent worker, broker, DLQ, or checkpoint database. Deterministic
window/object IDs and manifests are the checkpoint. CDC/outbox infrastructure
is a rejected escalation unless a load or failure test proves the scheduled
design insufficient.

Cross-provider jobs reuse the six reviewed short-lived identity-exchange
patterns but receive independent object-store permissions. They do not reuse
Eventing component IDs, payloads, acknowledgements, or pricing ownership.

## Scenario Semantics

Phase 8 retains two scenario families and pairs them by size only for the final
comparison.

### Core Twin Scenarios

| Field | Small | Medium | Large |
|---|---:|---:|---:|
| Devices | 100 | 4,000 | 30,000 |
| Telemetry interval | 120 s | 30 s | 6 s |
| Average payload | 0.25 KiB | 0.5 KiB | 0.8 KiB |
| Average telemetry rate | 0.833/s | 133.333/s | 5,000/s |
| Messages/month | 2,160,000 | 345,600,000 | 12,960,000,000 |
| Hot boundary `H` | 1 month | 1 month | 1 month |
| Cool boundary `C` | 3 months | 3 months | 3 months |
| Archive/expiry boundary `A` | 12 months | 12 months | 12 months |
| Twin entities | 100 | 4,000 | 30,000 |
| 3D scene entities | 0 | 0 | 1,200 |
| Total 3D scene asset size | 0 MiB | 0 MiB | 100 MiB |
| Aggregate dashboard refreshes/hour | 12 | 60 | 120 |
| API calls/aggregate refresh | 1 | 10 | 100 |
| Dashboard active hours/day | 1 | 4 | 8 |
| Aggregate active-window query rate | 0.0033/s | 0.1667/s | 3.3333/s |
| Monthly editor/viewer seats | 2/0 | 25/10 | 100/300 |
| Twin-state materializations/s | 0.1 | 2.5 | 50 |
| Twin graph/model updates/s | 0.01 | 0.1 | 1 |

Dashboard refreshes are workspace-wide, not per seat. Twin entities and scene
entities remain separate. The 1,200 Large scene entities are node/Twin
bindings inside the 100-MiB aggregate GLB asset set, not 1,200 separate
100-MiB files. State materializations and graph/model updates are synthetic
capacity inputs; they are not inferred from every raw message.

### Domain-Event Scenarios

| Scenario | Events/month | Peak events/s | Payload | Active keys/devices |
|---|---:|---:|---:|---:|
| `eventing-small-v1` | 100,000 | 10 | 4 KiB | 100 |
| `eventing-medium-v1` | 10,000,000 | 250 | 16 KiB | 10,000 |
| `eventing-large-v1` | 100,000,000 | 2,500 | 64 KiB | 100,000 |

The Phase 8.8 inputs and results remain byte-stable. Phase 8.10 reports both
the core and domain-event dimensions rather than silently treating device,
partition-key, and Twin counts as equal.

For new-profile runtime requests, the user selects one required
`eventingScenarioId` from these three rows. Management resolves and
digest-checks the canonical `eventing-workload.v1` object; neither Flutter nor
the caller submits an editable copy. This is intentional PoC scope: that
immutable schema marks each row as a bounded synthetic scenario. A future
custom Eventing workload requires a new runtime-contract version instead of
mislabeling edited values as frozen evidence. Both profiles always receive the
same selected Eventing snapshot.

## Theoretical Capacity Evaluation

### AWS

- The 5,000-record/s core peak is below DynamoDB's default table-level
  on-demand throughput ceiling when the reviewed item size and device/time
  partitioning avoid hot keys.
- TwinMaker's 50,000-entity default workspace quota covers the 30,000-entity
  Large graph. Raw values stay external, so 5,000/s is not a TwinMaker graph
  write rate.
- The aggregate L5 query peak is 3.3333/s. Connector query shape, pagination,
  and hot partitions remain workload-dependent live gates.
- Managed Grafana seat admission and measured concurrency are recorded
  separately.
- Event capacity remains governed by the immutable Phase 8.8 allocation.

Decision: theoretically admissible for all three sizes; live connector,
partition, bridge, and failure behavior remains pending.

### Azure

- ADX is initialized with `Standard_E8ads_v5` capacity 2 for Small/Medium and
  capacity 4 for Large. Queued ingestion is used where the scenario exceeds
  the documented streaming-ingestion guidance.
- ADT's published Twin and query limits cover 30,000 entities and 3.3333
  aggregate queries/s. Only 50 current-state materializations/s and one
  graph/model update/s reach the semantic store in Large.
- Managed Grafana uses Standard X1 for Small/Medium and X2 for Large.
- The optional 100-MiB Large scene asset remains within the reviewed 3D Scenes
  guidance, but preview/product behavior remains a visible risk.
- Event capacity remains governed by Phase 8.8 Event Hubs/Service Bus evidence.

Decision: theoretically admissible for all sizes with ADX query/ingestion and
3D behavior pending supervised evidence.

### GCP

- BifroMQ, Pub/Sub, Cloud Run event workers, and bridge capacity remain exactly
  as frozen by Phase 8.8.
- BigQuery Storage Write API committed/default streams make acknowledged data
  queryable with the selected at-least-once/idempotency contract.
- Firestore receives at most the synthetic 50 state materializations/s plus one
  graph/model update/s in Large, not all 5,000 raw messages/s. Required
  composite indexes and one-hop query limits are frozen in the decision
  package.
- Grafana uses one pod on the selected/shared GKE cluster, one incremental
  `e2-standard-4` node for Small/Medium or `e2-standard-8` for Large, and the
  priced Persistent Disk PVC. An isolation-only node pool, shared database,
  and multi-replica HA are not assumed.
- Workload Identity for GKE supplies short-lived metadata credentials to both
  BigQuery and the Twin API path.

Decision: theoretically admissible after the bounded Twin API and Grafana
plugin/panel are implemented; live BifroMQ, BigQuery, Firestore, GKE, and
failure behavior remains pending.

### Storage Jobs

Large core traffic is exactly 4,000 KiB/s (3.90625 MiB/s), or 1,200,000 KiB
(1,171.875 MiB, approximately 1.145 GiB) per five-minute batch before
transport overhead. The initial plan uses one task/batch for
Small, one for Medium, and three deterministic source partitions for Large,
with at most 512 MiB input per task. A 64-MiB uncompressed object target yields
approximately nineteen Large objects per window.

The calculation is reproducible, but source-query speed, compression,
cross-cloud latency, and recovery time are live gates. A failure re-runs the
same finite batch within the frozen 24-hour retry horizon; it does not justify
a permanent pipeline in advance. Cost includes non-overlapping hot/cool/
archive residence, the 48-hour source grace, provider minimum-duration
charges, lifecycle requests, stage transfer, and remote egress.

## Single-Cloud And Multicloud Result Space

Both profiles must evaluate:

- all AWS, all Azure, and all GCP;
- every admissible L1/L2/online-bundle/cool/archive assignment;
- for Six-layer, every admissible independent Event provider assignment;
- all six directed domain-event bridges when a resolved event edge is remote;
- all six directed hot-to-cool routes and all six directed cool-to-archive
  routes, sharing six trust directions;
- same-provider no-bridge/no-cross-cloud-copy behavior while retaining the
  local hot export job and native cool-to-archive lifecycle;
- every rejected online-analytics split with a stable reason.

The online bundle reduces the factorial space but does not predetermine a
provider as sender or receiver. Direction remains a property of each resolved
edge.

## Rejected Alternatives

| Alternative | Decision reason |
|---|---|
| Keep public Function URLs and `INTER_CLOUD_TOKEN` | Static shared secret and mismatch with the workload-identity contract |
| Treat Eventing proof as storage/query proof | Different payloads, APIs, permissions, acknowledgement, capacity, and cost |
| Remove L3-to-L5 and force all telemetry through L4 | Hides raw-data ownership, overloads the semantic store, and contradicts provider visualization capabilities |
| Allow L3/L4/L5 independent providers in v1 | Requires twelve unproven managed-Grafana datasource/authentication paths and changes the experiment |
| Keep Cosmos DB beside ADX | Duplicates Azure online telemetry storage without a selected functional need |
| Keep Spanner Graph for GCP | Adds Enterprise graph infrastructure without a multi-hop graph requirement |
| Give GCP Grafana a dedicated node pool by default | Adds capacity before a test demonstrates isolation is necessary |
| Use Grafana JSON/Infinity as a universal cross-cloud adapter | No single reviewed secretless automation path across the selected managed/self-hosted Grafana environments |
| Use Grafana BigQuery `workloadIdentityFederation` mode on GKE | That named mode is Grafana-Cloud-only; self-hosted GKE uses metadata-server authentication |
| Enable Grafana development mode or generally allow unsigned plugins | Broader code-loading authority is unnecessary; the PoC permits only the digest-pinned `twin2multicloud-twin-app` ID |
| Implement storage with CDC, dedicated outboxes/brokers, and permanent workers | Production-scale complexity without a PoC requirement or failing test |
| Use ADT data history for every raw message | Couples raw telemetry rate to semantic graph/history machinery |
| Reuse `entityCount`/`average3DModelSizeInMB` beside v2 Twin/scene fields | Creates two conflicting capacity and cost sources; legacy fields remain historical-only |
| Reuse legacy dashboard, seat, Eventing, or error-handling inputs beside workload v2 and the selected Eventing scenario | Creates duplicate request-rate and capacity sources; new profiles reject the retired inputs while historical `@1` remains reproducible |
| Let callers edit the immutable `eventing-workload.v1` evidence object inline | Its schema identifies bounded S/M/L synthetic scenarios; v1 accepts only a server-resolved scenario reference and reserves custom workloads for a new contract version |

## Offline Activation And Live-Readiness Gates

No new profile activates offline until all of the following pass:

1. immutable complete-provider bundle, workload, route, and component manifests;
2. exact Eventing scenario reference/digest resolution plus formulas and
   ownership for every selected service;
3. both visualization edges for all three online bundles;
4. all six domain-event routes, six storage trust directions, and twelve
   storage stage routes;
5. same-provider route elision;
6. minimal storage duplicate/failure/recovery tests;
7. Small/Medium/Large deterministic calculations for both scenario families;
8. OrbStack-backed cross-stack and Terraform no-apply/mock-plan gates;
9. historical/Eventing digest-stability, docs, links, and secret scans;
10. two new zero-finding reviews.

An offline-activated profile is not live-ready. Provider quota approval, real
identity exchange, workload-specific throughput, plugin behavior, and cloud
cleanup require separately approved supervised evidence.

## Primary Source Ledger

### AWS

- [AWS IoT TwinMaker data connectors](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/data-connector-interface.html)
- [TwinMaker time-series connector flow](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/time-series-data-connectors.html)
- [TwinMaker Grafana integration](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/grafana-integration.html)
- [AWS IoT TwinMaker quotas](https://docs.aws.amazon.com/general/latest/gr/iot-twinmaker.html)
- [AWS IoT TwinMaker pricing plans](https://aws.amazon.com/iot-twinmaker/pricing/)
- [DynamoDB on-demand capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)
- [EventBridge Scheduler for ECS tasks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/tasks-scheduled-eventbridge-scheduler.html)
- [S3 lifecycle management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [AWS outbound identity federation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_outbound.html)
- [AWS `AssumeRoleWithWebIdentity`](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_request.html)

### Azure

- [ADX ingestion from IoT Hub](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-iot-hub-overview)
- [Azure Digital Twins service limits](https://learn.microsoft.com/en-us/azure/digital-twins/reference-service-limits)
- [Azure Digital Twins query plugin for ADX](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-data-explorer-plugin)
- [Visualize ADX data with Grafana](https://learn.microsoft.com/en-us/azure/data-explorer/grafana)
- [Managed Grafana data sources and managed identity](https://learn.microsoft.com/en-us/azure/managed-grafana/how-to-data-source-plugins-managed-identity)
- [Azure Digital Twins 3D Scenes Studio](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-3d-scenes-studio)
- [Azure Container Apps jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
- [Azure Blob lifecycle management](https://learn.microsoft.com/en-us/azure/storage/blobs/lifecycle-management-policy-configure)
- [Microsoft Entra workload identity federation](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust)
- [Azure Event Hubs quotas and limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits#azure-event-hubs-limits)

### GCP And Grafana

- [Firestore document data model](https://cloud.google.com/firestore/native/docs/data-model)
- [BigQuery Storage Write API](https://cloud.google.com/bigquery/docs/write-api-streaming)
- [Workload Identity Federation for GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity)
- [Scheduled Cloud Run jobs](https://cloud.google.com/run/docs/execute/jobs-on-schedule)
- [Cloud Storage lifecycle management](https://cloud.google.com/storage/docs/lifecycle)
- [External workload identities](https://cloud.google.com/iam/docs/workload-identities)
- [Grafana BigQuery datasource configuration](https://grafana.com/docs/plugins/grafana-bigquery-datasource/latest/configure/)
- [Grafana plugin signatures](https://grafana.com/docs/grafana/latest/administration/plugin-management/plugin-sign/)
- [Grafana `allow_loading_unsigned_plugins` configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#allow_loading_unsigned_plugins)

The immutable Phase 8.8 source ledger remains the authority for Kinesis,
SNS/SQS, Event Hubs, Service Bus, Pub/Sub, Cloud Run worker pools, BifroMQ, and
all six domain-event bridge directions. Primary documentation proves published
capabilities and limits; it does not replace implementation or live testing.
