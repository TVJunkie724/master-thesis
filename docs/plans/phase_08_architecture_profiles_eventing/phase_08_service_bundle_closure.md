---
title: "Phase 8 Five-Layer v2 Service-Bundle And Boundary Closure"
description: "PoC-focused corrective plan for the executable five-layer-baseline@2 placement experiment."
tags: [architecture, services, multicloud, identity, capacity, optimizer, deployer, phase-8]
lastUpdated: "2026-08-03"
version: "1.13"
---

<!-- SOURCES:
- docs/research/phase_08_service_bundle_evaluation.md
- Phase 8.0-8.10 plans and handoff
- Immutable Phase 8.8 Eventing decision package
- Current Optimizer, Management, Deployer, Terraform, and Flutter behavior
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_9_six_layer_eventing_implementation.md
- Current official Grafana, AWS Managed Grafana, Azure Managed Grafana, Lambda
  Function URL, and Firestore database/IAM documentation checked on 2026-08-03
- User-approved functionality-first PoC selection, L3-hot/L5 co-location,
  independent L4 placement, Cosmos DB and Firestore L3 continuity, and mandatory
  single-cloud/multicloud coverage
EXTRACTED: 2026-08-03 | VERSION: 1.13
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
| Sequential profile | `six-layer-eventing@1`; its v2 plan is complete but its branch starts only from reviewed Five-layer v2 |
| Local environment | OrbStack; no live cloud execution |
| Selection rule | Provider service bundles are chosen for required functionality and theoretical Small/Medium/Large admissibility, not lowest service price; after that freeze, the Optimizer still ranks complete placement candidates by estimated cost within one profile |
| PoC rule | Add only components required by the shared functional contract or by a measured capacity boundary |
| LaTeX | Excluded without separate approval |
| Review status | Six prior planning passes plus three complete-service package reviews have zero unresolved findings; implementation was explicitly authorized on 2026-08-03 and is governed by the reviewed execution plan |

Where an older Phase 8 plan conflicts with this corrective gate, this document
controls new-profile implementation. Historical artifacts, digests, and
completion evidence remain unchanged and are annotated rather than rewritten.

The immutable `phase-08-eventing-implementation@1` package remains unchanged.
It proves the domain-event behavior and bridge primitives reused by embedded
Five-layer v2 ownership, not the complete Twin and not a Six-layer runtime
approval. Before Phase 8.9A implementation, this plan produces a separate immutable
`phase-08-complete-service-bundles@1` package, now approved at the offline
decision boundary. Runtime activation requires both
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
10. GCP retains Firestore Native Standard edition as L3 hot. BigQuery is not
    selected merely to obtain a native analytical Grafana datasource; its
    analytics advantages remain a documented later alternative.
11. Cost includes every selected component, but a cheaper incomplete service
    never wins admission.
12. Every successful deployment exposes one usable L4 browser surface and one
    usable L5 browser surface through a typed, secret-safe Management read
    model. Browser identities are preflighted independently from deployment
    credentials.
13. GCP uses one named Firestore database per deployment. L3 and L4 keep
    separate collection/index schemas, code paths, identities, and cost
    attribution, while the weaker database-wide IAM isolation is accepted and
    reported as a PoC limitation.

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
11. deterministic post-deployment access to a semantic L4 browser UI and a
    raw/rollup L5 dashboard for the selected providers;
12. theoretical Small/Medium/Large capacity evidence with unresolved live
    behavior labeled honestly.

Six-layer implementation remains sequentially deferred until reviewed 8.9A,
but its delta plan is now complete in
[`phase_08_9_six_layer_eventing_implementation.md`](phase_08_9_six_layer_eventing_implementation.md).
It must reuse the committed Five-layer v2 L1-L5 digest unchanged and add only
the ownership and placement delta introduced by the independent Eventing
responsibility. This Five-layer document does not activate that profile.

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
| L3 hot | DynamoDB on-demand with device/time primary key and a scenario-derived `stored_at` window-shard GSI | Cosmos DB for NoSQL with `/device_id`, bounded device/time queries, selective indexing, and scenario-selected serverless/autoscale capacity | Firestore Native Standard edition with scattered event IDs, scenario-derived timestamp shards, bounded device/time queries, and selective composite indexes |
| L3 cool | S3 Standard-IA | Blob Cool | Cloud Storage Nearline |
| L3 archive | S3 Glacier Deep Archive | Blob Archive | Cloud Storage Archive |
| L4 Twin | IoT TwinMaker Standard pricing plan for current semantic state and relationships | Azure Digital Twins with current graph/state | Cloud Run Twin API/materializer backed by the deployment Firestore Native database, plus one read-only Cloud Run Twin Explorer protected by direct IAP |
| L5 visualization | Amazon Managed Grafana 12 with a typed provider-local raw-history reader datasource | Azure Managed Grafana 12 with its supported JSON API datasource and a typed provider-local Cosmos reader | One Grafana OSS 12 pod on GKE with a Persistent Disk PVC, the signed Infinity datasource, and a typed provider-local Firestore reader |

AWS keeps raw history in DynamoDB and Azure keeps it in Cosmos DB. Their
provider-local reader APIs expose the same bounded `raw_history_query.v1`
contract to managed Grafana. GCP keeps raw history and the bounded Twin model
in one named Firestore database when it owns both L3 and L4. The logical
component IDs `gcp.firestore.l3_hot` and `gcp.firestore.l4_twin` retain
separate collections, indexes, runtime code paths, operations, and cost
attribution, but database creation is a shared support resource priced once.
No provider routes the mandatory dashboard through L4, and no Spanner Graph
resource is required. This PoC simplification accepts that Firestore server
libraries use database-wide IAM rather than collection-level Security Rules;
the exact residual isolation boundary is frozen in
[`phase_08_layer_access_handoff.md`](phase_08_layer_access_handoff.md).

The three Grafana reader realizations are exact supporting components,
not another scientific layer:

