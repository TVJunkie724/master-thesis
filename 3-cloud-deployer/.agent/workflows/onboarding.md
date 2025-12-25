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
10. Use descriptive commit messages

## Testing

11. Run unit tests after implementation
12. Run relevant E2E tests if infrastructure was modified
13. Report test results to user before marking task complete
