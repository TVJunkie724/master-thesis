# Phase 8 Eventing Decision Evidence

## Status

This directory is the working evidence package for Phase 8.8 and GitHub issue
#146.

**Research cut-off:** 2026-07-20

**Regions:** AWS `eu-central-1`, Azure `westeurope`, GCP `europe-west1`

**Current decision status:** `draft-envelope-and-manifest-pending`

The capability, compatibility, theoretical-capacity, source, and normalized
pricing reviews below are complete enough to nominate provider bundles. It is
not the final Phase 8.8 approval. The bridge/envelope decision, the
implementation-component manifest, the complete package validator, and the
independent approval reviews are still required.

No runtime code or cloud resource is changed by this evidence.

## Profile Boundary

The evaluated profiles have three different roles:

| Profile | Role |
|---|---|
| `five-layer-baseline@1` | Immutable historical/paper-compatible reference. Its omitted optional event paths remain omitted. |
| `five-layer-baseline@2` | Five-responsibility control profile. Rule evaluation, extension action, notification workflow, and device-command feedback are always present as embedded L1/L2 behavior. |
| `six-layer-eventing@1` | Treatment profile with the same domain-event behavior as `five-layer-baseline@2`, plus independent routing, buffering, fan-out, retry/DLQ, replay, ordering, observability, and cross-cloud transport ownership. |

The new profiles contain no `useEventChecking`,
`triggerNotificationWorkflow`, or `returnFeedbackToDevice` switch. A typed rule
match controls invocation volume; it does not control component presence.

The fair comparison is therefore not "without events" versus "with events".
It is embedded event behavior versus the same behavior with a separately owned
Eventing responsibility. The historical `@1` result is reproduced separately.

Functional parity covers the same event types, rule matches, actions,
workflows, device commands, outcomes, and scenario volumes. It does not claim
identical transport quality. The embedded profile records what its direct
edges actually provide; the treatment must additionally satisfy the
Event-Layer at-least-once, ordering, fan-out, replay, DLQ, and observability
contract. That quality delta is an evaluation result, not a hidden baseline
requirement.

## Shared Domain Flow

```text
device telemetry
  -> telemetry.received.v1
  -> processing
  -> telemetry.processed.v1
       +-> persistence
       +-> Twin state update
       +-> event-rule evaluation
              -> event.matched.v1
                   +-> extension action
                   +-> notification.requested.v1 -> stateful workflow
                   +-> device.command.requested.v1 -> device adapter
```

Each extension action, workflow, and device command emits one typed terminal
outcome. Storage lifecycle movement stays storage-owned and does not send object
payloads through the event broker. Query/read traffic remains synchronous.

The reference notification workflow has four steps: three provider-local
orchestration/control steps and one external notification delivery. This keeps
the user-visible behavior fixed without erasing Azure connector calls or the
internal/external-step distinction in Google Workflows. Required observability
uses a 1% sample of both full-payload telemetry publications and complete
capture of matches, notification/command requests, terminal outcomes, retries,
dead letters, replays, and bridge terminal failures. Every projected log record
is modeled as 1 KiB with 30-day retention. These are synthetic evaluation
assumptions, not observed production traffic or a recommended logging policy.

The incremental Event-Layer delivery adapter is modeled at 50 ms and 256 MiB
with one invocation per broker delivery. No consumer batch factor is invented;
the only explicit batching assumption in v1 remains the bridge maximum of ten
events. AWS Lambda and Azure Functions apply their own billing allocations and
duration blocks, while Google Cloud Run uses the reviewed request-based
resource allocation. The adapter is separate from the domain processor so its
incremental cost cannot disappear as unpriced glue.

## Corrected Capacity Basis

Every telemetry event carries a 1 KiB canonical-envelope overhead after device
ingress. Both `telemetry.received.v1` and `telemetry.processed.v1` carry the
full scenario telemetry payload. The Event-Layer therefore receives two
telemetry publications per source event.

