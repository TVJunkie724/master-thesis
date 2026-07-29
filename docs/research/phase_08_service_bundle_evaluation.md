---
title: "Phase 8 Five-Layer v2 Service-Bundle Evaluation"
description: "PoC-focused functional, placement, identity, and capacity evaluation for five-layer-baseline@2."
tags: [architecture, digital-twin, eventing, multicloud, services, capacity, phase-8]
lastUpdated: "2026-07-29"
version: "1.4"
---

<!-- SOURCES:
- Current Phase 8 plans and versioned architecture/Eventing evidence
- Current Optimizer workload presets and calculation semantics
- Current Deployer Terraform/provider/runtime implementation
- Primary AWS, Microsoft Azure, Google Cloud, and Grafana documentation linked below
- User-approved functionality-first PoC rule, L3-hot/L5 placement experiment,
  Azure Cosmos DB continuity, and Small/Medium/Large evaluation
EXTRACTED: 2026-07-29 | VERSION: 1.4
-->

# Phase 8 Five-Layer v2 Service-Bundle Evaluation

## Evaluation Question

Select one implementable service bundle per provider for
`five-layer-baseline@2`: five scientific responsibilities with mandatory
domain-event behavior embedded in their owners.

The current decision deliberately stops before selecting or implementing
`six-layer-eventing@1`. When that profile is resumed, it must inherit the
reviewed Five-layer v2 L1-L5 services, workload, and placement rules unchanged
and receive a separate service/ownership review for its independent Eventing
responsibility.

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
| L3 hot/raw history | DynamoDB on-demand with a window-shard GSI | Cosmos DB for NoSQL with `/device_id`, bounded time queries, and scenario-selected serverless/autoscale capacity | BigQuery partitioned on `stored_at` and clustered by device ID |
| L3 cool | S3 Standard-IA | Blob Cool | Cloud Storage Nearline |
| L3 archive | S3 Glacier Deep Archive | Blob Archive | Cloud Storage Archive |
| L4 semantic Twin | IoT TwinMaker Standard pricing plan | Azure Digital Twins | Cloud Run Twin API/materializer with Firestore Native |
| L5 visualization | Amazon Managed Grafana 12 with a provider-local typed raw-history reader datasource | Azure Managed Grafana 12 with the supported JSON API datasource and a provider-local Cosmos reader | One Grafana OSS 12 pod on GKE with Persistent Disk PVC and signed BigQuery datasource `3.2.0` |

The selected GCP bundle is provider-hosted. It does not claim that Google
offers a managed Digital Twin equivalent to TwinMaker or ADT. The implementation
and cost model therefore include the Twin API, Firestore schema/indexes,
Grafana deployment, signed BigQuery plugin, image, identity, logging, upgrades, and
cleanup.

TwinMaker Standard is selected for Small, Medium, and Large because the Basic
plan does not provide the required knowledge graph. Tiered bundles add a
commitment/selection variable without adding PoC functionality, so they are
not candidates. Standard-plan entities and queries are priced. A TwinMaker
external-history connector and scene viewer are not mandatory Five-layer v2
components because L5 reads raw history from its provider-local L3 hot bundle,
not through L4.

### Profile Lifecycle

| Profile | Role | Lifecycle |
|---|---|---|
| `five-layer-baseline@1` | Historical paper-compatible reference | Immutable; read, reproduce, verify, and destroy only |
| `five-layer-baseline@2` | New five-responsibility control with mandatory embedded events | Implement first; offline activation only after complete-service gates |
| `six-layer-eventing@1` | Later treatment profile with an independent Event Layer | Deferred; no implementation or activation decision in this evaluation |

No implementation silently repairs `@1`. Its current public
Function/shared-token boundary and L3/Grafana mismatch remain historical debt,
not a target implementation.

## Why L3 Hot And L5 Are Coupled But L4 Is Independent

