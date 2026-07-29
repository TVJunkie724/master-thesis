---
title: "Phase 8 Five-Layer v2 Service-Bundle And Boundary Closure"
description: "PoC-focused corrective plan for the executable five-layer-baseline@2 placement experiment."
tags: [architecture, services, multicloud, identity, capacity, optimizer, deployer, phase-8]
lastUpdated: "2026-07-29"
version: "1.5"
---

<!-- SOURCES:
- docs/research/phase_08_service_bundle_evaluation.md
- Phase 8.0-8.10 plans and handoff
- Immutable Phase 8.8 Eventing decision package
- Current Optimizer, Management, Deployer, Terraform, and Flutter behavior
- User-approved functionality-first PoC selection, L3-hot/L5 co-location,
  independent L4 placement, Cosmos DB continuity, and mandatory
  single-cloud/multicloud coverage
EXTRACTED: 2026-07-29 | VERSION: 1.5
-->

# Phase 8 Five-Layer v2 Service-Bundle And Boundary Closure

## 0. Authority And Status

| Field | Value |
|---|---|
| Scope | Corrective Five-layer v2 gate for Phases 8.4-8.9A |
| Planning branch | `codex/phase-8-service-bundle-closure` |
| Decision evidence | [`phase_08_service_bundle_evaluation.md`](../../research/phase_08_service_bundle_evaluation.md) |
| Historical profile | `five-layer-baseline@1`, immutable read/verify/destroy only |
| New profile | `five-layer-baseline@2` |
| Deferred profile | `six-layer-eventing@1`; plan only after reviewed Five-layer v2 implementation |
| Local environment | OrbStack; no live cloud execution |
| Selection rule | Functionality and theoretical Small/Medium/Large admissibility first; cost is measured, not minimized |
| PoC rule | Add only components required by the shared functional contract or by a measured capacity boundary |
| LaTeX | Excluded without separate approval |
| Review status | Two fresh zero-finding reviews complete; explicit user approval still required before implementation |

Where an older Phase 8 plan conflicts with this corrective gate, this document
controls new-profile implementation. Historical artifacts, digests, and
completion evidence remain unchanged and are annotated rather than rewritten.

The immutable `phase-08-eventing-implementation@1` package remains unchanged.
It proves the domain-event behavior and bridge primitives reused by embedded
Five-layer v2 ownership, not the complete Twin and not a Six-layer runtime
approval. Before Phase 8.9A implementation, this plan produces a separate immutable
`phase-08-complete-service-bundles@1` package. Runtime activation requires both
digests and fails closed on conflicting ownership, identity, service, route, or
version data.

The composed validator preserves rather than rewrites the Eventing package's
historical whole-profile statuses. `profile_target_not_implemented` records
that the whole AWS/Azure targets were not implemented when Eventing evidence
was frozen; `unsupported_missing_l4_l5` records the then-open GCP gap. A new
profile is admissible only when the complete-service package independently
maps each status to the exact implemented L1-L5 bundle and, for GCP, proves the
named L4/L5 gap closed. Missing, broader, or provider-mismatched closure
evidence rejects composition. The original Eventing status remains visible in
research provenance and is never mutated.

Within Phase 8, **activation** means offline repository activation: the
Management API may expose a profile for new selection and the implemented path
may calculate, resolve, package, and pass no-apply verification. Activation is
not a live deployment or measured-capacity claim. Those remain
`live_capacity_pending` until a separately approved supervised cloud run.

## 1. Corrected Planning Decisions

The following decisions replace the overextended v1.0 service-bundle plan:

1. `five-layer-baseline@2` always implements the approved domain-event
   behavior inside the five existing responsibilities. There is no Eventing
   feature flag.
2. Visualization has one mandatory logical read: `L3 hot -> L5` for bounded
   raw/historical telemetry and aggregates.
3. L4 receives selected current-state/model/relationship projections from L3
   through `twin_projection.v1`; raw telemetry is not mutated into the semantic
   Twin one message at a time.
4. `L3 hot` and `L5` form one provider-local raw-visualization bundle. `L4`
   remains independently placeable. This creates three single-cloud and six
   deliberate `L3-hot == L5 != L4` online placements.
5. `L4 -> L5`, Twin-context dashboards, scenes, and 3D visualization are not
   claimed by Five-layer v2. Adding them requires a later versioned capability
   decision. Historical `five-layer-baseline@1` remains unchanged.
6. GCP uses a bounded document-based Twin model in Firestore. Spanner Graph is
   not selected because the PoC requires only reviewed point and one-hop
   relationship queries, not arbitrary graph algorithms.
7. Storage transitions use finite scheduled batch jobs. Dedicated CDC,
   outbox, broker, and continuously running mover pipelines are rejected until
   evidence shows the simpler design cannot meet a scenario.
8. Same-provider domain-event paths create no bridge. Same-provider storage
   creates no cross-cloud copy, but hot-to-cool still uses the finite export
   job and cool-to-archive uses native lifecycle.
9. Azure retains Cosmos DB as L3 hot. ADX is not selected merely to obtain a
   more convenient datasource; its analytics-focused advantages remain a
   documented rejected alternative.
10. Cost includes every selected component, but a cheaper incomplete service
   never wins admission.

The current `five-layer-baseline@1` graph remains historical evidence even
where it differs. It is not silently upgraded to these semantics.

## 2. Shared Functional Contract

Every Five-layer v2 provider bundle must supply:

1. authenticated bidirectional device communication;
2. telemetry ingestion and processing;
3. rule evaluation, extension action, notification workflow, command, and
   correlated device outcome;
4. hot time-series, cool object, and archive object persistence;
5. a semantic Twin model with current state and bounded relationship queries;
6. bounded raw/historical visualization from L3 hot;
7. typed selected-state/model/relationship projection from L3 hot to L4;
8. typed domain-event delivery with ordering, retry, failure, and replay where
   required by the immutable Eventing contract;
9. same-cloud paths, all six directed cross-cloud domain-event routes, six
   storage trust directions, and twelve cross-cloud storage stage routes;
10. deterministic deployment, observability, cleanup, and cost ownership;
11. theoretical Small/Medium/Large capacity evidence with unresolved live
    behavior labeled honestly.