| Scenario | Canonical telemetry event | Peak telemetry | Event-Layer publish throughput | Event-Layer delivery throughput | Rule checks / matches / workflow / command per second |
|---|---:|---:|---:|---:|---:|
| Small | 5 KiB | 10/s | 0.1024 MB/s | 0.2048 MB/s | 10 / 0.1 / 0.025 / 0.025 |
| Medium | 17 KiB | 250/s | 8.704 MB/s | 17.408 MB/s | 250 / 2.5 / 0.625 / 0.625 |
| Large | 65 KiB | 2,500/s | 332.8 MB/s | 998.4 MB/s | 2,500 / 25 / 6.25 / 6.25 |

Delivery throughput is one `telemetry.received.v1` processing delivery plus
three processed-telemetry deliveries for Small/Medium and five for Large.
Control and outcome channels are additional but do not determine the selected
throughput tier.

Capacity allocations below include at least 20% headroom over serialized
application bytes. Provider-internal replication and network protocol overhead
are not invented as payload. They remain explicit sensitivity limitations.

## Selected Embedded Bundles: `five-layer-baseline@2`

These resources belong to their existing L1/L2 responsibilities. They do not
create an independently selectable Eventing layer.

| Provider | Device/telemetry boundary | Embedded processing and direct edges | Stateful notification | Device command | Result |
|---|---|---|---|---|---|
| AWS | AWS IoT Core MQTT/HTTPS plus an IoT rule | Lambda processor, rule evaluator, extension adapter, and bounded asynchronous Lambda delivery with failure destinations | Step Functions Standard | AWS IoT Commands over reserved MQTT topics | Capability-admissible; live verification pending |
| Azure | IoT Hub; Event Hubs-compatible route to the processor avoids the Event Grid Basic throughput ceiling | Azure Functions processor, rule evaluator, extension adapter, and bounded direct delivery | Logic Apps Consumption (stateful multitenant) | IoT Hub cloud-to-device per-device queue | Capability-admissible; live verification pending |
| GCP | Pub/Sub HTTPS/gRPC publisher boundary with per-device ordering key | Cloud Run functions/services for processor, rule evaluator, extension adapter, and authenticated direct delivery | Google Cloud Workflows | Pub/Sub command outbox plus Apache BifroMQ 4.0.0-incubating delivery cluster on GKE Standard | Capability-admissible for the PoC with explicit hosted-boundary and incubation-risk caveats |

Cross-cloud direct responsibility edges do not fall back to public
function-to-function invocation. A remote edge adds the same source-owned
durable outbox and bridge-forwarder pattern described below, but that resource
is costed to the producing five-layer responsibility rather than to a separate
Eventing responsibility.

### GCP Device-Boundary Qualification

Pub/Sub is not an MQTT device broker, and the current repository's
`google.cloud.iot_v1` command path targets the retired Cloud IoT Core API. It
cannot be retained as a working command implementation.

The selected proof-of-concept boundary is:

```text
telemetry:
  device/gateway -> Pub/Sub over HTTPS or gRPC

commands:
  device-command adapter -> BifroMQ MQTT topic -> connected device
```

The hosted command boundary is deliberately limited to commands and command
outcomes; the 166.4 MB/s Large telemetry stream does not need to traverse the
MQTT broker. The selected reference deployment is:

- Apache BifroMQ `4.0.0-incubating`, pinned to
  `sha256:14856495892e3b84d25092a90de3c2fc149a3482afd283abb95fdff18effd924`;
- three all-in-one cluster nodes on a regional GKE Standard cluster;
- one `e2-standard-8` node per broker pod/zone as the initial capacity
  dimension;
- an external passthrough Network Load Balancer;
- MQTT QoS 1 persistent sessions, with the Pub/Sub command subscription—not
  the broker session—as the end-to-end durable command owner;
- device mTLS with certificate common name mapped to client ID;
- an allow-by-client-ID command topic and deny-by-default authorization rule;
- persistent volumes, Prometheus-compatible metrics, and explicit backup,
  upgrade, and cleanup ownership.

Google's architecture guidance explicitly requires a standalone MQTT broker on
GKE or Compute Engine for this type of bidirectional device flow. This is a
provider-hosted software component, not a managed GCP IoT service. Its resource,
license, maintenance, and observability costs must remain visible.

The command adapter keeps the ordered Pub/Sub command delivery unacknowledged
until a correlated terminal device outcome arrives. Broker or node loss causes
redelivery with the same command ID; the device must deduplicate that ID.
MQTT persistent sessions reduce offline-device latency but are not treated as
the end-to-end durable acknowledgement boundary.