| Provider | Reader runtime | Datasource/authentication |
|---|---|---|
| AWS | Lambda HTTPS Function URL with application-level reader-key validation | `marcusolsson-json-datasource`; one generated 256-bit deployment-scoped key in `secureJsonData.httpHeaderValue1` under header `X-Twin-Reader-Key`; Lambda stores only its hash |
| Azure | Functions Flex HTTP route with `AuthLevel.FUNCTION` | Standard-tier `marcusolsson-json-datasource`; one deployment-scoped Function key in `secureJsonData.httpHeaderValue1` under header `x-functions-key` |
| GCP | Cloud Run HTTPS service with application-level reader-key validation and a read-only Firestore identity | Signed `yesoreyeram-infinity-datasource`; `jsonData.httpHeaderName1=X-Twin-Reader-Key`, one generated 256-bit deployment-scoped key in `secureJsonData.httpHeaderValue1`; the service stores only its hash |

The JSON API datasource is a deliberately bounded PoC dependency, not a
long-term platform recommendation. Grafana marks it as maintenance-only and
recommends Infinity for new functionality, but the current primary
documentation does not publish a fixed support-end date. The
complete-service package must therefore freeze its plugin ID, selected
version, Grafana-12 compatibility evidence, and provider-specific availability
evidence: the exact version in the Amazon Managed Grafana plugin catalog and
JSON API support in Azure Managed Grafana Standard. Deployment preflight
repeats the catalog/support check before any workspace mutation and `Save &
test` plus the bounded raw/rollup queries are live-readiness gates. If the
plugin is unavailable or incompatible, the affected AWS/Azure L3-hot/L5 bundle
is unsupported until a newly reviewed datasource decision replaces it.
Implementation must not invent a calendar expiry or silently substitute
Infinity, ADX, or another storage/query path.

The three HTTPS routes are internet-reachable PoC read boundaries. AWS and
Azure use managed Grafana outside a selected private network; GCP deliberately
avoids adding a Serverless VPC Access/private-ingress design to the PoC. The
routes are never application-anonymous: the reader credential,
strict query bounds, read-only backend identity, datasource permissions, and
concurrency limits are mandatory. Private connectivity is a later
hardening option, not an unpriced hidden component.

Reader concurrency is deterministic rather than an unspecified autoscaling
promise:

```text
readerMaxConcurrentRequests =
  max(2, ceil(aggregate_query_rate_per_second * 10 seconds * 1.25))
```

This resolves to 2/3/42 for Small/Medium/Large. AWS uses Lambda reserved
concurrency, Azure uses Flex maximum instances with HTTP concurrency one, and
GCP uses Cloud Run maximum instances with container concurrency one. Each
runtime scales from zero where the selected service permits it. Timeout
rejection, maximum-instance throttling, request count, duration, and logs are
priced and tested; a rejected/throttled request never falls back to an
unbounded database query.

The initial reader allocation is 512 MiB for Lambda, 512 MiB Flex instances,
and 1 vCPU/512 MiB Cloud Run instances. Provider preflight proves the resolved
2/3/42 ceiling fits the AWS regional concurrency balance, Azure regional Flex
memory/core quota, or GCP regional CPU/memory quota. A missing quota proof
returns `PROFILE_CAPACITY_EVIDENCE_INCOMPLETE`; it does not silently increase
concurrency or memory. Query latency and memory remain live gates.

TwinMaker uses its Standard pricing plan in all three scenarios because the
selected graph/query capability is unavailable in Basic. Tiered bundles are
not selected; their commitment would add a second scenario-dependent choice
without adding PoC functionality. Entity, query, projection-adapter, and
Grafana costs remain explicit. A TwinMaker external-history connector,
TwinMaker Grafana plugin, and scene resources are not selected.

The GCP L5 deployment reuses the BifroMQ GKE cluster when L1 is also GCP.
Otherwise the online GCP bundle creates one GKE Standard cluster for Grafana.
It does not create a dedicated Grafana node pool unless later capacity evidence
requires one. The selected Infinity plugin is maintained by Grafana Labs and
supports server-side API-key headers. Offline activation still requires its
signed self-hosted artifact, applicable license notice, version, and digest to
be available. If they cannot be obtained, GCP remains unsupported until a new
reviewed datasource decision; implementation may not silently replace the
plugin.

No custom Twin/scene Grafana plugin is selected. The content-addressed GCP
Grafana image contains only the pinned Grafana runtime and signed Infinity
plugin. Development mode, unsigned-plugin loading, runtime download, dangerous
HTTP methods, and UI plugin installation are disabled.

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
certificate in a Kubernetes Secret, separate internal provisioning Admin and
human Viewer credentials, and a non-empty `loadBalancerSourceRanges`
allowlist. The static IP, endpoint, Viewer username, and certificate
fingerprint are safe deployment outputs. The Viewer password is available
only through an owner-scoped rotate-and-reveal operation; no password-read
output exists. Plaintext, `0.0.0.0/0`, public buckets, public Twin APIs, and
credentials in contracts/tfvars/logs are forbidden. Public DNS, a public CA
certificate, and GKE IAP are not added to this PoC version. Direct IAP is used
only by the separate GCP L4 Cloud Run Twin Explorer.

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

### 3.4 Post-Deployment Layer Access

Every one of the nine placements resolves access separately from its L4 and
L5 assignments. The exact service, authentication, safe output, initial
content, readiness, Management API, Flutter, and secret-rotation rules are
binding in
[`phase_08_layer_access_handoff.md`](phase_08_layer_access_handoff.md).

| Layer/provider | Browser surface | Interactive access |
|---|---|---|
| L4 AWS | IoT TwinMaker console | IAM Identity Center account assignment and deployment-scoped read-only permission set |
| L4 Azure | Azure Digital Twins Explorer | Entra principal with `Azure Digital Twins Data Reader` |
| L4 GCP | Read-only Cloud Run Twin Explorer | Google principal with direct Cloud Run IAP access |
| L5 AWS | Amazon Managed Grafana | IAM Identity Center workspace association |
| L5 Azure | Azure Managed Grafana | Entra principal with Grafana role |
| L5 GCP | Grafana OSS on GKE | Generated human Viewer credential, separate from internal Admin and datasource secrets |

