---
title: "Phase 8.9 Execution Plan: Five-Layer v2 Then Six-Layer v1"
description: "Cross-stack implementation sequence for the complete bounded Phase 8 thesis PoC."
tags: [phase-8, architecture-profiles, optimizer, deployer, management-api, flutter, thesis]
lastUpdated: "2026-08-04"
version: "1.1"
---

<!-- SOURCES:
- docs/plans/phase_08_architecture_profiles_eventing/HANDOFF.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_6_deployer_graph_resolver.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_7_flutter_profile_workflow.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_8_eventing_decision_gate.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_service_bundle_closure.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_9_six_layer_eventing_implementation.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_ARCHITECTURE_PROFILE_EXPERIMENT.md
- User implementation authorization on 2026-08-03
EXTRACTED: 2026-08-04 | VERSION: 1.1
-->

# Phase 8.9 Execution Plan: Five-Layer v2 Then Six-Layer v1

## 1. Objective

Complete Phase 8 as a bounded thesis PoC through independently reviewable
steps. The result supports planning, calculation, deployment packaging, cloud
access preparation, and UI review for `five-layer-baseline@2`, then adds
`six-layer-eventing@1` as a strict delta. It does not attempt to become a
general multi-cloud architecture product.

## 2. Binding PoC Boundaries

- Closed-world profiles and service catalogs only.
- Functionality and theoretical scenario capacity decide admissibility;
  estimated cost ranks complete candidates but does not redesign bundles.
- Small, Medium, and Large are frozen reproducible scenarios, not autoscaling
  promises or measured production limits.
- GCP Large Eventing may use the reviewed fixed-size Cloud Run worker pool,
  which remains Preview and non-autoscaling; that limitation and availability
  check are evidence, not a production-readiness claim.
- Events are mandatory in both new profiles; legacy feature flags disappear
  from new-profile input.
- Storage tiering is the finite scheduled mechanism in the reviewed service
  plan; CDC, outbox platforms, permanent workers, and checkpoint databases are
  excluded.
- Single-cloud, all six directed provider pairs, valid three-provider
  compositions, and all nine Five-layer L3/L5-to-L4 placements are covered.
- No live cloud deployment, paid load test, or LaTeX change is authorized.
- UI is a typed Management API client; it never calls Optimizer, Deployer, or
  cloud APIs directly.

## 3. Required Architecture

### Five-layer v2

| Responsibility | AWS | Azure | GCP |
|---|---|---|---|
| L1 Acquisition | IoT Core and IoT Commands | IoT Hub | BifroMQ 4.0.0-incubating on GKE, Load Balancer, ordered MQTT-to-Pub/Sub adapter |
| L2 Processing | Lambda and Step Functions Standard | Functions Flex Consumption and Logic Apps Consumption | Cloud Run and Workflows |
| L3 Hot | DynamoDB on-demand, time-window shard GSI, hourly rollup table | Cosmos DB for NoSQL, `/device_id`, Serverless S/M and Autoscale Large, hourly rollup items | Firestore Native Standard, time shards, hourly rollup collection |
| L3 Cool | S3 Standard-IA | Blob Cool | Cloud Storage Nearline |
| L3 Archive | Glacier Deep Archive | Blob Archive | Cloud Storage Archive |
| L4 Twin | IoT TwinMaker Standard | Azure Digital Twins | Cloud Run Twin API/materializer and IAP Twin Explorer backed by the deployment Firestore database |
| L5 Visualization | Amazon Managed Grafana 12 and typed Lambda reader | Azure Managed Grafana 12 and typed Functions reader | Grafana OSS 12 on GKE, Persistent Disk, signed Infinity, typed Cloud Run reader |

L3 hot and L5 always share a provider. L4 is independently selectable. L5
queries only the typed L3 hot reader; L3 hot projects state/relationships to
L4. L4 does not feed L5.

### Six-layer v1

Six-layer inherits the table above and adds only the Event Layer table in
[`phase_08_9_six_layer_eventing_implementation.md`](phase_08_9_six_layer_eventing_implementation.md).

## 4. Contract Freeze Before Runtime Work

The first implementation commit must build the immutable
`phase-08-complete-service-bundles@1` package and validate it against the
already approved Eventing package. It must pin:

- service/capability/capacity decisions and rejected alternatives;
- workload v2 core presets and immutable event scenarios;
- provider/component/package/Terraform/permission/formula/pricing IDs;
- raw-history, Twin projection, tiering, layer-access, and bootstrap contracts;
- all supported and rejected topology fixtures;
- current source metadata and digests;
- `thesis-demo-v2` deployment/bootstrap permission packs;
- exact plugin versions/catalog evidence without an invented support-end date.

The contract freeze is data and tests only. It creates no cloud resources.

## 5. Implementation Order And Clean Commits

