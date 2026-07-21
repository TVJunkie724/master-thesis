---
title: "Phase 8 Complete Service-Bundle And Boundary Closure"
description: "PoC-focused corrective plan for five-layer-baseline@2 and six-layer-eventing@1."
tags: [architecture, services, multicloud, identity, capacity, optimizer, deployer, phase-8]
lastUpdated: "2026-07-22"
version: "1.3"
---

<!-- SOURCES:
- docs/research/phase_08_service_bundle_evaluation.md
- Phase 8.0-8.10 plans and handoff
- Immutable Phase 8.8 Eventing decision package
- Current Optimizer, Management, Deployer, Terraform, and Flutter behavior
- User-approved functionality-first PoC selection and mandatory single-cloud/multicloud coverage
EXTRACTED: 2026-07-22 | VERSION: 1.3
-->

# Phase 8 Complete Service-Bundle And Boundary Closure

## 0. Authority And Status

| Field | Value |
|---|---|
| Scope | Corrective gate for Phases 8.4-8.10 |
| Planning branch | `codex/phase-8-service-bundle-closure` |
| Decision evidence | [`phase_08_service_bundle_evaluation.md`](../../research/phase_08_service_bundle_evaluation.md) |
| Historical profile | `five-layer-baseline@1`, immutable read/verify/destroy only |
| New profiles | `five-layer-baseline@2`, then `six-layer-eventing@1` |
| Local environment | OrbStack; no live cloud execution |
| Selection rule | Functionality and theoretical Small/Medium/Large admissibility first; cost is measured, not minimized |
| PoC rule | Add only components required by the shared functional contract or by a measured capacity boundary |
| LaTeX | Excluded without separate approval |
| Review status | Two new full review passes completed with zero unresolved findings; explicit user approval remains required |

Where an older Phase 8 plan conflicts with this corrective gate, this document
controls new-profile implementation. Historical artifacts, digests, and
completion evidence remain unchanged and are annotated rather than rewritten.

The immutable `phase-08-eventing-implementation@1` package remains unchanged.
It proves domain-event bundles and bridge behavior, not the complete Twin.
Before Phase 8.9 implementation, this plan produces a separate immutable
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

1. Both new profiles implement the same mandatory domain behavior. There is no
   Eventing feature flag.
2. `five-layer-baseline@2` embeds domain-event ownership in the five existing
   responsibilities. `six-layer-eventing@1` moves the same contract into one
   independent Eventing responsibility.
3. Visualization has two explicit logical reads:
   `L3 hot -> L5` for raw/historical time series and `L4 -> L5` for current
   Twin state, relationships, model context, and scenes.
4. Raw telemetry is not proxied into or mutated through the semantic Twin
   store one message at a time.
5. For v1, `L3 hot`, `L4`, and `L5` form one provider-local online analytics
   bundle. This makes both read paths implementable with reviewed provider
   plugins and identities. L1, L2, L3 cool, L3 archive, and the Six-layer
   Eventing responsibility remain independently placeable.
6. GCP uses a bounded document-based Twin model in Firestore. Spanner Graph is
   not selected because the PoC requires only reviewed point and one-hop
   relationship queries, not arbitrary graph algorithms.
7. Storage transitions use finite scheduled batch jobs. Dedicated CDC,
   outbox, broker, and continuously running mover pipelines are rejected until
   evidence shows the simpler design cannot meet a scenario.
8. Same-provider domain-event paths create no bridge. Same-provider storage
   creates no cross-cloud copy, but hot-to-cool still uses the finite export
   job and cool-to-archive uses native lifecycle.
9. Cost includes every selected component, but a cheaper incomplete service
   never wins admission.

The current `five-layer-baseline@1` graph remains historical evidence even
where it differs. It is not silently upgraded to these semantics.

## 2. Shared Functional Contract

Every provider bundle for either new profile must supply:

1. authenticated bidirectional device communication;
2. telemetry ingestion and processing;
3. rule evaluation, extension action, notification workflow, command, and
   correlated device outcome;
