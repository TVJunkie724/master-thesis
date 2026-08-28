---
title: "Provider Service Selection Evolution"
description: "Trace from predecessor service mappings to the bounded Six-layer provider bundles."
tags: [thesis, architecture, services, providers, traceability]
lastUpdated: "2026-08-28"
version: "1.0"
---

# Provider service selection evolution

Status: active thesis rationale; current bundles are offline-verified and live
validation remains pending.

## Purpose

Architecture evolution includes both changes to logical responsibilities and
changes to the cloud services that realize them. A layer can keep the same name
while its protocol, durability, pricing, operational behavior, and deployment
risk change substantially. The thesis must therefore explain service changes
instead of presenting the final provider bundle as the original design.

This register complements
[`architecture_evolution.md`](architecture_evolution.md). It records the
service-level delta, while that document records the larger architectural
decisions and their research-question relationship.

## Comparison sources and interpretation

The comparison uses three different source roles:

| Source | Role |
|---|---|
| `2-twin2clouds/json/service_mapping.json` | Predecessor/compatibility mapping of functional slots to broad provider service labels |
| `docs/research/evidence/phase_08_service_bundles/complete-provider-bundles.json` | Current selected closed-world provider bundles and rejected alternatives |
| `docs/research/evidence/phase_08_service_bundles/implementation-component-manifest.json` | Concrete Terraform/runtime ownership and current offline implementation state |

The predecessor mapping is not treated as proof that every named service was a
complete or deployable implementation. Conversely, the current manifest is not
live evidence merely because Terraform resources exist.

Changes use the following classification:

- **retained** — the provider service family and responsibility remain the
  same;
- **refined** — the broad family remains, but tier, access path, data model, or
  support components are made explicit;
- **replaced** — another service or hosting model realizes the responsibility;
- **added** — an implicit responsibility now has an explicit service and cost
  owner; and
- **removed/absorbed** — a formerly named service is no longer independently
  required because a narrower endpoint or another bundle owns its behavior.

## Cross-cutting architecture and service changes

| ID | Earlier representation | Current representation | Class | Reason and thesis consequence | Status |
|---|---|---|---|---|---|
| SE-01 | Eventing was implicit in functions, triggers, and broad `event_bus` labels | Independent non-linear Event Layer with explicit provider bundles, routes, retry/DLQ, replay, monitoring, identities, and cost ownership | added/replaced | Makes Eventing observable for RQ3.2 and prevents hidden integration cost | offline-verified; live pending |
| SE-02 | `AWSEvents`, Azure Event Grid, and Cloud Pub/Sub appeared as comparable one-service mappings | AWS uses Kinesis/SNS/SQS/Lambda/S3 failure storage; Azure uses Event Hubs/Service Bus/Functions; GCP uses separated Pub/Sub topics and Cloud Run event services | replaced/refined | Product-name equivalence did not prove common durability, ordering, fan-out, retry, or command behavior | offline-verified; live pending |
| SE-03 | `AWSDataTransfer`, Azure Bandwidth, and GCP Compute Engine acted mainly as broad transfer/pricing labels | Directed source-owned bridges, short-lived destination identity, durable destination acceptance, and exactly-once cost attribution per edge | replaced | Turns cross-cloud transfer into an executable, auditable contract rather than an unowned charge | offline-verified; live pending |
| SE-04 | Cool/archive storage named the destination service but did not close every cross-cloud transition | Provider schedulers plus finite source-owned storage movers write directly to destination object storage | added | Lifecycle policy alone cannot implement every cross-provider transition with the same evidence and identity boundary | offline-verified; live pending |
| SE-05 | API Gateway/API Management/GCP API Gateway were broad data-access mappings | Bounded authenticated service-local reader endpoints: AWS Lambda Function URL, Azure Function endpoint, and GCP Cloud Run endpoint | removed/absorbed | Avoids three additional gateway products when one typed PoC read contract is sufficient | offline-verified; live pending |

