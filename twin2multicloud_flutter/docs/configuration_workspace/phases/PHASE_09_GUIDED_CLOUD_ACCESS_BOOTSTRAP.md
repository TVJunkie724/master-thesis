---
title: "Phase 9: Guided Cloud Access Bootstrap"
description: "Plan the shared Settings and configuration-workspace delivery of request-scoped provider bootstrap and resumable manual prerequisites."
tags: [flutter, configuration-workspace, settings, credentials, bootstrap]
lastUpdated: "2026-08-24"
version: "1.5"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md
- twin2multicloud_flutter/docs/feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md
- docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md
EXTRACTED: 2026-08-24 | VERSION: 1.4
-->

# Phase 9: Guided Cloud Access Bootstrap

## Status

**Implemented and zero-finding reviewed for the offline thesis PoC.** The
shared Settings/Prepare deployment flow, strict models, one-use credential
request, safe resume/recheck/cancel behavior, manual-revocation
acknowledgement, demo parity, and real local Management API integration are
complete. `deterministic_fake` creates no provider resources; production
remains `disabled`. The synchronized `supervised_live` mode is present but
cannot advance past its blocking guide until separately reviewed provider
adapters replace the fail-closed placeholder. See the
[implementation record](../implementation/guided_cloud_access_bootstrap.md).

## Summary

Add one guided deployment-access setup capability that can be entered from
Settings or the configuration workspace. It consumes only the typed Management
API bootstrap contract, never calls a provider directly, and preserves safe
bootstrap and subsequent Twin-preflight state without retaining the submitted
secret.

## Scope

| In scope | Out of scope |
|---|---|
| Provider guide, scope, bootstrap-authority pack, generated deployment-pack presentation, and GCP API-baseline disclosure | Hardcoded mutable provider setup instructions |
| Write-only bootstrap credential submission | Persisting, editing, or redisplaying submitted secrets |
| Credential-origin and disposal/revocation outcome | Automatically deleting existing administrator credentials |
| Generated CloudConnection selection/binding | Displaying generated deployment credential payloads |
| Manual bootstrap-revocation acknowledgement and separate Twin-preflight remediation/recheck | Embedded cloud consoles or automatic provider login |
| Settings and Prepare deployment entry points | Moving credential requirements before architecture selection |
| Default guided setup plus clearly labelled advanced import of an existing deployment credential | Removing or silently migrating existing CloudConnections |
| Desktop and compact Web states | Mobile support or live cloud E2E in default gates |

## Prerequisites

- [FR-002](../../feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md) is
  implemented with strict fixtures.
- The reviewed Phase 8 decision package has published immutable provider
  `thesis-demo-v2` deployment-pack IDs/digests; Flutter only presents the
  Management-selected pack. AWS additionally publishes the versioned
  `aws.thesis-demo-v2.iam-user-v1` binding for the implemented IAM-user and
  access-key path; Azure publishes
  `azure.thesis-demo-v2.service-principal-v1` for the implemented
  service-principal/client-secret path and its Deployer metadata reads.
- The Management API owns bootstrap sessions, owner isolation, request-only
  secret handling, idempotency, and generated CloudConnection persistence.
- GCP existing-project setup pins `bootstrap.gcp.admin-v3` and the fixed
  19-service Phase 8 API baseline; organization/project creation fails closed.
- Deterministic AWS, Azure, and GCP offline adapters return stable safe
  findings and disposal states. The synchronized `supervised_live` mode is
  fail-closed and live provider adapters remain unconfigured.
- Existing manual `/cloud-bootstrap/{provider}/plan` and
  `/cloud-bootstrap/import` endpoints remain compatible but are not invoked by
  Flutter.
- Cloud Access inventory can surface a newly created deployment connection.
- The configuration workspace can bind a selected connection after immutable
  architecture selection.

## Deliverables

- Shared conceptual flow for both entry points without duplicated state.
- Provider guide, both permission-pack presentations, and the provider-
  conditional GCP API-baseline summary from the Management API.
- Provider-specific write-only credential input and credential-origin choice.
- Explicit confirmation before the secret-bearing bootstrap request.
- Running, generated-connection, credential-reentry, revocation-required,
  ready, failed, and cancelled bootstrap behavior.
- Architecture-specific external-action and rerun-preflight behavior after app
  restart using only the Twin and generated CloudConnection references.
- Connection return/binding behavior for Settings and the active Twin draft.
- Compatibility behavior: existing connections remain selectable; Settings
  keeps advanced import while guided bootstrap becomes the default add path.
- Redaction, accessibility, responsive, and offline-demo requirements.
- Architect implementation plan before any Dart changes.

## Acceptance Criteria

- The user can reach provider preparation instructions before secret entry.
- No secret value enters emitted/restorable Flutter state, persistence,
  diagnostics, demo fixtures, or screen restoration; form controls clear when
  the one in-flight execute request starts.
- Duplicate submission is prevented while bootstrap is active.
- App restart restores Twin external-action and manual-revocation states
  without restoring any secret.
- Manual revocation completion is an explicit acknowledgement and does not
  claim provider verification. Twin recheck calls the existing deployment-
  preflight endpoint and does not ask for administrator credentials again.
- `released`, `revoked`, `expires at provider`, `manual revocation required`,
  and `existing credential remains valid` are presented accurately.
- A ready session returns a safe CloudConnection summary and uses the correct
  entry-point completion behavior.
- Existing deployment connections and the advanced manual import path continue
  to work without migration.
- GCP shows the fixed API mutation and retention boundary before credential
  submission and offers no organization/project-creation form.
- The configuration workspace stays credential-free before the selected
  architecture establishes provider requirements.
- Loading, unavailable-guide, invalid-input, running, blocked, failed,
  cancelled, and ready branches are keyboard- and screen-reader-usable at all
  supported desktop/Web widths.
- Flutter calls only the Management API.

## Verification Expectations

- Strict model tests for guide/session versions, states, findings, provider
  field combinations, and forbidden secret-like response fields.
- Feature-state tests for start, duplicate suppression, cancellation, restart,
  credential re-entry, manual-revocation acknowledgement, Twin-preflight
  recheck, stale response rejection, connection return, and failure.
- Presentation tests for both entry points and every state, including compact
  layout and focus recovery after external-action/revocation updates.
- Integration tests use the real HTTP Management API in Docker, configured
  with deterministic fake provider adapters and synthetic bootstrap
  credentials; the Flutter HTTP client is not mocked and no provider mutation
  occurs.
- Existing Flutter analyze, test, Web, macOS, Windows, Linux, architecture, and
  secret-literal gates remain mandatory in implementation.

## Roadmap Anchor

[Configuration Workspace Roadmap](../ROADMAP_CONFIGURATION_WORKSPACE.md), Phase
9.
