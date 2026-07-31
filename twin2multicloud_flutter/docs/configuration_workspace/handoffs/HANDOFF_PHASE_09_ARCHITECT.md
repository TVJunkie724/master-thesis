---
title: "Handoff: Guided Cloud Access Bootstrap To Architect"
description: "Self-contained handoff for producing the Flutter implementation plan for Configuration Workspace Phase 9."
tags: [flutter, handoff, architect, credentials, bootstrap]
lastUpdated: "2026-07-31"
version: "1.1"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md
- twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_09_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md
- twin2multicloud_flutter/docs/feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md
- .codex/skills/concept/references/handoff-protocol.md
EXTRACTED: 2026-07-31 | VERSION: 1.1
-->

# Handoff: Guided Cloud Access Bootstrap -> Architect

## 1. Context

- Pillar: Configuration Workspace, with a shared Settings entry point.
- Roadmap: `twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md`.
- Concept: `twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md`.
- Phase: `twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_09_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md`.
- Backend dependency: `twin2multicloud_flutter/docs/feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md`.

The user approved a guided one-time bootstrap: request-scoped provider
authority creates a reusable bounded CloudConnection; administrator secrets
are not retained; unavoidable external actions pause and resume through the
generated connection.

## 2. Objective

Produce one complete Flutter implementation plan for the shared guided cloud-
access setup capability in Settings and the configuration workspace, without
writing Dart code or re-deciding the approved credential lifecycle.

## 3. Required Reading

- `FRONTEND_ARCHITECTURE.md`
- `integration_vision.md`
- `ONBOARDING.md`
- `.codex/skills/concept/references/flutter-guardrails.md`
- `twin2multicloud_flutter/README.md`
- `twin2multicloud_flutter/docs/configuration_workspace/ROADMAP_CONFIGURATION_WORKSPACE.md`
- `twin2multicloud_flutter/docs/configuration_workspace/CONCEPT_CONFIGURATION_WORKSPACE.md`
- `twin2multicloud_flutter/docs/configuration_workspace/concepts/CONCEPT_CLOUD_ACCESS_BOOTSTRAP.md`
- `twin2multicloud_flutter/docs/configuration_workspace/phases/PHASE_09_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md`
- `twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_02_PROFILE_CLOUD_ACCESS.md`
- `twin2multicloud_flutter/docs/feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md`
- `docs/plans/phase_08_architecture_profiles_eventing/phase_08_guided_cloud_bootstrap.md`
- `docs/plans/phase_08_architecture_profiles_eventing/phase_08_layer_access_handoff.md`

## 4. Scope

In scope:

- both approved entry points with one shared bootstrap feature/result;
- provider guide, bootstrap-authority pack, generated deployment pack, scope,
  and credential-origin presentation;
- write-only AWS/Azure/GCP bootstrap inputs;
- start, execute, cancel, credential re-entry, restart, manual-revocation
  acknowledgement, disposal, and completion behavior;
- workspace composition of the separate Twin deployment-preflight external-
  action and rerun behavior;
- safe CloudConnection return/binding;
- default guided setup plus the explicitly labelled advanced existing-
  deployment-credential import compatibility path;
- wide desktop and compact Web layouts;
- typed Management API integration, demo parity, accessibility, tests, and
  secret-lifecycle verification.

Out of scope:

- backend/provider-adapter implementation;
- provider API calls from Flutter;
- real cloud E2E;
- browser-login automation;
- creating commercial cloud accounts or human Azure/Google accounts;
- post-deployment L4/L5 access cards, which remain Frontend Delta 8.6.

## 5. Constraints And Decisions

- Draft creation, workload, calculation, and architecture review remain
  credential-free.
- The workspace entry appears only after provider requirements are known.
- Settings and workspace must not own separate mutable bootstrap sessions.
- The bootstrap session ends at a ready CloudConnection. Settings stops there;
  only a bound Twin continues through the existing deployment-preflight owner.
- Flutter calls only the Management API.
- Provider instructions come from `cloud-bootstrap-guide.v1`; they are not
  hardcoded as mutable UI copy.
- The submitted secret is never persisted, restored, logged, placed in demo
  data, or redisplayed after submission.
- Manual bootstrap deletion uses explicit acknowledgement. Architecture-
  specific external action reruns Twin deployment preflight with the generated
  CloudConnection only.
- Existing user-owned administrator credentials are never deleted.
- Release, provider expiry, revocation, manual cleanup, and user-owned validity
  are different visible states.
- Generated deployment credentials are never rendered.
- No browser password is collected.
- Use the established Riverpod composition/BLoC feature ownership boundary;
  do not introduce another state-management package.
- Inventory and reuse/extend `lib/widgets/` before proposing any new component;
  justify every `[NEW]` widget in the plan.
- Use `lib/theme/` tokens and Material `Icons` only; the plan may not introduce
  hardcoded colors, spacing, typography, breakpoints, or another icon package.
- Preserve the implemented manual `plan`/`import` API as a compatibility path;
  Flutter does not execute its scripts or CLIs.
- Inspect and prefer extension/composition of `CloudAccessBloc`,
  `CloudAccountsPanel`, `CloudConnectionSelector`,
  `CloudConnectionValidationStatus`, `CloudConnectionCreateDialog`, and
  `ProviderPayloadForm`. If bootstrap receives a dedicated child BLoC, the plan
  must explain why `CloudAccessBloc` cannot own its long-running sub-state and
  keep inventory/mutations in Cloud Access.

## 6. Acceptance Criteria

- The implementation plan maps every API operation, strict model, state,
  event/command, ownership boundary, screen integration, and test owner.
- It includes complete wide and compact ASCII layouts and a marked component
  tree without mobile targets.
- It covers guide failure, invalid input, active submission, duplicate command,
  cancellation, partial provider failure, credential re-entry, restart,
  manual-revocation acknowledgement, Twin external pause/preflight rerun,
  ready result, stale response, and owner/404 failure.
- It proves no secret can rehydrate or enter diagnostics.
- It defines focus, keyboard, screen-reader, and responsive behavior.
- Implementation verification includes analyzer, full Flutter tests, Web and
  all desktop builds, architecture/security checks, and local Management API
  integration through real HTTP without mocking the Flutter client. The Docker
  Management API uses deterministic fake provider adapters; live providers
  remain forbidden.
- All async branches handle loading, error, empty/blocked, and data states.

## 7. Dependencies

- FR-002 is planned and blocks Flutter implementation. The current live
  OpenAPI exposes only manual bootstrap `plan`/`import`, not the guide/session
  operations.
- The Phase 8 decision package and immutable provider `thesis-demo-v2` packs
  must exist before FR-002 provider adapters; Flutter does not select or author
  permission-pack versions.
- Purpose-aware CloudConnections, Cloud Access inventory, and configuration-
  workspace architecture selection are implemented predecessors.
- The Architect plan may be written before FR-002 code lands, but Builder work
  must not begin until schemas and strict fixtures are committed.
- Layer Access implementation depends on this bootstrap boundary but is a
  separate later deliverable.

## 8. Open Questions

None. Provider credential fields, session states, manual prerequisites,
disposal semantics, entry points, and cross-service ownership are decided by
the cited authority.
