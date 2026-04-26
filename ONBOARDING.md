# Agent Onboarding Workflow

Follow this workflow when starting or resuming work in this repository.

## 1. Git And Session Context

Run git commands from the repository root, not from a service subdirectory.

```bash
git status --short
git branch --show-current
```

Branch rules:

- Never work directly on `master`.
- If the user already selected a feature branch, continue there.
- For new work, create a `codex/<short-task-name>` branch from `master` unless the user asks for a different branch.
- Push only when the user asks for push/merge/PR work.
- Use structured, conventional commit messages, for example `docs: add docs site bootstrap`.

Session tracking:

- `.ai-session.json` is optional, local, and gitignored.
- If it exists and is useful, keep it current.
- Do not let stale session metadata override the actual user request, branch, or GitHub issue/milestone state.

## 2. Source Of Truth

Use these as the current planning sources:

- `ASSESSMENT.md` for the architecture-debt roadmap.
- GitHub Issues and Milestones for active backlog tracking.
- `docs/plans/` for approved implementation concepts and plans.
- `docs-site/` for the canonical published documentation source once the docs-site phase is active.

Do not treat old TODO or future-work files as independent planning sources after their contents have been imported into GitHub Issues.

## 3. Project Map

| Project | Purpose | Port |
|---------|---------|------|
| `twin2multicloud_backend` | Management API and orchestration boundary | 5005 |
| `twin2multicloud_flutter` | Flutter UI | host-run |
| `2-twin2clouds` | Cost Optimizer / Brain | 5003 |
| `3-cloud-deployer` | Cloud Deployer / Muscle | 5004 |
| `twin2multicloud-latex` | Thesis source | on demand |
| `docs-site` | Canonical MkDocs documentation site | 5010 |

Architecture rule: Flutter calls the Management API only. Direct Flutter calls to Optimizer or Deployer are defects.

## 4. Read Relevant Context

Before editing, read only the context needed for the task:

- Overall architecture: `integration_vision.md`
- Roadmap: `ASSESSMENT.md`
- Frontend architecture: `FRONTEND_ARCHITECTURE.md`
- Backend/deployer/optimizer plans: relevant files under `docs/plans/` or `<project>/implementation_plans/`
- Docs-site work: `docs/plans/2026-04-26_repository_hygiene_documentation_architecture.md` and `docs/plans/2026-04-26_repository_hygiene_cleanup_plan.md`

For Flutter UI work, also use the project-specific frontend skills.

## 5. Docker And Local Services

Expected containers for the main stack:

| Container | Port | Project |
|-----------|------|---------|
| `master-thesis-management-api-1` | 5005 | Management API |
| `master-thesis-2twin2clouds-1` | 5003 | Optimizer |
| `master-thesis-3cloud-deployer-1` | 5004 | Deployer |

Common commands:

```bash
docker compose up -d
docker compose --profile docs up docs
docker compose --profile latex run --rm thesis-latex
```

Flutter runs on the host:

```bash
cd twin2multicloud_flutter
flutter run -d chrome
```

## 6. Credentials

Real credential files are local, gitignored, and sensitive:

- `config_credentials.json`
- `gcp_credentials.json`
- `google-credentials.json`
- credential files under `3-cloud-deployer/upload/template/` during the transition period

Rules:

- Never print, paste, commit, or summarize real credential values.
- Read schema from `*.example` files instead of real credential files.
- Do not delete currently valid credentials from `upload/template` until the credential SSOT and replacement test path are ready.

## 7. Tests

Never auto-run E2E tests. E2E tests may deploy real cloud resources and cost money.

Allowed without extra approval:

```bash
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v
cd twin2multicloud_flutter && flutter analyze && flutter test
```

When the user explicitly approves E2E tests, use the provider helper scripts where available and stop to discuss the results before making follow-up changes.

## 8. Working Rules

- Prefer `rg` / `rg --files` for search.
- Use `apply_patch` for manual edits.
- Preserve user changes in a dirty worktree.
- Keep implementation slices small, testable, and aligned with the existing roadmap milestone.
- Before finalizing, summarize what changed, what was verified, and anything not run.
