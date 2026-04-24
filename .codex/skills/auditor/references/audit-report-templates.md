# Audit Report Templates

## If APPROVED

```markdown
## AUDIT PASSED

**Feature:** [Feature Name]
**Date:** [YYYY-MM-DD]
**Plan:** [Repo-relative path to the implementation plan]
**Session:** AI-MMDD-xxxx (from `.ai-session.json`)
**Branch:** ai/dev[/<feature-slug>]

### Verification Summary

| Phase | Result |
|-------|--------|
| Plan Integrity | Verified |
| Structure | Compliant |
| Widget Tree | Matches plan |
| Visual & Layout | Matches plan (no hardcoded values) |
| Responsive | All breakpoints (Desktop + Web) |
| State (BLoC) | Correct ownership, events, states, side effects |
| Interactions | All implemented |
| Accessibility | Compliant |
| Integration | Wired through Management API only |
| Code Quality | `flutter analyze` clean, tests green, builds succeed |
| Plan Cross-Check | 100 % coverage |

**APPROVED FOR HANDOFF**
```

## If REJECTED

```markdown
## AUDIT FAILED

**Feature:** [Feature Name]
**Date:** [YYYY-MM-DD]
**Plan:** [Repo-relative path to the implementation plan]
**Session:** AI-MMDD-xxxx
**Branch:** ai/dev[/<feature-slug>]

### Failed Items

| Phase | Item | Evidence | Required Fix |
|-------|------|----------|--------------|
| 4 | Card padding 12px (plan said `Spacing.md` = 16px) | `lib/widgets/dashboard/stat_card.dart:42` | Replace `12` with `Spacing.md` |
| 6 | `WizardBloc` does not handle `WizardSubmitted` event | `lib/bloc/wizard/wizard_bloc.dart` — no `on<WizardSubmitted>` | Add the handler with the loading→data→error transitions specified in plan §6 |
| 9 | `LoginScreen` calls `http://localhost:5005/auth/google` from `dio` instance directly | `lib/screens/login_screen.dart:88` | Move into `AuthService.signInWithGoogle()` |

### Severity Summary

- Critical (blocks handoff): X items
- Major (must fix): Y items
- Minor (should fix): Z items

### Next Steps

1. Builder must fix all items (starting with Critical)
2. Re-audit after fixes are applied
3. No partial re-audits — full audit runs again

**REJECTED — REQUIRES REMEDIATION**
```

## Notes

- Always include the **session ID** so the user can `git log --grep="AI-MMDD-xxxx"` to find related commits.
- Always include **repo-relative file paths with line numbers** as evidence — never paraphrase ("somewhere in the wizard").
- Never include hypothetical fixes ("might also want to refactor X"). The audit verifies the plan; improvements belong in a new architect cycle.