Six-layer planning is intentionally deferred. When resumed, it must reuse the
reviewed Five-layer v2 L1-L5 contract unchanged and evaluate only the ownership
and placement delta introduced by an independent Eventing responsibility. This
document neither activates nor pre-approves that profile.

The immutable Phase 8.8 Six-layer row remains research provenance only. It is
not an instruction to implement Six-layer in 8.9A.

## 3. Fixed Provider Bundles

### 3.0 Fixed PoC Regions

Both profiles inherit the immutable Eventing scenario regions for every
responsibility and supporting component:

| Provider | Fixed region |
|---|---|
| AWS | `eu-central-1` |
| Azure | `westeurope` |
| GCP | `europe-west1` |

Region is not an Optimizer decision in these profile versions. All components
owned by one provider, including storage classes, registries, schedulers,
compute, Twin services, visualization, and local brokers, use that provider's
fixed region unless the provider exposes only a non-regional control-plane
object. Cross-cloud transfer is therefore visible only on declared remote
edges. The complete-service package must prove service/tier availability and
region-specific pricing for every selected member. An unavailable member
rejects that provider bundle; the resolver does not silently choose another
region.

### 3.1 Scientific L1-L5 Bundles

| Layer | AWS | Azure | GCP |
|---|---|---|---|
| L1 acquisition | AWS IoT Core and IoT Commands | Azure IoT Hub | Apache BifroMQ `4.0.0-incubating` on GKE Standard, external load balancer, and the reviewed ordered MQTT-to-Pub/Sub adapter |
| L2 processing | Lambda and Step Functions Standard | Functions Flex Consumption and Logic Apps Consumption | Cloud Run and Workflows |
| L3 hot | DynamoDB on-demand with device/time primary key and a scenario-derived `stored_at` window-shard GSI | Cosmos DB for NoSQL with `/device_id`, bounded device/time queries, selective indexing, and scenario-selected serverless/autoscale capacity | BigQuery time-series tables partitioned on `stored_at` and clustered by device ID, using the Storage Write API |
| L3 cool | S3 Standard-IA | Blob Cool | Cloud Storage Nearline |
| L3 archive | S3 Glacier Deep Archive | Blob Archive | Cloud Storage Archive |
| L4 Twin | IoT TwinMaker Standard pricing plan for current semantic state and relationships | Azure Digital Twins with current graph/state | Cloud Run Twin API/materializer with Firestore Native collections for models, twins, current state, and relationships |
| L5 visualization | Amazon Managed Grafana 12 with a typed provider-local raw-history reader datasource | Azure Managed Grafana 12 with its supported JSON API datasource and a typed provider-local Cosmos reader | One Grafana OSS 12 pod on GKE with a Persistent Disk PVC and signed BigQuery datasource `3.2.0` |

AWS keeps raw history in DynamoDB and Azure keeps it in Cosmos DB. Their
provider-local reader APIs expose the same bounded `raw_history_query.v1`
contract to managed Grafana. GCP uses BigQuery for raw history and Firestore
only for bounded semantic state. No provider routes the mandatory dashboard
through L4, and no Spanner Graph resource is required.

The two managed-Grafana reader realizations are exact supporting components,
not another scientific layer:

| Provider | Reader runtime | Datasource/authentication |
|---|---|---|
| AWS | Lambda HTTPS Function URL with application-level reader-key validation | `marcusolsson-json-datasource`; one generated 256-bit deployment-scoped key in `secureJsonData.httpHeaderValue1` under header `X-Twin-Reader-Key`; Lambda stores only its hash |
| Azure | Functions Flex HTTP route with `AuthLevel.FUNCTION` | Standard-tier `marcusolsson-json-datasource`; one deployment-scoped Function key in `secureJsonData.httpHeaderValue1` under header `x-functions-key` |
| GCP | No reader API; bounded BigQuery SQL templates | Signed `grafana-bigquery-datasource` `3.2.0` with `authenticationType=gce` and Workload Identity for GKE |

The AWS/Azure HTTPS routes are internet-reachable PoC read boundaries because
the selected managed Grafana services are not placed inside a private network
in this profile version. They are never anonymous: the reader credential,
strict query bounds, read-only backend identity, datasource permissions, and
rate/concurrency limits are mandatory. Private connectivity is a later
hardening option, not an unpriced hidden component.

TwinMaker uses its Standard pricing plan in all three scenarios because the
selected graph/query capability is unavailable in Basic. Tiered bundles are
not selected; their commitment would add a second scenario-dependent choice
without adding PoC functionality. Entity, query, projection-adapter, and
Grafana costs remain explicit. A TwinMaker external-history connector,
TwinMaker Grafana plugin, and scene resources are not selected.

The GCP L5 deployment reuses the BifroMQ GKE cluster when L1 is also GCP.
Otherwise the online GCP bundle creates one GKE Standard cluster for Grafana.
It does not create a dedicated Grafana node pool unless later capacity evidence
requires one. Current Grafana documentation does not identify the reviewed
BigQuery datasource as Enterprise-only, so the cost model does not invent a
plugin-license charge. Offline activation still requires the signed
self-hosted plugin artifact, applicable license notice, version, and digest to
be available. If they cannot be obtained, GCP remains unsupported until a new
reviewed datasource decision; implementation may not silently replace the
plugin.

No custom Twin/scene Grafana plugin is selected. The content-addressed GCP
Grafana image contains only the pinned Grafana runtime and signed BigQuery
plugin. Development mode, unsigned-plugin loading, runtime download, and UI
plugin installation are disabled.

Grafana uses one replica in all PoC scenarios so its SQLite state can remain on
one ReadWriteOnce Persistent Disk PVC. CPU and memory are sized per scenario;
dashboards and datasources are also provisioned declaratively. Multiple
replicas would require a separately reviewed shared Grafana database and are
therefore a capacity escalation, not a hidden default.

The cost model never assumes free BifroMQ-node headroom. When a GKE cluster is
already present, Grafana adds one incremental general-workload node to it;
otherwise the L3-hot/L5 bundle creates a one-node zonal GKE cluster. The initial
theoretical allocation is `e2-standard-4` for Small/Medium and
`e2-standard-8` for Large. This shares cluster control-plane/networking where
possible but does not create an isolation-only Grafana node pool.