| Step | Branch/commit boundary | Required outcome |
|---|---|---|
| A | planning branch `[AI-0803-P8PL]` | Concept, cross-stack plans, Flutter plans, issue map, and zero-finding plan review |
| B | `codex/phase-8-complete-service-decision` `[AI-0803-SVCD]` | Immutable complete-service package and `thesis-demo-v2`; no runtime activation |
| C | `codex/phase-8-deployer-graph-resolver` `[AI-0803-DPGR]` | Finish/review the existing dark 8.6 graph resolver without profile-specific runtime resources |
| D | `codex/phase-8-profile-workflow` `[AI-0803-PROF]` | Strict backend DTOs and Flutter Phase 8.1 selection/workload/resolved review |
| E | `codex/phase-8-guided-bootstrap` `[AI-0803-BOOT]` | Request-scoped admin bootstrap, bounded CloudConnections, shared Settings/Prepare Deployment UI |
| F | `codex/phase-8-five-layer-v2` multiple scoped commits | RTA v2/RDS v2/Manifest v4, provider services, tiering, readers, projection, access surfaces, optimizer costs, Management persistence, Deployer/Terraform, UI activation |
| G | Five-layer audit `[AI-0803-F5RV]` | Full safe review until zero findings and frozen Five-layer evidence commit |
| H | `codex/phase-8-six-layer-eventing-v1` multiple scoped commits | Exact 8.9B Event Layer delta and all directed bridges |
| I | Six-layer audit `[AI-0803-EVRV]` | Full safe review until zero findings and frozen Six-layer evidence commit |
| J | later Phase 8.10 branch | Comparative evaluation and current-system documentation; no new runtime design |

Each branch starts from the reviewed commit immediately above it. Generated
copies travel with their canonical contract change. A failing pre-existing gate
stops the affected branch; unrelated dirty changes are never swept into a
commit.

## 6. Five-Layer v2 Work Packages

1. **Shared contracts:** workload v2, event scenario reference, RTA v2, RDS v2,
   Manifest v4, profile/provider/catalog artifacts, permission packs, strict
   fixtures, generators, and drift checks.
2. **Optimizer:** profile-specific parsing, capacity/completeness gates,
   L3-hot/L5 placement constraint, independent L4 enumeration, tiering and
   transfer formulas, supporting/fixed cost ownership, profile-local ranking,
   and explicit unsupported reasons.
3. **Management:** strict DTO projections, migrations, selection/run identity,
   resolved persistence, bootstrap sessions, deployment access read model,
   safe errors, export, and historical compatibility.
4. **Deployer core:** generic graph/binding/stage compiler, version pairing,
   deterministic packages/tfvars, resume/destruction, and graph evidence.
5. **Provider implementations:** exact AWS, Azure, and GCP packages, identities,
   static Terraform, raw/rollup storage, scheduled tier jobs, readers, Twin
   projection, L4/L5 surfaces, outputs, and no-apply fixtures.
6. **Flutter:** profile/workload flow, guided bootstrap, generic resolved review,
   and post-deployment L4/L5 cards using the three reviewed UI plans.
7. **Documentation/evidence:** current docs, contract map, limitations,
   reproducible offline commands, and frozen Five-layer digest chain.

## 7. Cross-Cutting Special Cases

| Case | Required behavior |
|---|---|
| Single-cloud | Local domain/Event Layer edges, no bridge, no cross-cloud egress; tiering still runs |
| L4 remote from L3/L5 | Source-owned typed Twin projection only; Grafana remains local to L3 hot |
| L3 hot and L4 both GCP | One named Firestore database, separate collections/indexes/runtime identities, documented database-wide IAM limit |
| L3 hot and L4 on different providers | One database for each provider-owned responsibility; no artificial shared database |
| Same-provider hot-to-cool/archive | Reviewed local export and native lifecycle where selected |
| Cross-provider storage stage | Source-owned finite job, short-lived target identity, manifest/checksum, delayed source cleanup |
| AWS workload targets Azure | Preflight discloses and, after normal deployment confirmation, idempotently enables account-level shared AWS outbound identity federation; the source runtime alone may mint audience-, duration-, and algorithm-bound JWTs, and destroy never disables the shared account feature |
| Late/duplicate data | Idempotent raw and hourly rollup semantics; logical retention remains authoritative |
| Missing price/tier/plugin/quota evidence | Candidate or deployment readiness fails closed; no fallback service |
| Historical Twin | `five-layer-baseline@1` remains readable/verifiable/destroyable and cannot be newly selected |

## 8. Verification Strategy

Verification is layered and proportional to thesis risk:

- canonical/generated contract schema, digest, reference, mutation, and drift;
- workload/capacity/formula golden tests for Small/Medium/Large;
- exhaustive supported topology fixtures and hard-negative placements;
- Optimizer completeness before cost and exact cost ownership;
- Management migration/API/ownership/revision/security/export tests;
- Deployer graph/binding/stage/package/permission tests;
- Terraform format/validate and offline mock plans for every registered module;
- provider adapter and failure-semantics tests without cloud calls;
- Flutter analyzer, unit/widget tests, real Management API integration, Web and
  supported desktop builds;
- strict docs/link/source separation and secret scans;
- two review passes per implementation boundary, repeated until zero findings.

Live cloud deploy/destroy, measured capacity, browser sign-in, quota changes,
and billed operations remain a separately approved supervised protocol.

## 9. Completion Gate

Phase 8.9 is complete only when both profiles have separate immutable digest
chains, every supported scenario resolves through Optimizer -> Management ->
Deployer -> Terraform/package -> Flutter review, all default safe gates pass,
and review reports zero unresolved findings. A clean implementation commit is
required after each profile; Phase 8.10 may not repair architecture ambiguity.

## 10. Planning Review Record

| Pass | Perspective | Result |
|---|---|---|
| 1 | Architecture/concept | Zero unresolved findings on 2026-08-03 after reconciling Five-layer v2 and Six-layer inheritance, all single/multicloud cases, L3-hot/L5 versus independent L4, tiering, credential/access boundaries, current service limitations, and the historical profile |
| 2 | Builder/sequence | Zero unresolved findings on 2026-08-03 after pinning contract-first branches, clean commit boundaries, the unfinished 8.6 worktree integration, cross-stack owners, safe verification, and a separate post-8.9A Six-layer delta |
