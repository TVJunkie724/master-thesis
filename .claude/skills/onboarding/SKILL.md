---
name: onboarding
description: >
  Use when starting work on any project in this repository: "start working",
  "onboard", "new task", "understand the project", "get started", or when
  resuming a session. Sets up the ai/dev branch, session tracking, and loads
  project context before any implementation begins.
version: 0.1.0
user-invocable: true
---

# Agent Onboarding

## Mission

Before ANY task, complete all steps below in order. Do not skip steps.

---

## Step 0: Setup AI Working Branch & Session (MANDATORY)

> ⚠️ **CRITICAL:** All git commands run from the **workspace root** (`master-thesis/`), NOT from subdirectories.

### 0.1 Switch to ai/dev Branch

```bash
# 1. Verify you are at workspace root
git status

# 2. Check if ai/dev exists
git branch --list ai/dev

# 3a. If ai/dev EXISTS → switch and pull
git checkout ai/dev
git pull origin ai/dev --rebase

# 3b. If ai/dev DOES NOT EXIST → create from main
git checkout main && git pull origin main
git checkout -b ai/dev
git push -u origin ai/dev
```

> ⚠️ **NEVER work on `main` directly. NEVER push — the user pushes themselves.**

### 0.2 Initialize or Resume Session Tracking

Check for `.ai-session.json` (gitignored) at the workspace root.

**If the file exists AND the task is related to the previous session:** reuse the `session_id` and append to `files_modified`.

**If the file does NOT exist or this is a new unrelated task:** create it with a new ID:

```json
{
  "session_id": "AI-<MMDD>-<4-char-hash>",
  "task_description": "Brief description of the task",
  "started_at": "<ISO timestamp>",
  "files_modified": []
}
```

> Session ID format: `AI-<MMDD>-<first 4 chars of conversation ID>`
> Example: conversation `cc2e6ffe-…` on Dec 25 → `AI-1225-cc2e`

### 0.3 Commit Message Format (REQUIRED for ALL commits)

```
[AI-1225-a7f3] <type>: <description>
```

Types: `WIP` · `feat` · `fix` · `docs` · `test` · `refactor`

---

## Step 1: Check Knowledge Items

Review any KI summaries or artifacts provided at conversation start. Build on existing knowledge — do not start from scratch.

---

## Step 2: Review Integration Vision

Read `integration_vision.md` at the repository root for the 5-Layer Architecture and the relationship between the 3 core projects (Orchestrator → Brain → Muscle).

---

## Step 3: Identify the Target Project

| Project | Purpose | Priority |
|---------|---------|----------|
| `twin2multicloud_cli` | CLI orchestrator | 🎯 Thesis Goal |
| `twin2multicloud_flutter` | Flutter UI | Nice to have |
| `2-twin2clouds` | Cost optimizer (Brain) | Core component |
| `3-cloud-deployer` | Cloud deployer (Muscle) | Core component |
| `twin2multicloud-latex` | Thesis document | Documentation |

**Architecture rule:** Flutter NEVER calls Deployer directly → always `Flutter → Management API → Deployer API`

---

## Step 4: Read the Project's Development Guide

| Project | Guide |
|---------|-------|
| `twin2multicloud_cli` | `twin2multicloud_cli/DEVELOPMENT_GUIDE.md` |
| `2-twin2clouds` | `2-twin2clouds/DEVELOPMENT_GUIDE.md` |
| `3-cloud-deployer` | `3-cloud-deployer/development_guide.md` |

---

## Step 5: Check Existing Implementation Plans

```
list: <project>/implementation_plans/
```

Always check before creating a new plan to avoid duplicate work.

---

## Step 6: Verify Docker Environment

```bash
docker ps
```

| Container | Port | Project |
|-----------|------|---------|
| `master-thesis-0twin2multicloud-1` | — | twin2multicloud_cli |
| `master-thesis-2twin2clouds-1` | 5003 | 2-twin2clouds |
| `master-thesis-3cloud-deployer-1` | 5004 | 3-cloud-deployer |

If not running: `docker compose up -d`

---

## Critical Rules

### Never Auto-Run E2E Tests
E2E tests deploy real cloud resources and cost money.

- ❌ FORBIDDEN: Running `tests/e2e/` without explicit user instruction
- ✅ ALLOWED: Unit/integration tests with `--ignore=tests/e2e`

**When E2E tests are explicitly permitted**, use the helper script:
```bash
# ✅ CORRECT
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python tests/e2e/run_e2e_test.py --provider gcp

# ❌ WRONG — truncates output
docker exec ... python -m pytest tests/e2e/...
```
After test: read `3-cloud-deployer/e2e_output.txt`, then **STOP and discuss results** before any further action.

### Command Execution Rules

- ✅ Simple `docker exec` with one command
- ❌ Pipes, `&&`, `||`, redirects, `bash -c "..."` inside docker exec
- ❌ PowerShell commands
- ❌ Windows paths inside containers (use `/app/...`)

Prefer agent tools over shell commands:

| Task | Use | NOT |
|------|-----|-----|
| View file | Read tool | `docker exec … cat` |
| Search | Grep tool | `docker exec … grep` |
| List dir | Glob tool | `docker exec … ls` |

### No Browser UI Verification
- ❌ FORBIDDEN: Browser agent to verify UI changes by default
- ✅ ALLOWED: Only when user explicitly requests it

---

## Safe Test Commands

```bash
# twin2multicloud_cli
docker exec -e PYTHONPATH=/app master-thesis-0twin2multicloud-1 python -m pytest tests/ -v

# 2-twin2clouds
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v

# 3-cloud-deployer (no E2E)
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v
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
| Squash merge (recommended) | `git checkout main && git merge --squash ai/dev` |
| Regular merge | `git checkout main && git merge ai/dev` |
| PR | Via GitHub |

3. After merge: reset `ai/dev` to main
```bash
git checkout ai/dev
git reset --hard main
git push origin ai/dev --force
```
4. Delete `.ai-session.json`

### Rollback
```bash
git log --oneline --grep="AI-MMDD-xxxx"
git revert <commit-hash>   # safe — preserves history
```
