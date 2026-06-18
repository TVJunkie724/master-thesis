---
title: "Phase 5: Twin Overview Decomposition"
description: "Separate Twin Overview read models, deployment operations, logs, outputs, and simulator diagnostics into testable feature boundaries."
tags: [flutter, twin-overview, deployment, logs, refactoring]
lastUpdated: "2026-06-18"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_08_TWIN_OVERVIEW_DEPLOYMENT_OPERATIONS.md
- twin2multicloud_flutter/lib/bloc/twin_overview/twin_overview_bloc.dart
- twin2multicloud_flutter/lib/screens/twin_overview/twin_overview_screen.dart
- twin2multicloud_flutter/lib/widgets/deployment_verification_card.dart
- twin2multicloud_flutter/lib/widgets/deployment_terminal.dart
- twin2multicloud_flutter/lib/widgets/terraform_outputs_card.dart
EXTRACTED: 2026-06-18 | VERSION: 1.0
-->

# Phase 5: Twin Overview Decomposition

## Summary

Refactor Twin Overview so deployment operations, logs, outputs, and simulator
diagnostics are separate feature boundaries. This phase prepares the screen for
the later simulator/log-trace work without forcing that work into the first
overview cleanup.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Split twin read model from deployment command state | Real cloud E2E deployment tests |
| Move log/output parsing behind typed models or adapters | Full simulator redesign |
| Keep deployment operations behind Management API repositories | Direct Deployer calls |
| Defer simulator/test utility bug work into an explicit later slice | Rebuilding Grafana or monitoring features |

## Prerequisites

- Phase 2 deployment repository exists.
- Phase 3 deployment models exist.
- Backend core deployment operation read contracts are available.

## Deliverables

- Twin Overview ownership map for read model, operations, logs, outputs, and
  simulator/verification diagnostics.
- Deployment operation state contract for idle, loading, streaming, success,
  blocked, and failure branches.
- Log/output parsing boundary with redaction and source-deployment metadata.
- Deferred simulator/verification slice definition with explicit entry and exit
  criteria.
- Regression test matrix for operation reads, commands, log catch-up, SSE, and
  output rendering.

## Target Sub-Flows

| Sub-flow | Owns |
|---|---|
| Overview read model | Twin identity, state, optimizer/deployer summary, access links. |
| Deployment operations | Deploy, destroy, status refresh, active operation metadata. |
| Deployment logs | SSE subscription, catch-up loading, sanitized log entries. |
| Deployment outputs | Typed output groups, redaction metadata, source deployment reference. |
| Simulator/verification diagnostics | Deferred test utility behavior after core overview is stable. |

## Acceptance Criteria

- The overview screen no longer parses raw deployment response structures.
- Deployment actions expose consistent loading, blocked, error, success, and
  stream states.
- Terraform outputs render only sanitized values and preserve redaction status.
- Simulator/test utility issues are either fixed in a dedicated approved slice
  or tracked as deferred, not mixed into unrelated overview refactoring.
- Tests cover deployment command success/failure, SSE reconnect or fallback
  handling where applicable, output redaction rendering, and empty output state.

## Verification

- BLoC/repository tests for deployment operation reads.
- Widget tests for output and log display states.
- Static review for direct Deployer/Optimizer endpoint usage.
- Manual smoke in later implementation against local Management API mock
  deployment endpoints only, not real cloud E2E.

## Roadmap Anchor

Roadmap:
[Frontend Architecture Refactoring Roadmap](../ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md)