## AWS service evolution

| Responsibility | Predecessor mapping | Current bounded bundle | Class | Rationale/impact |
|---|---|---|---|---|
| L1 acquisition | `AWSIoT` | AWS IoT Core plus explicit command behavior | refined | Retains the native device boundary while making bidirectional command/outcome behavior part of RQ2 |
| L2 processing | AWS Lambda | Lambda plus Step Functions Standard for the bounded processing workflow | refined | Makes orchestration ownership and cost explicit instead of treating every step as an undifferentiated function |
| L3 hot | Amazon DynamoDB | DynamoDB on-demand raw and hourly-rollup stores | refined | Declares data shapes, reads/writes, and pricing dimensions used by L5 |
| L3 cool | Amazon S3 | S3 Standard-Infrequent Access | refined | Pins the storage class rather than a generic S3 label |
| L3 archive | Amazon S3 | S3 Glacier Deep Archive | refined | Pins archive semantics and minimum-duration pricing |
| L4 Twin | IoT TwinMaker | IoT TwinMaker Standard | retained/refined | Keeps the native semantic Twin surface and fixes the priced edition |
| L5 visualization | Amazon Grafana | Amazon Managed Grafana 12, Lambda raw-history reader, and Marcus Olsson JSON datasource | refined | Closes the actual authenticated read path instead of pricing only a dashboard service |
| Event Layer | `AWSEvents`/provider-native triggers | Kinesis Data Streams, SNS FIFO, SQS FIFO, Lambda event worker, S3 failure store, and CloudWatch | replaced/added | Separates telemetry streaming, control fan-out, durable work, terminal failure ownership, and observability |
| Storage transitions | EventBridge scheduler label plus storage services | EventBridge Scheduler and an ECS Fargate finite storage mover | refined/added | Gives cross-cloud cool/archive movement an executable source owner |
| Data access | Amazon API Gateway | Authenticated Lambda Function URL for the bounded raw-history reader | removed/absorbed | Removes a product surface not required by the common read contract |

## Azure service evolution

| Responsibility | Predecessor mapping | Current bounded bundle | Class | Rationale/impact |
|---|---|---|---|---|
| L1 acquisition | Azure IoT Hub | Azure IoT Hub | retained/refined | Retains the native device boundary and evaluates command/outcome behavior explicitly |
| L2 processing | Azure Functions | Functions Flex Consumption plus Logic Apps Consumption | refined | Pins the compute plan and makes workflow ownership explicit |
| L3 hot | Azure Cosmos DB | Cosmos DB for NoSQL raw and rollup data | refined | Fixes API, data roles, capacity mode, and pricing dimensions |
| L3 cool | Azure Storage | Blob Storage Cool | refined | Replaces a generic account label with the evaluated access tier |
| L3 archive | Azure Storage | Blob Storage Archive | refined | Fixes archive semantics and minimum-duration cost |
| L4 Twin | Azure Digital Twins | Azure Digital Twins | retained | Keeps the native semantic graph/twin service |
| L5 visualization | Azure Grafana Service | Azure Managed Grafana 12 Standard, Functions Flex raw-history reader, and Marcus Olsson JSON datasource | refined | Closes the real datasource path and seat/capacity cost |
| Event Layer | Event Grid/provider-native triggers | Event Hubs, Service Bus Standard, Functions Flex event workers, Azure Monitor, and shared Log Analytics | replaced/added | Uses different services for retained streams, durable queues, workers, and operations rather than forcing one Event Grid abstraction |
| Storage transitions | No dedicated scheduler in the broad mapping | Scheduled Azure Container Apps storage job | added | Provides finite source-owned cross-cloud transitions without a permanent worker |
| Data access | Azure API Management | Authenticated Azure Function endpoint for the bounded raw-history reader | removed/absorbed | Avoids an API-management product not required by the PoC read surface |

## GCP service evolution

