---
title: "Concept: Guided Cloud Access Bootstrap"
description: "User-facing concept for creating reusable deployment CloudConnections from request-scoped provider authority and resuming exact manual prerequisites."
tags: [flutter, configuration-workspace, settings, credentials, bootstrap, cloud-access]
lastUpdated: "2026-08-24"
version: "1.3"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_02_PROFILE_CLOUD_ACCESS.md
- docs/plans/2026-04-26_runtime_credentials_deployment_state_hardening.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
- User-approved manual-step and credential-lifecycle decisions from 2026-07-31
EXTRACTED: 2026-08-24 | VERSION: 1.3
-->

# Concept: Guided Cloud Access Bootstrap

## Summary

Twin2MultiCloud must help a researcher turn one-time provider bootstrap
authority into a reusable, bounded deployment CloudConnection. The researcher
does not manually design a bounded thesis deployment identity, and the
application does not retain administrator credentials.

The capability appears in two contexts and reuses one bootstrap feature owner:

- **Prepare deployment -> Cloud access**, after the immutable architecture is
  selected and the required provider scopes are known; and
- **Settings -> Cloud Accounts & Access**, when the researcher wants to prepare
  reusable access earlier.

Creating a draft, describing workload, calculating, and reviewing an
architecture remain credential-free.

The Management-owned guide/session contract and shared Flutter flow are
implemented and verified with deterministic offline adapters. Production
provider adapters remain fail-closed. The repository's existing manual
`plan -> local bootstrap script -> import` contract remains the supervised
compatibility path; Flutter never executes the local script or a provider CLI.

## Motivation

The existing CloudConnection UI assumes that deployer-ready credentials
already exist. That moves the hardest IAM work to the researcher and conflicts
with the approved bootstrap architecture. A guided flow makes the security
boundary visible: temporary bootstrap authority creates a bounded persistent
identity, then disappears from application state.

The flow must also be honest about provider actions that cannot be automated.
Rather than failing late during deployment, it pauses on one exact remediation
and resumes through the already generated CloudConnection.

## Scope

| In scope | Out of scope |
|---|---|
| Provider-specific preparation guidance | Creating commercial cloud accounts or billing relationships |
| Secret entry/upload for one bootstrap request | Persisting or redisplaying bootstrap secrets |
| Existing and disposable credential-origin choice | Automatically deleting an existing user-owned administrator credential |
| Generated CloudConnection status and safe metadata | Displaying generated deployment secrets |
| Typed external-action pause and recheck | Embedding provider consoles or automating browser sessions |
| Interactive identity selection without browser passwords | Managing MFA, password recovery, external IdP membership, or Google/Entra account creation |
| Truthful disposal/revocation result | Claiming provider-side revocation from local memory release alone |
| Wide desktop and compact Web behavior | Mobile targets |

## User Journey

```text
Selected architecture requires provider access
  -> compatible CloudConnection exists?
     -> yes: select and validate
     -> no: open guided bootstrap
        -> review provider preparation steps
        -> choose credential origin
        -> enter/upload bootstrap credential once
        -> wait while bounded identity is created and validated
        -> review credential-disposal result
        -> CloudConnection ready
        -> Settings: finish
        -> Prepare deployment: bind CloudConnection and run Twin preflight
           -> ready: continue
           -> external action required
              -> open official provider instructions
              -> complete action outside Twin2MultiCloud
              -> return and rerun Twin preflight
              -> continue without entering bootstrap credential again
```

Settings uses the same journey but does not bind the result to a Twin until the
researcher selects it later.

## Compatibility UX

Existing `purpose=deployment` CloudConnections remain valid and selectable;
they are not regenerated or migrated. In Settings, **Add deployment access**
opens guided setup by default. The current raw deployment-credential creation
path remains available as an explicitly labelled **Advanced: import existing
deployment credential** action so outputs from the manual script/import
compatibility path are not stranded. Prepare deployment prefers reuse, then
guided setup; it does not force an existing connection through bootstrap.

## Information Requirements

The default view explains four facts before accepting a secret:

1. which provider account/project/subscription and region will be affected;
2. which active `bootstrap.<provider>.admin-v2` authority pack the submitted
   credential must pass, and which Management-selected deployment pack will be
   assigned (`thesis-demo-v2` for Five-layer v2); AWS additionally presents
   the versioned `aws.thesis-demo-v2.iam-user-v1` binding that makes the PoC's
   IAM-user/access-key deployment identity explicit;
3. that the submitted secret is request-scoped and never rehydrated; and
4. whether Twin2MultiCloud will attempt to revoke a dedicated disposable
   credential or leave an existing user-owned credential untouched.

Provider preparation guidance contains only safe instructions, required
fields, both permission-pack identities/digests, and official links from the typed
Management API guide. Flutter does not hardcode mutable provider procedures.

## Provider Inputs

| Provider | Bootstrap input | Safe context | Human-access input |
|---|---|---|---|
| AWS | access key ID, secret access key, optional session token | account ID, region, and provider-issued expiry when a session token is used | Identity Center display label/email and existing/invite-built-in intent |
| Azure | tenant ID, subscription ID, client ID, client secret | region and safe credential key ID when automatic disposable-secret removal is requested; initial PoC scope is the subscription | existing Entra UPN/object ID |
| GCP existing-project path | service-account JSON | existing project ID and region | existing Google user/group; source CIDR when GCP L5 is selected |
| GCP organization path | service-account JSON | existing bootstrap/admin project, organization/folder target, billing account, and region | existing Google user/group; source CIDR when GCP L5 is selected |

