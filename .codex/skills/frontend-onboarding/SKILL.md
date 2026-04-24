---
name: frontend-onboarding
description: >
  Use this project-specific Twin2MultiCloud skill when the user asks to "onboard to Flutter", "understand the frontend", "frontend onboarding", "learn the Flutter codebase", "frontend overview", or "how does the Twin2MultiCloud Flutter app work". Use for onboarding new agents or sessions into the `twin2multicloud_flutter` codebase before any UI work.
metadata:
  project: master-thesis
  source: .claude/frontend-onboarding
---


# Frontend Onboarding — Twin2MultiCloud Flutter

Read and apply all guardrails from `references/flutter-guardrails.md` before any work.

## Mission

Thoroughly understand the **`twin2multicloud_flutter`** codebase before implementing any feature. The Flutter app is the visual front-end of the Twin2MultiCloud platform — Desktop and Web only (mobile dropped — see commit `f135bac`). It talks exclusively to the Management API (port 5005), which proxies to the Optimizer (5003) and Deployer (5004).

> [!CAUTION]
> **MANDATORY: Read `FRONTEND_ARCHITECTURE.md` and `integration_vision.md` before implementing any feature.**
> These two documents (at the repository root) define the architecture, screen wireframes, twin-state machine, BLoC layout, and the cross-project responsibility split. Skipping them produces UI that bypasses Management API or duplicates existing widgets.

## Step 1: Read the Architecture Sources (CRITICAL)

| Order | Document | Purpose |
|-------|----------|---------|
| 1 | `FRONTEND_ARCHITECTURE.md` | Architecture overview, SSE choice, SQLite rationale, OAuth design, screen wireframes (Login, Dashboard, Twin Detail, Wizard), twin-state machine |
| 2 | `integration_vision.md` | 5-Layer Architecture, why Flutter must go through Management API |
| 3 | `twin2multicloud_flutter/README.md` | Project-local conventions and run instructions |
| 4 | `twin2multicloud_flutter/docs/` | Feature-level docs (e.g. `TODO_infrastructure_deployment.md`) |
| 5 | `references/flutter-guardrails.md` | Hard rules — non-negotiable |

### What You'll Learn

- Why **SSE** (not WebSocket, not polling) is used for deployment log streaming
- Why **SQLite** is the source of truth (relational + zero-config + ACID for file versioning)
- The **OAuth provider plugin** design (Google first, Microsoft / university later)
- The **twin-state machine**: `draft → configured → deployed ⇄ destroyed / error → inactive`
- Why the **Wizard** brings a twin to `configured`, while the **Dashboard / Detail** view triggers `configured → deployed`

## Step 2: Map the Codebase

```
twin2multicloud_flutter/
├── lib/
│   ├── main.dart                ← App entry point
│   ├── app.dart                 ← MaterialApp + router setup
│   ├── bloc/                    ← STATE LAYER (flutter_bloc)
│   │   ├── wizard/              → WizardBloc, WizardEvent, WizardState
│   │   └── twin_overview/       → TwinOverviewBloc and friends
│   ├── screens/                 ← PRESENTATION LAYER (top-level screens)
│   │   ├── dashboard_screen.dart
│   │   ├── login_screen.dart
│   │   ├── settings_screen.dart
│   │   ├── twin_overview/       → Twin Detail screens
│   │   └── wizard/              → Wizard step screens
│   ├── widgets/                 ← PRESENTATION (reusable UI parts)
│   │   ├── architecture/        → ArchitectureGraph, ArchitectureLayerBuilder
│   │   ├── calc_form/           → Cost calculation form widgets
│   │   ├── credentials/         → Credential entry widgets
│   │   ├── dashboard/           → Dashboard cards
│   │   ├── file_inputs/         → ConfigForm, FileEditor, ZipUpload blocks
│   │   ├── form_inputs/         → Generic inputs (text, dropdown, etc.)
│   │   ├── results/             → Optimizer result displays
│   │   ├── step3/               → Wizard Step 3 widgets
│   │   ├── wizard/              → Wizard scaffold widgets
│   │   ├── branded_app_bar.dart, code_viewer_dialog.dart, …
│   ├── services/                ← SERVICES LAYER (HTTP / SSE)
│   ├── providers/               ← App-level providers (auth, theme)
│   ├── models/                  ← Plain Dart DTOs
│   ├── core/                    ← Shared utilities
│   ├── theme/                   ← colors.dart, spacing.dart (design tokens)
│   ├── config/                  ← Endpoints, env switches
│   └── utils/                   ← Generic helpers
├── test/
├── pubspec.yaml
└── analysis_options.yaml
```