| Responsibility | Predecessor mapping | Current bounded bundle | Class | Rationale/impact |
|---|---|---|---|---|
| L1 acquisition | Cloud Pub/Sub | Apache BifroMQ on GKE, external load balancer, ordered MQTT-to-Pub/Sub adapter, and Pub/Sub backend | replaced/added | Pub/Sub is not itself the bidirectional MQTT device/session boundary required by RQ2 |
| L2 processing | Cloud Functions | Cloud Run service plus Workflows | replaced/refined | Uses the selected containerized processing and explicit workflow boundary |
| L3 hot | Firestore | Firestore Native Standard raw and rollup collections | refined | Pins edition, database mode, data roles, sharding assumptions, and pricing dimensions |
| L3 cool | Cloud Storage Nearline | Cloud Storage Nearline | retained/refined | Retains the service while fixing workload and transition ownership |
| L3 archive | Cloud Storage Archive | Cloud Storage Archive | retained/refined | Retains the service while fixing minimum-duration and operation costs |
| L4 Twin | Compute Engine | Cloud Run Twin API/materializer, bounded Firestore Twin data, IAP-protected Cloud Run explorer, and direct IAP access | replaced | Supplies a bounded semantic Twin surface without claiming a native GCP equivalent to TwinMaker or Azure Digital Twins |
| L5 visualization | Compute Engine | Grafana OSS 12 on GKE, persistent disk, Cloud Run raw-history reader, Infinity datasource, and TLS load balancer | replaced/refined | Turns an unspecified VM into a reproducible, inspectable visualization bundle |
| Event Layer | Cloud Pub/Sub | Separated Event-Layer Pub/Sub topics, Cloud Run event service/adapter or fixed Large worker pool, Logging, and Monitoring | refined/added | Retains Pub/Sub durability while separating Event-Layer resources from L1 and exposing compute/operations costs |
| Storage transitions | No dedicated scheduler in the broad mapping | Cloud Scheduler and a finite Cloud Run storage job | added | Provides explicit source-owned transition execution |
| Data access | GCP API Gateway | Authenticated Cloud Run reader endpoint | removed/absorbed | Keeps one typed service-local PoC read surface without a gateway product |

## Open and bounded decisions

The register distinguishes service capability from capacity and product
maturity:

- GCP L1's BifroMQ-plus-Pub/Sub capability is the current functional decision.
  Small is fixed offline to one non-HA `e2-standard-4` broker node and one
  `e2-standard-2` adapter node; this is not a production-availability claim.
- The selected Small GCP L1 bundle remains live-unvalidated until one supervised
  component probe records readiness, latency, cleanup, and observed cost.
- GCP L4 and L5 are bounded provider-hosted PoC implementations, not claims of
  managed-service equivalence or production availability.
- Medium and Large allocations remain theoretical unless separately executed
  and recorded.
- Every selected bundle remains an offline architecture result until the live
  evaluation supplies provider evidence.

## Update rule for later changes

Any later service addition, replacement, tier change, hosting change, or
removal must be recorded here before the active provider bundle is refrozen.
The entry must state:

1. old and new service identifiers;
2. logical responsibility and affected edge contracts;
3. trigger for the change;
4. alternatives considered;
5. functional-equivalence consequence;
6. pricing and optimizer consequence;
7. Terraform/runtime and credential consequence;
8. evidence maturity; and
9. thesis sections and RQs affected.

A service change is not described as a mere implementation detail when it
changes protocol semantics, durability, latency path, access model, cost
formula, or validity of the provider comparison.

## Thesis placement

The Predecessor Analysis summarizes the broad original mappings. The Method
explains why functional bundles replace product-name matching. System
Architecture presents only the accepted compositions. Evaluation reports the
measured bundle behavior and cost. Discussion interprets service changes,
rejected alternatives, and provider-specific limitations. Detailed component
lists remain repository evidence rather than being copied wholesale into the
thesis body.