The GCP Grafana endpoint is an explicit PoC boundary: one Kubernetes
`LoadBalancer` Service, TLS terminated by Grafana with a deployment-generated
certificate in a Kubernetes Secret, generated Grafana credentials, and a
non-empty `loadBalancerSourceRanges` allowlist. The static IP, endpoint, and
certificate fingerprint are deployment outputs. Plaintext, `0.0.0.0/0`,
public buckets, public Twin APIs, and credentials in contracts/tfvars/logs are
forbidden. Public DNS, a public CA certificate, and IAP are not added to this
PoC version.

### 3.2 Event Bundles

The exact immutable Phase 8.8 selections remain authoritative:

| Scope | AWS | Azure | GCP |
|---|---|---|---|
| Embedded Five-layer v2 | IoT Core, Lambda, Step Functions Standard, IoT Commands, SQS FIFO, CloudWatch; Kinesis and SNS FIFO only for reviewed remote responsibility edges | IoT Hub, Functions Flex Consumption, Logic Apps Consumption, Service Bus Standard, Azure Monitor; Event Hubs Standard/Dedicated for reviewed remote telemetry edges | Pub/Sub, Cloud Run, Workflows, BifroMQ/GKE boundary, Cloud Load Balancing, Cloud Logging |
| Independent Six-layer Eventing | Kinesis Data Streams, SNS FIFO, SQS FIFO, S3 failure destination, Lambda, CloudWatch | Event Hubs Standard for Small/Medium and Dedicated for Large, Service Bus Standard, Functions Flex Consumption, Azure Monitor | Pub/Sub, Cloud Run services/worker pools, Cloud Logging |

These rows are bundle membership, not permission to deploy every conditional
resource in every topology. Same-provider edges create no bridge. AWS remote
stream/control resources and Azure remote telemetry resources appear only when
the resolved route requires them. In the independent Azure Event Layer both
Event Hubs and Service Bus are required: Event Hubs owns retained high-volume
telemetry; Service Bus owns ordered low-rate action, notification, and command
work. Service Bus is therefore internal as well as cross-cloud support.

One provider service family may host more than one logical responsibility,
but the graph must not collapse those responsibilities. In particular, a GCP
Six-layer deployment reuses the Pub/Sub project/API and the single L1
BifroMQ/GKE boundary, while L1 device-backbone and Event-Layer traffic use
different topics, subscriptions, component IDs, permissions, retention, and
cost records. Shared project/API enablement is priced once; message, storage,
delivery, and egress operations are attributed once to their owning logical
component. The same rule applies whenever one provider is both sender and
receiver. Same-provider edges use provider-local SDK/trigger bindings and no
bridge.

### 3.3 Raw Visualization And Twin Placement

For Five-layer v2:

```text
provider(L3_hot) == provider(L5)
provider(L4) is independent
```

The positive online placements are:

```text
L3 hot / L5 AWS   + L4 AWS | Azure | GCP
L3 hot / L5 Azure + L4 AWS | Azure | GCP
L3 hot / L5 GCP   + L4 AWS | Azure | GCP
```

Any `provider(L3_hot) != provider(L5)` assignment fails before pricing with
`PROFILE_RAW_VISUALIZATION_COLOCATION_REQUIRED`. An unequal L4 is valid and
must never be rejected by the old
`PROFILE_ONLINE_ANALYTICS_COLOCATION_REQUIRED` rule.

This is the deliberate PoC experiment. It holds the raw storage/datasource
boundary constant while measuring local versus six directed cross-cloud
`twin_projection.v1` routes. It avoids six unrelated cross-cloud Grafana
datasource integrations without assuming that L4 must share the L3/L5
provider.

## 4. Boundary Contracts

### 4.1 Event Taxonomy

Each event-like component has exactly one class:

| Class | Owner in Five-layer v2 | Owner in Six-layer v1 |
|---|---|---|
| Device MQTT/IoT traffic | L1 | L1 |
| Raw telemetry backbone | L1/L2 | L1/L2 |
| Canonical domain events | Embedded producer/consumer responsibilities | Eventing responsibility |
| Storage schedules and batch manifests | L3 | L3 |
| Twin materialization updates | L4 | L4 |
| Observability/audit records | Component owner | Component owner |
| Management operation updates/SSE | Application control plane | Application control plane |

Only canonical domain-event ownership would move into a later sixth
responsibility. Storage jobs, database ingestion, Twin materialization,
provider logs, and
Management SSE are not relabeled as Event Layer services.

### 4.2 Domain Events And Cross-Cloud Bridge

Reuse `phase-08-cross-cloud-bridge@1` exactly:

```text
source durable outbox/broker
  -> source-provider runtime
  -> canonical envelope validation
  -> short-lived destination credential
  -> destination broker data-plane publish
  -> destination durable acceptance
  -> source acknowledgement
```

All six directed AWS/Azure/GCP pairs are supported by the selected trust
primitives. A provider may send on one edge and receive on another. A
same-provider edge uses its local bundle and creates no bridge.

`twin_projection.v1` is one canonical domain-event route in Five-layer v2:
the L3 owner publishes selected current-state/model/relationship changes and
the L4 owner materializes them idempotently. The bridge is not a generic
public Function endpoint and does not prove storage or visualization
transport. `INTER_CLOUD_TOKEN`, anonymous Function URLs, static cloud keys, and
shared cross-deployment bearer tokens are forbidden.

### 4.3 Raw Visualization Read And Twin Projection

Add two separate logical edges:

```text
L3 hot -- raw_history_query.v1 --> L5
L3 hot -- twin_projection.v1 ---> L4
```

`raw_history_query.v1` supplies time-bounded telemetry series and aggregates.
It defines bounded device/time ranges, result limits, pagination, timeout,
idempotent read retry, correlation, safe error codes, datasource version,
identity, capacity, provisioning, and cleanup.

For AWS/Azure the Grafana datasource sends one `GET /raw-history/v1` request:

```text
device_id                required; one deployment-owned device
metric                   required; one configured numeric metric
from                     required RFC 3339 UTC timestamp
to                       required RFC 3339 UTC timestamp; from < to
bucket_seconds           one of 0, 60, 300, 3600
limit                    1..1000; default 1000
cursor                   optional opaque provider-signed continuation token
```

`bucket_seconds=0` is allowed only for ranges up to 24 hours. Aggregated
queries may cover at most 31 days. A response contains only
`schema_version`, `device_id`, `metric`, ordered `points`, `next_cursor`,
`truncated`, and `correlation_id`. A raw point contains `stored_at`,
`event_time`, and `value`; an aggregate point contains `bucket_start`, `min`,
`max`, `avg`, and `count`. The implementation returns at most 1,000 points and
times out after ten seconds; it never performs an unbounded scan. GCP's
declaratively provisioned BigQuery query templates enforce the same device,
metric, time, bucket, row, and byte-billing bounds and return the same logical
columns without adding an HTTP reader.

`twin_projection.v1` supplies selected current state, model, and relationship
changes after durable L3 acceptance. It uses the immutable canonical event
envelope, event ID, per-source ordering/idempotency, retry, failure, replay,
short-lived cross-cloud identity, and destination-acceptance rules. It carries
no raw-history query and is not invoked once for every telemetry message.

Its payload is one of four closed variants:

```text
twin.state.upserted        twin_id, source_id, source_sequence, observed_at,
                           state_patch
twin.model.upserted        model_id, model_version, model_document
twin.relationship.upserted relationship_id, from_twin_id, to_twin_id, type
twin.relationship.deleted  relationship_id, from_twin_id, to_twin_id, type
```

The canonical envelope supplies deployment, event, schema, correlation,
causation, producer, and timestamp fields; payload size remains within the
immutable Eventing envelope limit. The synthetic workload generator emits
explicit projection candidates at
`twinStateMaterializationsPerSecond`/`twinGraphUpdatesPerSecond`; it references
the already accepted source record or management mutation. Runtime code does
not infer these rates by sampling every telemetry message.

Provider realizations are:

| L3/L5 provider | Raw/history path |
|---|---|
| AWS | Managed Grafana -> pinned JSON datasource -> typed read-only API -> DynamoDB |
| Azure | Managed Grafana -> supported JSON API datasource -> typed read-only Function -> Cosmos DB |
| GCP | Grafana BigQuery datasource -> BigQuery |

Reader identities are exact and bounded:

| Provider | L5 reader identity and minimum target roles |
|---|---|
| AWS | One generated deployment-scoped read credential -> exact reader API stage; reader runtime role -> exact DynamoDB table/index read |
| Azure | One generated deployment-scoped read credential -> exact Function reader route; Function managed identity -> Cosmos DB built-in data reader on the exact account/database/container |
| GCP | Grafana Kubernetes service account -> GCP service account through Workload Identity for GKE -> dataset-scoped BigQuery Data Viewer, project-scoped BigQuery Job User, and the minimum documented project-read permission |

AWS/Azure reader credentials exist only in the provider endpoint and Grafana
`secureJsonData`. The Deployer may retrieve them once for datasource
provisioning but must not write them to persisted manifests, tfvars, state
projections, logs, fixtures, or docs. Destroy removes the endpoint credential
with the deployment. This local, read-only credential is not reused by
`twin_projection.v1`; remote projection remains short-lived and secretless.

The GCP datasource enables the BigQuery and Cloud Resource Manager APIs and is
provisioned with plugin authentication type `gce`. A Standard-cluster Grafana
pod is scheduled only on a node with the GKE metadata server enabled. Google
documents that existing Compute Engine metadata-server authentication works
unchanged through Workload Identity Federation for GKE; Grafana documents
`gce` metadata authentication and the additional project-read permission.
GCP live readiness still requires plugin `Save & test` plus a bounded BigQuery
query under the Grafana pod identity and an HTTPS browser request from an
allowed CIDR that verifies the recorded certificate fingerprint. Offline
activation retains `live_capacity_pending`; a failed supervised query or
endpoint/authentication check marks the GCP L3/L5 bundle
`live_readiness_failed`. No JSON service-account key is permitted.

### 4.4 Twin Materialization

Add `twin-materialization-policy.v1`:

- raw telemetry is written to L3 hot and stays queryable there;
- selected state changes materialize the latest operational state in L4;
- model, Twin, and relationship changes update L4 explicitly;
- no provider performs one graph mutation for every raw telemetry message;
- canonical event IDs make materialization idempotent;
- stale/out-of-order state follows one declared per-device policy;
- every provider exposes the same bounded logical fields.

The GCP query set is intentionally limited to:

- Twin by ID;
- current state by Twin ID;
- direct incoming/outgoing relationships for one Twin;
- model lookup;
- explicit materialization write by idempotency key.

The initial Firestore model is equally bounded:

```text
models/{model_id}
twins/{twin_id}
twins/{twin_id}/sources/{source_id}   # current values + last event/sequence
relationships/{relationship_id}      # from_id, to_id, type
```

Composite indexes cover only `(from_id, type)` and `(to_id, type)` relationship
queries. A transaction compares the stored source sequence/event ID before
updating current state, so duplicate or stale delivery does not create a
separate unbounded idempotency collection.

Five-layer v2 has no scene asset, scene binding, browser scene editor, or 3D
overlay contract. Historical scene inputs remain readable only for
`five-layer-baseline@1`. A later profile version must add an explicit
L4-to-L5 capability before any provider scene service or custom Grafana panel
can be selected.

Arbitrary multi-hop graph algorithms, graph analytics, and ad hoc traversal
are outside the profile. If they become requirements, the service decision is
reopened instead of silently adding Spanner Graph.

### 4.5 Minimal Storage Movement

Storage movement is a data-plane batch operation, not a canonical domain
event. One portable `storage-mover` image has source adapters for
DynamoDB/Cosmos DB/BigQuery and object adapters for S3/Blob/Cloud Storage.

| Source provider | Finite runtime |
|---|---|
| AWS | EventBridge Scheduler -> ECS task on Fargate; image in the deployment ECR repository |
| Azure | Scheduled Azure Container Apps Job; image in the deployment ACR Basic registry |
| GCP | Cloud Scheduler -> Cloud Run Job; image in the deployment Artifact Registry repository |

