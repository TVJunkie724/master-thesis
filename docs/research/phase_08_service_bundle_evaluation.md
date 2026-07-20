---
title: "Phase 8 Complete Twin Service-Bundle Evaluation"
description: "Functional, compatibility, identity, and capacity evaluation for the complete five-layer and six-layer Phase 8 profiles."
tags: [architecture, digital-twin, eventing, multicloud, services, capacity, phase-8]
lastUpdated: "2026-07-20"
version: "1.0"
---

<!-- SOURCES:
- Current Phase 8 plans and versioned architecture/Eventing evidence
- Current Optimizer workload presets and calculation semantics
- Current Deployer Terraform/provider/runtime implementation
- Primary AWS, Microsoft Azure, Google Cloud, Grafana, and Eclipse documentation linked below
- User-approved functionality-first PoC selection rule and mandatory Small/Medium/Large evaluation
EXTRACTED: 2026-07-20 | VERSION: 1.0
-->

# Phase 8 Complete Twin Service-Bundle Evaluation

## Decision Summary

Phase 8 uses one curated, functionally complete service bundle per provider.
Cost is calculated and reported, but it is not an admissibility or
service-selection criterion for this proof of concept.

The selected complete-profile bundles are:

| Provider | L1-L3 and embedded domain events | L4 Twin-state bundle | L5 visualization bundle | Complete single-cloud target |
|---|---|---|---|---|
| AWS | IoT Core, Lambda, Step Functions Standard, IoT Commands, SQS FIFO, Kinesis/SNS FIFO where a remote edge requires an outbox, DynamoDB, S3, EventBridge Scheduler, CloudWatch | IoT TwinMaker with platform-owned external time-series/data connectors and S3 scene assets | Amazon Managed Grafana 12 with IoT TwinMaker plugin `1.3.1`, data source, and scene viewer | Selected for `five-layer-baseline@2` and `six-layer-eventing@1` |
| Azure | IoT Hub, Functions Flex Consumption, Logic Apps Consumption, Service Bus Standard, Event Hubs where a remote edge or analytics landing requires it, Cosmos DB, Blob Storage, Azure Monitor | Azure Digital Twins plus Azure Data Explorer; Event Hubs/data connections carry time series and data-history records without treating this supporting stream as the scientific Event Layer | Azure Managed Grafana Standard X1/X2 on Grafana 12 with the Azure Data Explorer data source; 3D Scenes Studio assets/viewer are included when the workload requires 3D | Selected for `five-layer-baseline@2` and `six-layer-eventing@1` |
| GCP | GKE Standard, Apache BifroMQ, Pub/Sub, Cloud Run, Workflows, Cloud Storage, Firestore, Cloud Logging | A platform-owned Twin API/materializer on Cloud Run backed by Spanner Graph Enterprise and BigQuery time series, with Cloud Storage scene assets | Grafana OSS 12 on GKE with BigQuery datasource `3.2.0` in `Google Metadata Server` mode and a content-addressed platform Twin/scene backend plugin, both backed by Workload Identity for GKE | Selected as a provider-hosted bundle for the new profiles; it remains unsupported in historical `@1` |

This revises the earlier assumption that GCP must stay absent from L4/L5.
GCP has no first-class managed equivalent to IoT TwinMaker or Azure Digital
Twins plus Managed Grafana, but the Phase 8 methodology already permits an
explicit provider-hosted bundle when its software, compute, identity,
operations, capacity, and cost owners are modeled. Applying that rule
consistently makes the all-GCP path a valid implementation target for the new
profiles. It does not retroactively make the current or historical path
deployable.

L4 and L5 are one co-located provider bundle in v1 of the new executable
profiles. `L4 != L5` candidates are rejected before cost calculation. This is
not a claim that cross-cloud HTTPS is impossible. It is a bounded profile
decision because the selected AWS, Azure, and GCP visualizations rely on
provider-local plugins, identity, scene assets, and query backends. Supporting
six additional directed L4-to-L5 combinations would require six separately
reviewed data-source/authentication implementations and would change the
experiment.

## Profile Lifecycle