BifroMQ's published persistent-session benchmark reports one million
connections on one node at about 18 GB of memory. The Large scenario contains
100,000 concurrent device connections and only 6.25 command messages/s. Three
`e2-standard-8` nodes therefore provide theoretical headroom, but the dimension
and immutable image are not substitutes for the supervised Phase 8 load,
partition, and node-failure tests. BifroMQ is an Apache Incubator project. Its
Apache-2.0 license avoids an unpriced software subscription, but incubation is
an explicit operational-maturity risk that is acceptable only for this PoC
decision and must be reassessed before production use.

## Selected Event-Layer Bundles: `six-layer-eventing@1`

| Responsibility | AWS bundle | Azure bundle | GCP bundle |
|---|---|---|---|
| Ordered telemetry log | Two provisioned Kinesis Data Streams | `telemetry.received` and `telemetry.processed` Event Hubs | Two Pub/Sub topics with ordering keys |
| Independent fan-out | Kinesis enhanced fan-out consumer per named consumer | Consumer group per named consumer | Subscription per named consumer |
| Durable control/action delivery | SNS FIFO topic plus one SQS FIFO queue per consumer | Service Bus Standard topics/queues with sessions | Ordered Pub/Sub subscriptions |
| Retry and terminal failure | Lambda event-source retry/bisect plus S3 full-record failure destination; SQS DLQs for control | Functions Event Hubs retry policy plus explicit dead-letter Event Hub; Service Bus DLQs | Subscription retry policy and dead-letter topic |
| Retention and replay | Kinesis retention; SNS FIFO archive/replay for control | Event Hubs retention and checkpoint replay; explicit redrive processor | Topic retention plus subscription Seek/snapshot |
| Workflow | Step Functions Standard | Logic Apps Consumption (stateful multitenant) | Workflows |
| Device command | AWS IoT Commands | IoT Hub cloud-to-device queue | Hosted BifroMQ/GKE command boundary |
| Consumers and bridges | Lambda/KCL adapters | Azure Functions Event Hubs/Service Bus adapters | Cloud Run push for Small/Medium; StreamingPull worker pools for Large |
| Observability | CloudWatch metrics/logs and bounded failure destinations | Azure Monitor/Application Insights and broker metrics | Cloud Monitoring/Logging and subscription backlog/DLQ metrics |

### AWS Capacity

Kinesis provisioned mode is selected because `eu-central-1` on-demand streams
otherwise have a documented 200 MB/s regional scaling ceiling unless an
increase is granted. Each provisioned shard supplies 1 MB/s write and 2 MB/s
read. Each enhanced-fan-out consumer receives its own 2 MB/s per shard and a
provisioned stream supports 20 registered consumers.

| Scenario | Shards on `telemetry.received` | Shards on `telemetry.processed` | Total | Qualification |
|---|---:|---:|---:|---|
| Small | 1 | 1 | 2 | Pass |
| Medium | 6 | 6 | 12 | Pass |
| Large | 200 | 200 | 400 | Pass |

For Large, each stream must carry 166.4 MB/s. Two hundred shards provide
200 MB/s write capacity, and each of the five processed-stream consumers gets
400 MB/s dedicated read capacity. The total remains below the documented
1,000-or-6,000 default shard quota range for non-large AWS regions, but
deployment preflight must read the actual account quota and fail before plan
when it is below 400.

The AWS IoT Core boundary also passes Large without a quota increase:

- 2,500 raw 64-KiB publishes/s are below the 20,000 inbound publishes/s quota;
- 2,500 rule evaluations/s are below the 20,000 evaluations/s quota;
- 64 KiB is below the 128-KiB MQTT payload limit; and
- 100,000 active device keys distribute traffic far below the per-connection
  publish and throughput limits.

Control peaks are only 25 matches/actions per second and 6.25 workflow and
command requests per second. FIFO SNS/SQS and Step Functions Standard capacity
are not the limiting dimensions. Large requires 6.25
`StartCommandExecution` calls/s, below the documented 100/s default regional
quota, and the commands/jobs data endpoint is available in `eu-central-1`.
The 125 concurrent rule-evaluator executions implied by 2,500 events/s at
50 ms fit inside Lambda's default 1,000 regional concurrency only if deployment
preflight reserves the required concurrency and verifies remaining account
capacity.