Each provider that actually deploys at least one platform-owned container
creates or reuses exactly one content-addressed registry support component for
all such images. A provider selected only for managed services receives no
registry. ECR, ACR Basic, or Artifact Registry storage/requests are priced once
per qualifying provider, not once per layer or image. The registry is
deployment support, not a Twin or Eventing responsibility.

The existing storage-duration inputs become explicit cumulative age boundaries
for Five-layer v2. With `H = hotStorageDurationInMonths`,
`C = coolStorageDurationInMonths`, and
`A = archiveStorageDurationInMonths`, measured as 30-day months from
provider-assigned `stored_at`, a record is hot in `[0,H)`, cool in `[H,C)`,
archived in `[C,A)`, and expired at `A`. The existing constraint
is tightened to `1 <= H < C < A` for workload v2 so every selected tier has a
positive residence interval. Historical `@1` validation, formulas, and
artifacts remain unchanged; only workload v2/RDS v2 uses the corrected
non-overlapping intervals.

Hot-to-cool behavior:

1. assign every hot record a provider-writer `stored_at` ingestion timestamp
   while preserving the device `event_time` separately;
2. assign it to a deterministic five-minute `stored_at` batch; five minutes is
   a batching interval, not the hot-retention duration;
3. when the batch end reaches age `H`, read that bounded window from L3 hot
   with a stable partition plan;
4. write gzip NDJSON objects of at most 64 MiB uncompressed;
5. use deterministic `route/window/partition` object keys;
6. write count, schema, event-ID range, and SHA-256 checksum metadata;
7. create the object conditionally so concurrent retries cannot overwrite it;
8. treat an identical existing object as success and a conflicting checksum as
   a terminal error;
9. write the immutable window manifest last and retry the finite job; do not
   run a permanent CDC pipeline.

A device event arriving late receives a later `stored_at` value and therefore
enters a later storage window without changing the original `event_time`.
AWS queries a scenario-derived set of window shards through the priced GSI;
Azure assigns the sorted deployment device IDs deterministically across tasks
and queries each `/device_id` partition for the exact `stored_at` window; GCP
prunes the BigQuery `stored_at` partition. A task processes at most 512 MiB of
canonical source input, and an Azure Cosmos task additionally processes at
most 1,000 device partitions. A full-table or unbounded cross-partition scan
is not admissible.

At age `C`, same-provider cool-to-archive uses an S3, Blob, or Cloud Storage
lifecycle transition configured for `C - H` after cool-object creation. When
cool and archive providers differ, the same source-provider job lists a cool
prefix only after its window manifest exists and copies each immutable object
conditionally to the destination object API with deterministic keys. If the
destination archive tier requires a landing class, a destination-local
lifecycle rule performs the final class transition. Archive lifecycle expires
the data at age `A`: object age `A-H` for a same-provider cool object, or
`A-C` for a remote archive object created at the second boundary.

Those lifecycle offsets are exact for an on-time export. A successful retry
within the 24-hour horizon shifts the physical object-creation-based transition
and deletion by the same bounded delay. Logical query eligibility still uses
`stored_at`: the record leaves cool eligibility at `C` and all active reads at
`A`. The manifest records scheduled and actual timestamps; delayed physical
cleanup is marked `storage_transition_degraded`, remains bounded by the retry
horizon, and is included in overlap evidence. The plan does not claim that
native lifecycle can backdate an object's creation time.

The PoC freezes a 24-hour retry horizon and a 48-hour source-expiry grace for
each remote or hot-source transition. Incomplete due windows are retried by
the next finite scheduled invocation. Hot native retention and remote cool
source expiry therefore occur only at the relevant boundary plus 48 hours;
the overlap is priced. A window still incomplete after 24 hours emits
`storage_transition_failed`, fails the live-readiness gate, and leaves a
further 24-hour evidence-preservation window. This bounded rule is deliberately
not a conditional-retention control plane. Extending it requires a new
decision version.

No separate checkpoint database is required. Window IDs, deterministic object
keys, destination metadata, and immutable manifests form the PoC checkpoint.
There is no dedicated DynamoDB Stream/Lambda/Kinesis storage path, Cosmos
Change Feed/Event Hubs path, Firestore Eventarc/Pub/Sub path, storage DLQ, or
continuously running GKE/Fargate/Container Apps mover.

The immutable Eventing identity primitives are reused only as trust building
blocks. Storage routes receive separate object-store permissions and cost
ownership:

| Direction | Short-lived exchange | Destination permission |
|---|---|---|
| AWS -> Azure | AWS outbound OIDC -> Entra federated credential | Exact Blob container object write |
| AWS -> GCP | AWS subject token -> GCP Workload Identity Federation | Exact Cloud Storage bucket object write |
| Azure -> AWS | Managed-identity OIDC -> `AssumeRoleWithWebIdentity` | Exact S3 prefix write |
| Azure -> GCP | Managed-identity OIDC -> GCP Workload Identity Federation | Exact Cloud Storage bucket object write |
| GCP -> AWS | Google service-account OIDC -> `AssumeRoleWithWebIdentity` | Exact S3 prefix write |
| GCP -> Azure | Google service-account OIDC -> Entra federated credential | Exact Blob container object write |

The plan escalates to CDC/outbox machinery only if deterministic load or
failure tests show missed closed-window records, unacceptable recovery time,
or inability to sustain the reviewed Large input. Such escalation requires a
new decision-package version and cost model.

## 5. Workload And Capacity Contract

Add workload v2 fields:

```text
twinEntityCount
aggregateDashboardRefreshesPerHour
apiCallsPerAggregateDashboardRefresh
dashboardActiveHoursPerDay
monthlyEditorSeats
monthlyViewerSeats
twinStateMaterializationsPerSecond
twinGraphUpdatesPerSecond
```

The same request contains one required Eventing reference, not an inline copy
of the evidence object:

```text
eventingScenarioId = eventing-small-v1
                   | eventing-medium-v1
                   | eventing-large-v1
```

