---
name: onboarding
description: >
  Use this project-specific Twin2MultiCloud skill when starting work on any project in the master-thesis (Twin2MultiCloud) repository. Triggers: "start working", "onboard", "new task", "understand the project", "get started", or when resuming a session. Sets up the ai/dev branch, initializes/refreshes session tracking, and loads cross-project context before any code changes.
metadata:
  project: master-thesis
  source: .claude/onboarding
---


# Agent Onboarding — Twin2MultiCloud

## Mission

Before ANY task, complete all steps below in order. Do not skip steps. The source of truth for this workflow lives at `.agent/workflows/onboarding.md` — this skill mirrors and operationalizes it inside Codex.

---

## Step 0: Setup AI Working Branch & Session (MANDATORY)

> ⚠️ **CRITICAL:** All git commands run from the **workspace root** (`master-thesis/`), NOT from subdirectories such as `3-cloud-deployer/`, `2-twin2clouds/`, `twin2multicloud_backend/`, or `twin2multicloud_flutter/`.

### 0.1 Switch to `ai/dev` Branch

```bash
# 1. Verify you are at workspace root
git status

# 2. Check whether ai/dev exists
git branch --list ai/dev

# 3a. If ai/dev EXISTS → switch and pull
git checkout ai/dev
git pull origin ai/dev --rebase

# 3b. If ai/dev DOES NOT EXIST → create from master
git checkout master && git pull origin master
git checkout -b ai/dev
git push -u origin ai/dev
```

> ⚠️ **NEVER work on `master` directly. NEVER push — the user pushes themselves.**

### 0.2 Initialize or Resume Session Tracking

Check for `.ai-session.json` (gitignored) at the workspace root.

**If the file exists AND the new task is related to the previous session:** reuse the `session_id` and append to `files_modified`.

**If the file does NOT exist OR this is a new unrelated task:** create / replace it:

```json
{
  "session_id": "AI-<MMDD>-<4-char-hash>",
  "task_description": "Brief description of the task",
  "started_at": "<ISO timestamp>",
  "files_modified": []
}
```

> Session ID format: `AI-<MMDD>-<first 4 chars of conversation ID>`
> Example: conversation `cc2e6ffe-…` on 13 April → `AI-0413-cc2e`

### 0.3 Commit Message Format (REQUIRED for ALL commits)

```
[AI-MMDD-xxxx] <type>: <description>
```

Types: `WIP` · `feat` · `fix` · `docs` · `test` · `refactor` · `chore`

Examples:
```
[AI-0413-cc2e] WIP: started Azure compute fix
[AI-0413-cc2e] feat(flutter): wizard step 3 deployer config
[AI-0413-cc2e] fix(backend): populate cheapest_l* columns on bulk-save
```

---

## Step 1: Check Knowledge Items

Review any KI summaries or artifacts provided at conversation start. Build on existing knowledge — do not start from scratch.

---

## Step 2: Review Integration Vision

Read `integration_vision.md` at the repository root. Understand:

- The **5-Layer Architecture** (Data Acquisition → Processing → Storage → Management → Visualization)
- The relationship between the 3 core projects: **Orchestrator → Brain → Muscle**
- The role of the Management API as the single entry point for the Flutter UI

---

## Step 3: Identify the Target Project

| Project | Purpose | Priority |
|---------|---------|----------|
| `twin2multicloud_backend` | Management API + CLI orchestrator (FastAPI, port 5005) | 🎯 Thesis Goal |
| `twin2multicloud_flutter` | Flutter UI (Desktop + Web) | Visual front-end |
| `2-twin2clouds` | Cost optimizer / Brain (port 5003) | Core component |
| `3-cloud-deployer` | Cloud deployer / Muscle (port 5004) | Core component |
| `twin2multicloud-latex` | Thesis document | Documentation |

**Architecture rule:** Flutter NEVER calls Deployer or Optimizer directly → always `Flutter → Management API → {Deployer | Optimizer}`. Direct calls from Flutter to ports 5003 / 5004 are defects.

> **Flutter Frontend Blueprint:** [`FRONTEND_ARCHITECTURE.md`](../../FRONTEND_ARCHITECTURE.md) at the repository root contains the full architecture proposal, screen wireframes, twin-state machine, and the BLoC layout.

---

## Step 3b: Architecture Responsibilities

| Component | Owns | Does NOT do |
|-----------|------|-------------|
| **Flutter UI** | Visual display, basic visibility checks, user input | Business logic, validation, direct Deployer / Optimizer calls |
| **Management API** | Persists twin config + state, proxies to backends, SSE log streaming, file versioning, OAuth | Cloud-specific deployment knowledge |
| **Deployer API** | All deployment knowledge: validation, provider restrictions, cooldowns | User state persistence |
| **Optimizer API** | Cost formulas, real-time pricing fetch, optimal multi-cloud allocation | Deployment, persistence |

---

## Step 4: Read the Project's Development Guide

