---
title: "Phase 2: API Repository Split"
description: "Split the current broad ApiService into a Management API client plus focused feature repositories."
tags: [flutter, api, repository, refactoring]
lastUpdated: "2026-06-18"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
- twin2multicloud_flutter/lib/services/api_service.dart
- twin2multicloud_flutter/lib/services/sse_service.dart
- twin2multicloud_flutter/lib/config/api_config.dart
- twin2multicloud_flutter/lib/core/result.dart
- twin2multicloud_flutter/lib/core/error_handler.dart
EXTRACTED: 2026-06-18 | VERSION: 1.0
-->

# Phase 2: API Repository Split

## Summary

Replace the broad `ApiService` surface with focused repositories backed by a
small Management API client. This phase is the main boundary refactor that
prevents new UI work from adding more endpoint knowledge to a single class.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Core Management API client for HTTP mechanics | Direct Optimizer or Deployer clients |
| Feature repositories for user-visible workflows | Replacing backend contracts |
| Central auth header, runtime config, and error normalization | UI redesign |
| Temporary compatibility facade only where needed for incremental migration | Keeping a permanent god service |

## Prerequisites

- Phase 1 architecture baseline is approved.
- Backend routes used by the UI are documented in the Frontend Delta contract
  baseline or explicitly marked as deferred.

## Deliverables

- Core Management API client contract for base URL, auth header handling,
  request execution, response decoding, and normalized failures.
- Feature repository inventory with migration order and ownership.
- Temporary compatibility strategy for callers that cannot move in the first
  implementation slice.
- Repository test matrix covering success, backend validation error, network
  failure, unauthorized response, and secret-safe error messages.

## Target Repository Set

| Repository | Responsibility |
|---|---|
| `AuthRepository` | Current user/session shell calls. |
| `TwinRepository` | Twin list, details, create/update, dashboard stats. |
| `CloudAccessRepository` | Cloud account/access inventory and CloudConnection interactions. |
| `PricingRepository` | Pricing health, refresh runs, candidate review, reviewed decisions. |
| `WizardRepository` | Wizard draft/config persistence and optimizer/deployer step coordination. |
| `DeploymentRepository` | Deployment status, operations, logs, outputs, deploy/destroy actions. |
| `DeployerConfigRepository` | Typed deployer config read/update/validation surface. |

## Acceptance Criteria

- Endpoint paths are owned by the API client/repositories, not widgets or BLoCs.
- Feature BLoCs depend on repositories, not on raw HTTP mechanics.
- Existing behavior is preserved while migration proceeds incrementally.
- All repository methods return typed success data or normalized failures.
- SSE remains behind a deployment/log repository boundary.
- Tests cover repository error normalization and at least one success path per
  repository introduced in this phase.

## Verification

- Static search confirms no new direct endpoint paths are introduced outside
  approved API/repository files.
- Existing Flutter unit/widget tests remain green in the later implementation
  phase.
- Repository tests exercise auth headers, base URL configuration, error mapping,
  and secret-safe failure messages.

## Roadmap Anchor

Roadmap:
[Frontend Architecture Refactoring Roadmap](../ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md)