Management resolves that ID to the canonical `eventing-workload.v1` object in
the immutable Phase 8.8 package, verifies its digest, and persists the ID,
digest, and exact snapshot with the Optimizer run. Flutter submits only the ID;
the Optimizer receives only the server-resolved snapshot. Five-layer v2 uses
the selected object, and a later Six-layer plan must reuse it unchanged.
Inline/custom Eventing values are outside v1 because
the immutable schema explicitly describes bounded synthetic S/M/L scenarios.

Keep the existing `hotStorageDurationInMonths`,
`coolStorageDurationInMonths`, and `archiveStorageDurationInMonths`, but give
them the cumulative `[0,H)`, `[H,C)`, and `[C,A)` semantics and strict ordering
defined above.
Profile constants `storageBatchIntervalMinutes=5`,
`storageTransferRetryHorizonHours=24`, and
`storageSourceExpiryGraceHours=48` are resolved dimensions, not new user
switches.

Reject for new-profile requests:

```text
useEventChecking
triggerNotificationWorkflow
returnFeedbackToDevice
allowGcpSelfHostedL4
allowGcpSelfHostedL5
entityCount
needs3DModel
average3DModelSizeInMB
amountOfActiveEditors
amountOfActiveViewers
dashboardRefreshesPerHour
apiCallsPerDashboardRefresh
integrateErrorHandling
orchestrationActionsPerMessage
eventsPerMessage
numberOfEventActions
eventTriggerRate
```

The domain behavior behind the first three flags is always present. GCP
availability is a profile capability, not a user switch. Historical requests
keep the complete retired field set for reproduction. `needs3DModel` is also
historical-only because v2 has no L4-to-L5 scene contract. New requests use the
single workload-v2 object plus `eventingScenarioId`; they cannot submit either
an inline Eventing object or the old scene, dashboard, seat, Eventing, or
error-handling surrogates. `numberOfDeviceTypes` remains valid because it sizes
the distinct type-specific L2 processors rather than duplicating Eventing
load. Migration never invents `twinEntityCount`, an Eventing scenario ID, or
Eventing workload values.

Freeze `core-small-v2`, `core-medium-v2`, and `core-large-v2` from the research
evaluation. Preserve the immutable Phase 8.8 Eventing scenarios and pair them
only by size in Phase 8.10.

The Large core input is 5,000 records/s and exactly 4,000 KiB/s
(3.90625 MiB/s) before transport overhead. One five-minute batch is
1,200,000 KiB (1,171.875 MiB, approximately 1.145 GiB). The
initial storage-job parallelism is one task for Small, one for Medium, and
three partitioned tasks for Large; the decision-package calculator derives the
exact value from input bytes and a 512-MiB maximum source partition per task.
For Cosmos DB the calculator also enforces at most 1,000 `/device_id`
partitions per task, so Large starts with at least 30 Azure tasks.

For workload v2, steady-state logical storage volume is calculated without
double counting: monthly ingest multiplied by `H` for hot, `C - H` for cool,
and `A - C` for archive. The 48-hour source grace, provider minimum-storage
charges, lifecycle operations, one transfer per stage, and cross-cloud egress
are separate explicit cost terms. Historical `@1` golden costs are not
recalculated.

The Azure Cosmos capacity calculator records the canonical serialized item
bytes and measured RU charges for write, bounded device/time read, and mover
read fixtures. Small and Medium select serverless only when their peak total
remains within the published serverless partition capacity. Large selects
autoscale provisioned throughput with:

```text
Tmax = round_up_1000(
  max(
    1000,
    peak_write_ru_per_second
      + peak_dashboard_ru_per_second
      + peak_mover_ru_per_second,
    hot_storage_gib * published_minimum_autoscale_ru_per_gib
  )
)
```

The package also proves the maximum canonical bytes for one device over the
hot window remain below the published 20-GB logical-partition limit. Missing
request-charge evidence, a failed partition proof, or an unsupported
scenario-derived `Tmax` rejects Azure for that size. It never changes the
service silently to ADX.

| Bundle | Small | Medium | Large |
|---|---|---|---|
| AWS TwinMaker | 100 entities | 4,000 entities | 30,000 entities; external raw telemetry remains outside TwinMaker |
| AWS Grafana | Grafana 12 workspace | Same | Same; seats and measured concurrency remain distinct |
| Azure Cosmos DB | Serverless | Serverless | Autoscale maximum derived from measured RU/s and storage-driven minimum; fail admission if the proof does not pass |
| Azure Grafana | Standard X1 | Standard X1 | Standard X2 |
| GCP Firestore L4 | Bounded document/one-hop queries | Same schema, scenario-derived operations | 50 state materializations/s plus one graph/model update/s |
| GCP Grafana | One pod, one incremental `e2-standard-4` node, Persistent Disk PVC, TLS LoadBalancer | Same initial node with calculated pod CPU/RAM | One pod, one incremental `e2-standard-8` node, Persistent Disk PVC, TLS LoadBalancer; no default HA/shared database or isolation-only node pool |
| Storage mover | One finite task/batch | Provider-derived finite tasks/batch | AWS/GCP start at three byte-derived tasks; Azure starts at no fewer than 30 partition-derived tasks |

The exact embedded-event Kinesis/Event Hubs/Pub/Sub/BifroMQ allocations remain pinned
by Phase 8.8. All database partitions, Cosmos RU/BigQuery ingestion, Firestore
indexes, connector concurrency, Grafana replicas, scheduled-job resources,
retry, object counts, transfer, and observability dimensions are emitted into
RDS v2 and priced.

Published quotas prove only theoretical admission. Workload-dependent query,
projection, broker, bridge, identity, and storage-job behavior stays
`live_capacity_pending` until supervised evidence exists.

## 6. Immutable Complete-Service Decision Package

Before Phase 8.9A runtime changes, create:

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

scripts/phase_08_service_bundles/
  validate_decision_package.py
  calculate_capacity.py
  verify_sources.py
  tests/