The configuration workspace reuses or creates the required bounded deployment
CloudConnections through
[`phase_08_guided_cloud_bootstrap.md`](phase_08_guided_cloud_bootstrap.md), then
preflights the required interactive principals. The user never has to manually
construct a bounded deployment CloudConnection, and the platform never treats a
deployment credential as a browser password. Request-scoped bootstrap
authority creates the bounded connection and is released before any external
pause. AWS L4 organization-instance activation and first-time/no-organization
or external-user GCP IAP OAuth setup can require an account owner; a missing
prerequisite blocks deployment preparation with a typed remediation state and
resumes through the generated CloudConnection. Offline tests cannot claim that
a human browser sign-in succeeded.

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

The v2 PoC telemetry schema contains exactly one visualized numeric
`metric`/`value` pair per accepted record. Supporting multiple visualized
metrics per record would multiply rollup operations and requires a later
workload-contract version; arbitrary non-visualized payload fields remain part
of the raw envelope only.

For all three providers the Grafana datasource sends one
`GET /raw-history/v1` request:

```text
device_id                required; one deployment-owned device
metric                   required; one configured numeric metric
from                     required RFC 3339 UTC timestamp
to                       required RFC 3339 UTC timestamp; from < to
bucket_seconds           one of 0, 3600
limit                    1..1000; default 1000
cursor                   optional opaque provider-signed continuation token
```

`bucket_seconds=0` is allowed only for ranges up to 24 hours. Aggregated
queries may cover at most 30 days. A response contains only
`schema_version`, `device_id`, `metric`, ordered `points`, `next_cursor`,
`truncated`, and `correlation_id`. A raw point contains `stored_at`,
`event_time`, and `value`; an aggregate point contains `bucket_start`, `min`,
`max`, `avg`, and `count`. The implementation returns at most 1,000 points and
times out after ten seconds; it never performs an unbounded scan.

To make the 30-day aggregate contract finite on all three operational NoSQL
stores, L2 writes one idempotent hourly rollup beside each durably accepted raw
record. DynamoDB uses a transaction over the raw item and an hourly rollup
item, Cosmos DB uses a transactional batch inside the `/device_id` logical
partition, and Firestore uses one transaction over the raw document and hourly
rollup document. A duplicate raw event therefore cannot increment a rollup
twice. The rollup table/container/collection belongs to the same selected L3
service and is not another service or pipeline. Its extra reads, writes,
storage, indexes, and transaction operations are explicit capacity and cost
dimensions. One hourly point per device/metric keeps a 30-day result at no more
than 720 points and within the one-month hot-data boundary.

The physical rollup ownership is exact:

| Provider | Rollup storage |
|---|---|
| AWS | Separate DynamoDB table with `device_id#metric` partition key and `bucket_start` sort key |
| Azure | `kind=hourly_rollup` items in the L3 Cosmos container, retaining `/device_id` as partition key |
| GCP | `hourly_rollups` collection in the L3 Firestore database |

The writer reads the current rollup version, calculates the next
count/sum/min/max, and atomically commits a create-if-absent raw record plus a
compare-and-swap rollup update. DynamoDB uses `TransactWriteItems` conditions
across the raw and rollup tables; Cosmos uses one transactional batch in the
device partition with raw create and rollup ETag precondition; Firestore uses a
transaction. A missing rollup is created with version one. A version conflict
is retried at most three times with bounded jitter; an already-existing raw ID
with the same canonical payload digest returns idempotent success without
changing the rollup; the same ID with a different digest is a terminal
idempotency conflict. Exhausted version conflict or partial-failure evidence
fails the L3 write for upstream retry rather than acknowledging inconsistent
raw/aggregate state.

Every rollup stores `device_id`, `metric`, UTC `bucket_start`, finite `min`,
finite `max`, finite `sum`, and non-negative JSON-safe `count`; `avg` is returned
as `sum/count` and is not stored independently. Storage movement exports only
canonical raw records. Derived rollups expire with the L3 hot boundary plus
the same 48-hour failure-evidence grace and are never copied to cool/archive.
`bucket_start` is the UTC hour floor of provider-owned `stored_at`, not
device-owned `event_time`, so late device timestamps cannot reopen an already
expired ingestion bucket.

Boundary datatypes are closed: IDs and metric names are non-empty UTF-8 strings
within the existing canonical-envelope size limits; timestamps are RFC 3339
UTC strings; values/min/max/sum/avg are finite JSON numbers; counts and limits
are non-negative JSON-safe integers no greater than
`9_007_199_254_740_991`, preserving exact Dart Web representation. `NaN`,
infinity, unknown fields, invalid UTF-8, and a cursor over 16 KiB are rejected.

The opaque cursor is base64url canonical JSON containing profile, deployment,
provider, query-parameter digest, expiry no later than fifteen minutes, and
provider continuation state. It is authenticated with HMAC-SHA-256 using the
stored SHA-256 reader-key verifier; changing provider, query, deployment, or
expiry invalidates it. Firestore continuation state contains the last
`stored_at` and document ID for every resolved timestamp shard.

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
| GCP | Grafana OSS -> pinned Infinity datasource -> typed read-only Cloud Run service -> Firestore |

Reader identities are exact and bounded:

| Provider | L5 reader identity and minimum target roles |
|---|---|
| AWS | One generated deployment-scoped read credential -> exact reader API stage; reader runtime role -> exact DynamoDB table/index read |
| Azure | One generated deployment-scoped read credential -> exact Function reader route; Function managed identity -> Cosmos DB built-in data reader on the exact account/database/container |
| GCP | One generated deployment-scoped read credential -> exact Cloud Run reader route; reader service account -> `roles/datastore.viewer` constrained by IAM condition to the deployment Firestore database |

Reader credentials exist only in the provider endpoint and Grafana
`secureJsonData`. The Deployer may retrieve them once for datasource
provisioning but must not write them to persisted manifests, tfvars, state
projections, logs, fixtures, or docs. Destroy removes the endpoint credential
with the deployment. This local, read-only credential is not reused by
`twin_projection.v1`; remote projection remains short-lived and secretless.