### Azure Capacity

Event Hubs Standard supplies 1 MB/s ingress and 2 MB/s egress per throughput
unit, up to 40 TU and 32 partitions per Event Hub in one namespace. Since TU
capacity is namespace-scoped, Large must be explicitly sharded across
namespaces:

| Scenario | Namespaces | TU per namespace | Partitions per Event Hub | Aggregate ingress / egress capacity | Qualification |
|---|---:|---:|---:|---:|---|
| Small | 1 | 1 | 4 | 1 / 2 MB/s | Pass |
| Medium | 1 | 11 | 16 | 11 / 22 MB/s | Pass |
| Large | 15 | 40 | 32 | 600 / 1,200 MB/s | Pass |

The Large requirement including 20% headroom is 399.36 MB/s ingress and
1,198.08 MB/s egress. Fifteen namespaces at 40 TU therefore pass narrowly on
egress. Device ID is hashed first to a namespace and then used as the Event
Hubs partition key. Namespace and partition counts are immutable deployment
dimensions, not optimizer workload inputs.

The namespace count is below the documented 1,000 namespaces per subscription
per region. Each Event Hub needs only one processing consumer group or five
processed-telemetry consumer groups, below the Standard limit of 20.

IoT Hub sizing uses its own raw device traffic and 4-KiB metering:

| Scenario | IoT Hub tier/units | Reason |
|---|---|---|
| Small | S1 × 1 | 10 sends/s and about 3,334 4-KiB messages/day |
| Medium | S2 × 3 | 250 sends/s requires three 120-send/s units; daily 4-KiB chunks remain below allowance |
| Large | S3 × 1 | 2,500 sends/s is below 6,000/s; about 53.34 million 4-KiB chunks/day is below 300 million/day |

Large cloud-to-device demand is 6.25 commands/s, below the S3 limit of 83.33
sends/s/unit. C2D is selected instead of Direct Methods because C2D persists
messages in per-device queues and requires device acknowledgement.

Service Bus carries only the low-rate control channels. Standard tier is
sufficient: sessions provide per-device FIFO processing, peek-lock provides
at-least-once delivery, duplicate detection protects send retries, and each
queue/subscription owns a DLQ.

Azure Functions uses Flex Consumption with 2-GiB instances and target-based,
per-function scaling. Large exposes at most 480 partitions per telemetry event
type across the 15 namespaces, below the 1,000-instance plan limit. The
implementation uses one function app per namespace so no app accumulates the
entire sharded trigger set. Its configured maximum and the regional
subscription-memory quota are deployment preflight inputs, not assumed free
capacity. Logic Apps Consumption executes 7,500 actions per five minutes at
the Large peak, below the documented 100,000-action default.

### GCP Capacity

`europe-west1` is a Pub/Sub large region with 4 GB/s publisher, pull subscriber,
and StreamingPull subscriber quota. The default push-subscriber quota is only
440 MB/s.

| Scenario | Publish throughput | Delivery throughput | Consumer runtime | Qualification |
|---|---:|---:|---|---|
| Small | 0.1024 MB/s | 0.2048 MB/s | authenticated Pub/Sub push to Cloud Run | Pass |
| Medium | 8.704 MB/s | 17.408 MB/s | authenticated Pub/Sub push to Cloud Run | Pass |
| Large | 332.8 MB/s | 998.4 MB/s | StreamingPull on Cloud Run worker pools | Pass; push is rejected |

Large requires at least 100 open StreamingPull streams in aggregate at the
documented 10 MB/s per-stream limit. Capacity must also hold per subscription:
each of the one received-telemetry and five processed-telemetry subscriptions
needs 199.68 MB/s with headroom. The selected dimension is therefore 21 streams
per subscription, or 126 manually dimensioned Cloud Run worker-pool instances
with one stream, 1 vCPU, and 512 MiB each. Their aggregate 1,260 MB/s stream
capacity exceeds the 1,198.08-MB/s headroom target; one 80-Mbit/s stream stays
below Cloud Run's 600-Mbit/s per-instance non-VPC bandwidth limit. This is far
below the 72,000 open-stream regional quota, but project CPU and memory quota
remain deployment preflight checks.

