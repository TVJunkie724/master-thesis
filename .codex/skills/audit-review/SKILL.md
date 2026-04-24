---
name: audit-review
description: >
  Use this project-specific Twin2MultiCloud skill when the user asks to "audit review", "review the audit", "compliance review", "review against plan", "audit the build", or "review the implementation against the plan". Use for zero-tolerance compliance verification of completed implementations in `twin2multicloud_flutter` against the approved plan.
metadata:
  project: master-thesis
  source: .claude/audit-review
---


# Audit Review — Zero-Tolerance Compliance Verification

Read and apply all guardrails from `references/flutter-guardrails.md` before any work.

## Mandatory Criteria

Every implementation MUST be audited against the approved plan and ALL the following criteria. **No criterion may be skipped.**

### General Criteria

1. **Plan fidelity** — Read the concept and the approved implementation plan exactly and deeply. Every deviation is a finding.
2. **Unambiguity** — Is the implementation clear and maintainable?
3. **No over-engineering** — Watch for code that goes beyond the plan's scope. Only what the plan specifies belongs there.
4. **No side effects** — Explicitly check that the implementation does NOT break or negatively affect anything elsewhere (other screens, shared widgets, BLoCs, theme, routing).
5. **Datatype compatibility** — Verify datatype compatibility at every API boundary (Dart models ↔ Management API request / response shapes).
6. **Documentation conformance** — The work is 100 % conformant to the documentation hierarchy in `../concept/references/pillar-organization.md` and the standards in `../concept/references/documentation-standards.md`.
7. **Everything done** — Every item in the plan is complete. It is mandatory that everything is done exactly as the plan specifies.

### UI-Specific Criteria

8. **ASCII layout** — Does the rendered UI match the plan's ASCII layout (Desktop AND Web)?
9. **Widget tree** — Does the actual widget tree match the plan?
10. **No hardcoded tokens** — No hardcoded values (colors, spacing, text styles, magic numbers). Everything pulls from `lib/theme/`.
11. **Material `Icons`** — All icons sourced from Material `Icons`. No third-party icon library introduced.
12. **Reuse honored** — Every `[REUSE]` widget in the plan is actually reused — no silent duplication.
13. **BLoC separation** — Strict separation of presentation ↔ state ↔ services. No widget calling `dio` directly. No BLoC owning widgets.

### Test Criteria

14. **Hard assertions** — Tests have hard assertions. They do NOT pass silently. They verify that values exactly match expectations.
15. **Test coverage** — The test phase is fully implemented. All planned tests exist and run green (`flutter test` and, where applicable, `flutter test integration_test/`).
16. **Real Management API only** — Integration / E2E tests use the real Management API in Docker. NO direct database access, NO mocked HTTP at integration level.
17. **No real-cloud E2E** — No tests deploying real cloud resources unless the user explicitly authorized them.

### Documentation & DoD

18. **Documentation phase done** — The documentation phase from the plan is complete. Documentation lives under `twin2multicloud_flutter/docs/<pillar>/phases/` (and an `implementation/` subfolder where the plan specified one).
19. **DoD satisfied** — The Definition of Done is fully met. Every single checkbox.

## Review Perspectives

Audit from **both** perspectives:

1. **Architect** — Is the implementation technically correct, complete, and consistent with the plan?
2. **Builder** — Was everything implemented 1:1? Any silent deviations?

## Process

1. Read the approved implementation plan in full.
2. Read the underlying concept document in full.
3. Read all changed files (source + tests). Use `git diff master...HEAD` to see the complete diff.
4. Check against ALL criteria above.
5. Run all verification commands from the plan (`flutter analyze`, `flutter test`, `flutter build web`, `flutter build <desktop>`, plus ``rg` checks listed in `../auditor/references/audit-phases.md`).
6. Produce the audit report with findings.
7. **Repeat the dual-perspective review until ZERO gaps remain.**
8. Present the result to the user.
9. On findings: status = ❌ REJECTED with concrete remediation steps.
10. On 0 findings: status = ✅ APPROVED FOR HANDOFF.

## Output Format

For **each finding**:

| Field | Content |
|-------|---------|
| **File** | Exact repo-relative path + line number(s) |
| **Problem** | What deviates from the plan or is missing |
| **Severity** | 🔴 Critical / 🟡 Major / 🟠 Minor |
| **Evidence** | Concrete proof (`rg` output, test result, code snippet, `flutter analyze` line) |
| **Fix** | Exact correction proposal |