4. hot time-series, cool object, and archive object persistence;
5. a semantic Twin model with current state and bounded relationship queries;
6. raw/historical visualization from L3 hot;
7. Twin-context and optional 3D visualization from L4;
8. typed domain-event delivery with ordering, retry, failure, and replay where
   required by the immutable Eventing contract;
9. same-cloud paths, all six directed cross-cloud domain-event routes, six
   storage trust directions, and twelve cross-cloud storage stage routes;
10. deterministic deployment, observability, cleanup, and cost ownership;
11. theoretical Small/Medium/Large capacity evidence with unresolved live
    behavior labeled honestly.

The profiles differ only in architecture ownership:

| Concern | `five-layer-baseline@2` | `six-layer-eventing@1` |
|---|---|---|
| Scientific responsibilities | Five | Six |
| Domain behavior | Always present | Always present and identical |
| Event publisher/consumer ownership | Existing producing/consuming responsibilities | Independent Eventing responsibility |
| Event service placement | Follows embedded provider bundle and remote edges | Event Layer receives its own provider assignment |
| Event cost | Attributed to the five owning responsibilities | Attributed to Eventing |
| L1-L5 services, workloads, query paths, and storage behavior | Shared | Shared unchanged |

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
| L3 hot | DynamoDB on-demand with device/time primary key and a scenario-derived `stored_at` window-shard GSI | Azure Data Explorer with a typed `stored_at` column, ingesting raw IoT telemetry through the IoT Hub/Event Hubs-compatible data connection | BigQuery time-series tables partitioned on `stored_at` and clustered by device ID, using the Storage Write API |
| L3 cool | S3 Standard-IA | Blob Cool | Cloud Storage Nearline |
| L3 archive | S3 Glacier Deep Archive | Blob Archive | Cloud Storage Archive |
| L4 Twin | IoT TwinMaker Standard pricing plan with a Lambda external-data connector and S3 scene assets | Azure Digital Twins with current graph/state and optional 3D Scenes assets | Cloud Run Twin API/materializer with Firestore Native collections for models, twins, current state, relationships, and scene bindings; Cloud Storage scene assets |
| L5 visualization | Amazon Managed Grafana 12 with the TwinMaker plugin and scene viewer | Azure Managed Grafana 12 with the Azure Data Explorer datasource and ADT query context; Azure Digital Twins 3D Scenes viewer when required | One Grafana OSS 12 pod on GKE with a Persistent Disk PVC, paid BigQuery Marketplace datasource `3.2.0`, and a minimal platform-owned Twin API/scene datasource-panel |

AWS keeps raw history in DynamoDB. TwinMaker's connector interface reads it
without copying every raw value into TwinMaker. Azure uses ADX as the hot
time-series store and ADT as the semantic graph; no separate Cosmos DB is
required by the selected contract. GCP uses BigQuery for raw history and
Firestore only for bounded semantic state; no Spanner Graph resource is
required.

TwinMaker uses its Standard pricing plan in all three scenarios because the
selected graph/query capability is unavailable in Basic. Tiered bundles are
not selected; their commitment would add a second scenario-dependent choice
without adding PoC functionality. Entity, data-access, query, connector,
scene, and Grafana costs remain explicit.

The GCP L5 deployment reuses the BifroMQ GKE cluster when L1 is also GCP.
Otherwise the online GCP bundle creates one GKE Standard cluster for Grafana.
It does not create a dedicated Grafana node pool unless later capacity evidence
requires one. The BigQuery plugin entitlement/license is a required fixed cost
and immutable evidence item; it is not treated as free because Grafana OSS is
free. Offline activation also requires the signed self-hosted plugin artifact,
license terms, entitlement evidence, and digest to be available. If they cannot
be obtained, GCP remains unsupported until a new reviewed datasource decision;
implementation may not silently replace the plugin.

The platform-owned Twin API/scene app plugin is a separate artifact with the
fixed ID `twin2multicloud-twin-app`. Grafana rejects unsigned plugins by
default, so the PoC image includes this source-reviewed, content-digested
artifact and sets `allow_loading_unsigned_plugins` to that one ID only.
Development mode, a wildcard/general unsigned-plugin policy, runtime download,
and plugin-admin installation are disabled. The paid BigQuery plugin remains
signed and is not covered by this exception. Offline tests fail if the image
digest, plugin digest/ID, or exact allowlist drifts; live readiness still tests
the backend resource route and browser panel. Private signing may replace this
bounded exception only in a later decision version.