The 100,000 device ordering keys are valid high-cardinality keys. Each key is
far below Pub/Sub's 1 MB/s per-ordering-key limit. Publishers use a regional
endpoint, and subscribers enable message ordering. Redelivery can replay later
messages for the same key, while forwarding to a dead-letter topic may break
order; both behaviors must be represented in outcome and degradation evidence.

Workflows permits 6,000 execution writes per minute. Large starts 375 workflows
per minute and is below that quota. The hosted MQTT command boundary is sized
separately as described above.

## Cross-Cloud Bridge Decision

### Selected Shape

The bridge is a typed source-owned forwarding component, not an Azure Function,
Lambda, or Cloud Run URL exposed as the architecture boundary:

```text
source producer
  -> source durable outbox/stream
  -> source-owned bridge-forwarder
       -> short-lived target-cloud credential
       -> destination broker data-plane API
  -> acknowledge source only after destination durable acceptance
```

The logical component is stable, but its runtime is source- and
scenario-specific:

| Source | Small/Medium | Large |
|---|---|---|
| AWS | Lambda event-source mapping | Shard-parallel Lambda/KCL consumer |
| Azure | Functions Event Hubs/Service Bus trigger | Partition-parallel Functions deployment across the selected namespaces |
| GCP | Cloud Run push or worker pool | Cloud Run worker pool with StreamingPull |

A bridge batch contains at most ten 65-KiB telemetry envelopes, keeping the
application payload below the 1-MB destination batch/publication boundary.
The adapter preserves event ID, correlation ID, trace context, replay marker,
and device partition key. It never logs credentials, payloads, provider
resource IDs, raw exceptions, or arbitrary headers.

The destination mapping is channel-specific:

| Channel class | AWS landing | Azure landing | GCP landing |
|---|---|---|---|
| Telemetry/log | Kinesis stream with device partition key | Event Hub with device partition key | Pub/Sub topic with ordering key |
| Control/action/command | SNS/SQS FIFO with device message group | Service Bus topic/queue with device session ID | Pub/Sub topic/subscription with ordering key |

For one key, the bridge does not advance to a later batch while an earlier
batch is retrying. A terminal failure moves the envelope to the source bridge
DLQ and emits an ordering-degraded outcome. Redrive republishes the same event
ID and key with a replay marker; consumers remain idempotent.

### Six Directed Trust Paths

| Direction | Short-lived trust exchange | Destination authorization | Result |
|---|---|---|---|
| AWS → Azure | AWS STS `GetWebIdentityToken` produces an AWS-signed OIDC JWT trusted by an Entra federated identity credential | Event Hubs Data Sender or Service Bus Data Sender | Capability-admissible; exact claims and live exchange pending |
| AWS → GCP | GCP Workload Identity Federation uses its AWS provider and exchanges the AWS workload identity | `roles/pubsub.publisher` on the landing topic | Capability-admissible; live exchange pending |
| Azure → AWS | A user-assigned managed identity requests an Entra JWT for a dedicated federation API audience; AWS trusts the tenant-specific Entra OIDC issuer and exchanges it with `AssumeRoleWithWebIdentity` | Narrow Kinesis put or SNS/SQS send role | Capability-admissible; exact claims and live exchange pending |
| Azure → GCP | Entra token is exchanged through a GCP OIDC workload identity provider | `roles/pubsub.publisher` on the landing topic | Capability-admissible; live exchange pending |
| GCP → AWS | Google workload OIDC token is exchanged with AWS `AssumeRoleWithWebIdentity`; Google is a supported public identity provider | Narrow Kinesis put or SNS/SQS send role | Capability-admissible; exact claims and live exchange pending |
| GCP → Azure | Google workload ID token is trusted by an Entra federated identity credential | Event Hubs Data Sender or Service Bus Data Sender | Capability-admissible; live exchange pending |

Every trust configuration restricts issuer, audience, workload identity or
subject, environment, and destination resource. Azure-to-AWS uses a dedicated
Entra resource application with assignment required, one bridge app role, and
an assignment only to the selected user-assigned managed identity. Its
tenant-specific `https://sts.windows.net/<tenant-id>/` issuer exposes OIDC
discovery, and the requested application ID URI becomes the JWT `aud` value
checked by AWS. This gates token issuance to the intended workload even before
the later live test records its pairwise `sub` claim. A generic bearer token,
shared secret, cloud access key, SAS connection string, or long-lived
service-account key is not an admissible bridge credential.

