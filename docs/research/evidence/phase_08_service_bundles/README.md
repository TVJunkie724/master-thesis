# Phase 8 Complete-Service Bundle Decision

## Status

This directory is the immutable offline decision package
`phase-08-complete-service-bundles@1` for the complete Twin PoC service
boundary reviewed on 2026-08-03.

During contract integration on 2026-08-04, before either profile was activated
or deployed, the package was re-frozen once: the shared managed-Grafana plugin
alias was split into AWS- and Azure-owned component IDs, and composite capacity
labels were replaced by atomic priced dimensions. The service scope did not
change. `decision.json` records the superseded planning digest so this
pre-activation correction remains explicit rather than silently rewriting the
evidence history.

The pre-activation implementation reviews on 2026-08-07 also made the already
required container-delivery mechanism explicit for all three providers:
Terraform creates each selected deployment registry and its bounded build
foundation; regional CodeBuild, ACR Tasks, or Cloud Build then publish
content-addressed images; provider resources and Kubernetes workloads follow
in separate stages. Finite build support is owned by the existing conditional
registry component, not a new Twin responsibility. Build invocations are
deployment evidence rather than steady-state monthly architecture load. ACR
Task availability for Azure free-credit subscriptions remains a fail-closed
preflight because the provider currently documents a temporary pause.

The package approves the standalone `six-layer-eventing@1` service boundary.
It does **not** prove live cloud readiness. Live deployment, paid capacity,
identity exchange, browser sign-in, and cleanup remain separately supervised
gates.

The service-family choice is functionality-first. Cost is not used to replace
a required service with an incomplete one. Once the closed bundle is admitted,
the Optimizer still compares complete placement candidates by a current,
versioned price catalog within the selected profile.

## Frozen Boundary

- Six-layer v1 includes mandatory domain behavior and owns canonical
  domain-event transport in an independent Eventing responsibility.
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
provider `>= 2.38.0, < 3.0.0` for GKE workloads. Because neither container
images nor a Kubernetes provider can be resolved from resources that do not
yet exist, deployment is one automated lifecycle with five explicit stages:
image foundation, content-addressed image publication, cloud resources, GKE
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
| `implementation-component-manifest.json` | 73 provider-owned selected components, exact Terraform/SDK/platform bindings, provider requirements, apply stages, atomic capacity dimensions, and test ownership |

Deployment-authority provisioning and permission-pack evidence are outside
this package. The PoC uses preconfigured provider credentials.

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
4. Contract-integration review: zero unresolved findings after splitting the
   managed-Grafana plugin ownership, making capacity dimensions atomic,
   omitting remote-only Eventing services in single-cloud resolutions, and
   validating all 729 admissible Five-layer layer assignments.
5. Provider image/tiering implementation-support review: zero unresolved
   contract findings after binding CodeBuild, ACR Tasks, and Cloud Build
   publication, digest-only runtime images, five-minute storage batches, and
   the exact reviewed AWS 1/1/3, Azure 1/4/30, and GCP 1/1/3 mover task counts.
   Azure free-credit ACR Task availability and GKE project-network permission
   completeness remain explicit supervised activation gates.