The Five-layer v2 execution baseline exposes one mandatory visualization
dependency and one independent Twin projection:

```text
L3 hot -> L5: raw telemetry and historical aggregates
L3 hot -> L4: selected current-state/model/relationship projections
```

Direct L3 visualization is made explicit because it is the behavior the
predecessor actually deploys for AWS and Azure. The predecessor error was not
that Grafana read L3; it was that the Optimizer priced L4-to-L5 while the
Deployer bound Grafana to L3 without a matching contract or cost edge.

Five-layer v2 enforces:

```text
provider(L3_hot) == provider(L5)
provider(L4) is independent
```

This yields nine reviewed placements: three single-cloud
`L3-hot == L4 == L5` cases and six deliberate
`L3-hot == L5 != L4` cases. The raw dashboard path remains provider-local and
therefore needs only three datasource implementations. The L4 placement
experiment is carried by the typed `twin_projection.v1` edge. A remote
projection reuses the approved short-lived six-direction domain-event bridge;
a same-provider projection uses the local broker/trigger binding and creates
no bridge.

L4-to-L5 Twin-context and 3D-scene visualization are not part of the common
Five-layer v2 baseline. Adding them would reintroduce six independent
cross-provider Grafana/Twin query integrations and would be a separate
versioned capability experiment. `five-layer-baseline@1` remains the immutable
paper-compatible reference with its historical L4-to-L5 target; v2 is
explicitly the executable predecessor-compatible comparison profile. This
deviation is reported as a construct-validity limitation, not hidden.

The provider-local query identities are part of each bundle. AWS and Azure
retain a typed read-only hot-reader API because their selected operational
NoSQL stores do not provide a suitable secretless core datasource in the
selected managed Grafana tier. Each datasource receives one generated,
deployment-scoped, read-only credential stored only in Grafana secure
datasource configuration and the provider endpoint; it is never a shared
cross-cloud token, contract value, tfvars value, log field, or repository
secret. GCP Grafana uses Workload Identity for GKE with dataset-scoped BigQuery
Data Viewer, project-scoped BigQuery Job User, and the minimum project-read
permission required by the plugin.

The local reader credential is a conscious PoC compromise. Cross-cloud
`twin_projection.v1` routes remain secretless and use the approved workload
identity exchanges. Anonymous reader endpoints, the legacy
`INTER_CLOUD_TOKEN`, one credential shared by deployments, and any
L4-to-L5 fallback are forbidden.

The selected concrete path is deliberately small: AWS uses its hot-reader
Lambda Function URL with a generated `X-Twin-Reader-Key` whose hash is stored
by Lambda; Azure uses a Functions Flex HTTP route with a deployment-scoped
Function key. The `marcusolsson-json-datasource` plugin stores those values
only as secure header data. Both endpoints accept exactly one device, metric,
bounded time range, aggregation bucket, result limit, and opaque continuation
cursor. Raw queries are capped at 24 hours, aggregates at 31 days, and every
response at 1,000 points/ten seconds. GCP needs no reader Function: its signed
BigQuery datasource uses declarative, partition-filtered query templates with
equivalent bounds. The AWS/Azure routes remain authenticated
internet-reachable PoC read boundaries; private networking is not implied.

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

DynamoDB -- typed local raw-history reader --> Managed Grafana
selected state/model projections -----------> TwinMaker
```

The typed reader preserves the current raw-dashboard responsibility and adds
bounded query, pagination, correlation, and non-anonymous authorization.
TwinMaker holds current semantic state and relationships but is not in the
mandatory Grafana query path. Selected supporting components are the reader
Lambda/API boundary, TwinMaker workspace/entities, Grafana workspace,
datasource, reader credential, IAM roles, and Grafana 12 automation. Scene
assets and the TwinMaker Grafana plugin are outside this profile version.

### Azure

The predecessor and Five-layer v2 use Cosmos DB as the Azure L3 hot store:

```text
IoT Hub -> Functions -> Cosmos DB -> typed local reader -> Managed Grafana
                         |
                         +-> selected state/model projection -> ADT
