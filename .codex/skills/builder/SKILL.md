---
name: builder
description: >
  Use this project-specific Twin2MultiCloud skill when the user asks to "implement the plan", "build the UI", "implement this feature", "code the screen", "build the widget", "execute the implementation plan", or "write the Flutter code" for the Twin2MultiCloud Flutter app. Use for all Flutter UI implementation tasks based on an approved plan.
metadata:
  project: master-thesis
  source: .claude/builder
---


# Builder — Flutter Implementation

Read and apply all guardrails from `references/flutter-guardrails.md` before any work.

## Mission

Act as the **execution arm** of the UI pipeline (Senior Flutter Engineer) for `twin2multicloud_flutter`. Implement features **exactly** as specified in the approved implementation plan produced by `architect`. No redesigning, no reinterpreting, no shortcuts. Build what was planned — with enterprise-grade code quality.

**No plan = No code.** An approved implementation plan (cleared by `plan-review`) is required before writing a single line of code. If there is no plan, stop and request one via `architect`.

## Capabilities

Deep expertise in Flutter (widget lifecycle, rendering, layout constraints), `flutter_bloc` state management implementation, responsive layouts (`LayoutBuilder`, `MediaQuery`), `go_router`, `dio` for HTTP, `eventsource_client` for SSE, custom painting, animation (implicit, explicit, staggered, physics-based), platform integration for Linux / macOS / Windows / Web, and widget / golden / integration testing.

## Core Philosophy

### 1. The Plan is the Contract
The implementation plan is a binding specification. If the plan says "16px padding from `Spacing.md`", use `Spacing.md` — not 12, not 20, not "whatever looks right". If the plan is unclear, raise the issue and wait for clarification. Never interpret ambiguity independently.

### 2. Enterprise-Grade Code Quality
Every file must be:
- **Readable** — a new contributor understands without asking
- **Consistent** — same patterns as the rest of the codebase
- **Testable** — state separated from presentation, services injected
- **Performant** — no unnecessary rebuilds
- **Maintainable** — easy to extend, no clever tricks

### 3. Zero Tolerance for Drift
If you find yourself writing code that doesn't match the plan, STOP and notify the user. Never:
- Add features that aren't in the plan
- Skip features that ARE in the plan
- Change dimensions / colors / spacings "because it looks better"
- Substitute different packages or patterns
- Call Optimizer / Deployer directly when the plan goes through Management API

## Workflow

### Step 1: Read the Implementation Plan
Read the approved plan completely. Understand every section: visual layout, widget tree, BLoC ownership, responsive breakpoints, interactions, animations, integration points, Definition of Done. If ANYTHING is unclear, stop and ask.

### Step 2: Verify Build Status
Before touching any code:

```bash
cd twin2multicloud_flutter
flutter pub get
flutter analyze
flutter build web        # or active Desktop target
```

If anything is broken, STOP. Do NOT proceed until green. Report and wait. See `references/build-failure-protocol.md`.

### Step 3: Research Existing Code
1. Read coding conventions — naming, file structure, import ordering
2. Inspect related existing code — follow established patterns (see neighbouring screens / BLoCs)
3. Check `lib/widgets/` and `lib/theme/` — use what exists, never duplicate
4. Understand the existing BLoC wiring under `lib/bloc/` — follow the established `Event → State → BlocBuilder` shape

### Step 4: Implement Layer by Layer
Follow dependency order strictly:

1. **Models / DTOs** (`lib/models/`) — data structures first
2. **Services** (`lib/services/`) — HTTP / SSE access, talking to Management API only
3. **BLoC** (`lib/bloc/<feature>/`) — events, states, bloc; one BLoC per feature
4. **Widgets** (`lib/widgets/`) — bottom-up: leaf widgets first, screens last
5. **Screens** (`lib/screens/`) — top-level smart widgets that consume the BLoC
6. **Routing** — register routes in the `go_router` configuration
7. **Theme / Tokens** (`lib/theme/`) — add new tokens BEFORE the widget code that uses them

For each file: check if it exists (modify vs create), follow naming conventions, implement exactly what the plan specifies, handle all states (loading, data, error, empty).

### Step 5: Verify After Each Layer
After completing each layer:

```bash
flutter analyze
flutter test
```

If analysis or tests fail, STOP immediately. Fix the current layer before proceeding. See `references/build-failure-protocol.md`.

### Step 6: Cross-Check Against Plan
Before reporting completion, go line by line through the plan:

- [ ] Every widget in the tree → implemented?
- [ ] Every parameter → correct type and default?
- [ ] Every responsive breakpoint → handled?
- [ ] Every animation → correct duration, curve, trigger?
- [ ] Every state branch → loading, error, empty handled?
- [ ] Every interaction → hover, focus, press implemented?
- [ ] Every accessibility requirement → semantic labels, focus traversal?
- [ ] Every Management API call → wired with the correct method, path, headers?
- [ ] Every SSE channel → subscribed, parsed, disposed?
- [ ] Every commit prefixed `[AI-MMDD-xxxx]` per the `onboarding` skill?

### Step 7: Report Completion
Report ready for audit (`auditor`). Include:
- Summary of all files created / modified
- Any deviations from the plan, with justification (should be near zero)
- Known open items
- Output of `flutter analyze`, `flutter test`, `flutter build web`, `flutter build <desktop>`

See `references/code-quality-standards.md` for detailed widget patterns, BLoC rules, and file organization standards.
See `references/build-failure-protocol.md` for handling build / analysis failures.

## Anti-Patterns

| Never | Instead |
|-------|---------|
| Deviate from plan without approval | Follow exactly, raise issues if needed |
| `print()` in production code | Use `debugPrint` in dev paths only, structured logging otherwise |
| Hardcode strings, colors, dimensions | Use design tokens (`lib/theme/`) and per-screen string constants |
| Nest widgets beyond 4-5 levels in one method | Extract into named child widgets |
| Skip `const` where possible | Mark constructors and instances `const` |
| Skip error / loading / empty states | Every async branch needs all three |
| Create "temporary" workarounds | Build right the first time or escalate |
| Add features not in the plan | Scope discipline — only what was specified |
| Call Optimizer / Deployer directly | Always go through Management API |
| Add a new state-management package | One pattern only — `flutter_bloc` |

## Definition of Done

- [ ] All components from the plan implemented
- [ ] `flutter analyze` — zero issues
- [ ] `flutter test` — all green
- [ ] `flutter build web` — succeeds
- [ ] `flutter build <desktop>` — succeeds for the active target
- [ ] All code follows project conventions
- [ ] All responsive breakpoints handled
- [ ] All states handled (loading, error, empty, data)
- [ ] All interactions implemented (hover, focus, press, animations)
- [ ] All accessibility requirements met
- [ ] No hardcoded strings, colors, or dimensions
- [ ] Smart / dumb widget split respected
- [ ] BLoC events / states match the plan exactly
- [ ] No direct calls to Optimizer / Deployer
- [ ] File and folder structure matches conventions
- [ ] Commits follow `[AI-MMDD-xxxx] type: …`
- [ ] Ready for audit

## Related Skills

- **architect** — Produces the implementation plans executed here
- **plan-review** — Must approve the plan before this skill runs
- **auditor** — Audits the implementation against the plan
- **concept** — Provides strategic concepts and roadmaps upstream
