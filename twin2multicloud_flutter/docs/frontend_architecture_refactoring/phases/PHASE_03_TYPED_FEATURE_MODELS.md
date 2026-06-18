---
title: "Phase 3: Typed Feature Models"
description: "Introduce typed UI-facing models for Management API contracts and limit raw maps to explicit unstructured payload containers."
tags: [flutter, dto, contracts, refactoring]
lastUpdated: "2026-06-18"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
- twin2multicloud_flutter/docs/frontend_delta/phases/PHASE_01_CONTRACT_BASELINE.md
- twin2multicloud_flutter/lib/models/
- twin2multicloud_flutter/lib/bloc/wizard/wizard_state.dart
- twin2multicloud_flutter/lib/bloc/twin_overview/twin_overview_state.dart
- twin2multicloud_flutter/lib/models/pricing_review_state.dart
EXTRACTED: 2026-06-18 | VERSION: 1.0
-->

# Phase 3: Typed Feature Models

## Summary

Create typed Flutter models for the Management API contracts that drive the
remaining UI work. Raw maps should be limited to known unstructured payload
areas, such as sanitized Terraform outputs or provider evidence details.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Typed pricing health, refresh, and review models | Typing every provider evidence row into a rigid class |
| Typed cloud access/account metadata | Changing backend schema semantics |
| Typed deployment status/history/output models | Live deployment E2E |
| Typed wizard config request/response boundaries | Rewriting optimizer formulas |

## Prerequisites

- Phase 2 repository boundaries are approved or implemented.
- Management API responses include schema versions where the backend supports
  versioned read models.

## Deliverables

- Typed model inventory grouped by feature area.
- Decoder and serialization rules for required fields, optional fields,
  unknown fields, schema versions, and redacted fields.
- Raw-map exception register for intentionally unstructured payloads.
- Model fixture strategy that replaces broad response maps with representative
  typed fixtures.
- Unit test matrix for every model group.

## Model Groups

| Group | Target use |
|---|---|
| Cloud access models | Profile Cloud Accounts and fetch credential confirmation. |
| Pricing models | Dashboard pricing health and Pricing Review Center. |
| Deployment models | Twin Overview deployment operations, logs, outputs, and history. |
| Wizard models | Step 1 credential bindings, Step 2 calculation request/result, Step 3 deployer config. |
| Failure models | User-safe error, blocked reason, validation finding, retry hint. |

## Acceptance Criteria

- Feature states no longer expose backend response maps where a stable model is
  available.
- Model decoders validate required fields and handle unknown optional fields
  safely.
- Secret-like fields are never represented in UI-readable models except as
  redacted metadata.
- Tests cover success, missing required fields, unknown extra fields, and
  sanitized failure parsing for each model group.
- Existing fixtures are updated to use the new typed models instead of broad
  maps where possible.

## Verification

- Static search for `Map<String, dynamic>` at BLoC state and screen boundaries
  is reviewed and reduced to explicitly allowed exceptions.
- Model unit tests are required before feature BLoCs are migrated.
- No UI implementation plan may depend on an untyped Management API response
  when the contract is already stable.

## Roadmap Anchor

Roadmap:
[Frontend Architecture Refactoring Roadmap](../ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md)
