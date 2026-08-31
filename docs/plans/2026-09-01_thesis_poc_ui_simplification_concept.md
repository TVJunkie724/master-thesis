---
title: "Thesis PoC UI Simplification Concept"
description: "Screen-by-screen reduction of the Flutter client to the minimum workflow needed for the thesis evaluation."
tags: [flutter, thesis-scope, usability, phase-8]
lastUpdated: "2026-09-01"
version: "1.0"
---

<!-- SOURCES:
- User decision on 2026-09-01 to simplify the existing Flutter UI screen by screen without turning the thesis PoC into a product
- docs/plans/2026-08-26_thesis_poc_target_concept.md
- docs/research/research_questions_and_evaluation_design.md
- docs/plans/2026-08-26_thesis_poc_execution_plan.md
- FRONTEND_ARCHITECTURE.md
- integration_vision.md
- twin2multicloud_flutter/README.md
- Current routes and presentation code under twin2multicloud_flutter/lib/
EXTRACTED: 2026-09-01 | VERSION: 1.0
-->

# Thesis PoC UI simplification concept

## 1. Purpose

The Flutter client remains the presentation layer for the thesis PoC. The
change reduces cognitive load and manual repetition without replacing Flutter,
changing the Management API boundary, or adding product capabilities.

Every retained surface must support at least one of four responsibilities:

1. define one bounded Twin scenario;
2. review the comparable cost result and immutable graph;
3. bind CloudConnections and resolve readiness;
4. deploy, verify, access and destroy with traceable evidence.

| In scope ✅ | Out of scope ❌ |
|---|---|
| Simplify existing routes one at a time | React rewrite or second frontend |
| Remove redundant presentation and manual repetition | New backend capabilities or generic administration |
| Preserve research, safety and reproducibility evidence | Product dashboards, onboarding tours or customization |
| Desktop and Web behavior | Mobile targets |
| Offline and local verification | Provider mutation, Terraform Apply or live E2E |

## 2. Simplification rules

- Each screen has one primary user outcome and at most one visually dominant
  next action.
- Required scientific evidence remains available, but detail that is not needed
  for the next decision may be collapsed.
- A status must answer both "what is true?" and "what should I do next?".
- Provider credentials are import-first. Manual entry remains a fallback.
- Known metadata is extracted from supported files instead of being retyped.
- Destructive and persistent provider actions keep distinct confirmations.
- Existing routes, BLoCs, service contracts and Management-only traffic remain
  unless a later slice proves a concrete need to change them.
- No generic component, package or framework is introduced solely for visual
  consistency.

## 3. Screen inventory and target responsibility

| Order | Current route/surface | Target outcome | Primary reduction |
|---:|---|---|---|
| 1 | `/settings` | Prepare reusable provider access | Remove non-actionable profile presentation; make provider import the default; parse and explain supported Azure JSON forms |
| 2 | `/dashboard` | Start or resume one experiment | Reduce inventory chrome and row actions; keep the Twin state and one obvious continuation action |
| 3 | `/wizard` and `/wizard/:twinId` | Produce one valid immutable experiment configuration | Present the four thesis phases clearly and reduce the visible 15-task navigation without hiding required inputs or findings |
| 4 | `/twins/:id/overview` | Execute and inspect the safe lifecycle | Lead with readiness and the next permitted action; group access, verification and cleanup evidence by lifecycle stage |
| 5 | Shared shell and dialogs | Make the four screens feel like one PoC | Align labels, empty/error states, focus order and responsive behavior; remove superseded presentation code |

The dormant login screen and profile bootstrap gate are not product screens and
do not become part of this redesign. The local profile remains a runtime safety
boundary, not an account-management feature.

## 4. Delivery sequence

Each row is a bounded implementation slice with its own reviewed plan, tests,
audit and focused commit. A later screen is not redesigned while an earlier
slice is still failing its gates.

```text
Cloud access
    |
    v
Twin inventory
    |
    v
Configuration workspace
    |
    v
Lifecycle overview
    |
    v
Cross-screen consistency audit
```

The first slice repairs the current Azure import blocker. It accepts both the
standard Azure service-principal JSON and the Twin2MultiCloud compatibility
bundle, shows secret-free format help, prefills known fields locally and sends
only a normalized Azure deployment object to the existing Management endpoint.

## 5. Research and safety mapping

| UI responsibility | Thesis/safety contribution |
|---|---|
| Scenario and configuration | RQ1 reproducible typed intent |
| Cost and immutable graph review | RQ2 admission and RQ3 comparable estimate |
| Cloud access and readiness | RQ1 deployability and mutation safety |
| Deploy, verify and Destroy | RQ1 operational evidence, RQ2 functional behavior and RQ3 observed cost boundary |
| Evidence details | Reproducibility, limitations and residual-resource accountability |

Visual polish that cannot be mapped to this table is not part of the active
work.

## 6. Completion boundary

The screen-by-screen simplification is complete when the four supported
responsibilities can be demonstrated without redundant product chrome or
manual duplication, all existing safe workflow contracts remain green, and a
manual Desktop/Web review finds one obvious next action on every retained
screen. This temporary concept is then removed after its durable decisions are
reflected in `FRONTEND_ARCHITECTURE.md`, current user/developer documentation
and `docs/development_and_decision_log.md`.