## Step 3: Production Code vs. Prototype Mocks

Today there is no separate "playground" project (unlike the source codebase this skill set was lifted from). Visual prototypes for new concepts live alongside the production code in:

- `lib/screens/<feature>/_prototypes/` (create when needed) — isolated, hardcoded mocks for review before architect work begins
- The `mocker` skill defines the convention; it does NOT bring a parallel project

Production code (everything else under `lib/`):

- Never hardcode user-visible values
- Strict layer separation (presentation → bloc → service)
- Tokens for every color / spacing / typography choice

## Step 4: Learn the UI Pipeline

The frontend pipeline is divided across specialized agent skills. Familiarize yourself with all of them before contributing:

1. **`/concept` & `/concept-review`** — Strategic concept planning. NO code.
2. **`/mocker`** — Optional. Visual prototype next to the affected screen, used to sanity-check a concept.
3. **`/architect` & `/plan-review`** — Widget tree, ASCII layout, BLoC wiring, responsive breakpoints, test plan. **Desktop-first, Web-mandatory.**
4. **`/builder`** — Implements the plan exactly.
5. **`/auditor` & `/audit-review`** — Zero-tolerance compliance check against the plan.

> [!IMPORTANT]
> **No plan = No code.** A builder MUST have an approved implementation plan before writing a single line.

## Step 5: Coding Conventions (Non-Negotiable)

- **`const` everywhere**: mark constructors and instances `const` when possible — minimizes rebuilds.
- **Smart / dumb split**: one smart widget per screen consumes BLoC state. All children receive data via constructor.
- **No business logic in `build()`**: API calls, computations, side effects belong in BLoC event handlers.
- **Immutable state with `copyWith()`** + `Equatable` for value comparison.
- **ASCII diagrams only** in plans — Mermaid is forbidden.
- **Design tokens** for every color (`lib/theme/colors.dart`) and spacing (`lib/theme/spacing.dart`). No magic numbers in widgets.
- **Material `Icons`** only — no third-party icon libraries without architect approval.
- **Relative paths** in documentation and code references.
- **Routing via `go_router`** — required for Web back/forward.
- **HTTP via `dio`**, real-time logs via **SSE** (`eventsource_client`).

## Step 6: Reuse Before Creating

Before designing or building a new widget, check existing reusable components:

```
twin2multicloud_flutter/lib/widgets/
twin2multicloud_flutter/lib/widgets/<feature>/
```

If a widget already covers your case (`StatCard`, `BrandedAppBar`, `DeploymentTerminal`, `TwinListItem`, `CodeViewerDialog`, …), reuse or extend it. **Never duplicate.**

## Step 7: Verify the Toolchain

```bash
cd twin2multicloud_flutter
flutter pub get
flutter analyze        # MUST be green before any change
flutter test           # widget + unit tests
flutter build web      # confirm Web build
flutter build linux    # or macos / windows
```

If `flutter analyze` reports anything, STOP. The build is the precondition for any work.

## Step 8: Backend Wiring Sanity Check

Before integration work, confirm the local stack is up:

```bash
docker ps
# Expect: optimizer @ 5003, deployer @ 5004, management api @ 5005 (when implemented)

curl -s http://localhost:5003/health
curl -s http://localhost:5004/health
curl -s http://localhost:5005/health
```

If the Management API is not yet implemented for the feature you're touching, raise it as a Feature Request before designing UI that depends on it (see `concept` for the FR convention).

## Pre-Implementation Checklist

1. Read `FRONTEND_ARCHITECTURE.md` and `integration_vision.md` end to end.
2. Read `_shared/references/flutter-guardrails.md`.
3. Read the SKILL.md of the agent role you're playing (`architect`, `builder`, …).
4. Inspect the `lib/` folder map above — locate where your work lives.
5. Search `lib/widgets/` for reusable components.
6. Verify Flutter analyzes / tests / builds cleanly.
7. Verify Docker stack is up if integration matters.

## Related Skills

- **onboarding** — Cross-project onboarding for the whole `master-thesis` repository
- **concept** — Strategic concept planning upstream
- **architect** — Implementation plan design
- **builder** — Feature implementation from plans
- **auditor** — Compliance verification