```

Cosmos DB keeps the original operational NoSQL data model, existing
writer/reader path, and comparable DynamoDB/Cosmos/BigQuery cost contrast. ADT
owns current graph/state independently. The Cosmos container uses
`/device_id`; hot-reader requests must include a bounded device/time range and
route to that partition. The index includes only the query and lifecycle
fields required by the profile.

ADX was explicitly reconsidered. Its advantages are high-volume near-real-time
time-series analytics, KQL, queued ingestion, and a native Managed Grafana
datasource with managed identity. Those advantages would matter for an
analytics-focused profile. They are not required by this baseline's bounded
raw-history dashboard and would change the storage service, query language,
ingestion path, and capacity model at the same time as the L4 placement
experiment. ADX is therefore rejected for Five-layer v2, not declared
inferior. A later analytics profile may compare Cosmos and ADX directly.

Serverless Cosmos is not claimed to sustain every scenario. Small and Medium
use serverless. Large uses autoscale provisioned throughput, with maximum
RU/s rounded to the next 1,000 above the greater of:

```text
peak writer RU/s + bounded dashboard RU/s + mover RU/s
hot logical storage GiB * Azure minimum autoscale RU/s per GiB
```

with a floor of 1,000 maximum RU/s before rounding. The immutable decision
package must calculate write/query RU from the
canonical serialized document and recorded request-charge evidence. It must
also prove each `/device_id` logical partition remains below the published
20-GB limit. If the calculated capacity or partition proof fails, Azure Large
is rejected; the implementation must not silently substitute ADX.

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
```

BifroMQ is the MQTT device boundary. Pub/Sub is the durable cloud backbone; it
does not expose a general MQTT device interface. The pair is shared by Five-
layer v2 and Six-layer v1 whenever GCP owns L1, so BifroMQ is not a Six-layer
addition.

BigQuery is selected for L3 hot because it supports streaming writes and the
official Grafana datasource. Firestore is selected for L4 because the PoC
query set is bounded to Twin/model lookup, current state, direct relationships,
and idempotent materialization. Documents and indexed relationship collections
are sufficient for 30,000 Twin entities and one-hop queries.

The frozen document model uses `models/{model_id}`, `twins/{twin_id}`,
`twins/{twin_id}/sources/{source_id}`, `relationships/{relationship_id}`, and
no scene collection. Only `(from_id, type)` and `(to_id, type)` composite
relationship indexes are required. Per-source state stores the last accepted
event ID/sequence and updates transactionally, avoiding an unbounded global
idempotency collection.

Spanner Graph is rejected. It would add an Enterprise database and graph
capacity model for graph algorithms and traversal requirements the PoC does
not have. The decision must be reopened if arbitrary multi-hop traversal or
graph analytics becomes mandatory.

Grafana runs on the BifroMQ GKE cluster when that cluster already exists.
Otherwise the GCP L3-hot/L5 bundle creates one GKE Standard cluster. Grafana and
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
JSON key is generated. Version `3.2.0` is the reviewed Grafana-maintained
release. Current Grafana documentation does not identify it as an
Enterprise-only datasource, so the plan assigns no invented plugin-license
fee. The signed self-hosted artifact, version, digest, and applicable license
notice are mandatory activation evidence. If the artifact is not obtainable,
the all-GCP target fails closed and the datasource decision must be reopened;
no unsigned or unverified BigQuery-plugin binary is accepted.