```

The component manifest pins every logical/deployment component, service or
software version, image/chart/plugin digest, license, Terraform resource,
runtime package, port, output/input, permission, formula, capacity dimension,
file target, and test owner. Version-dependent values are refreshed from
primary sources before freezing; this plan does not invent future patch
versions.

The validator rejects unresolved/duplicate ownership, disagreement with the
immutable Eventing package, missing capacity or pricing dimensions, unknown
identity rules, missing single-cloud/mixed routes, secret-like data, and any
historical `@1` digest change. The future package status becomes `approved`
only after source refresh, deterministic calculations, schema/reference
validation, and its own two zero-finding reviews. The plan reviews recorded
below do not pre-approve that not-yet-built package.

## 7. Cross-Stack Changes

### Optimizer

The Optimizer must:

1. resolve `five-layer-baseline@2` only in this implementation slice;
2. reject the complete retired-field set for `@2`;
3. resolve and digest-check the required Eventing scenario reference, then
   resolve one of three L3-hot/L5 raw-visualization bundles and an independent
   L4 provider before pricing;
4. represent `L3_hot_to_L5_raw_history` and
   `L3_hot_to_L4_twin_projection`; reject an L4-to-L5 edge for this profile;
5. derive six event routes and both six-direction storage stages from
   assignments;
6. create no cross-cloud bridge or copy for a same-provider edge while still
   resolving the required local hot exporter and native archive lifecycle;
7. calculate all three single-cloud, all six L3-hot/L5-versus-L4 placements,
   and all otherwise admissible mixed paths;
8. price each service, fixed capacity, transfer, identity, observability, and
   cleanup owner exactly once;
9. keep `@1` only in the historical reproduction path.

### Management And Flutter

Management persists workload v2, the Eventing scenario ID/digest/snapshot, the
L3-hot/L5 bundle, independent L4 assignment, raw-visualization and Twin-
projection edges, generic components/edges/capacity,
and immutable decision digests. New Twins receive no active profile until
`@2` passes all gates. Existing `@1` records stay readable and destroyable.

Flutter shows Five-layer v2 only after server activation. It shows events as
mandatory profile behavior, selects one immutable Eventing S/M/L scenario and
renders its fields read-only, separates
Twin/dashboard inputs, and explains the provider-local L3-hot/L5 bundle plus
independent L4 placement. It does not offer scene/3D, inline Eventing, or
Eventing/GCP capability flags.

### Deployer And Terraform

Add static catalog/Terraform implementations for:

- the three L3-hot/L5 bundles and independent L4 implementations;
- `raw_history_query.v1` and all local/remote `twin_projection.v1` bindings;
- AWS DynamoDB reader, TwinMaker projection adapter, and Managed Grafana;
- Azure Cosmos DB serverless/autoscale, partitioned reader/mover, ADT
  projection adapter, and Managed Grafana without ADX;
- GCP BigQuery, Firestore Twin API, Grafana on GKE, signed plugin, Workload
  Identity, TLS LoadBalancer, CIDR allowlist, and generated credential/cert
  secrets without Spanner, a custom Twin plugin, or a dedicated node pool;
- the three finite storage-job runtimes, native lifecycle rules, and six
  directed storage trusts;
- one provider registry support component where selected container images
  require it, reused and priced once;
- the unchanged immutable embedded and Event-Layer bundles.

Every graph edge resolves from logical edge to catalog implementation to
source output, optional trust/route component, destination input, and exact
Terraform resource/output reference. No post-deploy name reconstruction,
anonymous public ingestion, or secret injection is permitted.

## 8. Phase Corrections And Commit Boundaries

### 8.0-8.3

Keep current inventories, historical `@1` decisions, contracts, and digests
unchanged. Annotate that they do not prove the new raw-visualization/Twin-
projection edges or provider-hosted GCP target. Phase 8.3 registers new
versioned bundle components only in 8.9A.

### 8.4-8.7

Preserve historical selections and migration 022. Phase 8.5 and 8.6 finish the
generic resolver/compiler dark; they must support generic multiple typed edges
but do not activate either new profile. Phase 8.7 implements server-driven
profile/workload UI and the no-active-profile state.

### 8.8

Preserve every immutable Eventing artifact byte and digest. Add documentation
only: its proof covers domain events, not L3-hot/L5, Twin projection, or
storage jobs.

### 8.9A

Implement workload v2, RDS v2/Manifest v4, the three L3-hot/L5 bundles,
independent L4 placement, raw-history read, Twin projection, minimal storage
jobs, corrected identity, and `five-layer-baseline@2`. Review to zero findings
and commit.

### 8.9B

Deferred. Do not branch or implement `six-layer-eventing@1` as part of this
plan. After 8.9A is implemented and reviewed, reopen the Six-layer service and
ownership evaluation against the exact committed Five-layer v2 L1-L5
baseline. That later plan may reuse the immutable Phase 8.8 evidence but must
receive explicit user approval and its own zero-finding reviews.

### 8.10

Deferred until the later Six-layer plan is approved and implemented. Five-
layer v2 must first emit its own reproducible three single-cloud, six
L3-hot/L5-versus-L4, mixed-path, rejection, capacity, and cost evidence. The
later comparative phase uses that frozen evidence rather than recalculating it
under changed L1-L5 assumptions.

Implementation sequence and clean commits:

1. commit this corrected plan/evaluation boundary;
2. build, review, and commit the immutable complete-service decision package;
3. finish/review/commit the dark Phase 8.6 compiler;
4. create the reviewed foundation branch and integrate the compiler commit;
5. implement/review/commit Phase 8.7;
6. branch and implement/review/commit 8.9A Five-layer v2;
7. stop and obtain a separately reviewed/approved Six-layer plan;
8. only then branch for Six-layer and the comparative Phase 8.10 evaluation.

A later branch never starts from an unreviewed or dirty boundary.

## 9. Verification

Required offline gates include:

- immutable `@1` and Eventing-package byte/digest stability;
- schema/reference/digest/generated-copy drift tests;
- all nine positive L3-hot/L4/L5 placements and every unequal L3-hot/L5
  rejection fixture;
- the raw-visualization edge for AWS, Azure, and GCP plus all six remote and
  three local Twin-projection routes;
- bounded GCP Twin query contract and a negative arbitrary-traversal fixture;
- three single-cloud and all admissible mixed calculations;
- all six event routes, six storage identity directions, twelve cross-cloud
  storage stage routes, and same-provider local export/lifecycle behavior with
  no remote route;
- storage late-event, duplicate-window, partial object, checksum conflict,
  retry, expired credential, destination outage, manifest, lifecycle, and
  cleanup tests, including delayed-export logical expiry versus physical
  lifecycle timing;
- Small/Medium/Large deterministic capacity and cost calculations, including
  Cosmos request-charge, autoscale, logical-partition, and partitioned-mover
  evidence;
- Optimizer, Management, Deployer, Terraform no-apply, Flutter, platform,
  docs strict/link/secret, and compatibility suites;
- no live cloud apply, deploy, destroy, paid operation, or capacity claim;
- two separate full review passes with zero unresolved findings.

Use OrbStack and existing project commands. Record services already running
before a test and stop only services started by that invocation.

For this planning boundary, run:

```bash
git diff --check
./thesis.sh test deployment-contract --focused
docker --context orbstack compose --profile docs run --rm docs mkdocs build --strict
```

The later implementation gate replaces the focused contract check with
`./thesis.sh test deployment-contract` and adds the affected service and
Flutter suites listed above. None of these commands may receive cloud
credentials or a live/apply flag.

### Review Record

| Pass | Scope | Result |
|---|---|---|
| 1 | Revised Five-layer v2 architecture and concept consistency across service evaluation, Phase 8 plans, Handoff, research design, and current docs | Pass after correction: stale triple-co-location, ADX, L4-to-L5/3D, Six-layer authority, and invented BigQuery-license assumptions removed; zero unresolved findings |
| 2 | Builder/API contract, workload math, identity/security, failure behavior, implementation sequence, compatibility, and testability | Pass after correction: exact reader runtimes/auth/query bounds, projection variants, Cosmos floor, commands, and deferred branch gates added; zero unresolved findings |

The UI-specific plan-review criterion is not applicable to this
service/architecture slice: it introduces no new Flutter layout or visual
component. Phase 8.7 remains the server-driven workflow authority.

Planning verification on 2026-07-29:

- relative Markdown links in all 24 changed files: pass;
- `git diff --check`: pass;
- `./thesis.sh test deployment-contract --focused`: pass
  (66 root, 40 Optimizer, 87 Management, and 73 Deployer/Terraform tests);
- OrbStack MkDocs strict build: pass.

## 10. Failure Codes

Add or update:

```text
PROFILE_HISTORICAL_READ_ONLY
PROFILE_NO_ACTIVE_VERSION
PROFILE_COMPLETE_BUNDLE_MISSING
PROFILE_RAW_VISUALIZATION_COLOCATION_REQUIRED
PROFILE_L4_TO_L5_NOT_SUPPORTED
PROFILE_WORKLOAD_V2_REQUIRED
EVENTING_SCENARIO_REFERENCE_INVALID
PROFILE_CAPACITY_EVIDENCE_INCOMPLETE
RAW_HISTORY_QUERY_BINDING_INVALID
RAW_HISTORY_QUERY_INVALID
RAW_HISTORY_QUERY_UNAUTHORIZED
RAW_HISTORY_QUERY_LIMIT_EXCEEDED
TWIN_PROJECTION_BINDING_INVALID
TWIN_PROJECTION_PAYLOAD_INVALID
TWIN_MATERIALIZATION_POLICY_INVALID
STORAGE_TRANSITION_ROUTE_UNSUPPORTED
STORAGE_TRANSITION_IDENTITY_INVALID
STORAGE_TRANSITION_DEGRADED
STORAGE_TRANSITION_FAILED
STORAGE_TRANSITION_CHECKSUM_CONFLICT
LEGACY_SHARED_TOKEN_FORBIDDEN
LIVE_CAPACITY_GATE_PENDING
```

Errors expose only safe logical IDs, profile/version, scenario, stable reason,
and correlation ID.

## 11. Definition Of Done

- [ ] The functionality-first service evaluation is source-backed and frozen.
- [ ] `@1` and the Phase 8.8 Eventing evidence remain immutable.
- [ ] `@2` implements mandatory embedded domain behavior without flags.
- [ ] AWS, Azure, and provider-hosted GCP have complete L1-L5 bundles.
- [ ] L3-hot-to-L5 raw visualization and L3-hot-to-L4 Twin projection are
      implemented and priced; L4-to-L5 is absent.
- [ ] The L3-hot/L5 co-location and independent L4 rule is enforced and
      explained with all nine placements.
- [ ] Azure L3 hot remains Cosmos DB; Small/Medium serverless and Large
      calculated autoscale pass RU, storage, partition, and mover proofs.
- [ ] GCP uses BigQuery plus a bounded Firestore Twin API; Spanner is absent.
- [ ] GCP Grafana uses the selected/shared GKE cluster without a default
      dedicated node pool.
- [ ] The signed BigQuery plugin artifact, applicable license notice, version,
      and digest are frozen, or GCP fails closed pending a new datasource
      decision.
- [ ] Storage uses finite scheduled jobs and deterministic object manifests;
      unproven CDC/outbox/broker pipelines are absent.
- [ ] All six event routes and all twelve storage stage routes use the six
      reviewed short-lived identity directions.
- [ ] Same-provider paths create no cross-cloud route.
- [ ] GCP Grafana has an exact TLS LoadBalancer, source-range allowlist,
      generated access credential, endpoint output, and certificate evidence.
- [ ] Raw telemetry, materialized Twin state, and relationships retain distinct
      ownership and update rates.
- [ ] Twin entities, dashboard traffic, and seats are separate; scene/3D fields
      are rejected for v2.
- [ ] Each new-profile run resolves one immutable Eventing scenario reference;
      Flutter/callers cannot edit or duplicate its canonical fields.
- [ ] Both scenario families pass theoretical Small/Medium/Large admission or
      return an explicit unsupported result.
- [ ] Live uncertainty remains visible and no offline check claims live proof.
- [ ] Optimizer, Management, Deployer, Terraform, Flutter, research, and MkDocs
      responsibilities agree.
- [ ] 8.9A uses a clean branch, commits, and review cycle; 8.9B remains
      explicitly deferred.
- [ ] Two fresh reviews find zero unresolved findings.
- [ ] This corrected planning boundary is committed before implementation.