These rows establish supported identity primitives and exact construction
rules, not observed live-cloud success. Phase 8.9 must generate each trust
resource through the component catalog, and the later supervised E2E gate must
capture the real token claims and execute all six directions.

## Single-Cloud And Three-Provider Cases

### Single Cloud

- AWS uses IoT Core, the AWS embedded/Event-Layer bundle, Step Functions, and
  IoT Commands. No bridge or inter-cloud egress exists.
- Azure uses IoT Hub, the Azure embedded/Event-Layer bundle, Logic Apps, and
  IoT Hub C2D. No bridge or inter-cloud egress exists.
- GCP uses Pub/Sub and Cloud Run/Workflows plus the explicitly hosted BifroMQ/GKE
  command boundary. No bridge or inter-cloud egress exists, but GKE, load
  balancer, persistent disk, and broker operations still have cost owners.

Same-cloud does not mean one service. It means the complete local bundle
provides the required domain flow without a cross-cloud forwarder.

### Three Providers

`six-layer-eventing@1` remains hub-and-spoke around the resolved Eventing
provider:

- a remote producer publishes through its one source-owned outbox and bridge;
- a remote consumer provider receives one channel copy in its landing broker;
- consumers on the same remote provider fan out locally;
- two remote providers cause two directed bridge deliveries, not a hidden
  global mesh;
- same-provider edges remain local.

AWS, Azure, and GCP remain candidate Eventing providers because all six
directions have a documented federation primitive and construction rule.
Capacity is derived per resolved channel route. A single directed telemetry
bridge can carry up to one canonical channel copy at 166.4 MB/s in Large; five
consumers on one destination provider do not multiply cross-cloud bytes
because fan-out occurs after the landing broker.

## Deterministic Scenario Results

`scenario-cost-results.json` is generated offline by
`scripts/phase_08_eventing/calculate_scenarios.py`. Its normalized result digest
is
`sha256:4d0d28da4afef2ee35ab9022e6c8ab6e77b6824808bc3b39344f5007f61a9370`.
The generator emits per-channel publication, delivery, retry, DLQ, replay,
retention, compute, workflow, observability, outbox, landing, and transfer
traces. Reordering source-ledger or pricing-matrix rows does not change the
result; a referenced price mutation does.

These are separate event-scope estimates in USD/month, not complete Twin
profile totals and not a ranking:

| Scenario | AWS embedded | Azure embedded | GCP embedded | AWS Event Layer | Azure Event Layer | GCP Event Layer |
|---|---:|---:|---:|---:|---:|---:|
| Small | 0.572645 | 37.526536 | 708.274221 | 78.877579 | 50.156006 | 0.008512 |
| Medium | 97.504650 | 1,296.531230 | 735.226836 | 704.792321 | 2,391.968290 | 87.531402 |
| Large | 2,005.320312 | 7,949.465384 | 1,676.651157 | 28,947.778501 | 45,736.559730 | 6,678.069412 |

The GCP embedded fixed floor exposes the hosted three-node BifroMQ/GKE boundary.
The Azure adapter estimate exposes Flex Consumption's one-second minimum
billable execution. The Large GCP Event-Layer estimate includes 126 continuous
StreamingPull worker-pool instances plus request-based control adapters. These
differences are intentionally visible outcomes; none was used to select or
reject a functionally admissible PoC bundle.

Every single-cloud case has zero bridge invocations and zero cross-cloud
egress. All six directed pairs are calculated as one copy of every closed-world
domain-event channel, with destination fan-out excluded. Each of the six
three-provider permutations calculates the exact
ingress→Eventing→processing→Eventing hub-and-spoke routes and removes the local
delivery adapter when the bridge-forwarder replaces it.

## Rejected Or Restricted Alternatives

