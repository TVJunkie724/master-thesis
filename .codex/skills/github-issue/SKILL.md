---
name: github-issue
description: >
  Use this project-specific Twin2MultiCloud skill when the user asks to create,
  classify, triage, update, close, label, milestone, or link GitHub Issues for
  the master-thesis repository, including roadmap tasks, architecture debt,
  credential/security work, Flutter/backend/deployer/optimizer handoff issues,
  future-work migration, TODO consolidation, and commit issue references.
metadata:
  project: master-thesis
  source: adapted-from-businesscompanion-github-issue
---

# GitHub Issue — Twin2MultiCloud / Master Thesis

GitHub Issues are the source of truth for actionable roadmap items, bugs,
architecture debt, future work, and implementation tasks in this repository.
Do not create new markdown TODO/Future-Work trackers for new actionable work.

## Required Repository

Default repo:

```bash
TVJunkie724/master-thesis
```

Before creating or editing issues, verify GitHub auth and repo access:

```bash
gh auth status
gh repo view TVJunkie724/master-thesis --json nameWithOwner,url
```

If GitHub API rate limits block issue lookup, do not invent issue references.
Continue with local commits if requested and state that issue linking was skipped
because lookup was unavailable.

## Issue Classification

Use existing repository labels. Prefer the project-specific label taxonomy below
over GitHub default labels when both could apply.

Every actionable issue must have:

- exactly one primary type label when possible: `type:task` or `type:roadmap`
- one priority label: `priority:p0`, `priority:p1`, `priority:p2`, or `priority:p3`
- at least one `area:*` label
- optional source label only for migrated historical items: `source:todo` or `source:future-work`
- `status:blocked` only when an external decision or explicit dependency blocks the issue

Default GitHub labels may still be used when they are clearer:

- `bug` for broken behavior, unsafe behavior, or regressions
- `documentation` for docs-only work
- `enhancement` for additive feature work
- `duplicate`, `invalid`, `question`, `wontfix` only during triage

## Area Labels

Use all that apply:

| Label | Use for |
|---|---|
| `area:credentials` | Credential SSOT, bootstrap, secrets, least privilege, cloud identity setup |
| `area:backend` | Management API, DB schema, repositories, services, orchestration |
| `area:flutter` | Flutter UI, Wizard, Twin views, API DTO consumption |
| `area:deployer` | `3-cloud-deployer`, Terraform generation/execution, deploy/destroy |
| `area:optimizer` | `2-twin2clouds`, pricing, region/capability contracts |
| `area:docs` | MkDocs/docs-site, README, setup guides, thesis/developer docs |
| `area:repo-hygiene` | Cleanup, ownership boundaries, generated/runtime artifacts |
| `area:observability` | Logs, SSE events, monitoring, error visibility |
| `area:thesis` | Thesis paper/documentation, evaluation, scientific framing |

## Priority Labels

| Label | Meaning |
|---|---|
| `priority:p0` | Critical architecture/security blocker or thesis-breaking risk |
| `priority:p1` | Important enterprise-readiness issue, major workflow blocker |
| `priority:p2` | Medium priority implementation or cleanup with clear value |
| `priority:p3` | Low priority polish, nice-to-have, or long-term follow-up |

## Milestones

Use one milestone matching the primary roadmap outcome:

| Milestone | Use for |
|---|---|
| `Phase 0 - Assessment & Backlog SSOT` | Assessment cleanup, backlog consolidation, issue migration |
| `Phase 1 - Deployer Canonical Path` | Canonical Deployer architecture, legacy endpoint/path removal |
| `Phase 2 - Deployer Contract Hardening` | Typed deploy/destroy contracts, path resolution, SSE/error contracts |
| `Phase 3 - Repository Hygiene & Docs Site` | Repository cleanup, docs-site, docs ownership |
| `Phase 4 - Runtime Credentials & Deployment State` | Credential SSOT, compose profiles, bootstrap, manifests, ephemeral workspaces |
| `Phase 5 - Backend Orchestrator Disentanglement` | Management API route/service/repository/client/orchestrator split |
| `Phase 6 - Brain Contracts & Pricing Reliability` | Optimizer contracts, pricing reliability, provider capabilities |
| `Phase 7 - Flutter Wizard & Twin Views` | Flutter Wizard, Twin views, DTOs, dev auth/runtime UI slices |
| `Later - Multi-Cloud Extensions & Thesis` | Long-term future work, thesis evaluation, non-blocking extensions |