| Profile | Lifecycle after this decision | New calculation/deployment path | Existing records |
|---|---|---|---|
| `five-layer-baseline@1` | Immutable historical/paper-compatible reference | Forbidden | Read, verify, and destroy only |
| `five-layer-baseline@2` | New five-responsibility comparison control with mandatory embedded domain-event behavior | Enabled only after the full offline bundle and theoretical-capacity gates pass | Normal immutable operation |
| `six-layer-eventing@1` | New treatment profile with the same domain behavior and an independent Eventing responsibility | Enabled only after `@2` and the Event-Layer implementation gates pass | Normal immutable operation |

No implementation may silently modify `@1` to repair runtime behavior. The
current public Function-URL/shared-token cross-cloud mechanism and the direct
L3-hot-to-Grafana binding remain historical implementation evidence only.

## Common Functional Contract

Every selected provider bundle must supply:

1. authenticated bidirectional device communication;
2. telemetry ingestion and processing;
3. mandatory rule evaluation, extension action, notification workflow, and
   device-command feedback;
4. hot, cool, and archive persistence with explicit transition ownership;
5. a semantic Twin graph/state API;
6. time-series history contextualized by the Twin graph;
7. dashboard/query visualization and optional 3D scene visualization;
8. typed asynchronous domain-event delivery with bounded retry/failure;
9. typed synchronous L4-to-L5 query behavior;
10. secretless same-cloud and cross-cloud workload identity;
11. deterministic deployment, verification, observability, and cleanup;
12. complete cost ownership, even where fixed capacity is not cost-optimal.

The raw telemetry stream is not written into the managed Twin graph one API
request at a time. AWS TwinMaker, Azure Digital Twins, and the GCP Twin API
hold semantic graph/current-state materialization, while provider-specific
time-series stores retain the complete telemetry history. This is required for
functional comparability and capacity:

- AWS TwinMaker resolves external time series through component data
  connectors;
- Azure Data Explorer combines direct time-series ingestion with Azure Digital
  Twins graph context;
- the GCP Twin API combines Spanner Graph context with BigQuery time series.

The materialization policy is versioned. Structural/model/relationship and
explicit current-state changes update the graph. Raw telemetry remains
queryable through L4 but does not consume one managed graph mutation per
message.

## Event Inventory And Ownership

The service review includes every event-like mechanism already planned, but
does not label all of them the scientific Event Layer:

| Event class | Purpose | Five-layer owner | Six-layer owner |
|---|---|---|---|
| Device protocol traffic | MQTT/IoT telemetry and bidirectional commands | L1 acquisition | L1 acquisition |
| Raw telemetry backbone | Partitioned transport into processing, hot storage, and time-series ingestion | L1/L2 | L1/L2; the Event Layer does not become the raw telemetry database |
| Canonical domain events | Rule, action, workflow, notification, command, outcome, persistence, and Twin-update channels | Mandatory embedded L1/L2 behavior | Independent Eventing responsibility |
| Storage CDC/platform events | Hot-store change capture, durable storage outbox, batching, and archive schedule | L3 supporting resources | L3 supporting resources |
| Twin materialization/history events | Semantic state/model/relationship changes and provider data-history feeds | L4 supporting resources | L4 supporting resources |
| Scheduler/lifecycle events | Cool/archive movement, retention, replay/redrive, and maintenance | Owning L3/operations component | Owning L3/Eventing/operations component |
| Observability/audit events | Metrics, logs, bounded failures, and correlation evidence | Component-local platform observability | Component-local platform observability plus Event-Layer metrics |
| Management operation updates | Optimizer/deployer progress exposed to Flutter through Management SSE | Application control plane, outside the Twin layers | Application control plane, outside the Twin layers |

L4-to-L5 dashboard and scene reads are typed synchronous queries, not event
bridges. Azure Event Hubs used for ADX ingestion/data history, Kinesis/Event
Hubs/Pub/Sub used as storage outboxes, and provider audit streams remain
supporting resources in both profiles. Only the independent ownership of the
canonical domain-event quality contract creates the sixth responsibility.

## Complete Boundary Model

### Domain-Event Boundaries

The approved Phase 8.8 bridge remains the only cross-cloud transport for the
canonical domain-event channels in both new profiles:

```text
source durable outbox/broker
  -> source-provider runtime
  -> short-lived destination credential
  -> destination broker data-plane publish
  -> destination durable acceptance
  -> source acknowledgement
```

