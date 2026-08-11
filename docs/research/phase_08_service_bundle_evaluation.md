---
title: "Phase 8 Five-Layer v2 Service-Bundle Evaluation"
description: "PoC-focused functional, placement, identity, and capacity evaluation for five-layer-baseline@2."
tags: [architecture, digital-twin, eventing, multicloud, services, capacity, phase-8]
lastUpdated: "2026-08-03"
version: "1.9"
---

<!-- SOURCES:
- Current Phase 8 plans and versioned architecture/Eventing evidence
- Current Optimizer workload presets and calculation semantics
- Current Deployer Terraform/provider/runtime implementation
- Primary AWS, Microsoft Azure, Google Cloud, and Grafana documentation linked below
- User-approved functionality-first PoC rule, L3-hot/L5 placement experiment,
  Azure Cosmos DB and GCP Firestore L3 continuity, and Small/Medium/Large
  evaluation
EXTRACTED: 2026-08-03 | VERSION: 1.9
-->

# Phase 8 Five-Layer v2 Service-Bundle Evaluation

## Evaluation Question

Select one implementable service bundle per provider for
`five-layer-baseline@2`: five scientific responsibilities with mandatory
domain-event behavior embedded in their owners.

This evaluation selects the complete Five-layer v2 boundary. The immutable
complete-service package also records the already reviewed Six-layer service
delta, but does not activate it: `six-layer-eventing@1` must inherit the
reviewed Five-layer v2 L1-L5 services, workload, and placement rules unchanged
and execute only on its separate branch after Five-layer review.

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
only declared remote edges incur cross-cloud transfer. The immutable
[`phase-08-complete-service-bundles@1`](evidence/phase_08_service_bundles/README.md)
package freezes availability/pricing ownership for every selected member and
fails closed rather than substitute a region or service.

### Common L1-L5 Service Matrix

| Layer | AWS | Azure | GCP |
|---|---|---|---|
| L1 acquisition | IoT Core and IoT Commands | IoT Hub | BifroMQ `4.0.0-incubating` on GKE Standard, load balancer, ordered MQTT-to-Pub/Sub adapter |
| L2 processing | Lambda and Step Functions Standard | Functions Flex Consumption and Logic Apps Consumption | Cloud Run and Workflows |
| L3 hot/raw history | DynamoDB on-demand with a window-shard GSI | Cosmos DB for NoSQL with `/device_id`, bounded time queries, and scenario-selected serverless/autoscale capacity | Firestore Native Standard edition with scattered event IDs, scenario-derived timestamp shards, bounded time queries, and selective indexes |
| L3 cool | S3 Standard-IA | Blob Cool | Cloud Storage Nearline |
| L3 archive | S3 Glacier Deep Archive | Blob Archive | Cloud Storage Archive |
| L4 semantic Twin | IoT TwinMaker Standard pricing plan | Azure Digital Twins | Cloud Run Twin API/materializer and read-only IAP-protected Twin Explorer backed by the deployment Firestore Native database |
| L5 visualization | Amazon Managed Grafana 12 with a provider-local typed raw-history reader datasource | Azure Managed Grafana 12 with the supported JSON API datasource and a provider-local Cosmos reader | One Grafana OSS 12 pod on GKE with Persistent Disk PVC, signed Infinity datasource, and a provider-local typed Firestore reader |

The selected GCP bundle is provider-hosted. It does not claim that Google
offers a managed Digital Twin equivalent to TwinMaker or ADT. The implementation
and cost model therefore include the Twin API, Firestore schema/indexes,
Grafana deployment, typed Cloud Run reader, signed Infinity plugin, image,
identity, logging, upgrades, and cleanup.

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
| `six-layer-eventing@1` | Later treatment profile with an independent Event Layer | Service delta approved offline; implementation remains deferred until reviewed Five-layer v2 |

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

## Why Layer Links Also Need Interactive Identity