| Candidate | Decision | Reason |
|---|---|---|
| AWS EventBridge as the telemetry backbone | Rejected | It does not provide the required per-device ordering contract. |
| AWS SNS as the telemetry log | Rejected | It is suitable for low-rate FIFO control fan-out, not the selected replayable high-throughput telemetry log. |
| AWS Step Functions Express for notifications | Rejected | Standard provides durable, auditable, exactly-once workflow execution at the required low start rate. |
| Azure Event Grid Basic as the Large telemetry backbone | Rejected | Its documented throughput is far below the 332.8/998.4-MB/s Large requirement and its retention is not the selected log contract. |
| Azure Service Bus as the telemetry backbone | Rejected | Queue/session semantics are useful for control, while Event Hubs has the selected log, consumer-group, retention, and throughput model. |
| Azure IoT Hub Direct Methods for device feedback | Rejected | Direct Methods are synchronous and intended for immediately connected devices; C2D supplies a persistent per-device queue and acknowledgement. |
| GCP Eventarc as the telemetry backbone | Rejected | Eventarc is a delivery/trigger surface around events, not the selected retained fan-out log with Seek replay. |
| GCP Cloud Tasks as general fan-out | Rejected | A task targets controlled endpoint execution; it is not a multi-subscriber ordered event log. |
| GCP Pub/Sub push for Large | Rejected | 998.4 MB/s required delivery exceeds the 440-MB/s regional push quota. |
| Direct Pub/Sub credentials on every heterogeneous device | Rejected | Google's direct pattern is aimed at controlled aggregation devices/gateways and does not replace a bidirectional MQTT fleet boundary. |
| Retired GCP Cloud IoT Core command API | Rejected | It is not a current deployable service; the repository's inherited `iot_v1` command client is architecture debt. |
| Public function-to-function bridge | Rejected | It couples domain functions to remote endpoints and lacks the selected durable acknowledgement, backpressure, DLQ, replay, and trust boundary. |
| EMQX Open Source 5.8.8 | Rejected | The selected version reached end of life in February 2026 and no longer meets the security-maintenance gate. |
| EMQX 6 clustered Community license | Rejected | Current clustered deployment requires a commercial license with quote-based pricing; it cannot produce the required reproducible public cost evidence. |
| BifroMQ broker-session state as the end-to-end command owner | Rejected | Pub/Sub remains the durable owner until the correlated device outcome; broker state is a delivery optimization rather than the acknowledgement boundary. |
| Long-lived cross-cloud keys/secrets | Rejected | Every candidate direction has a short-lived federation primitive; exact claim mappings must still pass their explicit gates. |

## Remaining Approval Work

The provider bundles pass the current functional and theoretical-capacity
review with the explicit trust and hosted-broker conditions above. Source
captures and digests, the Apache license/incubation record, normalized pricing,
formula and unit rules, and schemas for the current artifacts now exist and
pass their current offline checks. Phase 8.8 is not yet `approved` because the
following evidence is still missing:

1. the canonical envelope and selected bridge decision;
2. the exact Terraform/provider/runtime/permission component manifest;
3. the complete-package validator; and
4. two zero-finding reviews of the complete package.

No selected bundle may enter optimizer ranking before those gates pass.

## Primary Sources

### AWS