| Project | Guide |
|---------|-------|
| `twin2multicloud_backend` | `twin2multicloud_backend/DEVELOPMENT_GUIDE.md` (or root README until guide exists) |
| `twin2multicloud_flutter` | `twin2multicloud_flutter/README.md` + `FRONTEND_ARCHITECTURE.md` |
| `2-twin2clouds` | `2-twin2clouds/DEVELOPMENT_GUIDE.md` |
| `3-cloud-deployer` | `3-cloud-deployer/development_guide.md` |

For Flutter UI work, also load the `frontend-onboarding` skill — it walks through `lib/` structure, BLoC layout, and the design tokens.

---

## Step 5: Check Existing Implementation Plans

```
list: <project>/implementation_plans/
```

Always check before creating a new plan to avoid duplicate work or conflicts.

---

## Step 6: Verify Docker Environment

```bash
docker ps
```

| Container | Port | Project |
|-----------|------|---------|
| `master-thesis-management-api-1` | 5005 | twin2multicloud_backend |
| `master-thesis-2twin2clouds-1` | 5003 | 2-twin2clouds |
| `master-thesis-3cloud-deployer-1` | 5004 | 3-cloud-deployer |

If not running:

```bash
docker compose up -d
# debug build with hot reload:
docker compose -f compose.debug.yaml up -d
```

For Flutter, run on the host (no container):

```bash
cd twin2multicloud_flutter
flutter run -d chrome     # Web
flutter run -d linux      # Desktop (or macos / windows)
```

---

## Step 7: Understand Credentials

Credential files are mounted into the backend containers. They live at the repo root and are gitignored:

- `config_credentials.json` — combined cloud provider credentials (AWS, Azure, GCP)
- `google_credentials.json`, `gcp_credentials.json` — GCP service-account JSON

> ⚠️ **NEVER** read credential file contents into the chat, log them, paste them into commits, or share them in any artifact. Read only schema / shape from the `*.example` files when you need to know the structure.

---

## Critical Rules

### Never Auto-Run E2E Tests

E2E tests in `tests/e2e/` deploy real cloud resources and cost real money.

- ❌ FORBIDDEN: Running `tests/e2e/` without explicit user instruction
- ✅ ALLOWED: Unit / integration tests with `--ignore=tests/e2e`

**When E2E tests are explicitly permitted**, use the helper script (it captures full output that pytest would otherwise truncate):

```bash
# ✅ CORRECT
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python tests/e2e/run_e2e_test.py --provider gcp

# ❌ WRONG — truncates output
docker exec ... python -m pytest tests/e2e/...
```

After the test: read `3-cloud-deployer/e2e_output.txt`, then **STOP and discuss results** before any further action.

### Command Execution Rules

- ✅ Simple `docker exec` with one command
- ❌ Pipes, `&&`, `||`, redirects, `bash -c "..."` inside `docker exec`
- ❌ PowerShell commands
- ❌ Windows paths inside containers (use `/app/...`)

Prefer agent tools over shell commands:

| Task | Use | NOT |
|------|-----|-----|
| View file | `sed`/file read | `docker exec … cat` |
| Search | `rg` | `docker exec … grep` |
| List dir | `rg --files` / `ls` | `docker exec … ls` |

### No Browser UI Verification by Default

- ❌ FORBIDDEN: browser automation to verify UI changes by default
- ✅ ALLOWED: Only when the user explicitly requests it

---

## Safe Test Commands

```bash
# twin2multicloud_backend
docker exec -e PYTHONPATH=/app master-thesis-management-api-1 python -m pytest tests/ -v

# 2-twin2clouds
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v

# 3-cloud-deployer (no E2E)
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v

# Flutter (host)
cd twin2multicloud_flutter && flutter analyze && flutter test
```

---

## During Work: Commit Workflow

WIP commits can be made anytime without user approval:

```bash
git status                          # check modified files
# update files_modified in .ai-session.json
git add <only-your-files>
git commit -m "[AI-MMDD-xxxx] WIP: <what you did>"
```

**Always verify** you only stage files listed in `.ai-session.json`. If you see unexpected changes, ask the user before staging.

---

## Task Completion: Merge Workflow (MANDATORY)

A task is NOT complete until: ✅ implemented · ✅ tested · ✅ **user approves**

### On User Approval

1. Final commit on `ai/dev` (if uncommitted changes remain)
2. Inform user of merge options:

| Option | Command |
|--------|---------|
| Squash merge (recommended) | `git checkout master && git merge --squash ai/dev` |
| Regular merge | `git checkout master && git merge ai/dev` |
| Pull request | Via GitHub |

3. After merge, reset `ai/dev` to master:

```bash
git checkout ai/dev
git reset --hard master
git push origin ai/dev --force
```

4. Delete `.ai-session.json`.

### Rollback

```bash
git log --oneline --grep="AI-MMDD-xxxx"
git revert <commit-hash>   # safe — preserves history
```

---

## Related Skills

- **frontend-onboarding** — Onboard specifically into the `twin2multicloud_flutter` codebase (BLoC layout, design tokens, screen map)
- **concept / architect / builder / auditor** — The UI pipeline once the project context is loaded