The GCP datasource is provisioned with the exact Cloud Run base URL in its
allowed-host list, backend parsing, GET-only queries, and the generated reader
key in `secureJsonData`. Because Infinity does not mint Google ID tokens, Cloud
Run sets `invoker_iam_disabled=true` and the application rejects every request
without the constant-time validated deployment key. If organization policy
forbids that public invocation boundary, the GCP L3/L5 bundle is unsupported in
this profile version rather than gaining an unplanned gateway. The reader
service account has `roles/datastore.viewer` only through an exact-database
IAM condition; the Grafana pod receives no Firestore role or service-account
JSON key. GCP live readiness requires plugin `Save & test`, a
bounded raw query, a bounded 30-day hourly-rollup query, and an HTTPS browser
request from an allowed CIDR that verifies the recorded certificate
fingerprint. Offline activation retains `live_capacity_pending`; a failed
supervised query or endpoint/authentication check marks the GCP L3/L5 bundle
`live_readiness_failed`.

The L3 Firestore schema is:

```text
telemetry/{sha256(deployment_id,event_id)}
hourly_rollups/{sha256(device_id,metric,bucket_start)}
```

Raw records carry `device_id`, `metric`, provider-owned `stored_at`,
device-owned `event_time`, `value`, and a scenario-derived `timestamp_shard`.
The shard value is
`uint32_be(sha256(deployment_id || 0x00 || event_id)[0:4]) mod shard_count`.
Single-field indexes for `stored_at`, `event_time`, `timestamp_shard`, and
rollup `bucket_start` are disabled. Reviewed composite indexes cover
`(device_id, metric, timestamp_shard, stored_at)` for raw history,
`(timestamp_shard, stored_at)` for the mover, and
`(device_id, metric, bucket_start)` for hourly rollups. The high-cardinality
device/metric prefix distributes rollup-index entries; raw sequential time is
explicitly sharded. The reader fans out over the finite raw shard set, merges
in timestamp order, and records per-shard continuation state in the opaque
cursor.

Firestore runtime identities remain distinct even though the deployment uses
one database:

| Runtime | Role boundary |
|---|---|
| L3 writer/rollup transaction | `roles/datastore.user`, conditioned to the deployment database; application routes allowlist only L3 collections |
| L3 Grafana reader | `roles/datastore.viewer`, conditioned to the deployment database; reader contract exposes only L3 collections |
| L3 storage mover/expiry | Separate service account with `roles/datastore.user`, conditioned to the deployment database and bounded to L3 code paths |
| L4 Twin API/materializer | `roles/datastore.user`, conditioned to the deployment database; application routes allowlist only L4 collections |
| L4 Twin Explorer | `roles/datastore.viewer`, conditioned to the deployment database; read API allowlists only L4 collections and bounded queries |

Firestore server libraries bypass collection Security Rules and the selected
IAM roles are database-scoped. In an all-GCP placement, L3 and L4 identities
can therefore technically reach the other layer's collections even though
their applications and indexes forbid those routes. This is an accepted,
visible PoC limitation, not a collection-level IAM claim. The Deployer alone
creates the database and indexes and never passes its broader provisioning
credential into a runtime. A future strict-isolation profile may restore two
databases.

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

The L4 collection group in the shared deployment Firestore database has this
bounded model:

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

Every L4 implementation also provisions deterministic visible content: one
versioned PoC device model/component type, at least one entity/twin, current
state, and a relationship when two configured entities exist. AWS and Azure
open their provider explorers. GCP deploys one separate read-only Twin
Explorer Cloud Run service from the same content-addressed image as its L4
API, with direct IAP for human access. The materializer endpoint remains on
its workload-identity path; IAP is not placed in front of machine projection
traffic.

### 4.5 Minimal Storage Movement

Storage movement is a data-plane batch operation, not a canonical domain
event. One portable `storage-mover` image has source adapters for
DynamoDB/Cosmos DB/Firestore and object adapters for S3/Blob/Cloud Storage.

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
queries each finite Firestore timestamp shard for the exact `stored_at`
window. A task processes at most 512 MiB of canonical source input, and an
Azure Cosmos task additionally processes at most 1,000 device partitions. A
full-table or unbounded cross-partition scan is not admissible.

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
switches. The same is true for `visualizedNumericMetricsPerRecord=1`,
`rollupBucketSeconds=3600`, `timestampShardCount`,
`readerMaxConcurrentRequests`, `readerTimeoutSeconds=10`, and
`readerMaximumPoints=1000`. RDS v2 and Manifest v4 carry these as typed integer
dimensions together with raw/rollup read, write, transaction, index, storage,
expiry, function-duration, and throttling cost ownership.

Post-deployment L4 inspection adds two fixed PoC dimensions rather than new
user inputs:

```text
l4InspectionSessionsPerMonth = 12
l4ReadsPerInspectionSession = 20
```

All three Core scenario sizes therefore price 240 bounded semantic-Twin reads
per month, their one-time seed writes, provider interactive-role bindings, and
the GCP Twin Explorer Cloud Run requests/duration/logging/image support where
selected. The mandatory first human access principal is included in the
Grafana seat workload; no provider is allowed to hide it as a free deployment
operator.

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
at least three partitioned tasks for Large; the decision-package calculator
derives the exact value as
`ceil(canonical_serialized_batch_bytes / 512 MiB)`. Three is only the lower
bound from payload bytes before canonical-envelope overhead.
For Cosmos DB the calculator also enforces at most 1,000 `/device_id`
partitions per task, so Large starts with at least 30 Azure tasks.
For Firestore Large, the sixteen timestamp shards are assigned
deterministically across the calculated byte-derived tasks; a task never
splits or merges a shard query implicitly.

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
| GCP Firestore L3 | One timestamp shard; raw and hourly-rollup transactions | One timestamp shard; raw and hourly-rollup transactions | Sixteen timestamp shards; raw history queries and mover fan out over the finite shard set |
| GCP Firestore L4 | Bounded document/one-hop queries | Same schema, scenario-derived operations | 50 state materializations/s plus one graph/model update/s |
| GCP Grafana | One pod, one incremental `e2-standard-4` node, Persistent Disk PVC, TLS LoadBalancer | Same initial node with calculated pod CPU/RAM | One pod, one incremental `e2-standard-8` node, Persistent Disk PVC, TLS LoadBalancer; no default HA/shared database or isolation-only node pool |
| Storage mover | One finite task/batch | Provider-derived finite tasks/batch | AWS/GCP start at no fewer than three byte-derived tasks; Azure starts at no fewer than 30 partition-derived tasks |