Grafana uses one replica in all PoC scenarios so its SQLite state can remain on
one ReadWriteOnce Persistent Disk PVC. CPU and memory are sized per scenario;
dashboards and datasources are also provisioned declaratively. Multiple
replicas would require a separately reviewed shared Grafana database and are
therefore a capacity escalation, not a hidden default.

The cost model never assumes free BifroMQ-node headroom. When a GKE cluster is
already present, Grafana adds one incremental general-workload node to it;
otherwise the online bundle creates a one-node zonal GKE cluster. The initial
theoretical allocation is `e2-standard-4` for Small/Medium and
`e2-standard-8` for Large. This shares cluster control-plane/networking where
possible but does not create an isolation-only Grafana node pool.

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

### 3.3 Online Analytics Placement

For v1 of both new profiles:

```text
provider(L3_hot) == provider(L4) == provider(L5)
```

The three positive bundles are AWS/AWS/AWS, Azure/Azure/Azure, and
GCP/GCP/GCP. Any unequal online-analytics assignment fails before pricing with
`PROFILE_ONLINE_ANALYTICS_COLOCATION_REQUIRED`.

This is a bounded PoC decision, not a statement that cross-cloud queries are
impossible. Allowing independent L3-hot, L4, and L5 providers would require
six L3-to-L5 and six L4-to-L5 managed-Grafana plugin/authentication paths.
Those paths are not proven by the current services and would make datasource
engineering a second experiment. A later profile version may add them with a
separate capability decision.

Multicloud evaluation remains meaningful because L1, L2, L3 cool, L3 archive,
and the Six-layer Event Layer still receive independent provider assignments.
The three complete single-cloud assignments remain mandatory evaluation cases.

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

Only canonical domain-event ownership moves into the sixth responsibility.
Storage jobs, ADX ingestion, Twin materialization, provider logs, and
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

The bridge contract applies only to canonical domain events. It is not a
generic public Function endpoint and does not prove storage or visualization
transport. `INTER_CLOUD_TOKEN`, anonymous Function URLs, static cloud keys, and
shared bearer tokens are forbidden in both new profiles.

### 4.3 Dual Visualization Reads

Add two separate logical edges:

```text
L3 hot -- raw_history_query.v1 --> L5
L4 ----- twin_context_query.v1 --> L5
```

`raw_history_query.v1` supplies time-bounded telemetry series and aggregates.
`twin_context_query.v1` supplies models, current materialized state,
relationships, scene bindings, and safe logical IDs. Both contracts define
bounded query ranges, timeouts, idempotent read retry, correlation, safe error
codes, datasource/panel versions, identity, capacity, provisioning, and
cleanup.

Provider realizations are:

| Provider | Raw/history path | Twin-context path |
|---|---|---|
| AWS | Grafana/TwinMaker datasource -> TwinMaker external connector Lambda -> DynamoDB | Grafana/TwinMaker datasource -> TwinMaker entity/component/scene APIs |
| Azure | Managed Grafana -> ADX datasource -> raw telemetry tables | Managed Grafana -> ADX ADT-query plugin -> ADT current graph/state; conditional signed-in 3D Scenes Studio -> ADT plus private scene Blob container |
| GCP | Grafana BigQuery datasource -> BigQuery | Grafana Twin API/scene panel -> authenticated Cloud Run Twin API -> Firestore |

The AWS runtime may traverse TwinMaker for both calls, but the raw dataset and
cost remain owned by L3. Logical architecture edges describe responsibility
and data ownership, not every internal SDK hop.

Reader identities are exact and secretless:

| Provider | L5 reader identity and minimum target roles |
|---|---|
| AWS | Managed Grafana workspace role -> TwinMaker workspace read/query and exact S3 scene read; TwinMaker invokes the connector Lambda under its separate connector role |
| Azure | Azure Managed Grafana workspace managed identity -> ADX Viewer and Azure Digital Twins Data Reader; ADX receives that identity and its ADT query plugin must successfully use the caller's Entra token. Separately, conditional 3D Scenes viewers use their own Entra identity with Azure Digital Twins Data Reader and container-scoped Storage Blob Data Reader |
| GCP | Grafana Kubernetes service account -> GCP service account through Workload Identity for GKE -> dataset-scoped BigQuery Data Viewer, project-scoped BigQuery Job User, a custom role containing only `resourcemanager.projects.get`, and exact Cloud Run Invoker; the Twin API runtime identity receives only required Firestore/scene-object access |

No query path uses a service-account JSON key, Grafana API key as a cloud
credential, shared bearer token, or anonymous endpoint.

Microsoft documents Managed Grafana managed-identity authentication to ADX and
documents that the ADX ADT-query plugin authenticates with the caller's Entra
token. Treating the Managed Grafana identity as that end-to-end caller is a
source-backed inference, not yet a live proof. Before Azure live readiness, a
supervised query must demonstrate ADX Viewer plus Azure Digital Twins Data
Reader with this exact identity. Offline activation retains
`live_capacity_pending`; a failed supervised query marks the Azure online
bundle `live_readiness_failed` and reopens the service decision. It must not
fall back to a dashboard user's token or a static app secret.

The user-scoped 3D Scenes path is not such a fallback. When selected, its
private scene container receives the exact documented 3D Scenes Studio CORS
origin/method/header allowlist. Viewer users/groups receive only Azure Digital
Twins Data Reader and container-scoped Storage Blob Data Reader. The PoC does
not require browser scene editing, so it grants no Blob Contributor/Owner
role. Preview status and the interactive Entra login remain explicit Azure L5
limitations.

The GCP datasource enables the BigQuery and Cloud Resource Manager APIs and is
provisioned with plugin authentication type `gce`. A Standard-cluster Grafana
pod is scheduled only on a node with the GKE metadata server enabled. Google
documents that existing Compute Engine metadata-server authentication works
unchanged through Workload Identity Federation for GKE; Grafana documents
`gce` metadata authentication and the additional project-read permission.
GCP live readiness still requires plugin `Save & test` plus a bounded BigQuery
query under the Grafana pod identity. Offline activation retains
`live_capacity_pending`; a failed supervised query marks the GCP online bundle
`live_readiness_failed` and reopens the datasource decision. No JSON
service-account key is permitted.

### 4.4 Twin Materialization

Add `twin-materialization-policy.v1`:

- raw telemetry is written to L3 hot and stays queryable there;
- selected state changes materialize the latest operational state in L4;
- model, Twin, relationship, and scene-binding changes update L4 explicitly;
- no provider performs one graph mutation for every raw telemetry message;
- canonical event IDs make materialization idempotent;
- stale/out-of-order state follows one declared per-device policy;
- every provider exposes the same bounded logical fields.

The GCP query set is intentionally limited to:

- Twin by ID;
- current state by Twin ID;
- direct incoming/outgoing relationships for one Twin;
- model lookup;
- scene binding lookup;
- explicit materialization write by idempotency key.

The initial Firestore model is equally bounded:

```text
models/{model_id}
twins/{twin_id}
twins/{twin_id}/sources/{source_id}   # current values + last event/sequence
relationships/{relationship_id}      # from_id, to_id, type
scene_bindings/{twin_id}
```

Composite indexes cover only `(from_id, type)` and `(to_id, type)` relationship
queries. A transaction compares the stored source sequence/event ID before
updating current state, so duplicate or stale delivery does not create a
separate unbounded idempotency collection.

When `needs3DModel=false`, no provider creates scene-specific resources. When
it is true, the common PoC scene contract is intentionally small: GLB assets,
stable scene-node-to-Twin bindings, and latest selected state values for
overlays; no browser editor or arbitrary scene scripting is required. AWS uses
the TwinMaker scene viewer, Azure uses ADT 3D Scenes, and GCP uses the selected
custom Grafana panel. The GCP browser calls only an authenticated Grafana
backend-plugin resource route. That backend invokes the Cloud Run Twin API
with the Grafana workload identity; the Twin API reads the exact Cloud Storage
object with its own identity and streams it back. Buckets, Twin API, and assets
are never public, and no signed URL or extra gateway is introduced. The
100-MiB Large asset and overlay refresh are explicit live latency/memory gates.