The GCP L5 path has no custom Twin/scene plugin because L4-to-L5 is outside the
profile. Grafana is exposed through one GKE `LoadBalancer` Service with TLS
terminated by Grafana, a deployment-generated certificate stored only in a
Kubernetes Secret, generated Grafana credentials, and an explicit
`loadBalancerSourceRanges` allowlist. The fixed-IP endpoint and certificate
fingerprint are returned as deployment evidence. A public unrestricted
service, plaintext HTTP, wildcard CIDR, or secret in a contract is rejected.
The self-signed certificate and CIDR-scoped researcher access are explicit PoC
limitations; a public DNS/certificate/IAP control plane is not added.

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
| Azure | Scheduled Container Apps Job; ACR Basic stores the image | Cosmos DB partition-key/time-window query/export |
| GCP | Cloud Scheduler starts a Cloud Run Job; Artifact Registry stores the image | BigQuery bounded partition query/export |

One content-addressed registry support component is reused by all selected
container images in a provider deployment and priced once. A provider with no
selected platform-owned container receives no registry. It is supporting
deployment infrastructure, not another scientific responsibility.

For Five-layer v2, the three existing duration inputs are cumulative data
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
Azure assigns the sorted deployment device IDs deterministically across finite
tasks and queries each `/device_id` partition for the exact `stored_at`
window; BigQuery prunes its `stored_at` partition. A Cosmos job task processes
at most 1,000 device partitions and at most 512 MiB of canonical source input.
The task count is the larger of the device-count and byte-size calculations,
so the Large Azure path initially uses at least 30 tasks instead of hiding a
cross-partition full scan.

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
| Aggregate dashboard refreshes/hour | 12 | 60 | 120 |
| API calls/aggregate refresh | 1 | 10 | 100 |
| Dashboard active hours/day | 1 | 4 | 8 |
| Aggregate active-window query rate | 0.0033/s | 0.1667/s | 3.3333/s |
| Monthly editor/viewer seats | 2/0 | 25/10 | 100/300 |
| Twin-state materializations/s | 0.1 | 2.5 | 50 |
| Twin graph/model updates/s | 0.01 | 0.1 | 1 |

Dashboard refreshes are workspace-wide, not per seat. State materializations
and graph/model updates are synthetic capacity inputs; they are not inferred
from every raw message. Five-layer v2 has no scene workload fields because it
does not claim L4-to-L5 or 3D visualization.

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
mislabeling edited values as frozen evidence. A later Six-layer plan must reuse
the same selected Eventing snapshot rather than define a second workload.

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

- Cosmos DB serverless covers the bounded Small and Medium write/query rates
  subject to the published per-partition serverless ceiling. Large uses
  autoscale provisioned throughput derived from measured RU/write,
  bounded-reader/mover RU, and the storage-driven autoscale minimum.
- `/device_id` distributes the 30,000-device workload. The decision package
  proves the maximum canonical bytes per device over the one-month hot window
  remain below 20 GB and rejects the scenario otherwise.
- ADT's published Twin and query limits cover 30,000 entities and 3.3333
  management queries/s. Only 50 current-state materializations/s and one
  graph/model update/s reach the semantic store in Large; dashboard queries do
  not pass through ADT.
- Managed Grafana uses Standard X1 for Small/Medium and X2 for Large.
- Event capacity remains governed by Phase 8.8 Event Hubs/Service Bus evidence.

Decision: theoretically admissible for all sizes only if the immutable Cosmos
RU/partition calculator passes. Reader latency, autoscale behavior, and the
partitioned Large export remain supervised live gates.

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
  priced Persistent Disk PVC and external load balancer. An isolation-only
  node pool, shared database, public DNS/certificate service, and multi-replica
  HA are not assumed.
- Workload Identity for GKE supplies short-lived metadata credentials to both
  BigQuery and the Twin API path.

Decision: theoretically admissible after the bounded Twin API and signed
BigQuery datasource are implemented; live BifroMQ, BigQuery, Firestore, GKE, and
failure behavior remains pending.

### Storage Jobs

