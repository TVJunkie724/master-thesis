---
title: "FR-001 Deployment Layer Access Read Model"
description: "Typed Management API contract for post-deployment L4/L5 links, readiness, and bounded credential rotation."
tags: [flutter, feature-request, management-api, deployer, layer-access]
lastUpdated: "2026-08-11"
version: "1.1"
---

# FR-001 Deployment Layer Access Read Model

## Status

**Implemented and offline verified.** `twin2multicloud_backend`,
`3-cloud-deployer`, and Flutter share strict contracts and fixtures. The local
integration uses a real Management API with deterministic test-only provider
mutation; no cloud resource or browser session is involved. Five-layer v2 is
active for offline selection/evaluation, while its explicit live-capacity
gates keep deployment selection blocked.

## Problem

The current `GET /twins/{id}/outputs` response is generic, redacted Terraform
evidence. It does not guarantee that a browser user can sign into L4 or L5,
does not carry typed layer/auth/readiness semantics, and must not transport a
password. Twin Overview therefore cannot safely implement the approved Layer
Access section from existing endpoints.

## Requested Contract

1. Add owner-scoped `GET /twins/{id}/deployment-access` returning exact
   `deployment-access.v1`; `available` responses contain one L4 and one L5
   surface for deployed `five-layer-baseline@2` Twins, while historical
   profiles return `unsupported` with zero surfaces and a stable reason.
2. Persist only allowlisted safe URLs, provider/service IDs, principal labels,
   readiness, capability/limitation values, deployment/content revisions, and
   credential fingerprints.
3. Add owner-scoped
   `POST /twins/{id}/deployment-access/l5/credentials:rotate` only for the GCP
   Grafana Viewer. It rotates and returns a one-time
   `deployment-access-credential.v1` response.
4. Never expose the Grafana Admin credential, datasource reader key, provider
   token, Kubernetes Secret payload, Terraform state, or CloudConnection
   credential.
5. Return stable safe failure codes and preserve owner isolation as 404.
6. Clear active access on destroy or superseding deployment.
7. Serialize GCP Viewer rotation per deployment; concurrent calls return the
   stable 409 `GCP_GRAFANA_VIEWER_ROTATION_IN_PROGRESS` before mutation, and
   no request/response body is logged.

## Acceptance

- Strict backend and Dart parsers reject unknown schema versions, duplicate or
  missing layers, invalid provider/auth combinations, non-HTTPS URLs, unknown
  readiness values, and secret-like fields.
- Offline Management integration fixtures cover all nine L3/L4/L5 placements
  and historical/destroyed/error cases.
- Rotation stores only its timestamp/fingerprint and a second request rotates
  again; it never reads the previous password.
- Flutter calls only the Management API and generic Terraform outputs remain
  unchanged.

## Authority

See
[`phase_08_layer_access_handoff.md`](../../../docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md).

## Implemented Evidence

- Deployer emits allowlisted L4/L5 evidence only after provider resource,
  identity, content, and data-probe gates; synchronous output projection is
  redacted.
- Management persists and owner-scopes `deployment-access.v1`, returns an
  explicit historical-v1 unsupported shape, and serializes GCP Viewer
  rotation while retaining only its timestamp and SHA-256 fingerprint.
- Flutter implements strict DTOs, isolated BLoC state, responsive cards,
  injected external launching, confirmation, and one-time reveal/consume.
- The local integration suite covers all nine provider pairs plus owner 404,
  blocked readiness, historical, destroyed, output-redaction, replacement
  rotation, and concurrent 409 behavior.