If an issue spans multiple milestones, choose the milestone for the primary
outcome and express secondary ownership with labels.

## Issue Body Templates

### Architecture Debt / Task

```markdown
## Problem

## Target State

## Scope

## Non-Goals

## Acceptance Criteria
- [ ] ...

## Verification
- [ ] Exact command, audit, or smoke check
```

### Bug

```markdown
## Problem

## Evidence / Logs

## Expected Behavior

## Suspected Boundary

## Acceptance Criteria
- [ ] ...

## Verification
- [ ] Exact command or smoke check
```

### Roadmap / Future Work

```markdown
## Decision / Desired Capability

## Context

## Scope

## Non-Goals

## Acceptance Criteria
- [ ] ...

## Verification
- [ ] ...
```

Issues must be actionable without re-reading the chat. Include relevant file
paths, commands, API paths, plan links, and audit findings.

## Creation Workflow

1. Classify the work as bug, task, roadmap item, docs-only work, or enhancement.
2. Search for duplicates before creating anything:

```bash
gh issue list \
  --repo TVJunkie724/master-thesis \
  --state all \
  --search "credential ssot in:title,body" \
  --json number,title,state,labels,milestone,url
```

3. Select labels and milestone from this skill.
4. Write a concrete body in a temp file.
5. Create the issue:

```bash
gh issue create \
  --repo TVJunkie724/master-thesis \
  --title "Short actionable title" \
  --body-file /tmp/master-thesis-issue.md \
  --label "type:task,priority:p1,area:credentials,area:backend" \
  --milestone "Phase 4 - Runtime Credentials & Deployment State"
```

6. Verify the created issue:

```bash
gh issue view <number> \
  --repo TVJunkie724/master-thesis \
  --json number,title,state,labels,milestone,url
```

7. If blockers are explicit and unambiguous, set a native blocker relationship
   through GraphQL. Do not represent blockers only as body text.

## Updating Existing Issues

Before creating a duplicate, update the existing issue:

```bash
gh issue edit <number> \
  --repo TVJunkie724/master-thesis \
  --add-label "area:flutter,priority:p1" \
  --milestone "Phase 7 - Flutter Wizard & Twin Views"
```

When changing lifecycle:

- close completed issues and comment with commit/verification evidence
- add `status:blocked` only while truly blocked
- remove stale `status:blocked` when the blocker is resolved

## Blockers and Dependencies

Use native GitHub issue relationships when dependency language is explicit:

- `blocked by #123`
- `depends on #123`
- `Blocker: #123`
- `Voraussetzung: #123`
- open tasklist items in a roadmap/epic that genuinely block completion

Relationship direction:

- If issue `A` cannot be completed until issue `B` is done, set issue `A` as
  blocked by issue `B`.

```bash
blocked_issue=90
blocking_issue=62

blocked_id=$(gh issue view "$blocked_issue" \
  --repo TVJunkie724/master-thesis \
  --json id --jq .id)

blocking_id=$(gh issue view "$blocking_issue" \
  --repo TVJunkie724/master-thesis \
  --json id --jq .id)

gh api graphql \
  -f issueId="$blocked_id" \
  -f blockingIssueId="$blocking_id" \
  -f query='mutation($issueId: ID!, $blockingIssueId: ID!) {
    addBlockedBy(input: {
      issueId: $issueId,
      blockingIssueId: $blockingIssueId
    }) {
      issue { number }
      blockingIssue { number }
    }
  }'
```

If the dependency is ambiguous, do not guess. Mention the ambiguity in the
handoff.

## Commit Discipline

When committing work, link an issue when a relevant issue already exists from
the chat, branch, implementation plan, PR, or issue search.

Use commit body footers:

```text
Refs #123
```

Use `Closes #123` only when the commit truly completes the issue and it should
close after merge to the default branch.

Do not create a low-quality placeholder issue only to satisfy a commit footer.
If no issue exists or issue lookup is unavailable, commit without a reference and
say so in the handoff.

## Quality Gate

Do not create vague issues such as "fix credentials" or "clean UI". Enrich them
with problem, target state, acceptance criteria, and verification first.

Do not encode secrets, credential JSON, tokens, private cloud identifiers, or
full stack traces containing secrets in issue bodies. Redact before posting.
