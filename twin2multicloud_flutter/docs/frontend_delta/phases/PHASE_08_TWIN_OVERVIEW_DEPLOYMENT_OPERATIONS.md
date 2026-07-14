---
title: "Phase 8: Twin Overview Deployment Operations"
description: "Plan Twin Overview hardening for deploy, destroy, preflight, logs, outputs, and permission-set visibility."
tags: [flutter, frontend-delta, twin-overview, deployment, preflight]
lastUpdated: "2026-07-14"
version: "1.3"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- docs/plans/2026-06-04_permission_set_version_contract.md
- docs/plans/deployment-verification-architecture-v4.md
- twin2multicloud_backend/src/api/routes/cloud_connections.py
- twin2multicloud_flutter/lib/screens/twin_overview/twin_overview_screen.dart
- twin2multicloud_flutter/lib/bloc/twin_overview/twin_overview_bloc.dart
EXTRACTED: 2026-06-13 | VERSION: 1.0
-->

# Phase 8: Twin Overview Deployment Operations

**Status:** Done on `codex/twin-overview-operations-hardening`.

The binding implementation contract is
[`2026-07-14_twin_overview_operations_hardening.md`](../../../implementation_plans/2026-07-14_twin_overview_operations_hardening.md).
It divides this phase into five independently reviewed and committed subphases:
typed contracts/state, twin-scoped readiness, resilient logs, testing utilities,
and the final responsive/accessibility quality gate.

## Progress

| Subphase | Status | Evidence |
|---|---|---|
| 8.1 Typed operation contracts and nullable state | Done | 55 focused tests, 451 complete Flutter tests, analyzer clean |
| 8.2 Twin-scoped readiness and explicit preflight | Done | 25 focused backend tests, 582 complete backend tests, 463 complete Flutter tests, Bandit/analyzer clean, Web/macOS builds pass |
| 8.3 Persisted log catch-up and SSE recovery | Done | 51 focused backend tests, 592 complete backend tests, 466 complete Flutter tests, Bandit/analyzer clean, Web/macOS builds pass |
| 8.4 Trace/simulator workflows and secure archives | Done | 34 focused and 1,131 offline Deployer tests; 53 focused and 601 complete Management API tests; 480 complete Flutter tests; Terraform/Bandit/analyzer/build gates pass |
| 8.5 Responsive/accessibility release gate | Done | 57 focused BLoC/widget/screen tests; 495 complete Flutter tests; analyzer clean; Web/macOS release builds pass |

The 8.1 gate covers Management API and demo adapters, strict versioned parsers,
session-scoped cursors, immutable output/download data, and stale-state clearing.
Verification used no live cloud resources.

The 8.2 gate covers a persisted secret-free readiness cache, owner and provider
binding checks, credential-fingerprint and permission-set invalidation, bounded
redacted evidence, explicit resource-free preflight, and server-side deployment
enforcement. Flutter renders a compact readiness panel, keeps provider evidence
collapsed when healthy, expands remediation when blocked, and independently
guards the deploy command. The demo adapter implements the same fail-closed
contract. Verification used no live cloud resources.

The 8.3 gate consolidates deployment streaming on one owner-scoped Management
API registry and adds bounded replay/live buffers with stale-generation safety.
Flutter performs paginated persisted catch-up before cursor-based SSE, keeps one
typed operation state, suppresses duplicate events, rejects gaps, bounds visible
history, and exposes cancellable reconnect/status-recovery states. The custom
SSE transport uses the current Management API auth token and validates relative
URLs, cursors, payload shape, timestamps, and event size. Verification used no
live cloud resources.

The 8.4 gate introduces independent typed trace and simulator-download state,
bounded collapsed diagnostics, acknowledgement before sensitive downloads, and
race-safe cancellation across deployment lifecycle changes. Simulator archives
are assembled from provider allowlists and validated at both the Deployer and
Management API boundaries. AWS uses exact client/topic permissions, Azure uses
the device identity, and GCP uses a dedicated Pub/Sub topic-publisher identity;
deployment, bootstrap, and CloudConnection credentials are never packaged.
Verification used synthetic credentials and no live cloud resources.

The 8.5 gate replaces the former command-center aggregate with sibling
navigation, operations, outputs, and utility sections under a presentation-only
content boundary. It uses one responsive breakpoint down to 640 px, theme and
spacing tokens, isolated confirmation dialogs, keyboard/focus assertions, and
defense-in-depth output redaction for rendering and clipboard copy. The typed
deployment-output snapshot remains intact from the Management API adapter to
the UI. Verification used the offline demo and no live cloud resources.

## Summary

Harden the Twin Overview deployment surface so deploy/destroy actions, preflight
readiness, permission-set versions, logs, errors, and outputs are visible and
actionable.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Deployment preflight visibility | Creating cloud resources during tests |
| Permission-set status display | Replacing the Deployer API |
| Structured log and error UX | Direct Terraform workspace access |
| Output persistence and copy/download behavior | Layer-by-layer redeployment |
| Simulator/test message utilities | Treating test utilities as deployment success criteria |

## Prerequisites

- Phase 5 credential boundary is implemented.
- CloudConnection preflight endpoint returns ready/checks/permission-set status.
- Deployment SSE contract is stable.
- If simulator/test utility Management API contracts are missing, Phase 1 must
  record them as backend gaps with approved implementation plans.

## Deliverables

- Twin Overview operations concept.
- Preflight card and failure action requirements.
- Permission-set version visibility rules.
- Log viewing behavior for failed, running, completed, and reconnected sessions.
- Output card requirements and residual-risk messaging.
- Simulator/test utility requirements for deployed twins, including broken-state
  handling and visible diagnostic output.

## UI Shape

```text
Twin Overview
|-- Deployment Readiness
|   |-- preflight status
|   |-- permission-set status
|   `-- remediation actions
|-- Deployment Actions
|   |-- Deploy / Destroy
|   `-- structured logs
|-- Testing Utilities
|   |-- Send Test Message / Run Simulator Check
|   |-- Download Simulator
|   `-- collapsed diagnostic output
`-- Deployment Outputs
```

## Architecture Guardrails

- Twin Overview BLoC owns deploy/destroy/test utility side effects.
- Widgets do not call deployment, simulator, or log services directly.
- Test utilities call Management API routes only.
- Diagnostic output is collapsed by default and separate from primary deploy
  status.
- The architect implementation plan must include desktop and compact Web ASCII
  layouts before build work starts.

## Acceptance Criteria

- Users can see why deploy is blocked before clicking Deploy.
- Permission-set mismatches are visible and actionable.
- Failed deployment logs are accessible from the error state.
- Simulator/test message actions work for deployed twins or fail with a
  user-actionable error.
- Simulator/test diagnostics are available without overloading the default view.
- Deploy/destroy SSE states are resilient to refresh and reconnect where the
  backend supports it.
- Terraform/deployment outputs remain visible after successful deploy reload.

## Verification

- Later implementation requires BLoC tests for deploy, destroy, reconnect,
  failure, simulator/test utility states, and output persistence states.
- Widget tests cover preflight pass/fail/outdated/missing permission-set states.
- Widget tests cover testing utility success, failure, running, and unavailable
  states.
- Integration tests run against local Management API without cloud E2E.

## Roadmap Anchor

Roadmap: [Frontend Delta Roadmap](../ROADMAP_FRONTEND_DELTA.md)
