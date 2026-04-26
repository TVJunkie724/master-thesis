---
name: onboarding
description: >
  Use when starting or resuming work in this repository. Loads current branch
  rules, roadmap and GitHub backlog sources, project boundaries, credential
  safety rules, and safe verification commands.
version: 0.2.0
user-invocable: true
---

# Agent Onboarding

## 1. Git And Session Context

Run from the repository root:

```bash
git status --short
git branch --show-current
```

Branch rules:

- Never work directly on `master`.
- Continue on the user's current feature branch when one is already selected.
- For new work, create `codex/<short-task-name>` from `master` unless the user requests a different branch.
- Push only when the user asks for push, merge, or PR work.
- Use concise conventional commits unless the user requests another format.

`.ai-session.json` is optional local metadata and must not override the current user request, branch, GitHub Issues, or Milestones.

## 2. Source Of Truth

- `ASSESSMENT.md` is the architecture-debt roadmap.
- GitHub Issues and Milestones are the active backlog.
- `docs/plans/` contains approved concepts and implementation plans.
- `docs-site/` is the canonical published documentation source once bootstrapped.

## 3. Project Map

| Project | Purpose | Port |
|---------|---------|------|
| `twin2multicloud_backend` | Management API and orchestration boundary | 5005 |
| `twin2multicloud_flutter` | Flutter UI | host-run |
| `2-twin2clouds` | Cost Optimizer / Brain | 5003 |
| `3-cloud-deployer` | Cloud Deployer / Muscle | 5004 |
| `twin2multicloud-latex` | Thesis source | on demand |
| `docs-site` | MkDocs documentation site | 5010 |

Architecture rule: Flutter calls only the Management API. Direct Flutter calls to Optimizer or Deployer are defects.

## 4. Context To Read

Read only task-relevant context:

- `integration_vision.md`
- `ASSESSMENT.md`
- `FRONTEND_ARCHITECTURE.md` for Flutter work
- relevant files under `docs/plans/` or `<project>/implementation_plans/`

## 5. Credentials

Never print, paste, commit, or summarize real credential values. Use `*.example` files for schema inspection.

Sensitive local files include `config_credentials.json`, `gcp_credentials.json`, `google-credentials.json`, and transition credentials under `3-cloud-deployer/upload/template/`.

## 6. Tests

Never auto-run E2E tests. Safe tests:

```bash
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v
cd twin2multicloud_flutter && flutter analyze && flutter test
```

## 7. Editing Rules

- Prefer `rg` / `rg --files` for search.
- Use `apply_patch` for manual edits.
- Preserve user changes in dirty worktrees.
- Keep work aligned with the active GitHub milestone and issue.