Terraform can create an L4/L5 resource without making it usable in a human
browser. Deployment API credentials are not AWS Identity Center, Microsoft
Entra, Google/IAP, or Grafana login credentials. The evaluated bundle therefore
includes both the browser surface and its interactive access binding:

| Layer | AWS | Azure | GCP |
|---|---|---|---|
| L4 | TwinMaker console plus Identity Center read assignment | ADT Explorer plus Data Reader | Read-only Cloud Run Twin Explorer plus direct IAP |
| L5 | Managed Grafana plus Identity Center workspace association | Managed Grafana plus Grafana role | Grafana OSS plus generated human Viewer account |

AWS Identity Center activation and first-time GCP IAP configuration in a
project without an organization can require account-owner action. This makes
universal unattended user provisioning an invalid claim, but does not make the
deployment inaccessible: preflight validates the external prerequisite, then
Terraform binds the selected existing principal. Azure role binding and GCP
IAP policy binding are likewise separate from the runtime workload identities.

The complete nine-placement and one-time GCP Viewer credential boundary is
frozen in
[`phase_08_layer_access_handoff.md`](../plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md).

The provider-local query identities are part of each bundle. AWS and Azure
retain a typed read-only hot-reader API because their selected operational
NoSQL stores do not provide a suitable secretless core datasource in the
selected managed Grafana tier. Each datasource receives one generated,
deployment-scoped, read-only credential stored only in Grafana secure
datasource configuration and the provider endpoint; it is never a shared
cross-cloud token, contract value, tfvars value, log field, or repository
secret. GCP follows the same bounded-reader pattern: the Grafana pod has no
Firestore role, while the typed Cloud Run reader has read access only to the
named deployment database and its application exposes only the L3 query
contract.

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
cursor. Raw queries are capped at 24 hours, aggregates at 30 days, and every
response at 1,000 points/ten seconds. GCP uses the signed
`yesoreyeram-infinity-datasource` and the same generated
`X-Twin-Reader-Key` pattern against a typed Cloud Run reader. Infinity is
maintained by Grafana Labs, supports server-side API-key headers, allowed-host
restriction, backend parsing, and GET-only operation. The three routes remain
authenticated internet-reachable PoC read boundaries; private networking is
not implied.

Grafana now marks the JSON API datasource deprecated, recommends Infinity for
new work, and publishes 1 February 2027 as its support end. JSON API remains
admissible only as a frozen thesis-PoC dependency before that boundary: the
complete-service package records the plugin ID, selected version, end date,
Grafana-12 compatibility, the Amazon Managed Grafana catalog result, and Azure
Managed Grafana Standard support evidence. The runtime gate repeats those
checks before datasource/dashboard content mutation, and the affected bundle
fails closed if the plugin is absent, incompatible, or past the published
boundary. Infinity is not assumed to exist in either managed-provider catalog
and may not be substituted without a new reviewed decision. GCP can
select Infinity because that Grafana runtime and its content-addressed plugin
image are owned by this deployment.

All providers store idempotent hourly rollups inside the selected L3 service so
the 30-day aggregate query reads at most 720 documents/items and stays inside
the one-month hot-data boundary. The raw write and rollup update occur in one
DynamoDB transaction, one Cosmos transactional batch inside `/device_id`, or
one Firestore transaction. This adds no service
family, worker, broker, or pipeline, but its operations and storage are priced.
AWS uses a separate rollup table, Azure uses typed items in the existing
container, and GCP uses a separate collection in the L3 database. Rollups
expire with hot data plus the failure-evidence grace and are not exported to
object storage. Their UTC bucket is derived from provider-owned `stored_at`;
the original device `event_time` remains available only on raw points.
Each provider uses raw create-if-absent plus version/ETag-guarded rollup update
inside its native transaction, with at most three conflict retries. Duplicate
raw IDs succeed without another rollup increment; an exhausted transaction
fails before durable acknowledgement.