Large core traffic is exactly 4,000 KiB/s (3.90625 MiB/s), or 1,200,000 KiB
(1,171.875 MiB, approximately 1.145 GiB) per five-minute batch before
transport overhead. The initial plan uses one task/batch for
Small, one for Medium, and three deterministic source partitions for Large,
with at most 512 MiB input per task. A 64-MiB uncompressed object target yields
approximately nineteen Large objects per window.

For Azure Cosmos, the additional maximum of 1,000 device partitions per task
raises the initial Large parallelism to at least 30 tasks. AWS and GCP retain
the byte-derived three-task starting point.

The calculation is reproducible, but source-query speed, compression,
cross-cloud latency, and recovery time are live gates. A failure re-runs the
same finite batch within the frozen 24-hour retry horizon; it does not justify
a permanent pipeline in advance. Cost includes non-overlapping hot/cool/
archive residence, the 48-hour source grace, provider minimum-duration
charges, lifecycle requests, stage transfer, and remote egress.

## Single-Cloud And Multicloud Result Space

Five-layer v2 must evaluate:

- all AWS, all Azure, and all GCP;
- every admissible L1/L2/L3-hot-plus-L5/L4/cool/archive assignment;
- all nine L3-hot/L4/L5 placements, including the three single-cloud and six
  `L3-hot == L5 != L4` cases;
- all six directed domain-event bridges when a resolved event edge is remote;
- all six directed hot-to-cool routes and all six directed cool-to-archive
  routes, sharing six trust directions;
- same-provider no-bridge/no-cross-cloud-copy behavior while retaining the
  local hot export job and native cool-to-archive lifecycle;
- every rejected `L3-hot != L5` split with a stable reason.

The L3-hot/L5 bundle reduces only the raw-datasource space. L4 remains an
independent sender/receiver target, so the six remote Twin-projection
directions remain observable and costed.

## Rejected Alternatives

| Alternative | Decision reason |
|---|---|
| Keep public Function URLs and `INTER_CLOUD_TOKEN` | Static shared secret and mismatch with the workload-identity contract |
| Treat Eventing proof as storage/query proof | Different payloads, APIs, permissions, acknowledgement, capacity, and cost |
| Remove L3-to-L5 and force all telemetry through L4 | Hides raw-data ownership, overloads the semantic store, and contradicts provider visualization capabilities |
| Require L3/L4/L5 co-location | Removes the deliberate L4 placement variable and hides the six cross-cloud Twin-projection routes |
| Allow L3 hot and L5 to differ | Requires six extra cross-cloud Grafana datasource/authentication paths unrelated to the selected L4 placement experiment |
| Replace Cosmos DB with ADX in Five-layer v2 | ADX is stronger for high-volume interactive time-series analytics and native managed-identity Grafana, but the baseline does not require those capabilities; replacing the implemented operational store would change a second experimental variable |
| Keep Cosmos DB serverless for Large | The published ceiling and lack of predictable throughput cannot justify the 5,000-write/s scenario; Large must use calculated autoscale or fail admission |
| Keep Spanner Graph for GCP | Adds Enterprise graph infrastructure without a multi-hop graph requirement |
| Give GCP Grafana a dedicated node pool by default | Adds capacity before a test demonstrates isolation is necessary |
| Use Grafana JSON/Infinity as a universal cross-cloud adapter | No single reviewed secretless automation path across the selected managed/self-hosted Grafana environments |
| Use Grafana BigQuery `workloadIdentityFederation` mode on GKE | That named mode is Grafana-Cloud-only; self-hosted GKE uses metadata-server authentication |
| Enable Grafana development mode or generally allow unsigned plugins | Broader code-loading authority is unnecessary; the PoC installs only the signed, version- and digest-pinned BigQuery datasource |
| Implement storage with CDC, dedicated outboxes/brokers, and permanent workers | Production-scale complexity without a PoC requirement or failing test |
| Add L4-to-L5 and 3D scenes to the base | Changes the predecessor-compatible visualization contract and introduces six additional cross-cloud query integrations; requires a later profile version |
| Retain `needs3DModel`, `sceneEntityCount`, `totalSceneAssetSizeMiB`, or `average3DModelSizeInMB` in Five-layer v2 | Claims a scene path the profile does not implement; the fields remain historical-only until a later visualization-capability version |
| Reuse legacy dashboard, seat, Eventing, or error-handling inputs beside workload v2 and the selected Eventing scenario | Creates duplicate request-rate and capacity sources; new profiles reject the retired inputs while historical `@1` remains reproducible |
| Let callers edit the immutable `eventing-workload.v1` evidence object inline | Its schema identifies bounded S/M/L synthetic scenarios; v1 accepts only a server-resolved scenario reference and reserves custom workloads for a new contract version |