The exact embedded-event Kinesis/Event Hubs/Pub/Sub/BifroMQ allocations remain pinned
by Phase 8.8. All database partitions, Cosmos RU, Firestore raw/rollup
operations and indexes, connector concurrency, Grafana replicas, scheduled-job resources,
retry, object counts, transfer, and observability dimensions are emitted into
RDS v2 and priced.

The Firestore timestamp-shard count is
`next_power_of_two(ceil(peak_raw_writes_per_second / 400))`, with a minimum of
one. This keeps planned raw writes below 80% of Firestore's documented
500-writes/s limit for a sequentially indexed field: one shard for Small and
Medium, sixteen for Large. Large therefore plans 5,000 raw creates/s plus
5,000 distributed hourly-rollup updates/s. The decision package also proves
scattered document IDs, the exact composite indexes, the current 100-database
project quota, hot bytes, read/delete operations, and the documented gradual
traffic ramp. Deployment preflight requires
`existingDatabaseCount + selectedNewDatabases <= refreshedDatabaseQuota`.
Published design guidance is theoretical admission only; sustained live throughput
remains a supervised gate.

Published quotas prove only theoretical admission. Workload-dependent query,
projection, broker, bridge, identity, and storage-job behavior stays
`live_capacity_pending` until supervised evidence exists.

## 6. Immutable Complete-Service Decision Package

Before Phase 8.9A runtime changes, the repository now contains:

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

The approved package contains 72 selected components. Its component manifest
pins every logical/deployment component, service or
software version, image/chart/plugin digest, license, Terraform resource,
runtime package, port, output/input, permission, formula, capacity dimension,
file target, and test owner. Version-dependent values are refreshed from
primary sources before freezing; this plan does not invent future patch
versions.

The validator rejects unresolved/duplicate ownership, disagreement with the
immutable Eventing package, missing capacity or pricing dimensions, unknown
identity rules, missing single-cloud/mixed routes, secret-like data, and any
historical `@1` digest change. Its status is `approved` for offline
implementation authority after source refresh, deterministic calculations,
schema/reference/digest validation, and two zero-finding reviews. It explicitly
retains `live_capacity_pending` and does not activate either runtime profile.

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
immutable decision digests, and secret-free post-deployment layer-access
evidence. New Twins receive no active profile until `@2` passes all gates.
Existing `@1` records stay readable and destroyable.

Flutter shows Five-layer v2 only after server activation. It shows events as
mandatory profile behavior, selects one immutable Eventing S/M/L scenario and
renders its fields read-only, separates
Twin/dashboard inputs, and explains the provider-local L3-hot/L5 bundle plus
independent L4 placement. It does not offer scene/3D, inline Eventing, or
Eventing/GCP capability flags.

Creating the draft and selecting the immutable architecture remain
credential-free. `Prepare deployment -> Cloud access` requests connections only
for the resolved providers and reuses the same Management-owned guided
bootstrap available from Settings. Bootstrap secrets never rehydrate; an
bootstrap session ends at a validated bounded CloudConnection. The separate
Twin deployment preflight then pauses on any external provider action and
rechecks through that generated connection.

After deployment, Twin Overview loads typed `deployment-access.v1` through the
Management API and renders exactly one L4 and one L5 access card. Each card
shows service/provider, HTTPS link, interactive identity/readiness, available
content, and limitations. GCP Grafana alone offers an owner-scoped
rotate-and-reveal Viewer credential action. Generic Terraform outputs remain
technical evidence and never become a credential or URL-discovery contract.

### Deployer And Terraform

Add static catalog/Terraform implementations for:

- the three L3-hot/L5 bundles and independent L4 implementations;
- `raw_history_query.v1` and all local/remote `twin_projection.v1` bindings;
- AWS DynamoDB reader, TwinMaker projection adapter, and Managed Grafana;
- Azure Cosmos DB serverless/autoscale, partitioned reader/mover, ADT
  projection adapter, and Managed Grafana without ADX;
- GCP Firestore hot storage with sharded timestamps and the bounded Twin model
  in one named deployment database, distinct L3/L4 application boundaries, a
  read-only IAP-protected Cloud Run Twin Explorer, typed Cloud Run reader,
  Grafana on GKE, signed Infinity plugin, TLS LoadBalancer, CIDR allowlist, and
  separate internal Admin/human Viewer credentials without BigQuery, Spanner,
  a custom Twin plugin, or a dedicated node pool;
- provider-native interactive access bindings, deterministic seed content,
  typed safe L4/L5 output projection, and GCP Grafana Viewer rotation exactly
  as specified by `deployment-access.v1`;
- generated deployment CloudConnections only; raw bootstrap credentials,
  bootstrap sessions, and administrator secrets are forbidden in deployment
  manifests, packages, tfvars, Terraform state, logs, and outputs;
- immutable provider `thesis-demo-v2` deployment permission artifacts derived
  from this complete-service graph; existing `thesis-demo-v1` files remain
  unchanged and valid only for consumers that still require v1. Canonical new
  manifests are
  `3-cloud-deployer/docs/references/permission_sets/{aws,azure,gcp}_thesis_demo_v2.json`
  with matching v2 scope reviews, provider policy/role inputs, and generated
  drift copies;
- the three finite storage-job runtimes, native lifecycle rules, and six
  directed storage trusts;