It covers all six directed AWS/Azure/GCP identity paths and the graph-derived
remote L1/L2/persistence/Twin-update consumers. Same-provider edges create no
bridge. `five-layer-baseline@2` owns this transport inside the producing
responsibility; `six-layer-eventing@1` owns it inside the Eventing
responsibility.

### Storage Transitions

Storage movement is a data-plane operation, not an Eventing payload:

| Boundary | Same-provider mechanism | Cross-provider mechanism |
|---|---|---|
| Hot to cool | Source database change capture plus a dedicated durable storage outbox and source-owned batching mover into object storage | The same source-owned batching mover obtains short-lived destination credentials and writes directly to the destination object-store API |
| Cool to archive | Provider-native object lifecycle rule where source and destination are the same object-store provider | Source-owned scheduled container mover writes directly to the destination object-store API and records an idempotent checkpoint before source expiry |

The destination does not expose a public Function endpoint. The six directed
identity exchanges already approved for Eventing are reusable trust primitives,
but storage routes have separate component IDs, permissions, cost formulas,
acknowledgement rules, failure tests, and evidence. Eventing proof is not
storage-transition proof.

The exact source-owned storage services are:

| Source provider | Hot-to-cool path | Cross-provider cool-to-archive path |
|---|---|---|
| AWS | DynamoDB Streams -> Lambda capture with retry/failure destination -> dedicated Kinesis Data Stream -> ECS/Fargate batching service | EventBridge Scheduler -> ECS/Fargate task |
| Azure | Cosmos DB Change Feed Processor in Azure Container Apps with lease container -> dedicated Event Hubs stream -> separate Azure Container Apps batching app | Scheduled Azure Container Apps Job |
| GCP | Firestore direct Eventarc event -> Cloud Run capture -> dedicated Pub/Sub subscription/dead-letter topic -> GKE batching deployment | Cloud Scheduler -> Cloud Run Job |

The common `telemetry-batch.v1` object is gzip NDJSON, flushed at 64 MiB
uncompressed or five minutes. It retains canonical event IDs and records
schema, route, window, count, and SHA-256 metadata. The transport is
at-least-once, so storage readers deduplicate by event ID.

Small and Medium use one AWS Kinesis shard, one Azure Event Hubs Standard TU,
and one initial batching-worker replica. Large uses eight Kinesis shards,
Event Hubs Standard with eight TUs and auto-inflate capped at sixteen, and
three initial worker replicas; GCP Pub/Sub uses its regional quota with three
GKE mover replicas. The Large input is 5,000 records/s and approximately
3.91 MiB/s before transport overhead, so five Kinesis shards or five Event
Hubs TUs would meet the nominal ceilings with effectively no record-rate
headroom. Eight is the reproducible functionality-first allocation.

At 64 MiB, Large fills one batch in about 16.4 seconds, or approximately 5,273
objects/day. Small and Medium hit the five-minute flush first. Worker CPU,
compression, destination latency, backlog recovery, and quota-adjustment
behavior remain live-capacity gates.

Same-provider archive transitions use S3 Lifecycle, Azure Blob lifecycle
management on an archive-compatible account, or Cloud Storage Object Lifecycle
Management. Cross-provider jobs call the destination S3, Azure Blob, or Cloud
Storage data plane with the separately permissioned AWS/Azure/GCP workload
identity exchanges. The source may be a sender on one edge and a receiver on
another; no provider has a permanent direction.

### Storage Identity Compatibility

The storage movers reuse the six short-lived identity primitives already
frozen by Phase 8.8, not the Eventing bridge components or their broker
permissions:

| Direction | Exact source assertion and exchange | Storage authorization |
|---|---|---|
| AWS -> Azure | Account-enabled regional AWS STS `GetWebIdentityToken` JWT -> Entra federated identity credential | Narrow Blob Data Contributor scope on the destination landing container |
| AWS -> GCP | AWS-signed `GetCallerIdentity` subject -> GCP Workload Identity Federation AWS provider | Narrow Cloud Storage object create/read-resume scope |
| Azure -> AWS | User-assigned managed-identity OIDC token for a dedicated audience -> AWS `AssumeRoleWithWebIdentity` | Narrow S3 multipart/`PutObject` role |
| Azure -> GCP | User-assigned managed-identity OIDC token -> GCP Workload Identity Federation OIDC provider | Narrow Cloud Storage object create/read-resume scope |
| GCP -> AWS | Google service-account OIDC ID token -> AWS `AssumeRoleWithWebIdentity` | Narrow S3 multipart/`PutObject` role |
| GCP -> Azure | Google service-account OIDC ID token -> Entra federated identity credential | Narrow Blob Data Contributor scope on the destination landing container |

