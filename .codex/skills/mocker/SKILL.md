---
name: mocker
description: >
  Use this project-specific Twin2MultiCloud skill when the user asks to "create mock", "UI mock", "mock the concept", "build a mock", or "create a visual mock" for a Twin2MultiCloud frontend concept. Use for creating isolated visual prototypes inside `twin2multicloud_flutter` to validate a concept before the architect produces an implementation plan.
metadata:
  project: master-thesis
  source: .claude/mocker
---


# Mocker — Visual Prototypes

Read and apply all guardrails from `references/flutter-guardrails.md` before any work.

The Twin2MultiCloud project does NOT ship a separate "playground" project. Visual prototypes for new concepts live alongside the production code under a clearly marked prototype folder, and they are removed (or promoted) once the architect produces the real plan.

## Where Mocks Live

```
twin2multicloud_flutter/lib/
├── _prototypes/                       ← Created when first needed
│   ├── PROTOTYPE_CATALOG.md           ← Index of active prototypes
│   ├── prototype_NN_short_name/
│   │   ├── prototype_NN_screen.dart   ← The prototype screen
│   │   ├── prototype_NN_state.dart    ← Optional local BLoC for interaction
│   │   └── widgets/                   ← Local-only widgets for this prototype
│   └── ...
└── (rest of production lib/)
```

Each prototype is registered behind a build-time / debug-only route (e.g. `/prototypes/<NN>`) — never reachable from the production navigation graph. The catalog lists every active prototype with its purpose and target concept document.

## Workflow

### Step 1: Read the Concept
- Read the concept document and every dependency it references
- Read the relevant existing files (`lib/theme/`, neighbouring screens, existing widgets in `lib/widgets/`)

### Step 2: Reuse Matrix (MANDATORY)
1. Read `lib/widgets/` — list candidate reusable widgets
2. Build a reuse table in the prototype's plan:

   | Widget | Use? | Why (not) |
   |--------|------|-----------|
   | `BrandedAppBar` | ✅ / ❌ | … |
   | `StatCard` | ✅ / ❌ | … |
   | `DeploymentTerminal` | ✅ / ❌ | … |

3. Document concrete usage per panel / screen
4. Confirm with the user: reuse plan or blank prototype?

### Step 3: Plan the Mock
- Exact scope: which layout, which widgets, which styles, which animations, which interactions
- No over-engineering — just enough to validate the concept

### Step 4: ASCII + Widget Tree
- ASCII layout for the prototype
- ASCII widget-tree diagram

### Step 5: Helper Action Bar (only for interaction prototypes)
A second app-bar row under the back button with prototype-only actions:

```
┌──────────────────────────────────────────────┐
│  ← Back   Prototype NN: short name           │  ← AppBar
├──────────────────────────────────────────────┤
│  [Add row] [Remove row] [Toggle overflow]    │  ← Helper bar
├──────────────────────────────────────────────┤
│        (Prototype content)                    │
└──────────────────────────────────────────────┘
```

### Step 6: Implement
- Presentation layer only (widgets in `lib/_prototypes/prototype_NN_short_name/widgets/`)
- Optional local BLoC if the prototype needs interaction:
  ```
  prototype_NN_short_name/
  ├── prototype_NN_screen.dart    ← Presentation (smart widget here)
  ├── prototype_NN_bloc.dart      ← Local state
  ├── prototype_NN_event.dart
  ├── prototype_NN_state.dart
  └── widgets/                    ← Local widgets
  ```

### Step 7: Register the Route
- Add a debug-only route in `app.dart` (or a dedicated `_prototypes_router.dart` imported only in debug builds) reaching the new prototype screen
- The route MUST NOT be linked from any production screen

### Step 8: Update PROTOTYPE_CATALOG.md
- Add a row with: NN, short name, target concept document, what it tests, which production widgets it reuses, status (`active` / `promoted` / `removed`)

### Step 9: Cleanup Plan
- Note in the prototype's header who is responsible for removal once the architect produces the real plan, or for promotion (moving widgets into `lib/widgets/`)

## Rules

- **No services layer** — no real Management API calls; use hardcoded mock data
- **Prototypes are isolated** — no prototype may import another prototype
- **No imports from production code into a prototype other than `lib/theme/` and reusable widgets in `lib/widgets/`**
- **Material `Icons`** only
- **Hardcoded values OK** — prototypes are explicitly outside the design-token discipline IF you put them in `_prototypes/`. If a value is worth keeping, it belongs in `lib/theme/` first.
- **No tests for prototypes** — prototypes are themselves the visual test
- **Never commit a prototype to `master`** — they live on `ai/dev` until promoted or removed
