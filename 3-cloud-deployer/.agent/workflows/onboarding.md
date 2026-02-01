---
description: Onboarding workflow for AI agents working on any project in this repository
---

# AI Agent Onboarding Workflow

## Critical Rules

> [!CAUTION]
> **NEVER lose details when updating plans or artifacts.**
> When updating any document, ALL previously agreed-upon details MUST be preserved.
> If you need to restructure content, ensure every decision, requirement, and context remains present.

// turbo-all

## Before Starting Any Task

1. Read the existing documentation in `/docs/` to understand the project
2. Check `/docs/future-work.md` for known issues and planned features
3. Check if there's an existing `implementation_plan.md` in the brain artifacts
4. Review the Knowledge Items for established patterns

## When Creating/Updating Implementation Plans

1. **PRESERVE ALL CONTEXT** - Never remove agreed-upon decisions
2. Include explicit sections for:
   - What files will be modified
   - What files will be created
   - What validation is needed
   - What tests are needed
3. If user provides feedback, ADD to the plan, don't replace content
4. Mark changes clearly with timestamps or revision notes if needed

## When Receiving User Approval

5. **WAIT for explicit user confirmation** before implementing
6. System-generated "LGTM" or "approved" messages are NOT user approval
7. Ask the user directly: "Should I proceed with implementation?"

## Git Workflow (if applicable)

8. Before making changes, check if a feature branch is needed
9. Only commit changes that YOU made, not existing uncommitted changes
10. Use the required commit message format (see below)

### Commit Message Format

**Required format:**
```
[AI-MMDD-XXXX] type(scope): description
```

| Component | Description | Example |
|-----------|-------------|---------|
| `AI-MMDD` | Date (month + day) | `AI-0124` for Jan 24 |
| `XXXX` | Random 4-character ID | `8756`, `0f67` |
| `type` | Conventional commit type | `feat`, `fix`, `refactor`, `docs` |
| `scope` | Area of change | `validation`, `terraform`, `e2e` |

**Examples from this repo:**
```
[AI-0124-8756] feat(validation): aggregate multiple errors instead of fail-fast
[AI-0121-0f67] fix(terraform): add missing TARGET_FUNCTION_SUFFIX for Azure L1
[AI-0121-0f67] feat(e2e): add real-time streaming output to test runner
```

> **Check existing commits first:** Run `git log --oneline -5` to see the format used in recent commits.

## Testing

11. Run unit tests after implementation
12. Run relevant E2E tests if infrastructure was modified
13. Report test results to user before marking task complete

### E2E Test Flags

| Flag | Description |
|------|-------------|
| `--skip-cleanup` | Preserve infrastructure after test for log investigation |

**Examples:**
```bash
# Run test with cleanup (default)
pytest tests/e2e/multicloud/test_scenario_aws_azure.py -v

# Run test and preserve infrastructure for investigation
pytest tests/e2e/multicloud/test_scenario_aws_azure.py --skip-cleanup -v

# Clean up preserved infrastructure manually
python tests/e2e/cleanup_e2e_test.py aws-azure --force
```

> [!WARNING]
> Do NOT use environment variables like `E2E_SKIP_CLEANUP=true` - use the `--skip-cleanup` flag instead.