Secret form controls clear as soon as submission begins. The service retains
the value only long enough to serialize the in-flight execute request; no BLoC
state ever emits it. A retry after a transport failure requires explicit user
action and must never recover the previous secret from persisted state.

## Conceptual States

Bootstrap state and Twin deployment-preflight state remain separate even when
the workspace presents them consecutively.

| Bootstrap state | User outcome |
|---|---|
| Guide loading | Stable progress while safe provider guidance loads |
| Guide unavailable | Safe retry; no secret form is shown from stale embedded instructions |
| Ready for input | Scope, bootstrap-authority pack, generated deployment pack, credential origin, and required fields are visible |
| Bootstrap running | Navigation and duplicate submission are blocked; no secret is echoed |
| Generated connection ready | Safe account/scope/identity metadata and validation progress are visible |
| Manual revocation required | Exact credential identifier and provider deletion steps are visible; completion requires acknowledgement |
| Ready | Reusable CloudConnection is available and any Twin binding may continue |
| Credential re-entry required | The prior request ended before a connection was validated; partial safe identifiers are reconciled and a new explicit submission is required |
| Failed | Redacted stable finding with Retry/Cancel; no provider response or secret value |
| Cancelled | Partial safe state is cleaned up or explicitly reported; user-owned administrator credentials are untouched |

| Twin preflight state | User outcome |
|---|---|
| Checking | Existing `/twins/{twin_id}/deployment-preflight` evaluates the immutable architecture with stored connection references |
| External action required | Exact reason, official link, retained Twin/connection state, and Rerun preflight are visible |
| Ready | Deployment preparation can finish |
| Failed | Typed configuration/provider finding is shown without changing the selected architecture |

Closing and reopening the app restores only safe bootstrap-session and Twin-
preflight state. It can restore an external-action or manual-revocation
reminder, never a credential form value.

## Manual-Step Boundary

The UI distinguishes:

- **always user-owned preparation**: create or obtain a dedicated bootstrap
  credential in the provider account;
- **conditional pre-deployment actions**: AWS L4 Identity Center organization
  instance, external IdP provisioning, GCP first-time/external OAuth/IAP,
  quota, billing, or organization-policy remediation; and
- **post-deployment human actions**: invitation/password/MFA, normal provider
  sign-in, GCP Viewer rotation, and certificate-fingerprint verification.

These categories must never be collapsed into a generic “credentials missing”
error.

## Security And Trust

- Flutter calls the Management API only.
- Secret fields are write-only presentation state and are never included in
  diagnostics, navigation state, drafts, demo snapshots, clipboard feedback,
  analytics, or error strings.
- The UI uses `dedicated_disposable` and `existing_user_owned` terminology.
- `released`, `revoked`, `expires at provider`, `manual cleanup required`, and
  `user-owned credential remains valid` are different visible outcomes.
- Manual bootstrap deletion uses acknowledgement rather than a false provider-
  verification claim. Twin prerequisite recheck reruns the existing deployment
  preflight using stored CloudConnection references.
- The generated deployment secret is never rendered. Only provider, scope,
  identity label, deployment-pack status, and validation state are shown.
- Browser passwords are not accepted for AWS, Azure, or GCP human principals.
- Managed runtimes cannot prove cryptographic zeroization of every immutable
  string. UI wording claims non-persistence and no deliberate retention, not
  guaranteed memory erasure.

## Flutter Architecture Guardrails

- The implemented dedicated `CloudBootstrapBloc` owns bootstrap commands and
  safe session state. It composes with the existing `CloudAccessBloc`
  inventory instead of duplicating CloudConnection mutations; widgets remain
  pure presentation and services call the Management API only.
- `CloudAccountsPanel`, `CloudConnectionSelector`,
  `CloudConnectionValidationStatus`, and the existing credential/dialog
  patterns are reused. The shared bootstrap flow is composed by Settings and
  Prepare deployment rather than copied into either entry point.
- All spacing, color, typography, and breakpoint choices come from
  `lib/theme/`; Material `Icons` remain the only icon source.
- Settings and Prepare deployment compose the same bootstrap feature classes
  and DTOs instead of duplicating them. Each active form owns and disposes its
  own ephemeral secret controllers; no global provider-secret controller or
  restorable secret state is allowed.
- The Architect handoff owns complete wide-desktop and compact-Web ASCII
  layouts and `[NEW]`/`[MODIFY]`/`[REUSE]` widget trees before Builder work.

## Dependencies

- [FR-002 Guided Cloud Access Bootstrap Contract](../../feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md)
- [Phase 8 Guided Cloud Bootstrap](../../../../docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md)
- Purpose-aware CloudConnections and Cloud Access inventory
- Configuration-workspace architecture selection and Prepare deployment phase
- Existing production authentication and owner isolation

## Acceptance

- A draft and calculation can be completed without cloud credentials.
- Only providers required by the selected architecture request deployment
  access.
- Both entry points use the same strict session contract, feature classes, and
  safe result model.
- A successful bootstrap yields a selectable bounded CloudConnection without
  exposing its secret.
- A Twin-specific external action survives restart and reruns deployment
  preflight without administrator credentials.
- The UI never equates local secret disposal with provider revocation.
- Reusing a compatible connection does not reopen the bootstrap.
- Every async, empty, failed, blocked, cancel, and resumed state is defined for
  desktop and compact Web.

## Roadmap Anchor

[Configuration Workspace Roadmap](../ROADMAP_CONFIGURATION_WORKSPACE.md), Phase
9.