Every route pins issuer, audience, subject or mapped workload identity, token
expiry, destination resource, and negative-claim tests. AWS-to-Azure also
requires account-level outbound federation and a regional STS endpoint.
These are capability-admissible patterns; real token exchange remains an
explicit supervised live gate.

### L4-To-L5

| Provider | Query path | Authentication | 3D path |
|---|---|---|---|
| AWS | Amazon Managed Grafana -> IoT TwinMaker Grafana data source -> TwinMaker graph/external time-series connector | Grafana workspace role with least-privilege TwinMaker/S3 permissions; Grafana 12 automation uses service accounts, not removed API keys | TwinMaker scene viewer and S3 scene assets |
| Azure | Azure Managed Grafana -> Azure Data Explorer data source -> ADX time series plus ADT query plugin | Grafana managed identity receives ADX Viewer and ADT Data Reader; no client secret | Azure Digital Twins 3D Scenes Studio/viewer plus private Blob assets; preview status remains visible |
| GCP | Grafana OSS on GKE -> BigQuery data source and platform Twin/scene backend plugin -> BigQuery/Spanner Graph | BigQuery plugin `Google Metadata Server` (`gce`) mode backed by GKE Workload Identity and metadata tokens; no service-account key | Platform-owned Grafana panel/viewer with Cloud Storage assets |

The current generic JSON-API datasource is rejected. The predecessor path
queries L3 directly, cannot prove the L4 contract, uses post-deploy mutable
configuration, and does not provide one reviewed secretless authentication
path for all providers.

## Scenario Semantics

Phase 8 retains two scenario families and pairs them by size for final profile
evaluation. They are not treated as interchangeable measurements.

### Core Twin Scenarios

The current UI presets are frozen as `core-*-v2` after correcting their
ambiguous Twin and dashboard semantics:

| Field | Small | Medium | Large |
|---|---:|---:|---:|
| Devices | 100 | 4,000 | 30,000 |
| Telemetry interval | 120 s | 30 s | 6 s |
| Average payload | 0.25 KiB | 0.5 KiB | 0.8 KiB |
| Average telemetry rate | 0.833/s | 133.333/s | 5,000/s |
| Messages/month | 2,160,000 | 345,600,000 | 12,960,000,000 |
| Twin entities | 100 | 4,000 | 30,000 |
| 3D scene entities | 0 | 0 | 1,200 |
| 3D asset size | N/A | N/A | 100 MiB |
| Aggregate dashboard refreshes/hour | 12 | 60 | 120 |
| API calls/aggregate refresh | 1 | 10 | 100 |
| Dashboard active hours/day | 1 | 4 | 8 |
| Aggregate active-window query rate | 0.0033/s | 0.1667/s | 3.3333/s |
| Monthly editor/viewer seats | 2/0 | 25/10 | 100/300 |
| Twin-state materializations/s | 0.1 | 2.5 | 50 |
| Twin graph/model updates/s | 0.01 | 0.1 | 1 |

`aggregate dashboard refreshes/hour` is explicitly workspace-wide. Editor and
viewer counts are billing/admission quantities and are not silently multiplied
into the query rate. A later study may add measured concurrent-user traffic
as a new scenario version.

`twinEntityCount` and `sceneEntityCount` are separate workload fields.
`entityCount` in the predecessor API is a legacy 3D-scene field and cannot
remain the TwinMaker/ADT/Spanner graph-capacity input.

The state/graph update bounds are synthetic capacity inputs, not observed
traffic. State materialization changes the latest operational state; graph
updates change models, entities, relationships, or scene bindings. Raw
telemetry remains in the time-series backend.

### Domain-Event Scenarios

The approved Phase 8.8 scenarios remain unchanged:

| Scenario | Events/month | Peak events/s | Payload | Active keys/devices |
|---|---:|---:|---:|---:|
| `eventing-small-v1` | 100,000 | 10 | 4 KiB | 100 |
| `eventing-medium-v1` | 10,000,000 | 250 | 16 KiB | 10,000 |
| `eventing-large-v1` | 100,000,000 | 2,500 | 64 KiB | 100,000 |

For Phase 8.10, Small pairs with Small, Medium with Medium, and Large with
Large. Device/partition-key count and Twin-entity count remain separate because
multiple sensors may belong to one modeled asset. Every result must expose both
inputs.

## Capacity Evaluation

### AWS

- DynamoDB on-demand can cover the 5,000 message/s core peak below the default
  40,000 table-level read/write-unit quota when item size and partition-key
  distribution satisfy the frozen workload; hot-partition and burst tests
  remain mandatory.
- TwinMaker's default 50,000 entities/workspace covers the 30,000-entity Large
  graph. Its non-adjustable 100 TPS data API limit covers the 3.333 aggregate
  L5 query/s only because raw telemetry is externalized rather than written to
  TwinMaker per message.
- Amazon Managed Grafana's 10,000 provisioned/500 concurrent users per
  workspace cover the conservative 400-seat Large admission bound. The actual
  concurrency remains a live observation, not an inferred fact.
- The Phase 8.8 Kinesis/SNS/SQS/Lambda configuration covers the Eventing
  scenario peaks subject to its existing supervised load gates.

Decision: theoretically admissible for all paired scenarios; live
partitioning, connector, Grafana, bridge, and failure tests still gate a
live-readiness claim.

### Azure

- Cosmos DB dynamic autoscale must derive `Tmax` from measured RU/record and
  storage, with `device_id` or another reviewed high-cardinality partition key.
  The Large path is not allowed to assume the minimum 1,000 RU/s.
- Azure Digital Twins' default two-million-twin limit and 500 query
  requests/s cover 30,000 entities and 3.333 aggregate query/s. Raw telemetry
  is ingested into ADX; graph mutation remains below the 1,000 patch/s default
  through the versioned materialization policy.
- ADX uses `Standard_E8ads_v5` with capacity 2 for Small/Medium and capacity 4
  for Large as the reproducible initial configuration. Small may use streaming
  ingestion. Medium/Large use queued ingestion with an explicit batching policy
  because their peak byte rate exceeds the published 4-GB/hour streaming
  guidance. Exact query/ingestion performance remains workload-dependent and
  therefore requires the named OrbStack integration tests plus a supervised
  live load gate.
- Azure Managed Grafana uses Standard X1 for Small/Medium and X2 for Large,
  Grafana 12, managed identity, and ADX/ADT role assignments. The published
  90 requests/IP/s and datasource limits are tested against aggregate rather
  than per-seat synthetic traffic.
- The Large 100-MiB scene asset matches the recommended Azure 3D Scenes Studio
  file-size limit. Preview status, refresh behavior, and scene configuration
  are residual risks and must remain visible.

Decision: theoretically admissible for all paired scenarios with an explicit
ADX live-capacity and 3D-preview gate.

### GCP

- Pub/Sub, Cloud Run, BifroMQ/GKE, and bridge capacity remain governed by the
  approved Phase 8.8 configuration and live gates.
- The Cloud Run Twin materializer uses bounded concurrency and the BigQuery
  Storage Write API default stream. The acknowledged default stream makes data
  immediately queryable with at-least-once semantics; idempotency uses the
  canonical event ID.
- Regional Spanner Graph uses Enterprise edition and SSD storage. Small and
  Medium start at one node; Large starts at two nodes. Google's approximate
  regional guidance of 3,500 writes/s per node covers the synthetic
  50 state materializations/s plus one graph/model update/s with substantial
  theoretical margin. The 5,000 raw telemetry messages/s flow to BigQuery,
  not into Spanner Graph. Throughput-optimized writes and schema/partition
  design remain live-test concerns.
- Grafana OSS 12 runs on a dedicated GKE node pool. Its BigQuery datasource is
  pinned to plugin `3.2.0` and uses `Google Metadata Server` (`gce`) mode
  against the GKE metadata server. The platform Twin/scene plugin uses the same
  workload identity boundary. The plugin's separately named Workload Identity
  Federation mode is not selected because it is Grafana-Cloud-only. No JSON
  service-account key is generated.
