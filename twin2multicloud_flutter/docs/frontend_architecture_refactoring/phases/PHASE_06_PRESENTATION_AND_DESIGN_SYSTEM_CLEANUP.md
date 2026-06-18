---
title: "Phase 6: Presentation And Design System Cleanup"
description: "Move business logic out of large screens/widgets and align reusable presentation with the existing theme and spacing tokens."
tags: [flutter, presentation, design-system, refactoring]
lastUpdated: "2026-06-18"
version: "1.0"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/frontend_architecture_refactoring/ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md
- .codex/skills/concept/references/flutter-guardrails.md
- twin2multicloud_flutter/lib/theme/colors.dart
- twin2multicloud_flutter/lib/theme/spacing.dart
- twin2multicloud_flutter/lib/screens/
- twin2multicloud_flutter/lib/widgets/
EXTRACTED: 2026-06-18 | VERSION: 1.0
-->

# Phase 6: Presentation And Design System Cleanup

## Summary

After the state and repository boundaries are stable, split large screens and
widgets into presentation-only components and align the UI with existing theme
and spacing tokens.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Extract dumb reusable widgets from large screens | Changing product workflow |
| Remove parsing and API side effects from widgets | Introducing a new design system package |
| Consolidate hardcoded spacing/color usage into tokens | Pixel-perfect redesign without approved mock |
| Make collapsed diagnostic details consistent | Hiding evidence needed for thesis/debugging |

## Prerequisites

- Phase 4 Wizard decomposition is complete for wizard screens.
- Phase 5 Twin Overview decomposition is complete for overview screens.
- Feature states expose typed data and normalized failures.

## Deliverables

- Presentation extraction map for large screens and widgets.
- Feature-level string/label ownership plan for provider labels, states, and
  user-visible errors.
- Token alignment review for colors, spacing, typography, buttons, cards, and
  diagnostic panels.
- Collapsed evidence-panel pattern for pricing traces, candidate evidence,
  deployment logs, and output details.
- Widget test matrix for extracted components and state branches.

## Cleanup Areas

| Area | Target |
|---|---|
| Screens | Route-level smart widgets and layout composition only. |
| Widgets | Constructor data in, callbacks out; no repository/API calls. |
| Formatting | Central helpers for currency, age, provider labels, and state badges. |
| Diagnostics | Collapsed-by-default detail panels for pricing intent, candidates, logs, and deployment evidence. |
| Tokens | Existing theme colors, spacing, typography, and card/button conventions. |

## Acceptance Criteria

- Large widgets are split where it improves ownership and testability.
- User-visible strings, provider labels, and state labels are centralized per
  feature where practical.
- No widget performs HTTP calls, SSE subscriptions, or backend response parsing.
- Diagnostic detail panels are available for advanced evidence without
  overwhelming the default screen.
- Widget tests cover important empty, error, loading, blocked, and data states.

## Verification

- Static review for service/repository imports under presentation-only widgets.
- Static review for hardcoded colors/spacing introduced by the refactor.
- Widget tests for extracted components.
- Accessibility and responsive desktop/web layout review in the later audit
  phase.

## Roadmap Anchor

Roadmap:
[Frontend Architecture Refactoring Roadmap](../ROADMAP_FRONTEND_ARCHITECTURE_REFACTORING.md)
