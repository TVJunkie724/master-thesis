---
title: "Frontend Architecture Target Concept"
description: "Target-state concept for making the Flutter app maintainable, contract-driven, and thesis-ready before the remaining UI delta work."
tags: [flutter, architecture, concept, clean-architecture, thesis]
lastUpdated: "2026-06-18"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
- FRONTEND_ARCHITECTURE.md sections "Architecture Overview", "Flutter Tech Stack Explained", "Critical Architectural Review"
- integration_vision.md sections "System Architecture" and "The Management Platform"
- twin2multicloud_flutter/docs/frontend_delta/ROADMAP_FRONTEND_DELTA.md
- twin2multicloud_flutter/lib/services/api_service.dart
- twin2multicloud_flutter/lib/bloc/wizard/wizard_bloc.dart
- twin2multicloud_flutter/lib/bloc/twin_overview/twin_overview_bloc.dart
EXTRACTED: 2026-06-18 | VERSION: 1.0
-->

# Frontend Architecture Target Concept

## Summary

The Flutter app should become a contract-driven Management API client with
clear separation between API mechanics, feature use cases, feature state, and
presentation. This is the architecture needed for the remaining credential,
pricing, deployment, and wizard work to be implemented safely.

## Motivation

The app already demonstrates the user journey, but the current implementation
places too many responsibilities in a few classes. That makes every new backend
contract harder to wire, every test harder to isolate, and every UI bug harder
to reason about.

For the thesis, the UI should demonstrate the final platform architecture:
Flutter is the Orchestrator front-end, the Management API is the integration
boundary, and Optimizer/Deployer complexity is exposed through typed contracts
rather than Flutter-specific workarounds.

## Scope

| In scope ✅ | Out of scope ❌ |
|---|---|
| Split HTTP mechanics from feature repositories | Replacing the Management API with direct service calls |
| Stabilize BLoC ownership for feature flows | Introducing a second feature state-management pattern |
| Type the contract boundaries used by UI state | Typing every arbitrary Terraform output value as a fixed model |
| Move formatting and parsing out of large screens | Visual redesign without a separate UI concept |
| Establish testable error/loading/empty/blocked behavior | Real cloud E2E deployment verification |

## Target Boundaries

```text
User action
  |
  v
Screen-level smart widget
  |
  v
Feature BLoC
  |
  v
Feature Repository
  |
  v
ManagementApiClient
  |
  v
Management API
```

The important rule is that only repositories talk to the API client. Widgets do
not parse API payloads, and BLoCs do not know endpoint paths.

## Feature Ownership

| Feature area | Owns | Does not own |
|---|---|---|
| Dashboard | Twin list read model, stat cards, pricing health summary entry point | Provider refresh execution details |
| Profile/Settings | Cloud account inventory and purpose visibility | Admin credential persistence |
| Pricing Review | Provider refresh run state, candidate review state, user-reviewed decision submission | Optimizer formula implementation |
| Wizard | Draft state, selected cloud connections, typed optimizer/deployer config flow | Global pricing maintenance |
| Twin Overview | Twin read model, deployment actions, typed logs/outputs | Wizard config editing internals |
| Simulator/Verification | Test utility diagnostics after the core overview is stable | Blocking the architecture refactor |

## Error And State Model

Each async feature must expose the same conceptual branches:

| Branch | Meaning |
|---|---|
| Initial | The feature has not loaded yet. |
| Loading | A request or stream subscription is active. |
| Data | Valid typed data is available. |
| Empty | The request succeeded but no user-visible data exists. |
| Blocked | User action is required before the operation can run. |
| Error | A normalized, non-secret failure is available. |

## Thesis Value

This refactor supports the thesis by making the implementation reflect the
documented architecture:

- the UI becomes a clean Management API client,
- pricing/deployment evidence is shown through typed read models,
- credential and access state is visible without exposing secrets,
- complex provider behavior is isolated outside presentation code,
- future work can extend optimization and deployment UI without rewriting the
entire app.

## Roadmap Anchor

Roadmap:
[Frontend Architecture Refactoring Roadmap](../ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md)