Arbitrary multi-hop graph algorithms, graph analytics, and ad hoc traversal
are outside the profile. If they become requirements, the service decision is
reopened instead of silently adding Spanner Graph.

### 4.5 Minimal Storage Movement

Storage movement is a data-plane batch operation, not a canonical domain
event. One portable `storage-mover` image has source adapters for
DynamoDB/ADX/BigQuery and object adapters for S3/Blob/Cloud Storage.

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
for both new profiles. With `H = hotStorageDurationInMonths`,
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
Azure filters the ADX `stored_at` column; GCP prunes the BigQuery `stored_at`
partition. A full-table scan is not an admissible Large implementation.

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
the Optimizer receives only the server-resolved snapshot. Both new profiles use
the same selected object. Inline/custom Eventing values are outside v1 because
the immutable schema explicitly describes bounded synthetic S/M/L scenarios.

`needs3DModel=false` requires `sceneEntityCount=0` and
`totalSceneAssetSizeMiB=0`. `needs3DModel=true` requires both values to be
greater than zero. This same cross-field rule is shared by Management,
Optimizer, and Flutter.

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
keep the complete retired field set for reproduction. New requests use the
single workload-v2 object plus `eventingScenarioId`; they cannot submit either
an inline Eventing object or the old scene, dashboard, seat, Eventing, or
error-handling surrogates. `numberOfDeviceTypes` remains valid because it sizes
the distinct type-specific L2 processors rather than duplicating Eventing
load. Migration never invents `twinEntityCount`, `sceneEntityCount`,
`totalSceneAssetSizeMiB`, an Eventing scenario ID, or Eventing workload values.

Freeze `core-small-v2`, `core-medium-v2`, and `core-large-v2` from the research
evaluation. Preserve the immutable Phase 8.8 Eventing scenarios and pair them
only by size in Phase 8.10.

The Large core input is 5,000 records/s and exactly 4,000 KiB/s
(3.90625 MiB/s) before transport overhead. One five-minute batch is
1,200,000 KiB (1,171.875 MiB, approximately 1.145 GiB). The
initial storage-job parallelism is one task for Small, one for Medium, and
three partitioned tasks for Large; the decision-package calculator derives the
exact value from input bytes and a 512-MiB maximum source partition per task.

For workload v2, steady-state logical storage volume is calculated without
double counting: monthly ingest multiplied by `H` for hot, `C - H` for cool,
and `A - C` for archive. The 48-hour source grace, provider minimum-storage
charges, lifecycle operations, one transfer per stage, and cross-cloud egress
are separate explicit cost terms. Historical `@1` golden costs are not
recalculated.

| Bundle | Small | Medium | Large |
|---|---|---|---|
| AWS TwinMaker | 100 entities | 4,000 entities | 30,000 entities; external raw telemetry remains outside TwinMaker |
| AWS Grafana | Grafana 12 workspace | Same | Same; seats and measured concurrency remain distinct |
| Azure ADX | `Standard_E8ads_v5`, capacity 2 | Same, queued ingestion as required | Capacity 4, queued ingestion |
| Azure Grafana | Standard X1 | Standard X1 | Standard X2 |
| GCP Firestore L4 | Bounded document/one-hop queries | Same schema, scenario-derived operations | 50 state materializations/s plus one graph/model update/s |
| GCP Grafana | One pod, one incremental `e2-standard-4` node, Persistent Disk PVC | Same initial node with calculated pod CPU/RAM | One pod, one incremental `e2-standard-8` node, Persistent Disk PVC, optional scene panel; no default HA/shared database or isolation-only node pool |
| Storage mover | One finite task/batch | One finite task/batch | Three finite tasks/batch |

The exact Eventing Kinesis/Event Hubs/Pub/Sub/BifroMQ allocations remain pinned
by Phase 8.8. All database partitions, ADX/BigQuery ingestion, Firestore
indexes, connector concurrency, Grafana replicas, scheduled-job resources,
retry, object counts, transfer, and observability dimensions are emitted into
RDS v2 and priced.

