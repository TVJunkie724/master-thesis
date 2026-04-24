---
name: plan-review
description: >
  Use this project-specific Twin2MultiCloud skill when the user asks to "review plan", "plan review", "review the implementation plan", "check the plan", "validate the plan", or "plan quality check". Use for reviewing implementation plans against mandatory quality criteria from architect + builder perspectives.
metadata:
  project: master-thesis
  source: .claude/plan-review
---


# Plan Review — Mandatory Quality Criteria

Read and apply all guardrails from `references/flutter-guardrails.md` before any work.

## Mandatory Criteria

Every implementation plan MUST be checked against ALL the following criteria. **No criterion may be skipped.**

### General Criteria

1. **Deep concept understanding** — Read the underlying concept fully and carefully. The plan must faithfully reflect the concept; deviations are findings.
2. **Unambiguous** — The plan must be so clear that no agent ever needs to ask a clarifying question.
3. **No over-engineering** — Only what the phase demands. No speculative scaffolding.
4. **No side effects** — Explicitly check that the plan doesn't break or negatively affect anything outside its declared scope (other screens, shared widgets, BLoCs, theme).
5. **Datatype compatibility** — Verify datatype compatibility at every API boundary (Management API request / response shapes match the Dart models the plan introduces).
6. **Documentation conformance** — The plan is 100 % conformant with the documentation hierarchy described in `../concept/references/pillar-organization.md` and the standards in `../concept/references/documentation-standards.md`.
7. **Mandatory hints** — Every step in the plan is marked as required ("must be done", "do not skip"). Builders must understand that every checkbox in the Definition of Done is binding.

### UI-Specific Criteria

8. **ASCII layout** — A complete ASCII layout exists for every screen / panel the plan introduces or modifies (Desktop AND Web variants where they differ).
9. **Widget tree ASCII** — Every widget tree is fully drawn, parent → child, with `[NEW]` / `[MODIFY]` / `[REUSE]` markers.
10. **No hardcoded tokens** — No magic numbers, no inline color literals, no inline `TextStyle` constructors. All values pull from `lib/theme/`.
11. **Reuse before new** — For every proposed new widget, the plan justifies why no existing widget in `lib/widgets/` could be reused or extended.
12. **Material `Icons` only** — No third-party icon library introduced silently.
13. **BLoC separation** — Clear separation of presentation (widget) ↔ state (BLoC) ↔ services (HTTP / SSE). No widget calling `dio` directly. No BLoC owning Flutter widgets.
14. **Management API only** — Every backend interaction is documented as going through the Management API (port 5005). Direct calls to Optimizer (5003) or Deployer (5004) are findings.

### Test Criteria

15. **Real Management API in integration tests** — All integration tests hit the live Management API in Docker. No mocking the HTTP client at integration level. Mocks exist only at the unit level (BLoC isolated from its services).
16. **Hard assertions** — Tests must NOT pass silently. Every test verifies real values match expectations (see `../architect/references/test-plan-requirements.md`).
17. **Comprehensive test phase** — The plan describes the test phase end-to-end: which `flutter test`, which `flutter test integration_test/`, which Docker prep (`docker compose up -d`), how to bring services down. Verify against the conventions in the `onboarding` skill.
18. **No real cloud E2E** — The plan does NOT schedule E2E tests that deploy real cloud resources. Such tests are forbidden by default and only run on explicit user instruction (see `onboarding`).

### Documentation & DoD

19. **Documentation phase** — The plan includes an explicit documentation phase. Where appropriate, results land under `twin2multicloud_flutter/docs/<pillar>/phases/` and any new component gets a short reference doc in an `implementation/` subfolder.
20. **Exact Definition of Done** — The plan ends with a concrete, verifiable Definition of Done checklist (see `../architect/references/plan-template.md` Section 12).

## Review Perspectives

Review the plan from **both** perspectives:

1. **Architect** — Is the plan technically correct, complete, and internally consistent?
2. **Builder** — Can a builder implement the plan 1:1 without follow-up questions?

## Process

1. Read the underlying concept document fully and carefully.
2. Read all referenced documents (concepts, roadmaps, test strategy notes, `FRONTEND_ARCHITECTURE.md`, `integration_vision.md`).
3. Check the plan against ALL criteria above.
4. Apply trivial corrections immediately.
5. Surface decisions only when user input is required.
6. Confirm 100 % conformance to the documentation hierarchy.
7. Consider context around the change and the implications of every edit.
8. **Repeat the dual-perspective review until ZERO gaps remain.**
9. Present the result to the user.
10. Wait for explicit approval with the keyword **"Approved"** (or **"Genehmigt"**) before unblocking the builder.
11. Apply changes carefully and conservatively — nothing already approved may regress, nothing already specified may be lost.