## Offline Activation And Live-Readiness Gates

Five-layer v2 does not activate offline until all of the following pass:

1. immutable complete-provider bundle, workload, route, and component manifests;
2. exact Eventing scenario reference/digest resolution plus formulas and
   ownership for every selected service;
3. the provider-local L3-hot-to-L5 visualization edge for all three bundles
   and stable rejection of L3-hot/L5 splits;
4. all six domain-event routes, six storage trust directions, and twelve
   storage stage routes;
5. same-provider route elision;
6. minimal storage duplicate/failure/recovery tests;
7. Small/Medium/Large deterministic calculations for the core and referenced
   embedded-event scenario, including Cosmos RU/partition proofs;
8. OrbStack-backed cross-stack and Terraform no-apply/mock-plan gates;
9. historical/Eventing digest-stability, docs, links, and secret scans;
10. two new zero-finding reviews.

An offline-activated profile is not live-ready. Provider quota approval, real
identity exchange, workload-specific throughput, plugin behavior, and cloud
cleanup require separately approved supervised evidence.

## Primary Source Ledger

### AWS

- [AWS IoT TwinMaker quotas](https://docs.aws.amazon.com/general/latest/gr/iot-twinmaker.html)
- [AWS IoT TwinMaker pricing plans](https://aws.amazon.com/iot-twinmaker/pricing/)
- [DynamoDB on-demand capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)
- [EventBridge Scheduler for ECS tasks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/tasks-scheduled-eventbridge-scheduler.html)
- [S3 lifecycle management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [AWS outbound identity federation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_outbound.html)
- [AWS `AssumeRoleWithWebIdentity`](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_request.html)

### Azure

- [Cosmos DB request units](https://learn.microsoft.com/en-us/azure/cosmos-db/request-units)
- [Cosmos DB serverless performance](https://learn.microsoft.com/en-us/azure/cosmos-db/serverless-performance)
- [Cosmos DB limits and autoscale minimums](https://learn.microsoft.com/en-us/azure/cosmos-db/concepts-limits)
- [Cosmos DB partitioning](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning)
- [Azure Digital Twins service limits](https://learn.microsoft.com/en-us/azure/digital-twins/reference-service-limits)
- [Azure Managed Grafana supported data sources](https://learn.microsoft.com/en-us/azure/managed-grafana/how-to-data-source-plugins-managed-identity)
- [Azure Data Explorer overview](https://learn.microsoft.com/en-us/azure/data-explorer/data-explorer-overview)
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
- [Grafana JSON API datasource status](https://grafana.com/grafana/plugins/marcusolsson-json-datasource/)
- [Grafana plugin signatures](https://grafana.com/docs/grafana/latest/administration/plugin-management/plugin-sign/)
- [Grafana `allow_loading_unsigned_plugins` configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#allow_loading_unsigned_plugins)

The immutable Phase 8.8 source ledger remains the authority for Kinesis,
SNS/SQS, Event Hubs, Service Bus, Pub/Sub, Cloud Run worker pools, BifroMQ, and
all six domain-event bridge directions. Primary documentation proves published
capabilities and limits; it does not replace implementation or live testing.