Published quotas prove only theoretical admission. Workload-dependent query,
connector, scene, broker, bridge, identity, and storage-job behavior stays
`live_capacity_pending` until supervised evidence exists.

## 6. Immutable Complete-Service Decision Package

Before Phase 8.9 runtime changes, create:

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

1. resolve `@2` and Six-layer in separate runs;
2. reject the complete retired-field set for both new profiles;
3. resolve and digest-check the required Eventing scenario reference, then
   resolve one of three online analytics bundles before pricing;
4. represent both `L3_hot_to_L5_raw_history` and
   `L4_to_L5_twin_context` edges;
5. derive six event routes and both six-direction storage stages from
   assignments;
6. create no cross-cloud bridge or copy for a same-provider edge while still
   resolving the required local hot exporter and native archive lifecycle;
7. calculate all three single-cloud and all otherwise admissible mixed paths;
8. price each service, fixed capacity, transfer, identity, observability, and
   cleanup owner exactly once;
9. keep `@1` only in the historical reproduction path.

### Management And Flutter

Management persists workload v2, the Eventing scenario ID/digest/snapshot, the
online bundle, both visualization edges, generic components/edges/capacity,
and immutable decision digests. New Twins receive no active profile until
`@2` passes all gates. Existing `@1` records stay readable and destroyable.

Flutter shows Five-layer v2 and Six-layer v1 only after server activation. It
shows events as mandatory profile behavior, selects one immutable Eventing
S/M/L scenario and renders its fields read-only, separates
Twin/scene/dashboard inputs, and explains the provider-local online analytics
bundle. It does not offer inline Eventing fields or Eventing/GCP capability
flags.

### Deployer And Terraform

Add static catalog/Terraform implementations for:

- the three online analytics bundles and both logical read edges;
- AWS TwinMaker connector and Managed Grafana provisioning;
- Azure ADX/ADT/Managed Grafana/3D provisioning without Cosmos;
- GCP BigQuery, Firestore Twin API, Grafana on GKE, plugins, identity, and
  scene assets without Spanner or a dedicated node pool, including the exact
  single-ID unsigned custom-plugin exception;
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
unchanged. Annotate that they do not prove the new dual-query or provider-hosted
GCP target. Phase 8.3 registers new versioned bundle components only in 8.9A.

### 8.4-8.7

Preserve historical selections and migration 022. Phase 8.5 and 8.6 finish the
generic resolver/compiler dark; they must support generic multiple typed edges
but do not activate either new profile. Phase 8.7 implements server-driven
profile/workload UI and the no-active-profile state.

### 8.8

Preserve every immutable Eventing artifact byte and digest. Add documentation
only: its proof covers domain events, not online analytics or storage jobs.

### 8.9A

Implement workload v2, RDS v2/Manifest v4, the three complete online bundles,
dual visualization reads, minimal storage jobs, corrected identity, and
`five-layer-baseline@2`. Review to zero findings and commit before branching.

### 8.9B

Branch from reviewed 8.9A. Add only the independent Eventing responsibility
using the unchanged Phase 8.8 bundle/bridge decisions. Do not duplicate L1-L5,
storage, query, or Twin components. Review to zero findings and commit.

### 8.10

Evaluate three single-cloud paths, all admissible mixed paths, explicit
rejections, both scenario families, and the fair `@2` versus Six-layer delta.
Report provider-hosted GCP and live-capacity uncertainty as threats to validity.

Implementation sequence and clean commits:

1. commit this corrected plan/evaluation boundary;
2. build, review, and commit the immutable complete-service decision package;
3. finish/review/commit the dark Phase 8.6 compiler;
4. create the reviewed foundation branch and integrate the compiler commit;
5. implement/review/commit Phase 8.7;
6. branch and implement/review/commit 8.9A Five-layer v2;
7. branch and implement/review/commit 8.9B Six-layer v1;
8. branch and implement/review/commit Phase 8.10 evaluation.

A later branch never starts from an unreviewed or dirty boundary.

## 9. Verification

Required offline gates include:

- immutable `@1` and Eventing-package byte/digest stability;
- schema/reference/digest/generated-copy drift tests;
- three positive and every unequal online-analytics placement fixture;
- both visualization edges for AWS, Azure, and GCP;
- bounded GCP Twin query contract and a negative arbitrary-traversal fixture;
- three single-cloud and all admissible mixed calculations;
- all six event routes, six storage identity directions, twelve cross-cloud
  storage stage routes, and same-provider local export/lifecycle behavior with
  no remote route;
- storage late-event, duplicate-window, partial object, checksum conflict,
  retry, expired credential, destination outage, manifest, lifecycle, and
  cleanup tests, including delayed-export logical expiry versus physical
  lifecycle timing;
- Small/Medium/Large deterministic capacity and cost calculations;
- Optimizer, Management, Deployer, Terraform no-apply, Flutter, platform,
  docs strict/link/secret, and compatibility suites;
- no live cloud apply, deploy, destroy, paid operation, or capacity claim;
- two separate full review passes with zero unresolved findings.

Use OrbStack and existing project commands. Record services already running
before a test and stop only services started by that invocation.

### Review Record

| Pass | Scope | Result |
|---|---|---|
| 1 | Architecture and concept consistency across the service evaluation, all Phase 8 plans, Handoff, research design, and current docs | Findings corrected: PoC scope, complete retired-field inventory, same-provider storage semantics, lifecycle-delay semantics, complete-service/Eventing composition, offline activation versus live readiness, and exact GCP/Azure visualization boundaries |
| 2 | Builder/API contract, workload math, identity/security, failure behavior, implementation sequence, compatibility, and testability | Zero unresolved findings after rerun; immutable `@1` and Phase 8.8 evidence remain untouched |

The second pass also re-ran the strict MkDocs build, the immutable Eventing
package validator, repository diff checks, and the focused deployment-contract
gate. User approval is still a separate prerequisite for implementation.

## 10. Failure Codes

Add or update:

```text
PROFILE_HISTORICAL_READ_ONLY
PROFILE_NO_ACTIVE_VERSION
PROFILE_COMPLETE_BUNDLE_MISSING
PROFILE_ONLINE_ANALYTICS_COLOCATION_REQUIRED
PROFILE_WORKLOAD_V2_REQUIRED
EVENTING_SCENARIO_REFERENCE_INVALID
PROFILE_CAPACITY_EVIDENCE_INCOMPLETE
RAW_HISTORY_QUERY_BINDING_INVALID
TWIN_CONTEXT_QUERY_BINDING_INVALID
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
- [ ] `@2` and Six-layer share mandatory domain behavior without flags.
- [ ] AWS, Azure, and provider-hosted GCP have complete L1-L5 bundles.
- [ ] Both L3-hot-to-L5 and L4-to-L5 logical reads are implemented and priced.
- [ ] The online analytics co-location rule is enforced and explained.
- [ ] GCP uses BigQuery plus a bounded Firestore Twin API; Spanner is absent.
- [ ] GCP Grafana uses the selected/shared GKE cluster without a default
      dedicated node pool.
- [ ] The signed paid BigQuery plugin artifact, entitlement, license, cost, and
      digest are frozen, or GCP fails closed pending a new datasource decision.
- [ ] Storage uses finite scheduled jobs and deterministic object manifests;
      unproven CDC/outbox/broker pipelines are absent.
- [ ] All six event routes and all twelve storage stage routes use the six
      reviewed short-lived identity directions.
- [ ] Same-provider paths create no cross-cloud route.
- [ ] Raw telemetry, materialized Twin state, relationships, and scene state
      retain distinct ownership and update rates.
- [ ] Twin entities, scene entities, dashboard traffic, and seats are separate.
- [ ] Each new-profile run resolves one immutable Eventing scenario reference;
      Flutter/callers cannot edit or duplicate its canonical fields.
- [ ] Both scenario families pass theoretical Small/Medium/Large admission or
      return an explicit unsupported result.
- [ ] Live uncertainty remains visible and no offline check claims live proof.
- [ ] Optimizer, Management, Deployer, Terraform, Flutter, research, and MkDocs
      responsibilities agree.
- [ ] 8.9A and 8.9B use separate branches, clean commits, and review cycles.
- [x] Two new reviews find zero unresolved findings.
- [x] This corrected planning boundary is committed before implementation.