- The provider-hosted L4/L5 bundle must pin software versions, image digests,
  licenses, replicas, node pools, load balancer, persistent configuration,
  backup, logging, upgrades, cleanup, and all fixed/variable costs.

Decision: theoretically admissible for all paired scenarios after the
platform-owned Twin/Grafana plugin contract is implemented; live Spanner,
BigQuery, GKE, and failure gates remain mandatory.

## Single-Cloud And Multi-Cloud Result Space

The new profiles evaluate:

- three complete single-cloud paths: all AWS, all Azure, and all GCP;
- mixed L1-L3 and Eventing placements across all providers;
- all six directed asynchronous domain-event bridge routes;
- all six directed hot/cool and cool/archive storage-transition routes;
- only three co-located L4/L5 bundles.

This does not require one provider to be permanently a sender or permanently a
receiver. The same provider may own several responsibilities and may send on
one edge and receive on another. Route direction is resolved per edge.

The Eventing Layer is a separate scientific responsibility only in
`six-layer-eventing@1`. Azure Event Hubs inside the Azure L4 bundle and any
broker/outbox inside the embedded five-layer profile are supporting resources;
their existence does not add a sixth layer.

## Rejected Alternatives

| Alternative | Reason |
|---|---|
| Keep the public Function-URL plus shared `INTER_CLOUD_TOKEN` | Long-lived shared secret, public endpoint, and mismatch with the declared workload-identity contract |
| Treat the Eventing bridge proof as proof for storage movers | Different payload, acknowledgement, API, permission, retry, and cost semantics |
| Query L3 directly from Grafana | Bypasses the modeled L4 responsibility and produces optimizer/deployer divergence |
| Allow all six cross-provider L4/L5 directions now | Requires separate plugin/authentication implementations and changes the bounded experiment |
| Keep GCP permanently unsupported because no managed Digital Twin product exists | Inconsistent with the accepted provider-hosted GCP device boundary and the functionality-first selection rule |
| Use Grafana JSON API/Infinity as the universal L5 adapter | Authentication/maintenance limitations and no complete secretless, fully automated path across all selected managed Grafana environments |
| Configure the GCP BigQuery plugin with `workloadIdentityFederation` mode | That plugin mode is Grafana-Cloud-only; self-hosted Grafana on GKE uses `Google Metadata Server` mode backed by Workload Identity for GKE |
| Use ADT data history for every raw telemetry sample | Exceeds the intended graph-update boundary and couples high-rate telemetry to ADT mutation limits |
| Use `entityCount` for both scene objects and Twin entities | Produces zero Twin entities for current Small/Medium scenarios and invalid capacity/cost evidence |
| Use the Azure Functions Cosmos trigger as the sole durable storage capture | Its handler behavior does not supply the selected retry/checkpoint contract after an unhandled batch; the selected Container Apps host runs the Change Feed Processor with a lease container and documented at-least-once behavior |

## Offline Activation And Live-Readiness Gates

For this PoC, activation means new selection plus an implemented calculation,
resolution, packaging, and deployment path. Verification during this phase is
repository-controlled and no-apply. No new profile reaches that state until
all of the following offline gates pass:

1. versioned complete-provider bundle and workload contracts;
2. exact cost formulas for every supporting resource;
3. six domain-event and six storage-transition trust/permission routes;
4. removal of the shared-token/public-Function mechanism from all new-profile
   operations;
5. native/provider-hosted L4/L5 deployment, datasource, identity, 3D, cleanup,
   and rollback tests;
6. Small/Medium/Large offline capacity calculations for both scenario
   families;
7. OrbStack-backed cross-stack tests and Terraform no-apply/mock-plan gates;
8. supervised live identity and load gates represented explicitly as pending,
   without being reported as successful;
9. two zero-finding implementation reviews.

An activated offline profile is not thereby live-ready. A live deployment,
measured capacity result, or production-readiness claim additionally requires
the separately approved supervised gates to pass.

## Primary Source Ledger

