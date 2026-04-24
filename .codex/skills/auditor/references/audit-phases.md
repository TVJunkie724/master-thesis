# Audit Phases — Complete Verification Checklists

## Phase 1: Plan Integrity Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| Approved implementation plan exists | Locate the plan artifact | ⬜ |
| Plan is complete (all 12 sections filled) | Review all sections | ⬜ |
| Plan was approved by `plan-review` (not a draft) | Check for approval confirmation | ⬜ |

**No approved plan = immediate rejection.**

## Phase 2: Structural Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| All files from the plan exist under `twin2multicloud_flutter/lib/` | File inspection | ⬜ |
| No unexpected files were created | Compare file list to plan; `git diff --name-only` | ⬜ |
| File names match snake_case (file) / PascalCase (widget) conventions | Code inspection | ⬜ |
| Folder placement matches layer rules (`bloc/`, `screens/`, `widgets/`, `services/`, …) | Code inspection | ⬜ |
| Import ordering (`dart:*` → `package:*` → relative) | Code inspection | ⬜ |
| One public widget per file (where applicable) | Code inspection | ⬜ |

## Phase 3: Widget Tree Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| Widget hierarchy matches the plan's tree | Code inspection of build methods | ⬜ |
| All `[NEW]` widgets exist with correct names | Code inspection | ⬜ |
| All `[MODIFY]` widgets have the specified changes | Diff inspection | ⬜ |
| All `[REUSE]` widgets actually reused (no silent duplication) | Grep for the reused widget's name | ⬜ |
| Constructor parameters match the plan (name, type, required, default) | Code inspection | ⬜ |
| Smart / dumb widget split is respected (only smart widgets read BLoC state) | Code inspection | ⬜ |
| `const` constructors used where possible | Code inspection / `flutter analyze` hint | ⬜ |
| Keys provided for list items and re-orderable widgets | Code inspection | ⬜ |

## Phase 4: Visual & Layout Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| Layout matches the plan's ASCII diagram (Desktop + Web variants) | Visual inspection or code review | ⬜ |
| Spacing values match the plan, sourced from `lib/theme/spacing.dart` | Code inspection against spec | ⬜ |
| Color values match the plan, sourced from `lib/theme/colors.dart` | Code inspection | ⬜ |
| Typography matches the plan, sourced from `ThemeData.textTheme` | Code inspection | ⬜ |
| No hardcoded dimensions | `Grep` for magic numbers in the modified files | ⬜ |
| No hardcoded colors | `Grep` for `Color(0x` and `Colors.` outside the theme file | ⬜ |
| No inline `TextStyle` constructors that don't override a theme style | `Grep` for `TextStyle(` outside the theme file | ⬜ |
| No hardcoded user-facing strings outside per-screen constant files | Code inspection | ⬜ |

## Phase 5: Responsive Behavior Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| All breakpoints from the plan are implemented (`LayoutBuilder` / `MediaQuery`) | Code inspection | ⬜ |
| Layout changes at each breakpoint match the plan | Code inspection / visual test | ⬜ |
| No content overflow at any breakpoint (Web included) | Visual inspection or `flutter test` golden | ⬜ |
| Transitions between breakpoints are smooth (if specified) | Visual inspection | ⬜ |

## Phase 6: State Management (BLoC) Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| BLoC ownership matches the plan (which BLoC owns which state) | Code inspection of `BlocProvider` placements | ⬜ |
| All events from the plan exist with the specified payload | `Grep` for event class names | ⬜ |
| All states from the plan exist with the specified `copyWith` shape | Code inspection | ⬜ |
| Data flow direction matches the plan (UI → Event → BLoC → Service → API → State → UI) | Trace data through code | ⬜ |
| All async states handled: loading | Code inspection | ⬜ |
| All async states handled: error | Code inspection | ⬜ |
| All async states handled: empty | Code inspection | ⬜ |
| No state access in "dumb" widgets | Code inspection (`context.read` / `BlocBuilder` only in smart widget) | ⬜ |
| Immutable state with `copyWith()` and `Equatable` | Code inspection | ⬜ |
| Subscriptions and controllers properly disposed in `close()` | Code inspection | ⬜ |
| Side effects match the plan (snackbar, navigation, SSE subscription) | Code inspection | ⬜ |

## Phase 7: Interaction & Animation Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| Hover effects match the plan | Code inspection | ⬜ |
| Focus states match the plan | Code inspection | ⬜ |
| Press / tap effects match the plan | Code inspection | ⬜ |
| Animations have correct duration | Code inspection against spec | ⬜ |
| Animations have correct curve | Code inspection against spec | ⬜ |
| Animations have correct trigger | Code inspection against spec | ⬜ |

## Phase 8: Accessibility Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| `Semantics` labels present on every interactive element | Code inspection | ⬜ |
| Focus traversal order matches the plan | Code inspection / widget test | ⬜ |
| Contrast ratios meet requirements (≥ 4.5:1 body, ≥ 3:1 large) | Inspection against `lib/theme/colors.dart` | ⬜ |
| Screen reader compatibility (`Semantics`, no decorative widgets blocking focus) | Code inspection | ⬜ |
| Keyboard shortcuts wired (Esc to close dialogs, Enter to submit, etc.) | Code inspection | ⬜ |

## Phase 9: Integration Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| Management API endpoints consumed match the plan (method + path) | Code inspection | ⬜ |
| Request / response shapes match the API contract | Code + backend cross-check | ⬜ |
| SSE subscription wired and disposed correctly | Code inspection | ⬜ |
| Error responses (4xx / 5xx) handled gracefully and surfaced to the user | Code inspection | ⬜ |
| `go_router` routes registered as planned, with auth guards if specified | Code inspection of router config | ⬜ |
| **No direct calls to Optimizer (5003) or Deployer (5004)** | `Grep` for `:5003`, `:5004`, `optimizer`, `deployer.api` literals | ⬜ |

## Phase 10: Code Quality Verification

| Item | Verification Method | Status |
|------|---------------------|--------|
| `flutter analyze` passes with zero issues | Run analysis | ⬜ |
| `flutter test` passes (unit + widget) | Run tests | ⬜ |
| `flutter build web` succeeds | Run build | ⬜ |
| `flutter build <desktop>` succeeds | Run build | ⬜ |
| No `print()` statements in committed code | `Grep` for `print(` | ⬜ |
| No `TODO` / `FIXME` / `HACK` comments | `Grep` for those tokens | ⬜ |
| No commented-out code | Code inspection / `git diff` | ⬜ |
| Build methods are focused (< ~30 lines) | Code inspection | ⬜ |
| No business logic inside `build()` methods | Code inspection | ⬜ |
| No `Cupertino*` widgets / mobile-only packages added | `Grep` for `Cupertino`, check `pubspec.yaml` | ⬜ |

## Phase 11: Plan Completeness Cross-Check

This is the most critical phase. Go through the plan's **Definition of Done** checklist item by item:

| Item | Verification Method | Status |
|------|---------------------|--------|
| Every DoD item from the plan verified | Line-by-line cross-check | ⬜ |
| No items from the plan were skipped | Systematic comparison | ⬜ |
| No items were added that aren't in the plan | Systematic comparison; `git diff` review | ⬜ |
| Commit messages all carry `[AI-MMDD-xxxx] type: …` | `git log --oneline` review | ⬜ |
| `.ai-session.json` `files_modified` matches actual git diff | Compare both | ⬜ |