- one provider registry support component where selected container images
  require it, reused and priced once;
- the unchanged immutable embedded and Event-Layer bundles.

The exact provider boundary is frozen in the complete-service component
manifest. AWS IoT Commands uses `awscc_iot_command`. TwinMaker creates only
the workspace with `awscc_iottwinmaker_workspace`; component types, entities,
and relationships retain the bounded post-Terraform AWS SDK lifecycle. The
Google provider must move from the current v5 constraint to
`>= 7.22.0, < 8.0.0` for the reviewed Worker Pool and direct Cloud Run IAP
resources. GKE objects use Kubernetes provider `>= 2.38.0, < 3.0.0`.

The Deployer orchestrates three automatic stages under one deployment trace:

1. create cloud-provider resources, including GKE;
2. after the cluster endpoint and short-lived credentials exist, apply
   BifroMQ/Grafana Kubernetes resources;
3. execute bounded SDK and Grafana plugin/datasource provisioning.

This stage boundary follows the provider initialization constraint; it is not
a new manual prerequisite, product-grade control plane, or separate user
workflow.

Every graph edge resolves from logical edge to catalog implementation to
source output, optional trust/route component, destination input, and exact
Terraform resource/output reference. No post-deploy name reconstruction,
anonymous public ingestion, or secret injection is permitted.

### Documentation

Documentation is a mandatory implementation task, not a postscript:

1. update this controlling plan and the research evaluation when an implemented
   service/version/capacity fact differs;
2. update `HANDOFF.md` and the Phase 8 `README.md` with the exact committed
   boundary and next branch;
3. update docs-site architecture, provider-capability, GCP setup, and known-
   limitation pages while keeping planned and currently available behavior
   visibly separate;
4. generate and validate the complete-service source ledger, formula ledger,
   component manifest, and route/capacity evidence;
5. leave LaTeX untouched without separate approval.

No phase may mark documentation complete while current-system docs claim an
unimplemented service is available or while a suspended Six-layer draft is
presented as implementation authority.

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
jobs, corrected identity, provider `thesis-demo-v2` permission artifacts, and
`five-layer-baseline@2`. Review to zero findings and commit.

### 8.9B

Out of scope for this Five-layer branch. Do not branch or implement
`six-layer-eventing@1` as part of 8.9A. After 8.9A is implemented and reviewed,
execute the separately reviewed
[`phase_08_9_six_layer_eventing_implementation.md`](phase_08_9_six_layer_eventing_implementation.md)
against the exact committed Five-layer v2 L1-L5 digest and run its own
zero-finding reviews.

### 8.10

Sequentially blocked until Six-layer is implemented and reviewed. Five-layer
v2 must first emit its own reproducible three single-cloud, six
L3-hot/L5-versus-L4, mixed-path, rejection, capacity, and cost evidence. The
later comparative phase uses that frozen evidence rather than recalculating it
under changed L1-L5 assumptions.

Implementation sequence and clean commits:

1. commit this corrected plan/evaluation boundary;
2. build, review, and commit the immutable complete-service decision package,
   including the three new `thesis-demo-v2` deployment permission artifacts
   and their source/known-gap ledgers;
3. finish/review/commit the dark Phase 8.6 compiler;
4. create the reviewed foundation branch and integrate the compiler commit;
5. implement/review/commit Phase 8.7;
6. branch and implement/review/commit the guided cloud-bootstrap prerequisite
   in its declared shared-contract, Management, provider-adapter, Deployer,
   Flutter, and documentation slices;
7. branch and implement/review/commit 8.9A Five-layer v2 and its Layer Access
   surfaces on that reviewed credential boundary;
8. stop and obtain a separately reviewed/approved Six-layer plan;
9. only then branch for Six-layer and the comparative Phase 8.10 evaluation.

A later branch never starts from an unreviewed or dirty boundary.

## 9. Verification

Required offline gates include:

- immutable `@1` and Eventing-package byte/digest stability;
- immutable `thesis-demo-v1` permission artifacts plus exact v2
  graph-to-`thesis-demo-v2` permission-inventory/digest drift tests;
- schema/reference/digest/generated-copy drift tests;
- all nine positive L3-hot/L4/L5 placements and every unequal L3-hot/L5
  rejection fixture;
- the raw-visualization edge for AWS, Azure, and GCP plus all six remote and
  three local Twin-projection routes;
- bounded GCP Twin query contract and a negative arbitrary-traversal fixture;
- exact 1/1/16 Firestore timestamp-shard resolution, deterministic shard hash,
  required index exemptions/composites, finite fan-out/merge, cursor
  query-binding/expiry/tamper rejection, and one-database L3/L4 identity
  separation with the documented database-wide IAM limitation;
- DynamoDB/Cosmos/Firestore raw-plus-hourly-rollup success, duplicate,
  transaction rollback, 30-day/720-point bound, hot expiry, and
  no-cool/archive-rollup fixtures;
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

The later implementation gate runs this exact credential-free sequence:

```bash
git diff --check
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test backend
./thesis.sh test deployment-contract
./thesis.sh test frontend
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
docker --context orbstack compose --profile docs run --rm docs mkdocs build --strict
```

Before `frontend-integration`, record the services already running for the
current Compose project. Afterward, stop only services that command started;
never use a blanket teardown against user-owned containers. Integration tests
must call the live local Management API and hard-assert returned profile,
component, edge, capacity, cost, rejection, and safe-error values. Unit tests
may mock an isolated client; integration tests may not mock HTTP. None of these
commands may receive cloud credentials or a live/apply flag.

### Review Record

