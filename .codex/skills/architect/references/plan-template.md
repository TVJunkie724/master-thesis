# Implementation Plan Template

Every implementation plan produced by the `architect` skill MUST follow this 12-section structure.

```markdown
# Implementation Plan: [Feature Name]

## 0. Git Branch
- **Branch name:** `ai/dev/<feature-slug>`  (sub-branch of `ai/dev`, or `ai/dev` itself if trivial)
- **Base branch:** `ai/dev`
- **Merge strategy:** Merge commit (NO rebase). The user merges `ai/dev → master` separately.
- **Session ID:** `AI-MMDD-xxxx` (from `.ai-session.json`) — used as the commit prefix.

## 1. Summary
What this UI feature accomplishes and why it matters for Twin2MultiCloud.
Reference the relevant section of `FRONTEND_ARCHITECTURE.md` (e.g. "Dashboard stat cards", "Wizard Step 3 deployer config").

## 2. Visual Layout (ASCII)
Spatial structure of all panels, sections, and elements.
Designed from scratch for the specific requirements — no templates, no defaults.
Include the layout for **Desktop** AND **Web** if they differ.

## 3. Widget Tree
Parent-child hierarchy of all widgets with exact types and file locations.
Mark each node `[NEW]`, `[MODIFY]`, or `[REUSE]`.

## 4. Component Specifications
For each `[NEW]` or `[MODIFY]` component:
- File path under `twin2multicloud_flutter/lib/...`
- Constructor parameters (table: name, type, required, default)
- Stateless vs StatefulWidget vs `BlocBuilder` / `BlocListener` consumer
- Widget skeleton (Dart pseudocode — not the full implementation)
- Visual specs (dimensions, spacing **from `lib/theme/spacing.dart`**, colors **from `lib/theme/colors.dart`**, typography **from `ThemeData`**)

## 5. Responsive Behavior
Breakpoints table with exact layout changes per breakpoint.
Desktop is primary, but EVERY element must have a defined Web layout.
If a component cannot reasonably work on a narrow viewport, document why explicitly.

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Wide Desktop | ≥ 1440px | … |
| Narrow Desktop / Web | 800–1439px | … |
| Compact Web | < 800px | … (or "out of scope, show notice") |

## 6. State Flow (BLoC)
- Which BLoC (existing or new) owns which state
- Events the BLoC accepts (with payload)
- States the BLoC emits (with `copyWith()` shape)
- Side effects (HTTP call to Management API, SSE subscription, navigation push) and their triggers
- ASCII data-flow diagram (UI → Event → BLoC → Service → Management API → response → State → UI)

## 7. Design Tokens
- New colors / spacing values / typography styles required (added to `lib/theme/` BEFORE the widget code)
- Existing tokens this plan reuses

## 8. Interactions & Animations
- Hover, focus, press, drag behaviors
- Transitions with duration, curve, trigger
- Loading states (`CircularProgressIndicator` placement, skeleton shimmer, …)
- Error states (inline message, snackbar, dialog — pick one and justify)
- Empty states (illustration / message / call-to-action)

## 9. Accessibility
- Focus traversal order (Tab order)
- Semantic labels for every interactive element
- Contrast ratios (≥ 4.5:1 for body, ≥ 3:1 for large text)
- Keyboard shortcuts where relevant (Esc to close dialog, Enter to submit, …)

## 10. Integration Points
Management API endpoints consumed:

| Method | Path | Request body | Response shape | Notes |
|--------|------|--------------|----------------|-------|
| GET | `/twins` | – | `List<TwinSummary>` | Used for Dashboard list |
| POST | `/twins/{id}/deploy` | – | `{deployment_id}` | Triggers SSE stream |
| GET (SSE) | `/stream/deploy/{twin_id}` | – | `text/event-stream` | Log lines |

Plus `go_router` route registrations:

| Route | Screen | Guards (auth, etc.) |
|-------|--------|---------------------|

**Forbidden**: any direct call to ports 5003 / 5004. Management API only.

## 11. Test Plan
For every testable component / behavior, specify concrete test cases.
See `test-plan-requirements.md` for minimum requirements (≥ 2 happy, ≥ 2 unhappy, ≥ 5 edge — or justified deviation).

Test types in scope:
- **Unit** — pure Dart (`flutter test`)
- **Widget** — `WidgetTester` (`flutter test`)
- **Integration** — against the running Docker stack (`flutter test integration_test/`)

E2E that would deploy real cloud resources is **forbidden by default**.

## 12. Definition of Done
Checklist for the builder to verify completion. Suggested baseline:

- [ ] All `[NEW]` / `[MODIFY]` components implemented as specified
- [ ] `flutter analyze` — zero issues
- [ ] `flutter test` — all green
- [ ] `flutter build web` — succeeds
- [ ] `flutter build linux` (or active Desktop target) — succeeds
- [ ] No hardcoded colors / spacings / strings
- [ ] BLoC events and states match Section 6
- [ ] All async branches handle loading / error / empty
- [ ] Accessibility checklist (Section 9) verified
- [ ] No direct calls to Optimizer / Deployer
- [ ] Commit history follows `[AI-MMDD-xxxx] type: …` format
- [ ] Ready for `auditor`
```