- [AWS IoT TwinMaker quotas](https://docs.aws.amazon.com/general/latest/gr/iot-twinmaker.html)
- [AWS IoT TwinMaker and Amazon Managed Grafana](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/amazon-managed-grafana.html)
- [AWS IoT TwinMaker Grafana integration and scene viewer](https://docs.aws.amazon.com/iot-twinmaker/latest/guide/grafana-integration.html)
- [Amazon Managed Grafana quotas](https://docs.aws.amazon.com/grafana/latest/userguide/AMG_quotas.html)
- [Amazon Managed Grafana 12 differences](https://docs.aws.amazon.com/grafana/latest/userguide/version-differences.html)
- [DynamoDB on-demand capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html)
- [DynamoDB Streams and Lambda triggers](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.Lambda.html)
- [DynamoDB event-source retry and failure destinations](https://docs.aws.amazon.com/lambda/latest/dg/services-dynamodb-errors.html)
- [Kinesis Data Streams quotas and limits](https://docs.aws.amazon.com/streams/latest/dev/service-sizes-and-limits.html)
- [EventBridge Scheduler for ECS tasks](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/tasks-scheduled-eventbridge-scheduler.html)
- [S3 Object Lifecycle Management](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)
- [AWS outbound identity federation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_outbound.html)
- [AWS STS `GetWebIdentityToken`](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetWebIdentityToken.html)
- [AWS `AssumeRoleWithWebIdentity`](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_request.html)
- [Azure Digital Twins limits](https://learn.microsoft.com/en-us/azure/digital-twins/reference-service-limits)
- [Azure Digital Twins data history](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-data-history)
- [Azure Digital Twins query plugin for Azure Data Explorer](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-data-explorer-plugin)
- [Azure Data Explorer streaming-ingestion guidance](https://learn.microsoft.com/en-us/azure/data-explorer/ingest-data-streaming)
- [Azure Data Explorer cluster creation and `Standard_E8ads_v5`](https://learn.microsoft.com/en-us/azure/data-explorer/create-cluster-database)
- [Azure Managed Grafana Azure Data Explorer datasource](https://learn.microsoft.com/en-us/azure/managed-grafana/how-to-connect-azure-data-explorer)
- [Azure Managed Grafana 12](https://learn.microsoft.com/en-us/azure/managed-grafana/how-to-upgrade-grafana-12)
- [Azure Digital Twins 3D Scenes Studio](https://learn.microsoft.com/en-us/azure/digital-twins/concepts-3d-scenes-studio)
- [Cosmos DB autoscale throughput](https://learn.microsoft.com/en-us/azure/cosmos-db/autoscale-faq)
- [Cosmos DB change feed with Azure Functions](https://learn.microsoft.com/en-us/azure/cosmos-db/read-change-feed)
- [Cosmos DB Change Feed Processor](https://learn.microsoft.com/en-us/azure/cosmos-db/change-feed-processor)
- [Azure Event Hubs quotas and limits](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/azure-subscription-service-limits#azure-event-hubs-limits)
- [Azure Container Apps jobs](https://learn.microsoft.com/en-us/azure/container-apps/jobs)
- [Azure Blob lifecycle management](https://learn.microsoft.com/en-us/azure/storage/blobs/lifecycle-management-policy-configure)
- [Microsoft Entra federated identity credential trust](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust)
- [Spanner Graph overview](https://cloud.google.com/spanner/docs/graph/overview)
- [Spanner performance guidance](https://cloud.google.com/spanner/docs/performance)
- [BigQuery Storage Write API](https://cloud.google.com/bigquery/docs/write-api-streaming)
- [Cloud Run quotas](https://cloud.google.com/run/quotas)
- [Workload Identity Federation for GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity)
- [Firestore direct events to Cloud Run](https://cloud.google.com/eventarc/standard/docs/run/route-trigger-cloud-firestore)
- [Eventarc at-least-once delivery and retry](https://cloud.google.com/eventarc/docs/retry-events)
- [Pub/Sub quotas and limits](https://cloud.google.com/pubsub/quotas)
- [Scheduled Cloud Run jobs](https://cloud.google.com/run/docs/execute/jobs-on-schedule)
- [Cloud Storage Object Lifecycle Management](https://cloud.google.com/storage/docs/lifecycle)
- [Workload identities for external AWS and Azure workloads](https://cloud.google.com/iam/docs/workload-identities)
- [Grafana BigQuery datasource](https://grafana.com/docs/plugins/grafana-bigquery-datasource/latest/configure/)

Primary sources prove published capabilities and limits. They do not replace
the required implementation and live workload tests.