Reader capacity uses
`max(2, ceil(aggregate_query_rate_per_second * 10 * 1.25))`, yielding
2/3/42 maximum concurrent requests for Small/Medium/Large. Lambda reserved
concurrency, Functions Flex maximum instances with HTTP concurrency one, and
Cloud Run maximum instances with container concurrency one enforce that
boundary without another gateway or rate-limiter service.
The initial reader memory is 512 MiB on all providers, with 1 vCPU on Cloud
Run. Admission proves the relevant AWS concurrency, Azure Flex regional
memory/core, and GCP regional CPU/memory quotas; latency and memory remain
supervised live gates.

For GCP, Infinity is provisioned with the exact Cloud Run base URL as an
allowed host, the generated key in `secureJsonData`, backend parsing, and
dangerous HTTP methods disabled. Because the plugin cannot mint Google ID
tokens, Cloud Run sets `invoker_iam_disabled=true` while the application
rejects requests without the constant-time validated deployment key. An
organization policy that forbids this boundary makes GCP unsupported for this
profile rather than adding another gateway. The reader
service account receives `roles/datastore.viewer` through an IAM condition for
the deployment Firestore database; the reader application allowlists only L3
collections and the Grafana pod receives no database role or JSON
service-account key. The composed path is verified with plugin
`Save & test`, one bounded raw query, and one 30-day hourly-rollup query before
live readiness. Offline activation keeps the bundle `live_capacity_pending`; a
failed supervised query reopens the bundle.

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
writer/reader path, and comparable DynamoDB/Cosmos/Firestore cost contrast. ADT
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
                                                +-> Firestore raw history

selected state/model changes -> Cloud Run Twin API -> L4 collections