- [AWS IoT Core quotas](https://docs.aws.amazon.com/general/latest/gr/iot-core.html)
- [Kinesis Data Streams quotas and limits](https://docs.aws.amazon.com/streams/latest/dev/service-sizes-and-limits.html)
- [Kinesis enhanced fan-out](https://docs.aws.amazon.com/streams/latest/dev/enhanced-consumers.html)
- [Kinesis concepts, retention, partition keys, and consumers](https://docs.aws.amazon.com/streams/latest/dev/key-concepts.html)
- [Lambda Kinesis failure destinations](https://docs.aws.amazon.com/lambda/latest/dg/kinesis-on-failure-destination.html)
- [Lambda quotas and regional concurrency](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
- [SNS FIFO features](https://docs.aws.amazon.com/sns/latest/dg/welcome-features.html)
- [SNS message archive and replay](https://docs.aws.amazon.com/sns/latest/dg/message-archiving-and-replay-subscriber.html)
- [SQS queue types](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-queue-types.html)
- [Step Functions workflow types](https://docs.aws.amazon.com/step-functions/latest/dg/choosing-workflow-type.html)
- [Step Functions quotas](https://docs.aws.amazon.com/step-functions/latest/dg/service-quotas.html)
- [AWS IoT Commands](https://docs.aws.amazon.com/iot/latest/developerguide/iot-remote-command.html)
- [AWS IoT Device Management endpoints and commands quotas](https://docs.aws.amazon.com/general/latest/gr/iot_device_management.html)
- [AWS IAM outbound identity federation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_outbound.html)
- [AWS IAM OIDC providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html)
- [AWS temporary credentials with web identity](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_request.html)

### Azure

- [Azure IoT Hub quotas and throttling](https://learn.microsoft.com/en-us/azure/iot-hub/iot-hub-devguide-quotas-throttling)
- [Azure IoT Hub cloud-to-device messaging](https://learn.microsoft.com/en-us/azure/iot-hub/how-to-cloud-to-device-messaging)
- [Azure Event Hubs quotas](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-quotas)
- [Azure Event Hubs scalability](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-scalability)
- [Azure Event Hubs features](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-features)
- [Resilient Event Hubs and Functions design](https://learn.microsoft.com/en-us/azure/architecture/serverless/event-hubs-functions/resilient-design)
- [Service Bus sessions and FIFO](https://learn.microsoft.com/en-us/azure/service-bus-messaging/message-sessions)
- [Service Bus delivery, duplicates, and DLQ behavior](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-message-loss-and-duplicates)
- [Logic Apps limits](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-limits-and-config)
- [Logic Apps hosting options](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview)
- [Azure Functions event-driven scaling](https://learn.microsoft.com/en-us/azure/azure-functions/event-driven-scaling)
- [Azure Functions hosting limits](https://learn.microsoft.com/en-us/azure/azure-functions/functions-scale)
- [Managed-identity token acquisition and audience](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/how-to-use-vm-token)
- [Microsoft identity-platform access-token claims](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference)
- [Grant API permissions to managed identities](https://learn.microsoft.com/en-us/powershell/entra-powershell/grant-api-permissions-managed-identity)
- [Microsoft Entra workload identity federation](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation)
- [Event Hubs Microsoft Entra authorization](https://learn.microsoft.com/en-us/azure/event-hubs/authenticate-application)

### GCP And Hosted MQTT Boundary

- [Pub/Sub quotas](https://docs.cloud.google.com/pubsub/quotas)
- [Pub/Sub ordered delivery](https://docs.cloud.google.com/pubsub/docs/ordering)
- [Pub/Sub replay with Seek](https://docs.cloud.google.com/pubsub/docs/replay-overview)
- [Pub/Sub dead-letter topics](https://docs.cloud.google.com/pubsub/docs/handling-failures)
- [Pub/Sub pull and StreamingPull](https://docs.cloud.google.com/pubsub/docs/pull)
- [Cloud Run worker pools for Pub/Sub](https://docs.cloud.google.com/run/docs/tutorials/autoscale-workerpools-pubsub)
- [Cloud Run worker-pool manual scaling](https://docs.cloud.google.com/run/docs/managing/workerpools)
- [Cloud Run resource types](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run)
- [Cloud Run quotas and networking limits](https://docs.cloud.google.com/run/quotas)
- [Workflows quotas](https://docs.cloud.google.com/workflows/quotas)
- [Google standalone MQTT broker architecture](https://docs.cloud.google.com/architecture/connected-devices/mqtt-broker-architecture)
- [Google device-on-Pub/Sub architecture](https://docs.cloud.google.com/architecture/connected-devices/device-pubsub-architecture)
- [GKE modes](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/choose-cluster-mode)
- [Apache BifroMQ repository, release, and license](https://github.com/apache/bifromq)
- [BifroMQ cluster architecture](https://bifromq.apache.org/docs/cluster/intro/)
- [BifroMQ security and mutual TLS](https://bifromq.apache.org/docs/3.0.x/admin_guide/security/intro/)
- [BifroMQ connection benchmark](https://bifromq.apache.org/docs/3.0.x/test_report/report/)
- [EMQX 5.8 Open Source end-of-life notice](https://www.emqx.com/en/news/a-notice-on-the-emqx-5-8-open-source-version)
- [Current EMQX clustered license boundary](https://docs.emqx.com/en/emqx/latest/deploy/license.html)
- [GCP Workload Identity Federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation)
- [GCP federation with AWS and Azure](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds)
