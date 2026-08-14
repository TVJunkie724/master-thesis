---
title: "Phase 8.9B: Six-Layer Eventing Implementation"
description: "Executable delta plan that adds one independent Eventing responsibility to the reviewed Five-layer v2 PoC."
tags: [architecture, eventing, optimizer, management-api, deployer, flutter, issue-140]
lastUpdated: "2026-08-14"
version: "2.10"
---

<!-- SOURCES:
- GitHub issue #140
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_8_eventing_decision_gate.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_service_bundle_closure.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md
- contracts/phase-08-eventing-decision/v1/decision.json
- contracts/phase-08-eventing-decision/v1/implementation-component-manifest.json
- User-approved Five-layer v2 and Six-layer v1 PoC boundaries from the 2026-08-03 planning conversation
EXTRACTED: 2026-08-14 | VERSION: 2.10
-->

# Phase 8.9B: Six-Layer Eventing Implementation

## 0. Authority And Branch Gate

| Field | Value |
|---|---|
| Issue | [#140 Implement six-layer-eventing@1 across the platform](https://github.com/TVJunkie724/master-thesis/issues/140) |
| Branch | `codex/phase-8-six-layer-eventing-v1` |
| Required base | Reviewed and committed `five-layer-baseline@2` implementation, including workload v2, bootstrap, L4/L5 access, RDS v2, and Deployment Manifest v4 |
| Inherited implementation commit | `c5c6232478d29a9cc3c7d280bdc9ca0e79c47226` |
| Five-layer audit-freeze commit | `d4c080f6` |
| Five-layer profile digest | `sha256:d8a57a1f9ff1c530282dd42dcf595f1a9ec8051f8cd8574acfb0a81e655d9386` |
| Complete-service catalog digest | `sha256:3396848028a5b8862e1c948a8017cd8e7bb7d118a0ee5edc120cd3d7a3956c1d` |
| Five-layer activation manifest digest | `sha256:319433834c75147d6d18665840a17626dd67dcd182a449fa574e7ab9860aef6f` |
| Eventing decision file digest | `sha256:b2afdaff2793391f0bab0127c93e13b0ff281964d1184818090781234444be35` |
| Eventing implementation-manifest file digest | `sha256:bcc8fd9465243bd92028cf7c6cb970973096227048aeac98294f429b1f24252f` |
| Profile | `six-layer-eventing@1` |
| Decision authority | Approved `phase-08-eventing-decision@1` plus the committed Five-layer v2 digest |
| Verification | Offline/no-apply by default; no live cloud resource creation |

**Implementation checkpoint:** The scoped contract, Optimizer, Management,
Deployer, AWS, Azure, GCP, bridge, and Flutter commits are present on the
required branch. Component gates pass locally without credentials or apply.
Documentation reconciliation and the repeated final audit are in progress;
this document therefore does not yet claim the final zero-finding freeze.
The current audit also binds every inherited Terraform resource and every
profile-local AWS, Azure, and GCP runtime to the resolved profile identifier
and version. Runtime health/read cursors, Twin Explorer text, provider Grafana
dashboards, and build metadata may not misidentify a Six-layer deployment as
Five-layer. The inherited finite tiering artifact format deliberately retains
its `five-layer-v2-storage-*.v1` schema identifier because it is part of the
unchanged L1-L5 baseline contract, not a deployment-profile label.
The inherited Layer Access contract now accepts both active profile/version
pairs. Six-layer deployments therefore project, persist, and expose the same
typed L4/L5 surfaces as Five-layer v2, including the owner-scoped GCP Grafana
Viewer rotation operation; historical Five-layer v1 remains unsupported.
The same inheritance now covers SDK-owned post-deployment work: AWS TwinMaker
and Azure Digital Twins receive the deterministic visible seed, AWS/Azure
Grafana receive the typed dashboard configuration, and Azure publishes the
finite storage-mover image for either active profile.
The provider-combination audit additionally proved the L1-to-Event and
L2-to-Event source paths independently of L2 placement. AWS already resolves
the local Event log or remote source outbox in Terraform. Azure now makes the
same selection explicitly in both Function apps and supplies the L2 runtime
with its local Event-layer and remote outbox destinations. GCP ingress now
selects its local Event topic or remote source outbox from
`event_layer_provider`, rather than incorrectly treating a local L2 as a reason
to bypass a remote Event Layer. Focused no-network runtime and static Terraform
tests cover both local and remote branches; no cloud resource was created.
The following GCP identity trace closes the matching return paths as well: the
L2 Cloud Run service receives the selected local Event-control or remote
control-outbox topic, and the GCP L1 ingress identity receives publisher access
to the remote control outbox when the Event Layer is not GCP. Consequently,
rule matches and device-command outcomes return to the independent Event Layer
under the same resolved placement instead of relying on embedded-topic rights.

The branch gate above now proves the exact reviewed Five-layer v2 commits and
decision digests, so this document is executable planning authority. It replaces
the suspended pre-2026-07-29 draft in full. No BigQuery, ADX, scene/3D,
L3/L4/L5 co-location, dual visualization path, or L4-to-L5 edge survives from
that historical draft.

## 1. Outcome

`six-layer-eventing@1` inherits the complete Five-layer v2 L1-L5 profile and
adds one nonlinear Eventing and Messaging responsibility. The domain behavior
is identical in both comparison profiles: rule evaluation, event actions,
notification workflow, and device feedback are mandatory. The difference is
where routing, durable buffering, fan-out, retry/DLQ, replay, observability,
and cross-cloud transport are owned and costed.

```text
five-layer-baseline@2 L1-L5 digest
              |
              v
same domain events + independent Eventing responsibility
              |
              +--> provider-local Event Layer bundle
              +--> source-owned bridge only for a remote destination
              +--> Event Layer cost/evidence dimensions
              |
              v
six-layer-eventing@1 resolved architecture and deployment manifest
```

## 2. Scope Boundary

| Included | Excluded |
|---|---|
| One curated Event Layer bundle for AWS, Azure, and GCP | Every provider event service or user-selectable broker |
| Three single-cloud cases, all six directed two-provider pairs, and valid three-provider hub/spoke paths | A premise that a provider is permanently sender-only or receiver-only |
| Source-owned cross-cloud bridge with short-lived destination identity | Public destination Function endpoint, shared static token, or permanent cross-cloud key |
| Exact Eventing workload, capacity, price, transfer, observability, and failure ownership | Cost-minimizing service substitution or a generic topology optimizer |
| Static Terraform resources and registered provider packages | Runtime-generated Terraform |
| Profile-local Optimizer results and the existing compact Flutter workflow | A second Eventing wizard or inline event flags |
| Offline contract/package/Terraform tests and credential-free Management integration | Automatic live-cloud E2E, paid load tests, or production SLO claims |

## 3. Inherited Five-Layer Contract

The following are inherited byte-for-byte from the reviewed 8.9A boundary and
must not be reimplemented or reinterpreted:

- L1-L5 logical components and services;
- L3 hot/cool/archive and hourly-rollup semantics;
- `provider(L3_hot) == provider(L5)` with independently placed L4;
- `raw_history_query.v1` from L3 hot to L5;
- `twin_projection.v1` from L3 hot to L4;
- no L4-to-L5 edge and no scene/3D requirement;
- nine L3/L5-to-L4 placements;
- one GCP Firestore database per deployment with separate L3/L4 ownership;
- guided bootstrap, bounded CloudConnections, provider prerequisites, and
  deployment preflight;
- exactly one L4 and one L5 post-deployment access card;
- workload v2 core fields, immutable event scenarios, fixed regions, and
  historical `five-layer-baseline@1` read/destroy compatibility.

Any required change to this list blocks 8.9B and reopens 8.9A review.

## 4. Selected Event Layer Bundles

Every listed row is a bundle. The services are complementary responsibilities,
not alternatives presented to the runtime user.

| Provider | Telemetry transport | Ordered control/fan-out | Runtime | Failure/observability | Scenario rule |
|---|---|---|---|---|---|
| AWS | Kinesis Data Streams | SNS FIFO plus SQS FIFO subscriptions | Lambda | S3 failure destination plus CloudWatch metrics/logs | Stream/shard count is derived from the frozen scenario; Large retains the reviewed two-channel capacity and headroom calculation |
| Azure | Event Hubs Standard for Small/Medium, Dedicated for Large | Service Bus Standard | Functions Flex Consumption | Azure Monitor system metrics plus explicit diagnostic settings to one shared Log Analytics workspace | Event Hubs owns high-rate telemetry; Service Bus owns ordered low-rate control and bridge work |
| GCP | Pub/Sub | Separate Pub/Sub topics/subscriptions for control | Cloud Run services; a fixed-size Cloud Run worker pool only for the Large telemetry adapter selected by the decision package | Cloud Logging and platform Cloud Monitoring metrics | L1 and L6 may use the same service family but remain different resources, identities, topics, costs, and logical ownership |

Azure Monitor and Google Cloud Monitoring are provider-platform monitoring
capabilities, not additional custom brokers. No alerting estate, dashboard
fleet, tracing platform, or permanent worker is added without an exact
decision-package entry.

Cloud Run worker pools remain a Pre-GA/Preview resource and do not autoscale.
The Large bundle must freeze the manual instance count, Preview terms/source
metadata, Terraform/provider support, region availability, and cost/capacity
assumptions. Deployment preflight fails closed if that exact resource is no
longer available. This is a visible PoC limitation and no production
availability or autoscaling claim is made.

For the resolved Large topology, GCP allocates 21 instances per local
telemetry consumer subscription and per distinct source-owned bridge
telemetry channel. A physical received/processed source subscription may fan
out to several destination routes, so target count does not duplicate the
worker pool. Control subscriptions remain authenticated Pub/Sub push. The RDS
exports one exact aggregate dimension, and Terraform must reconcile that
dimension to the sum of local and bridge worker allocations before planning.

## 5. Event Contracts And Delivery

All providers implement the approved canonical event envelope and strict
schema version. The registered edges declare:

- source/destination logical component;
- channel (`telemetry`, `control`, `notification`, `feedback`, or `failure`);
- ordering key and scope;
- at-least-once delivery and idempotency key;
- retry budget and terminal failure destination;
- replay/redrive owner and retention;
- safe correlation and observability fields;
- transfer direction and cost owner;
- same-provider or cross-cloud transport binding.

An upstream domain function publishes to a registered local endpoint. It never
constructs a downstream function name, ARN, URL, topic, namespace, or physical
resource identifier.

## 6. Cross-Cloud Bridge

The only v1 bridge is source-owned:

```text
source durable broker/subscription
          |
          v
source-provider bridge runtime
          |
          v
short-lived destination workload identity
          |
          v
destination broker data-plane API
          |
          v
durable destination acceptance
          |
          `--> acknowledge source message
```

The bridge runs in the source cloud and consumes the source broker or queue.
It publishes directly to the target broker's supported data API. The target
domain consumer attaches to its local target broker; no public target Function
is used as a bridge endpoint. A same-provider edge resolves to a local binding
with no bridge component, no inter-cloud transfer, and no bridge cost.

All six directed pairs are mandatory:

| Source | AWS target | Azure target | GCP target |
|---|---|---|---|
| AWS | Local binding | AWS runtime -> Azure broker API | AWS runtime -> GCP broker API |
| Azure | Azure runtime -> AWS broker API | Local binding | Azure runtime -> GCP broker API |
| GCP | GCP runtime -> AWS broker API | GCP runtime -> Azure broker API | Local binding |

Three-provider paths compose only registered directed edges. They do not turn a
provider into a permanent hub by assumption.

## 7. Shared Contracts And Compatibility

Implementation must add or activate the exact approved artifacts for:

- `six-layer-eventing@1` architecture profile;
- provider implementation profiles and Event Layer component catalog;
- Eventing workload/scenario, capability, pricing/unit, formula, envelope,
  edge, permission, and bridge registries;
- `ResolvedTwinArchitecture v2`, `ResolvedDeploymentSpecification v2`, and
  `DeploymentManifest v4` Event Layer assignments, bindings, dimensions, and
  digests;
- valid/invalid fixtures for local, every directed pair, three-provider,
  capacity, missing evidence, and incompatible versions.

New operations use only RTA v2 with RDS v2 and Manifest v4. Historical RTA/RDS
v1 with their supported v2/v3 manifests remain readable, verifiable, and
destroyable but cannot be upgraded in place or selected for a new deployment.
Cross-version combinations fail closed.

## 8. Optimizer

The Optimizer must:

1. validate the selected profile, workload v2, immutable event scenario, fixed
   region, evidence freshness, and decision digests;
2. enumerate only provider assignments allowed by the profile;
3. bind one complete Event Layer bundle per Eventing placement;
4. add a source-owned bridge for each unequal event edge and no bridge for a
   local edge;
5. apply functional and theoretical Small/Medium/Large capacity gates before
   publishing cost;
6. own each fixed, usage, tier, request, transfer, retry, DLQ, replay,
   observability, adapter, and bridge cost exactly once;
7. rank complete candidates only within `six-layer-eventing@1`;
8. keep Five-layer v2 runs and evidence separate.

Cost is measured for the thesis comparison. It is not the criterion used to
select or replace the provider services in Section 4.

## 9. Management API And Persistence

Management persists normalized generic component assignments and immutable
resolution/run identities. It exposes the existing profile catalog, selection
preview/confirmation, run resolution, readiness, bootstrap, and deployment
access surfaces without an Eventing-specific side API.

Strict response DTOs must replace raw nested component/edge dictionaries at
the Flutter boundary. API errors expose safe profile/component/edge codes and
correlation IDs, never payloads, credentials, target endpoints, tfvars, or raw
provider responses.

## 10. Deployer And Terraform

The Deployer graph resolver validates every Event Layer node and edge before
Terraform. It emits deterministic stages, registered static module bindings,
typed tfvars, package digests, and redacted graph evidence. Required work:

- provider package/adapters for the three bundles;
- bridge adapters for every directed pair using one canonical interface;
- least-privilege producer, consumer, bridge, failure-store, replay, logging,
  and diagnostic permissions from `thesis-demo-v2`;
- static Terraform resources and exact output/input bindings;
- local-edge elimination of bridge resources;
- retry-safe package/build behavior and teardown ownership;
- no apply in default verification.

## 11. Flutter Delta

Flutter extends the same Phase 8.1 profile workflow:

- the Six-layer row becomes selectable only when Management reports it active;
- the logical flow includes the independent Eventing responsibility;
- the resolved review shows Event Layer services, support components, local or
  bridge edges, capacity/evidence status, and incremental cost dimensions;
- workload input still requires the same immutable event scenario and exposes
  no feature flag or broker settings;
- guided bootstrap derives provider access from the resolved architecture;
- Twin Overview retains exactly one L4 and one L5 card and adds no Event Layer
  administration console.

## 12. Implementation And Commit Sequence

Each boundary must be clean, reviewed, and committed before the next begins:

1. `[AI-0803-EVCT] feat(contracts): activate six-layer eventing contracts`
   (`40f47548`, with follow-up contract freezes `8f784906` and `2e9375f9`)
2. `[AI-0803-EVOP] feat(optimizer): price complete eventing candidates`
   (`13afbf0f`)
3. `[AI-0803-EVMA] feat(management): persist six-layer resolutions`
   (`b1ab9ac8`, with catalog binding `e8634e41`)
4. `[AI-0803-EVDP] feat(deployer): build eventing graph packages`
   (`97e30488`)
5. `[AI-0803-EVAW] feat(aws): implement reviewed event layer bundle`
   (`7cb846fa`)
6. `[AI-0803-EVAZ] feat(azure): implement reviewed event layer bundle`
   (`024c8baa`)
7. `[AI-0803-EVGC] feat(gcp): implement reviewed event layer bundle`
   (`6b04a6cc`)
8. `[AI-0803-EVBR] feat(eventing): implement directed bridge adapters`
   (`83f8c9bc`)
9. `[AI-0803-EVUI] feat(flutter): expose six-layer profile delta`
   (`e977982b`, with Demo catalog activation `a661d789`)
10. `[AI-0803-EVDOC] docs(phase-8): document six-layer implementation`
11. `[AI-0803-EVRV] fix(phase-8): close six-layer audit findings`

Generated contract copies may be included with their owning contract commit;
unrelated changes must not be swept into these commits.

## 13. Verification

Offline gates must cover:

- schema, semantic registry, reference, digest, and generated-copy drift;
- all three local bundles, all six directed bridges, and representative
  three-provider graphs;
- missing/duplicate/incompatible/unauthorized/cyclic binding failures;
- canonical envelope, ordering, duplicate, retry exhaustion, DLQ,
  replay/redrive, destination outage, and acknowledge-after-acceptance;
- exact Small/Medium/Large capacity math including Kinesis shard headroom,
  Azure tier selection, and GCP Large fixed worker-pool selection plus Preview
  availability rejection;
- fixed/usage/transfer/observability/bridge cost ownership exactly once;
- same-provider absence of bridge, egress, and bridge cost;
- package hashes, permission manifests, Terraform format/validate, and no-apply
  mock plans for every selected bundle/pair;
- Management ownership, revision, persistence, safe error, export, and
  historical compatibility;
- Flutter model/BLoC/widget/demo and real Management API integration on Web,
  macOS, Windows, and Linux;
- secret, endpoint, provider-identifier, tfvars, and log redaction scans.

No default gate deploys a provider resource or claims measured throughput.

## 14. Definition Of Done

- [x] The exact reviewed Event Layer bundles are implemented; no service was
      added, removed, or substituted locally.
- [x] `six-layer-eventing@1` inherits the committed Five-layer v2 digest and
      changes only the approved Eventing delta.
- [x] All single-cloud, six directed pair, and representative three-provider
      candidates pass functional/capacity gates or fail with a typed reason.
- [x] Source acknowledgement occurs only after durable destination acceptance.
- [x] Same-provider paths deploy no bridge and own no cross-cloud cost.
- [x] RTA v2/RDS v2/Manifest v4, persistence, graph, packages, Terraform, permissions,
      pricing, and UI agree on one immutable resolution digest.
- [x] Historical contracts remain read/verify/destroy-only and byte-stable.
- [ ] Safe full repository verification passes with real cloud E2E excluded.
- [ ] Two independent implementation reviews reach zero unresolved findings.
- [ ] A final clean commit records only reviewed 8.9B work.
- [ ] Phase 8.10 receives frozen separate Five-layer and Six-layer evidence.
