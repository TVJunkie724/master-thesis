---
title: "FR-002 Guided Cloud Access Bootstrap Contract"
description: "Management API and provider-adapter contract required for request-scoped bootstrap authority, generated CloudConnections, and resumable manual prerequisites."
tags: [flutter, feature-request, management-api, deployer, credentials, bootstrap]
lastUpdated: "2026-08-24"
version: "1.4"
---

<!-- SOURCES:
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md
- docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md
- docs/plans/2026-05-21_provider_bootstrap_preflight_plan.md
- Current Management API OpenAPI contract on 2026-07-31
- GitHub issue #154
EXTRACTED: 2026-08-24 | VERSION: 1.4
-->

# FR-002 Guided Cloud Access Bootstrap Contract

## Status

**Implemented and locally zero-finding reviewed for the offline PoC under
[#154](https://github.com/TVJunkie724/master-thesis/issues/154).** Contracts,
strict fixtures, Management lifecycle, deterministic provider adapters,
Deployer admission, Flutter Phase 9, and request-secret security tests are
committed. This status does not claim live provider mutation: production is
fail-closed and supervised live adapters remain outside the default gate.

## Problem

The current UI can persist and select a deployer-ready CloudConnection, but it
does not create that bounded identity from temporary provider authority. It
also has no typed way to pause for a provider-owned manual prerequisite,
resume after restart, or distinguish local secret release from provider-side
credential revocation.

The current Management API already provides the implemented manual-first
`POST /cloud-bootstrap/{provider}/plan` and
`POST /cloud-bootstrap/import` contract. FR-002 adds the in-application guided
lifecycle and keeps those endpoints compatible; it does not silently replace
or relabel the script flow.

## Requested Contract

1. Add versioned `cloud-bootstrap-guide.v1` provider guidance with safe setup
   steps, official links, required fields, new
   `bootstrap.<provider>.admin-v2` authority-pack identity/digest, Management-
   selected generated-deployment-pack identity/digest (`thesis-demo-v2` for
   Five-layer v2), the AWS `aws.thesis-demo-v2.iam-user-v1` identity binding
   and Azure `azure.thesis-demo-v2.service-principal-v1` identity binding where
   applicable, known scope gaps, credential-origin options, and disposal
   behavior through a safe-context
   `POST /cloud-bootstrap/{provider}/guide` request.
2. Add owner-scoped `cloud-bootstrap-session.v1` and the following Management
   API operations:

   ```text
   POST /cloud-bootstrap/sessions
   GET  /cloud-bootstrap/sessions?provider={provider}&active={bool}
   GET  /cloud-bootstrap/sessions/{session_id}
   POST /cloud-bootstrap/sessions/{session_id}/execute
   POST /cloud-bootstrap/sessions/{session_id}/acknowledge-manual-revocation
   POST /cloud-bootstrap/sessions/{session_id}/cancel
   ```

3. Create the safe session before secret submission. Accept bootstrap secrets
   only in the synchronous `execute` request; exclude its body from logs,
   traces, metrics, audits, retries, temporary files, crash dumps under
   application control, and durable state.
4. Create and guard the three new provider bootstrap-authority artifacts before
   session execution; create, validate, encrypt, and persist only a bounded
   `purpose=deployment` CloudConnection; return its safe summary when ready.
5. Support `dedicated_disposable` and `existing_user_owned` origins with exact
   disposal states: `revoked`, `expires_at_provider`, `manual_revocation_required`,
   `not_retained_user_managed`, and `released_after_failure`.
6. Keep bootstrap session state separate from Twin deployment admission.
   Bootstrap owns credential validation, generated identity, disposal, and
   manual revocation acknowledgement. Existing
   `POST /twins/{twin_id}/deployment-preflight` owns AWS Identity Center, Azure
   Entra, GCP IAP, quota, billing, and architecture-specific policy findings.
7. Manual revocation acknowledgement, cancel, and Twin-preflight recheck must
   operate without a bootstrap secret.
8. Enforce one active session per owner/provider/scope, idempotent provider
   writes, partial-resource cleanup, and 404 owner isolation.
9. Prevent bootstrap sessions and credentials from entering deployment
   manifests, packages, tfvars, Terraform state, provider outputs, or generic
   deployment evidence.
10. Keep the current `plan` and `import` endpoints and their tests compatible
    until all guided provider adapters and migration gates pass; endpoint
    removal is outside FR-002.

## Acceptance

- Strict parsers reject unknown versions/states, incompatible provider fields,
  unsafe URLs, and secret-like response fields.
- Tests prove no bootstrap secret persists or appears in logs/errors after
  success, failure, cancellation, timeout, or process restart.
- Replaying session creation or execute with the same session/idempotency
  identity cannot create duplicate provider identities or CloudConnections.
- A manual bootstrap deletion is explicitly acknowledged without claiming
  provider verification. A Twin-specific prerequisite can be resolved after
  restart and the existing deployment preflight rerun using only the generated
  CloudConnection.
- Existing user-owned credentials are never revoked by the platform.
- Disposable credentials never report `revoked` without provider-side success;
  failed automatic cleanup returns exact manual guidance.
- Flutter can implement both entry points without provider calls or duplicated
  state.
- The new contract passes compatibility tests for the existing manual
  plan/script/import flow.

## Authority

See
[`phase_08_guided_cloud_bootstrap.md`](../../../docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md).
