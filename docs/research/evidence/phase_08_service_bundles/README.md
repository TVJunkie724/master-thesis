# Phase 8 Complete-Service Bundle Decision

## Status

This directory is the immutable offline decision package
`phase-08-complete-service-bundles@1` for the complete Twin PoC service
boundary reviewed on 2026-08-03.

The package approves implementation authority for `five-layer-baseline@2` and
the later `six-layer-eventing@1` delta. It does **not** activate either profile,
prove live cloud readiness, or modify the historical
`five-layer-baseline@1`/Phase 8.8 evidence. Live deployment, paid capacity,
identity exchange, browser sign-in, and cleanup remain separately approved
supervised gates.

The service-family choice is functionality-first. Cost is not used to replace
a required service with an incomplete one. Once the closed bundle is admitted,
the Optimizer still compares complete placement candidates by a current,
versioned price catalog within the selected profile.

## Frozen Boundary

- Five-layer v2 and Six-layer v1 expose the same mandatory domain behavior;
  Six-layer moves canonical domain-event transport into an independently owned
  Eventing responsibility.
- L3 hot and L5 are provider-local; L4 remains independently placeable. The
  package contains all three single-cloud and six `L3 hot/L5 != L4` cases.
- `L3 hot -> L5` uses `raw_history_query.v1`.
- `L3 hot -> L4` uses `twin_projection.v1` locally or through the source-owned
  Phase 8.8 bridge. No public destination Function is introduced.
- Hot/cool/archive movement uses finite scheduled jobs and native lifecycle,
  not CDC, a permanent worker, an outbox, or a new broker.
- All six directed event/projection and storage identity pairs are explicit.
  Same-provider paths have no bridge and no cross-cloud egress charge.
- New requests use the three immutable Core v2 scenarios paired by size with
  the Phase 8.8 Eventing v1 scenarios. Event feature flags and historical
  scene/dashboard surrogates are forbidden.

## Selected PoC Services

| Layer/scope | AWS | Azure | GCP |
|---|---|---|---|
| L1 | IoT Core, IoT Commands | IoT Hub | Apache BifroMQ 4.0.0-incubating on GKE, load balancer, ordered Pub/Sub adapter |
| L2 | Lambda, Step Functions Standard | Functions Flex Consumption, Logic Apps Consumption | Cloud Run services, Workflows |
| L3 hot | DynamoDB on-demand raw and rollup tables | Cosmos DB NoSQL raw/rollup; serverless S/M, calculated autoscale Large | Firestore Native Standard raw/rollup collections with 1/1/16 timestamp shards |
| L3 cool/archive | S3 Standard-IA / Glacier Deep Archive | Blob Cool / Archive | Cloud Storage Nearline / Archive |
| L4 | IoT TwinMaker Standard | Azure Digital Twins | Cloud Run bounded Twin API/materializer and IAP Explorer on the deployment Firestore database |
| L5 | Managed Grafana 12, typed Lambda reader, JSON API 1.4.0 | Managed Grafana 12, typed Flex reader, JSON API 1.4.0 | Grafana OSS 12.4.2 on GKE, Infinity 3.10.1, typed Cloud Run reader |
| Six-layer Eventing | Kinesis, SNS FIFO, SQS FIFO, Lambda, S3 failure store, CloudWatch | Event Hubs Standard S/M and Dedicated Large, Service Bus Standard, Functions Flex, Monitor/Log Analytics | Pub/Sub, Cloud Run service S/M, fixed Cloud Run worker pool Large, Logging/Monitoring |

The JSON API plugin is an explicit maintenance-mode dependency for the two
managed Grafana paths. No unsupported end date is invented; exact managed
catalog availability is checked before mutation. The self-hosted GCP image,
BifroMQ image, and Infinity Linux/amd64 artifact are version/digest pinned.
Cloud Run worker pools remain Preview and non-autoscaling; the Large
Six-layer path uses the fixed reviewed size or fails preflight.

