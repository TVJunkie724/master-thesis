# GCP Phase 8 API Enablement Ownership

**Date:** 2026-08-24  
**Status:** Approved implementation plan; offline implementation pending  
**Profiles:** `five-layer-baseline@2`, `six-layer-eventing@1`  
**Live scope:** existing-project path only; no provider call is authorized by this plan

## 1. Problem

The frozen `gcp.thesis-demo-v2` deployment role intentionally excludes
`serviceusage.services.enable`, but the active Five-/Six-layer Terraform still
declares `google_project_service` resources. The provider resource requires the
Service Usage API and enables a service, so plan/apply cannot be admitted for
the generated non-admin identity as currently specified. Cloud Build is also
owned twice by the shared GCP setup and the v2 API collection.

The mismatch must be removed before any paid plan/apply gate. It must not be
hidden by broadening the frozen deployment pack or by treating a failed API
check as a warning.

## 2. Decision

API enablement belongs to the short-lived GCP bootstrap authority, not to the
retained deployment identity and not to Terraform.

- Publish `bootstrap.gcp.admin-v3` for the existing-project PoC path. It adds
  only `serviceusage.services.enable` to the prior identity-bootstrap
  authority.
- The bootstrap enables one reviewed fixed superset of the public APIs used by
  every supported GCP placement of both Phase 8 profiles. The PoC deliberately
  prefers a deterministic superset over placement-specific cost optimization.
- The enabled APIs remain enabled after bootstrap cleanup. Cleanup removes only
  gate-owned credentials, bindings, service account, and custom role; it does
  not disable shared project APIs.
- `gcp.thesis-demo-v2` remains byte-identical and keeps only
  `serviceusage.services.get`, allowing the generated identity to verify the
  baseline without retaining API-enable authority.
- Active v2 Terraform stops managing `google_project_service`. Historical
  Five-layer v1 keeps its existing Terraform behavior.
- Organization/project-creation mode remains outside the first supervised live
  gate because the future project does not exist when bootstrap runs. It needs
  a separate reviewed ownership design and must fail closed rather than borrow
  the existing-project claim.

This is a setup mutation, but it creates no Twin workload, compute instance,
cluster, database, broker, or billable message/storage traffic. Some APIs can
create Google-managed service agents; the guide and evidence must state that
side effect explicitly.

## 3. Fixed Phase 8 API Baseline

The canonical baseline is sorted and contains 19 services, below the Service
Usage `batchEnable` limit of 20 services per operation:

1. `artifactregistry.googleapis.com`
2. `cloudbilling.googleapis.com`
3. `cloudbuild.googleapis.com`
4. `cloudresourcemanager.googleapis.com`
5. `cloudscheduler.googleapis.com`
6. `compute.googleapis.com`
7. `container.googleapis.com`
8. `firestore.googleapis.com`
9. `iam.googleapis.com`
10. `iamcredentials.googleapis.com`
11. `iap.googleapis.com`
12. `logging.googleapis.com`
13. `monitoring.googleapis.com`
14. `pubsub.googleapis.com`
15. `run.googleapis.com`
16. `serviceusage.googleapis.com`
17. `storage.googleapis.com`
18. `sts.googleapis.com`
19. `workflows.googleapis.com`

The list is the union of the active v2 Terraform service dependencies across
all single-cloud, directed two-provider, and three-provider placements plus
the Cloud Billing and Service Usage APIs used by bootstrap/preflight. It does
not include historical Five-layer v1-only APIs such as Cloud Functions or
Eventarc.

## 4. User and System Flow

Manual preparation remains intentionally small and explicit:

1. Select an existing billing-enabled project in `europe-west1`.
2. Ensure the Service Usage, IAM, and Cloud Resource Manager APIs are available
   so the dedicated bootstrap service account and its authority can be created
   and inspected.
3. Create a dedicated temporary bootstrap service account, bind
   `bootstrap.gcp.admin-v3`, create one JSON key only when organization policy
   permits it, and submit that key once in the UI.

The guided bootstrap then performs, in order:

1. authenticate the submitted bootstrap identity and verify project scope;
2. verify the exact v3 authority without retaining the submitted key;
3. enable Cloud Billing first, verify billing, then enable the complete fixed
   19-service baseline idempotently and wait for the long-running operations;
4. create the bounded deployment service account, `gcp.thesis-demo-v2` custom
   role/binding, and one generated deployment key;
5. authenticate as the generated identity and verify every baseline API with
   `serviceusage.services.get` plus the project-testable permission subset;
6. persist only the generated encrypted CloudConnection;
7. delete or explicitly hand back cleanup for the temporary submitted key and
   other gate-owned bootstrap artifacts.

The UI must show the exact baseline, the enable-only mutation, the retained
enabled state, the existing-project-only live limitation, and the fact that no
Twin workload is deployed during setup.

## 5. Implementation Slices

1. Contract: add a strict synchronized GCP API-baseline artifact and active
   `bootstrap.gcp.admin-v3`; retain v2 as historical evidence.
2. Validation: make the v2 GCP checker read and verify every baseline service;
   missing APIs are hard failures, not architecture-deferred warnings.
3. Terraform: gate all shared `google_project_service` resources to legacy v1,
   remove the v2 dynamic API resource, and add source tests proving the v2
   dependency union is covered exactly once by the bootstrap baseline.
4. Management/UI/demo: expose v3, the baseline digest/list, and the exact
   mutation/limitation text without introducing a live provider adapter.
5. Verification: contract sync, negative drift tests, credential/preflight
   tests, Terraform native mock plans for all supported placements, Flutter
   model/UI tests, setup smoke, strict docs, and secret scans.
6. Supervised follow-up: only after the offline gate is clean, implement and run
   the existing-project live adapter through G2-G5. Paid G6/G7 remain separately
   authorized.

## 6. Rejected Alternatives

- Retaining `serviceusage.services.enable` on the generated deployment account
  would turn a bounded workload identity into a persistent project-setup
  identity and silently mutate the frozen v2 boundary.
- Keeping Terraform as API owner cannot work with the approved non-admin pack
  and already produces duplicate ownership.
- Requiring the user to enable a placement-specific list manually after Twin
  resolution makes the guided setup incomplete and error-prone.
- Enabling the union with general owner credentials is too broad; the dedicated
  v3 pack keeps the temporary authority reviewable and revocable.

## 7. Primary References

- [Google Cloud: Enable and disable services](https://docs.cloud.google.com/service-usage/docs/enable-disable)
- [Google Cloud: `services.enable` authorization](https://docs.cloud.google.com/service-usage/docs/reference/rest/v1/services/enable)
- [Google Cloud: Service Usage access control](https://docs.cloud.google.com/service-usage/docs/access-control)
- [Terraform Google provider: `google_project_service`](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_project_service)