| Pass | Scope | Result |
|---|---|---|
| 1 | Revised Five-layer v2 architecture and concept consistency across service evaluation, every Phase 8 plan, Handoff, research design, and current docs | Pass on 2026-07-30 with zero unresolved findings after retaining Firestore L3 and correcting stale L3/L4/L5 diagrams; the 2026-08-03 review corrected the unsupported JSON API end-date claim to maintenance-mode plus frozen availability/version evidence |
| 2 | Builder/API contract, workload math, identity/security, failure behavior, implementation sequence, compatibility, Flutter boundary, and testability | Pass on 2026-07-30 with zero unresolved findings; exact Firestore sharding/transactions, raw/rollup reader contract, plugin fail-closed gates, nine placements, capacity math, and credential-free integration commands are implementation-ready |
| 3 | Layer-access architecture feasibility across AWS/Azure/GCP, all nine placements, single-cloud/multicloud identity, one-Firestore tradeoff, visible content, cost ownership, and live/offline claim boundary | Pass on 2026-07-31 with zero unresolved findings after adding interactive-principal preflight, direct Cloud Run IAP, safe Viewer rotation, explicit L4 inspection load, Small Viewer cost, and provider Terraform evidence |
| 4 | Architect and builder review of concept hierarchy, FR/API datatypes, BLoC/Riverpod ownership, responsive widget tree, secret lifecycle, concurrency, accessibility, integration tests, documentation, and exact commit order | Pass on 2026-07-31 with all 20 plan-review criteria satisfied and zero unresolved findings |
| 5 | Guided-bootstrap cross-service concept review against the live OpenAPI, implemented manual script/import baseline, provider credential realities, selected Five-layer v2 services, and exact user/manual lifecycle | Pass on 2026-07-31 with zero unresolved findings after preserving the legacy path, separating bootstrap from Twin preflight, replacing least-privilege/zeroization overclaims, adding the user runbook, and distinguishing release/expiry/revocation/manual cleanup |
| 6 | Guided-bootstrap architect/builder readiness review across strict guide/session datatypes, authority/deployment permission packs, `thesis-demo-v1` compatibility, new immutable `thesis-demo-v2`, BLoC/reuse/token boundaries, restart/concurrency, real-API fake-adapter integration, roadmaps, FR-002, and handoff | Pass on 2026-07-31 with zero unresolved findings; Builder remains blocked until FR-002 schemas/fixtures and an approved Architect implementation plan exist |
| 7 | Complete-service package architecture review across Five-layer/Six-layer parity, 72 component decisions, all nine online placements, every local/remote route class, current service/plugin facts, and the bounded thesis-PoC exclusions | Pass on 2026-08-03 with zero unresolved findings after removing the fabricated JSON API support date, pinning Grafana/Infinity/BifroMQ artifacts, and retaining explicit live-readiness gates |
| 8 | Complete-service package builder review across deterministic S/M/L formulas, generated manifests, exactly-once cost ownership, `thesis-demo-v1` stability, `thesis-demo-v2` scope evidence, byte digests, source references, secret scanning, and drift-gate integration | Pass on 2026-08-03 with zero unresolved findings; package tests plus the composed offline validator pass without cloud credentials |
| 9 | Complete-service IaC feasibility review across exact Terraform/SDK bindings, provider-version floors, GKE apply ordering, direct Cloud Run IAP, and closed edge contracts | Pass on 2026-08-03 with zero unresolved findings after replacing fictitious AWS bindings, adding the IAP service-agent binding and deployer policy permissions, recording the Google-provider upgrade, and keeping Kubernetes application as an automatic second stage |

This service/architecture slice adds no new Flutter route, but it does add a
typed Layer Access section to the existing Twin Overview. Its authoritative
desktop/compact wireframes, marked widget tree, BLoC/service boundary,
Management-API-only contract, token/icon rules, and real-API integration gates
are defined in the linked layer-access implementation plan. Phase 8.7 remains
authoritative for profile configuration and still shows `L3 hot -> L5` and
`L3 hot -> L4` with L4 independent.

Planning verification on 2026-07-30:

- active Phase 8 cross-document service/placement consistency: pass;
- actual Flutter Riverpod/BLoC ownership versus Phase 8.7: pass;
- `git diff --check`: pass;
- `./thesis.sh test deployment-contract --focused`: pass
  (66 root, 40 Optimizer, 87 Management, and 73 Deployer/Terraform tests);
- OrbStack MkDocs strict build: pass.

Layer-access planning verification on 2026-07-31:

- cross-document one-Firestore, L4/L5 service, identity, nine-placement, and
  sequential-Six-layer inheritance consistency: pass;
- provider-primary-source and Terraform primitive feasibility: pass;
- Flutter plan dual review against all architect/builder criteria: pass with
  zero unresolved findings;
- `git diff --check`: pass;
- `./thesis.sh test deployment-contract --focused`: pass
  (66 root, 40 Optimizer, 87 Management, and 73 Deployer/Terraform tests);
- OrbStack MkDocs strict build: pass.

Guided-bootstrap planning verification on 2026-07-31:

- live local Management OpenAPI inspection: pass; current manual
  `/cloud-bootstrap/{provider}/plan`, `/cloud-bootstrap/import`, CloudConnection,
  and Twin deployment-preflight boundaries are reflected accurately;
- concept and dual architect/builder readiness reviews: pass with zero
  unresolved findings;
- changed-document local-link validation and `git diff --check`: pass;
- `THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test deployment-contract --focused`:
  pass (66 root, 40 Optimizer, 87 Management, and 73 Deployer/Terraform tests);
- OrbStack MkDocs strict build: pass.

## 10. Failure Codes

Add or update:

```text
PROFILE_HISTORICAL_READ_ONLY
PROFILE_NO_ACTIVE_VERSION
PROFILE_COMPLETE_BUNDLE_MISSING
PROFILE_RAW_VISUALIZATION_COLOCATION_REQUIRED
PROFILE_L4_TO_L5_NOT_SUPPORTED
DEPLOYMENT_ACCESS_NOT_AVAILABLE
DEPLOYMENT_ACCESS_CONTRACT_INVALID
BOOTSTRAP_CREDENTIAL_REQUIRED
BOOTSTRAP_CREDENTIAL_INVALID
BOOTSTRAP_CREDENTIAL_REENTRY_REQUIRED
BOOTSTRAP_AUTHORITY_PACK_MISMATCH
BOOTSTRAP_GENERATED_DEPLOYMENT_PACK_MISMATCH
BOOTSTRAP_IDENTITY_CREATION_FAILED
BOOTSTRAP_CONNECTION_VALIDATION_FAILED
BOOTSTRAP_MANUAL_REVOCATION_REQUIRED
BOOTSTRAP_SESSION_CONFLICT
INTERACTIVE_PRINCIPAL_REQUIRED
INTERACTIVE_PRINCIPAL_NOT_FOUND
INTERACTIVE_ROLE_BINDING_FAILED
AWS_IDENTITY_CENTER_ORGANIZATION_INSTANCE_REQUIRED
GCP_IAP_PREREQUISITE_REQUIRED
PROVIDER_BILLING_ACTION_REQUIRED
PROVIDER_QUOTA_ACTION_REQUIRED
PROVIDER_ORGANIZATION_POLICY_BLOCKED
LAYER_ACCESS_CONTENT_PROVISIONING_FAILED
LAYER_ACCESS_DATA_PROBE_FAILED
LAYER_ACCESS_URL_INVALID
GCP_GRAFANA_VIEWER_ROTATION_FAILED
GCP_GRAFANA_VIEWER_ROTATION_IN_PROGRESS
PROFILE_WORKLOAD_V2_REQUIRED
EVENTING_SCENARIO_REFERENCE_INVALID
PROFILE_CAPACITY_EVIDENCE_INCOMPLETE
RAW_HISTORY_QUERY_BINDING_INVALID
RAW_HISTORY_QUERY_INVALID
RAW_HISTORY_QUERY_UNAUTHORIZED
RAW_HISTORY_QUERY_LIMIT_EXCEEDED
L3_IDEMPOTENCY_CONFLICT
L3_ROLLUP_TRANSACTION_FAILED
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

- [x] `phase-08-complete-service-bundles@1` is frozen, digest-checked, covered
      by the deployment-contract gate, and approved only for offline
      implementation authority.
- [x] The functionality-first service evaluation is source-backed and frozen.
- [x] `@1` and the Phase 8.8 Eventing evidence remain immutable.
- [x] Existing `thesis-demo-v1` provider permission artifacts remain immutable;
      Five-layer v2 publishes new `thesis-demo-v2` artifacts whose inventories
      cover every selected service, role binding, and preflight action, with
      scope gaps documented rather than labelled least-privilege.
- [ ] `@2` implements mandatory embedded domain behavior without flags.
- [ ] AWS, Azure, and provider-hosted GCP have complete L1-L5 bundles.
- [ ] L3-hot-to-L5 raw visualization and L3-hot-to-L4 Twin projection are
      implemented and priced; L4-to-L5 is absent.
- [ ] The L3-hot/L5 co-location and independent L4 rule is enforced and
      explained with all nine placements.
- [ ] Azure L3 hot remains Cosmos DB; Small/Medium serverless and Large
      calculated autoscale pass RU, storage, partition, and mover proofs.
- [ ] GCP uses one named Firestore Native database per deployment for the
      selected L3/L4 collection groups; the weaker database-wide IAM boundary
      is documented and BigQuery and Spanner are absent.
- [ ] Firestore timestamp sharding resolves to 1/1/16 for Small/Medium/Large;
      scattered IDs, exact indexes, per-shard pagination, mover partitioning,
      database quota, operations, and gradual-ramp evidence are frozen.
- [ ] Every provider writes one idempotent hourly rollup per accepted canonical
      record inside its selected L3 service; 30-day aggregate reads are bounded
      to 720 points and derived rollups never enter cool/archive.
- [ ] GCP Grafana uses the selected/shared GKE cluster without a default
      dedicated node pool.
- [ ] The signed Infinity plugin artifact, applicable license notice, version,
      and digest are frozen, or GCP fails closed pending a new datasource
      decision.
- [ ] The maintenance-only JSON API datasource has exact AWS/Azure availability
      and Grafana-12 compatibility evidence frozen, and deployment preflight
      fails closed when the selected plugin version is absent or incompatible.
- [ ] Storage uses finite scheduled jobs and deterministic object manifests;
      unproven CDC/outbox/broker pipelines are absent.
- [ ] All six event routes and all twelve storage stage routes use the six
      reviewed short-lived identity directions.
- [ ] Same-provider paths create no cross-cloud route.
- [ ] GCP Grafana has an exact TLS LoadBalancer, source-range allowlist,
      generated human Viewer credential, endpoint output, and certificate
      evidence; its internal Admin and reader secrets are never returned.
- [ ] Every one of the nine placements returns one typed, usable L4 browser
      surface and one typed, usable L5 browser surface with independent
      interactive identity/readiness evidence.
- [ ] AWS TwinMaker, Azure Digital Twins Explorer, and the GCP Twin Explorer
      expose deterministic semantic content; every Grafana exposes the same
      logical raw/rollup dashboard.
- [ ] Missing deployment access starts the guided bootstrap and produces a
      validated bounded CloudConnection; it never requires the user to build
      bounded deployment credentials manually. Five-layer v2 requires the
      exact `thesis-demo-v2` version/digest and rejects a v1 connection as
      outdated without silently upgrading it.
- [ ] Bootstrap-secret release, provider expiry, disposable provider-side
      revocation/manual cleanup, and existing user-owned non-revocation are
      distinct truthful states, and no bootstrap secret crosses into a
      deployment package.
- [ ] The configuration workspace blocks on missing AWS L4 Identity Center
      organization-instance, Azure Entra principal/role-assignment, GCP IAP,
      quota, billing, or organization-policy prerequisites without asking for
      browser passwords; recheck uses the generated CloudConnection.
- [ ] The fixed monthly L4 inspection reads, seed operations, interactive
      bindings, mandatory human seat, and GCP Explorer runtime are costed once.
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
- [ ] 8.9A uses a clean branch, commits, and review cycle; 8.9B starts only from
      its reviewed digest under the separate v2 plan.
- [ ] Two fresh reviews find zero unresolved findings.
- [ ] This corrected planning boundary is committed before implementation.