The implementation bindings are also closed. AWS IoT Commands uses
`awscc_iot_command`; TwinMaker uses `awscc_iottwinmaker_workspace`, followed by
the existing bounded SDK lifecycle for component types, entities, and
relationships. GCP logging and monitoring are provider-platform capabilities,
not invented sink/dashboard resources. The manifest requires Google provider
`>= 7.22.0, < 8.0.0` for Worker Pools plus direct Cloud Run IAP and Kubernetes
provider `>= 2.38.0, < 3.0.0` for GKE workloads. Because a Kubernetes provider
must not be initialized from a cluster created in the same apply, deployment
is one automated lifecycle with three explicit stages: cloud resources, GKE
workloads, then bounded SDK/plugin provisioning. This adds no manual cloud
step after validated bootstrap.

## Deterministic Capacity Results

| Size | Firestore shards | Reader max concurrency | AWS/GCP mover tasks | Azure mover tasks | Objects/batch lower bound |
|---|---:|---:|---:|---:|---:|
| Small | 1 | 2 | 1 | 1 | 1 |
| Medium | 1 | 3 | 1 | 4 | 1 |
| Large | 16 | 42 | 3 | 30 | 19 |

The calculator derives these values from device count, telemetry interval, and
payload size instead of rounded display rates. Cosmos per-device hot payload
remains below the published 20-GB logical-partition limit. Provider-specific
request-charge, contention, latency, quota, plugin, Preview-resource, and
failure behavior remain fail-closed activation/live gates; the package does
not fabricate measurements.

## Artifacts

| Artifact | Purpose |
|---|---|
| `decision.json` | Approval scope, immutable input/artifact digests, reviews, and activation gates |
| `common-functional-contract.json` | Closed raw-history, Twin-projection, storage-transition and domain-event boundaries plus shared invariants and non-goals |
| `complete-provider-bundles.json` | Exact provider/layer/support/Eventing selections and pinned self-hosted artifacts |
| `boundary-route-matrix.json` | Nine online placements, all local/cross-cloud route classes, identities, and rejections |
| `workload-scenarios.json` | Core v2 inputs, fixed dimensions, and immutable Eventing scenario references |
| `capacity-matrix.json` | Deterministic capacity derivations and honest live gates |
| `pricing-ownership-matrix.json` | Exactly-once component/route cost ownership without stale price fallback |
| `source-ledger.json` | Primary-source facts checked at the research cutoff |
| `implementation-component-manifest.json` | 72 selected components, exact Terraform/SDK/platform bindings, provider requirements, apply stages, profiles, permissions, and test ownership |

The matching `thesis-demo-v2` permission manifests and scope reviews live in
`3-cloud-deployer/docs/references/permission_sets/`. They deliberately expose
known scoping gaps and are not labelled least privilege. All v1 permission
artifacts remain byte-stable.

## Reproducibility

Run from the repository root:

```bash
python3 scripts/phase_08_service_bundles/calculate_capacity.py
python3 scripts/phase_08_service_bundles/generate_manifests.py
python3 scripts/phase_08_service_bundles/freeze_decision.py
python3 scripts/phase_08_service_bundles/validate_decision_package.py
python3 -m unittest discover -s scripts/phase_08_service_bundles/tests -p 'test_*.py'
```

`verify_sources.py` checks source shape and local digests offline. Its optional
network mode only sends read-only HEAD/GET requests and is not part of the
deterministic default gate.

## Review Record

1. Architecture/service review: zero unresolved findings after covering both
   profiles, all single-/multicloud placements and routes, service reuse,
   tiering, access, current plugin facts, and PoC non-goals.
2. Builder/evidence review: zero unresolved findings after pinning formulas,
   artifacts, byte digests, permission inventories, source references,
   activation failures, and the offline-versus-live claim boundary.
3. IaC feasibility review: zero unresolved findings after replacing fictitious
   bindings, freezing the required provider upgrade, and separating managed
   cluster creation from Kubernetes-resource application.