Grafana on GKE -> Infinity datasource -> Cloud Run reader -> Firestore
```

BifroMQ is the MQTT device boundary. Pub/Sub is the durable cloud backbone; it
does not expose a general MQTT device interface. The pair is shared by Five-
layer v2 and Six-layer v1 whenever GCP owns L1, so BifroMQ is not a Six-layer
addition.

The executable thesis boundary pins the official amd64 BifroMQ image by digest
and exposes only MQTT over TLS on port 8883. BifroMQ's bundled webhook provider
delegates authentication and topic authorization to the ordered adapter. One
generated deployment-scoped device credential is shared by the simulated PoC
devices; a separate, non-exported bridge credential may only subscribe to the
shared telemetry filter and publish device commands. The adapter forwards
telemetry to the authenticated Cloud Run ingress, pulls the ordered Pub/Sub
command subscription, and acknowledges a command only after its QoS-1 MQTT
publish completes. Per-device identities, client certificates, a public CA,
broker persistence, and a general device registry remain explicit live/future
hardening boundaries rather than hidden product infrastructure.

Firestore Native Standard edition remains L3 hot, matching the existing
deployer, writer, reader, mover, Optimizer, and pricing model instead of
changing the storage technology merely to gain a native Grafana datasource.
Raw documents use
scattered deterministic IDs. Small and Medium use one timestamp shard; Large
uses sixteen, derived from
`next_power_of_two(ceil(peak_raw_writes_per_second / 400))`. The reader and
mover issue a finite query per shard and merge the results. This deliberately
keeps planned raw writes below 80% of Firestore's documented 500-writes/s
limit for a sequentially indexed field.

The shard is
`uint32_be(sha256(deployment_id || 0x00 || event_id)[0:4]) mod shard_count`.
Reader cursors bind the provider, deployment, query digest, fifteen-minute
expiry, and every per-shard continuation position in HMAC-authenticated
base64url canonical JSON, so pagination cannot widen the original query.

The L3 database contains
`telemetry/{sha256(deployment_id,event_id)}` and
`hourly_rollups/{sha256(device_id,metric,bucket_start)}`. Single-field indexes
for `stored_at`, `event_time`, `timestamp_shard`, and rollup `bucket_start` are
disabled. Composite indexes cover
`(device_id, metric, timestamp_shard, stored_at)`,
`(timestamp_shard, stored_at)`, and
`(device_id, metric, bucket_start)`. The raw event create and current
hourly-rollup update run in one transaction, so an already accepted event
cannot increment the aggregate twice.

The PoC creates one named Firestore database per deployment. When GCP owns both
L3 and L4, their collection groups, indexes, code paths, service accounts,
operations, and cost attribution remain distinct inside that database. When it
owns only one responsibility, only that responsibility's collections exist.
This avoids a second database resource that adds no PoC capability.

The writer, reader, storage mover, and Twin API use separate service accounts.
`roles/datastore.user` is condition-scoped to the deployment database for each
writer/mover/Twin runtime; readers use condition-scoped
`roles/datastore.viewer`. Firestore server libraries bypass Security Rules and
the relevant IAM boundary is the database, so application collection/query
allowlists do not provide strict IAM isolation between L3 and L4. That weaker
isolation is an accepted and reported PoC tradeoff. The broader deployment
identity is not injected into a runtime.

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

The signed Infinity datasource is maintained by Grafana Labs and talks only to
the typed Cloud Run reader. Its exact version, artifact digest, and applicable
license notice are frozen in the complete-service package rather than guessed
in this evaluation. The base URL is allowlisted, the generated reader key is
stored in `secureJsonData`, backend parsing is used, and dangerous HTTP methods
are disabled. The Cloud Run service stores only the key hash and uses a
read-only identity scoped to the deployment database plus an L3-only
application contract. The Grafana pod receives no Firestore role or
service-account JSON key.

The GCP L5 path has no custom Twin/scene plugin because L4-to-L5 is outside the
profile. Grafana is exposed through one GKE `LoadBalancer` Service with TLS
terminated by Grafana, a deployment-generated certificate stored only in a
Kubernetes Secret, separate internal Admin and human Viewer credentials, and
an explicit `loadBalancerSourceRanges` allowlist. The fixed-IP endpoint,
Viewer username, and certificate fingerprint are safe deployment evidence.
The Viewer password is rotated and revealed once through an owner-scoped
Management operation; the Admin and datasource secrets never leave their
runtime boundary. A public unrestricted service, plaintext HTTP, wildcard
CIDR, or secret in a contract is rejected. The self-signed certificate and
CIDR-scoped researcher access are explicit PoC limitations; a public
DNS/certificate/GKE-IAP control plane is not added.

GCP L4 adds one separate, read-only Cloud Run Twin Explorer service protected
by direct IAP. It reuses the L4 image/read model and scales to zero. Keeping it
separate from the materializer is functionally necessary: interactive IAP
must not intercept workload-identity projection traffic. It is not a second
Twin service, scene stack, or general Firestore console.

BigQuery remains a rejected analytics alternative for this baseline. It would
provide SQL analytics and a dedicated Grafana datasource, but it would replace
the already implemented operational L3 store and change ingestion, query,
retention, movement, pricing, and identity at the same time as the L4 placement
experiment. A later analytics-focused profile can compare it explicitly.

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
| GCP | Cloud Scheduler starts a Cloud Run Job; Artifact Registry stores the image | Firestore bounded timestamp-shard/time-window query |

One content-addressed registry support component is reused by all selected
container images in a provider deployment and priced once. A provider with no
selected platform-owned container receives no registry. It is supporting
deployment infrastructure, not another scientific responsibility.

The Deployer materializes each required image without a local Docker daemon:
AWS uses regional CodeBuild with a deterministic context in a one-day S3
source bucket, Azure uses an on-demand ACR Task run with an uploaded
deterministic context, and GCP uses regional Cloud Build with a deterministic
context in a one-day Cloud Storage source bucket. Each build publishes to the
deployment-owned provider registry and the Deployer resolves the immutable
image digest before runtime Terraform is allowed to continue. The build
identities can read only their finite source context, write only their selected
registry, and emit build logs. These bounded deployment-time invocations are
packaging evidence, not steady-state Twin services; the monthly Optimizer
prices registry storage but does not present one-time build minutes as
recurring architecture load. Current Azure documentation warns that ACR Task
runs are temporarily paused for Azure free-credit subscriptions, so that
condition is an explicit pre-mutation activation gate rather than a silent
fallback to local Docker.

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
window; GCP queries each finite Firestore timestamp shard for that exact
window. A Cosmos job task processes at most 1,000 device partitions and at
most 512 MiB of canonical source input. The task count is the larger of the
device-count and byte-size calculations, so the Large Azure path initially
uses at least 30 tasks instead of hiding a cross-partition full scan.

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
| Monthly editor/viewer seats | 2/1 | 25/10 | 100/300 |
| L4 inspection sessions/month | 12 | 12 | 12 |
| L4 bounded reads/session | 20 | 20 | 20 |
| Twin-state materializations/s | 0.1 | 2.5 | 50 |
| Twin graph/model updates/s | 0.01 | 0.1 | 1 |

Dashboard refreshes are workspace-wide, not per seat. State materializations
and graph/model updates are synthetic capacity inputs; they are not inferred
from every raw message. Five-layer v2 has no scene workload fields because it
does not claim L4-to-L5 or 3D visualization. Its canonical PoC telemetry
record contains exactly one visualized numeric metric/value pair, so each
accepted raw record causes exactly one hourly-rollup update.

The mandatory Small Viewer closes the post-deployment access requirement
instead of treating the researcher as a free/unpriced operator. The twelve
monthly L4 inspection sessions and twenty bounded reads per session are fixed
researcher-PoC dimensions across all sizes. They price TwinMaker/ADT/Twin-API
reads and GCP Explorer runtime without pretending that every Grafana seat also
uses the semantic Twin UI.

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
  bounded-reader/mover RU, and the frozen storage/operation autoscale minimum.
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
- Firestore L3 receives 5,000 raw creates/s and 5,000 distributed
  hourly-rollup updates/s in Large. Sixteen timestamp shards keep planned raw
  index writes below 400/s per shard; scattered IDs, exact composite indexes,
  gradual load ramp, transaction retries, reads, storage, and deletes remain
  explicit decision/live evidence.
- The Firestore L4 collection group receives at most the synthetic 50 state
  materializations/s plus one graph/model update/s in Large, not all 5,000 raw
  messages/s. Required relationship indexes and one-hop query limits are
  frozen separately from L3.
- Grafana uses one pod on the selected/shared GKE cluster, one incremental
  `e2-standard-4` node for Small/Medium or `e2-standard-8` for Large, and the
  priced Persistent Disk PVC and external load balancer. An isolation-only
  node pool, shared database, public DNS/certificate service, and multi-replica
  HA are not assumed.
- The typed Cloud Run reader is limited to one database, device, metric, time
  range, result size, and ten-second request. The Grafana pod receives no
  Firestore credential.

Decision: theoretically admissible after the sharded Firestore path, bounded
Twin API, typed reader, and signed Infinity datasource are implemented; live
BifroMQ, Firestore, GKE, reader, and failure behavior remains pending.

### Storage Jobs

Large core traffic is exactly 4,000 KiB/s (3.90625 MiB/s), or 1,200,000 KiB
(1,171.875 MiB, approximately 1.145 GiB) per five-minute batch before
transport overhead. The initial plan uses one task/batch for
Small, one for Medium, and at least three deterministic source partitions for
Large, with at most 512 MiB canonical serialized input per task. Three is the
payload-only lower bound; the package freezes
`ceil(canonical_serialized_batch_bytes / 512 MiB)`. A 64-MiB uncompressed
object target similarly yields at least nineteen Large objects per window and
is recalculated from canonical bytes.

For Azure Cosmos, the additional maximum of 1,000 device partitions per task
raises the initial Large parallelism to at least 30 tasks. AWS and GCP retain
the byte-derived, no-fewer-than-three-task starting point. GCP assigns its
sixteen timestamp shards deterministically across the calculated tasks and
never performs an unbounded collection scan.

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
| Replace Firestore L3 with BigQuery in Five-layer v2 | BigQuery is stronger for analytical SQL and has a dedicated Grafana datasource, but replacing the implemented operational store would also change GCP ingestion, querying, movement, pricing, and identity during the L4 placement experiment |
| Keep Cosmos DB serverless for Large | The published ceiling and lack of predictable throughput cannot justify the 5,000-write/s scenario; Large must use calculated autoscale or fail admission |
| Keep Spanner Graph for GCP | Adds Enterprise graph infrastructure without a multi-hop graph requirement |
| Keep two Firestore databases in the PoC | Adds a second database resource solely for stronger IAM isolation; one database is sufficient for the selected functionality, while the weaker database-wide IAM boundary is explicitly accepted |
| Give GCP Grafana a dedicated node pool by default | Adds capacity before a test demonstrates isolation is necessary |
| Use Grafana JSON/Infinity as a universal cross-cloud adapter | No single reviewed secretless automation path across the selected managed/self-hosted Grafana environments |
| Let Grafana read Firestore directly | There is no selected native Firestore datasource; giving the visualization pod database credentials would also bypass the common bounded query contract |
| Use the deprecated JSON API plugin for new self-hosted GCP Grafana | The Grafana-maintained Infinity plugin supplies the needed backend parser, API-key header, allowed-host, and current maintenance path; JSON API remains only a frozen managed-AWS/Azure PoC dependency whose exact catalog availability, Grafana-12 compatibility, and support boundary are checked before content mutation |
| Enable Grafana development mode or generally allow unsigned plugins | Broader code-loading authority is unnecessary; the PoC installs only the signed, version- and digest-pinned Infinity datasource |
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
   embedded-event scenario, including Cosmos RU/partition proofs and
   Firestore timestamp-shard/index/database-quota proofs;
8. OrbStack-backed cross-stack and Terraform no-apply/mock-plan gates;
9. historical/Eventing digest-stability, docs, links, and secret scans;
10. two new zero-finding reviews.

An offline-activated profile is not live-ready. Provider quota approval, real
identity exchange, workload-specific throughput, plugin behavior, and cloud
cleanup require separately approved supervised evidence.

## Primary Source Ledger

### AWS

- [AWS IoT TwinMaker console and concepts](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/what-is-twinmaker.html)
- [Amazon Managed Grafana authentication](https://docs.aws.amazon.com/grafana/latest/userguide/authentication-in-AMG.html)
- [Amazon Managed Grafana user roles](https://docs.aws.amazon.com/grafana/latest/userguide/Grafana-user-roles.html)
- [AWS IoT TwinMaker quotas](https://docs.aws.amazon.com/general/latest/gr/iot-twinmaker.html)
- [AWS IoT TwinMaker pricing plans](https://aws.amazon.com/iot-twinmaker/pricing/)
- [DynamoDB on-demand capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)
- [AWS Lambda reserved concurrency](https://docs.aws.amazon.com/lambda/latest/dg/configuration-concurrency.html)
- [EventBridge Scheduler for ECS tasks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/tasks-scheduled-eventbridge-scheduler.html)
- [S3 lifecycle management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [AWS outbound identity federation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_outbound.html)
- [AWS `AssumeRoleWithWebIdentity`](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_request.html)

### Azure

- [Azure Digital Twins Explorer](https://learn.microsoft.com/en-us/azure/digital-twins/how-to-use-azure-digital-twins-explorer)
- [Azure Digital Twins security and data roles](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-security)
- [Azure Managed Grafana user and identity roles](https://learn.microsoft.com/en-us/azure/managed-grafana/how-to-manage-access-permissions-users-identities)
- [Cosmos DB request units](https://learn.microsoft.com/en-us/azure/cosmos-db/request-units)
- [Cosmos DB serverless performance](https://learn.microsoft.com/en-us/azure/cosmos-db/serverless-performance)
- [Cosmos DB limits and autoscale minimums](https://learn.microsoft.com/en-us/azure/cosmos-db/concepts-limits)
- [Cosmos DB partitioning](https://learn.microsoft.com/en-us/azure/cosmos-db/partitioning)
- [Azure Digital Twins service limits](https://learn.microsoft.com/en-us/azure/digital-twins/reference-service-limits)
- [Azure Managed Grafana supported data sources](https://learn.microsoft.com/en-us/azure/managed-grafana/how-to-data-source-plugins-managed-identity)
- [Azure Functions Flex Consumption scaling and concurrency](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-plan)
- [Azure Data Explorer overview](https://learn.microsoft.com/en-us/azure/data-explorer/data-explorer-overview)
- [Azure Container Apps jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
- [Azure Blob lifecycle management](https://learn.microsoft.com/en-us/azure/storage/blobs/lifecycle-management-policy-configure)
- [Microsoft Entra workload identity federation](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust)
- [Azure Event Hubs quotas and limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits#azure-event-hubs-limits)

### GCP And Grafana

- [Firestore document data model](https://cloud.google.com/firestore/native/docs/data-model)
- [Firestore Native best practices](https://cloud.google.com/firestore/native/docs/best-practices)
- [Firestore sharded timestamps](https://cloud.google.com/firestore/native/docs/solutions/shard-timestamp)
- [Firestore quotas and limits](https://cloud.google.com/firestore/quotas)
- [Firestore multiple-database management](https://cloud.google.com/firestore/docs/manage-databases)
- [Firestore server-client IAM](https://cloud.google.com/firestore/docs/security/iam)
- [Firestore server-library Security Rules boundary](https://cloud.google.com/firestore/native/docs/security/rules-conditions)
- [Direct IAP for Cloud Run](https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)
- [Cloud Run public invocation](https://cloud.google.com/run/docs/authenticating/public)
- [Cloud Run service identity](https://cloud.google.com/run/docs/securing/service-identity)
- [Cloud Run request concurrency](https://cloud.google.com/run/docs/about-concurrency)
- [Scheduled Cloud Run jobs](https://cloud.google.com/run/docs/execute/jobs-on-schedule)
- [Cloud Storage lifecycle management](https://cloud.google.com/storage/docs/lifecycle)
- [External workload identities](https://cloud.google.com/iam/docs/workload-identities)
- [BigQuery overview](https://cloud.google.com/bigquery/docs/introduction)
- [Grafana Infinity datasource configuration](https://grafana.com/docs/plugins/yesoreyeram-infinity-datasource/latest/configure/)
- [Grafana Infinity datasource installation](https://grafana.com/docs/plugins/yesoreyeram-infinity-datasource/latest/installation/)
- [Grafana JSON API datasource status](https://grafana.com/grafana/plugins/marcusolsson-json-datasource/)
- [Amazon Managed Grafana plugin catalog and lifecycle](https://docs.aws.amazon.com/grafana/latest/userguide/grafana-plugins.html)
- [Grafana plugin signatures](https://grafana.com/docs/grafana/latest/administration/plugin-management/plugin-sign/)
- [Grafana `allow_loading_unsigned_plugins` configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#allow_loading_unsigned_plugins)

The immutable Phase 8.8 source ledger remains the authority for Kinesis,
SNS/SQS, Event Hubs, Service Bus, Pub/Sub, Cloud Run worker pools, BifroMQ, and
all six domain-event bridge directions. Primary documentation proves published
capabilities and limits; it does not replace implementation or live testing.
