---
description: Onboarding workflow for AI agents working on any project in this repository
---

# Agent Onboarding Workflow

Follow these steps **in order** when starting work on any project in this repository.

---

## Step 0: Setup AI Working Branch & Session (MANDATORY)

**Before starting ANY task**, set up the working branch and session tracking.

### 0.1 Switch to AI Working Branch

> ⚠️ **CRITICAL:** All git commands must run from the **workspace root** (`d:\Git\master-thesis`), NOT from subdirectories like `3-cloud-deployer` or `twin2multicloud_flutter`.

AI agents always work on a dedicated `ai/dev` branch (not per-task feature branches):

```bash
# 0. IMPORTANT: Run from workspace root!
cd d:\Git\master-thesis

# 1. Check current git status
git status

# 2. Check if ai/dev branch exists
git branch --list ai/dev

# 3a. If ai/dev EXISTS: switch to it and pull latest
git checkout ai/dev
git pull origin ai/dev --rebase

# 3b. If ai/dev DOES NOT EXIST: create it from main
git checkout main
git pull origin main
git checkout -b ai/dev
git push -u origin ai/dev
```

### 0.2 Initialize or Resume Session Tracking

Check for existing session file `.ai-session.json` (gitignored):

```bash
# Check if session file exists
view_file: d:\Git\master-thesis\.ai-session.json
```

**If file exists and task is RELATED to previous session:**
- Reuse the existing `session_id`
- Add new files to `files_modified` list

**If file does NOT exist or this is a NEW unrelated task:**
- Generate a new session ID using format: `AI-<MMDD>-<4-char-hash>`
- Create new `.ai-session.json` file:

```json
{
  "session_id": "AI-1225-a7f3",
  "task_description": "Brief description of the task",
  "started_at": "2025-12-25T10:40:00Z",
  "files_modified": []
}
```

> 💡 **Session ID Format:** `AI-<MMDD>-<first 4 chars of conversation ID>`
> Example: For conversation `cc2e6ffe-...` on Dec 25 → `AI-1225-cc2e`

### 0.3 Commit Message Format (REQUIRED)

ALL commits must include the session ID:

```
[AI-1225-a7f3] <type>: <description>
```

**Types:**
- `WIP` - Work in progress (can commit anytime)
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `test` - Test changes
- `refactor` - Code refactoring

**Examples:**
```
[AI-1225-cc2e] WIP: started Azure compute fix
[AI-1225-cc2e] feat: resolve Azure E2E test failure
[AI-1225-cc2e] test: add unit test for new function
```

> ⚠️ **CRITICAL:** Never work directly on `main` branch. Always use `ai/dev`.
> 
> ⚠️ **CRITICAL:** AI agents **NEVER push** to remote. The user will run `git push` themselves.

---

## Step 1: Check Knowledge Items (KIs)

Before any research or implementation, check existing Knowledge Items for relevant context:

1. Review any KI summaries provided at conversation start
2. Read relevant KI artifacts that match your task
3. Build upon existing knowledge rather than starting fresh

---

## Step 2: Review Overall Vision

Read the integration vision to understand the complete ecosystem:

```
view_file: d:\Git\master-thesis\integration_vision.md
```

**Key concepts to understand:**
- The 5-Layer Architecture (Data Acquisition, Processing, Storage, Management, Visualization)
- How the 3 core projects relate: Orchestrator → Brain → Muscle

---

## Step 3: Identify the Target Project

| Project | Purpose | Priority |
|---------|---------|----------|
| `twin2multicloud_cli` | CLI orchestrator | 🎯 **Thesis Goal** |
| `twin2multicloud_flutter` | Flutter UI | Nice to have (see `FRONTEND_ARCHITECTURE.md`) |
| `2-twin2clouds` | Cost optimizer (Brain) | Core component |
| `3-cloud-deployer` | Cloud deployer (Muscle) | Core component |
| `twin2multicloud-latex` | Thesis document | Documentation |

> **Flutter Frontend Blueprint:** For the Flutter UI implementation, see [`FRONTEND_ARCHITECTURE.md`](file:///d:/Git/master-thesis/FRONTEND_ARCHITECTURE.md) in the repository root. This contains the complete architecture proposal, UI wireframes, and implementation plan.

---

## Step 4: Read the Project's Development Guide

Each project has its own development guide with Docker commands and standards:

| Project | Development Guide |
|---------|-------------------|
| `twin2multicloud_cli` | `d:\Git\master-thesis\twin2multicloud_cli\DEVELOPMENT_GUIDE.md` |
| `2-twin2clouds` | `d:\Git\master-thesis\2-twin2clouds\DEVELOPMENT_GUIDE.md` |
| `3-cloud-deployer` | `d:\Git\master-thesis\3-cloud-deployer\development_guide.md` |

> **Note:** Read the development guide for your target project before making any changes.

---

## Step 5: Check Existing Implementation Plans

**ALWAYS** check for existing implementation plans before starting work:

```
list_dir: d:\Git\master-thesis\<project>\implementation_plans\
```

Review any relevant plans to avoid duplicate work or conflicts.

---

## Step 6: Verify Docker Environment

All projects run in Docker. Verify containers are running:

```bash
docker ps
```

**Expected containers:**
| Container | Port | Project |
|-----------|------|---------|
| `master-thesis-0twin2multicloud-1` | - | twin2multicloud_cli |
| `master-thesis-2twin2clouds-1` | 5003 | 2-twin2clouds |
| `master-thesis-3cloud-deployer-1` | 5004 | 3-cloud-deployer |

If containers are not running:
```bash
docker compose up -d
```

---

## Step 7: Understand Credentials

Credential files are mounted into containers:
- `config_credentials.json` - Cloud provider credentials (AWS, Azure, GCP)
- `google_*.json` - GCP service account

> ⚠️ **NEVER** share, log, or modify credentials without explicit user consent.

---

## ⚠️ Critical Rules

### NEVER Auto-Run E2E Tests
E2E tests in `tests/e2e/` deploy real cloud resources that cost money.

```
❌ FORBIDDEN: Running E2E tests without explicit user instruction
✅ ALLOWED: Running unit/integration tests (--ignore=tests/e2e)
```

### E2E Test Protocol
When running E2E tests (with explicit user permission):

**⚠️ ALWAYS use the helper script** - never run pytest directly for E2E tests:
```bash
# ✅ CORRECT: Use helper script (saves full output to e2e_output.txt)
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python tests/e2e/run_e2e_test.py --provider gcp

# ❌ WRONG: Direct pytest (truncates output, loses critical info)
docker exec ... python -m pytest tests/e2e/gcp/test_gcp_terraform_e2e.py
```

**After test completes:**
1. Read the output file: `view_file: 3-cloud-deployer/e2e_output.txt`
2. **STOP immediately** - return to PLANNING mode
3. Discuss results with user before any further action

### ALWAYS Check implementation_plans/ First
Before creating a new implementation plan, check if one already exists for your task.

### UI Verification
Do NOT use browser subagent to verify UI changes unless explicitly instructed.
The user will check UI themselves.

```
❌ FORBIDDEN: Browser verification of UI changes by default
✅ ALLOWED: Browser verification only when user explicitly requests it
```

---

## Command Execution Rules

All commands must run inside Docker containers. Follow these patterns strictly:

### ✅ PERMITTED Patterns
```bash
# Simple docker exec - ONE command only
docker exec -e PYTHONPATH=/app <container> python script.py
docker exec -e PYTHONPATH=/app <container> python -m pytest tests/ -v
```

### ❌ FORBIDDEN Patterns
```bash
# Complex commands with pipes, &&, ||, redirects
docker exec ... | grep           # ❌ Use grep_search tool instead
docker exec ... && command2      # ❌ Run commands separately
docker exec ... bash -c "..."    # ❌ Find alternative approach

# PowerShell commands
Get-Content, Select-String       # ❌ Use agent tools

# Windows paths inside container
docker exec ... ls d:\path       # ❌ Use forward slashes /app
```

### Prefer Agent Tools Over Commands
| Task | Use Tool | NOT Command |
|------|----------|-------------|
| View file | `view_file` | `docker exec ... cat` |
| Search | `grep_search` | `docker exec ... grep` |
| List dir | `list_dir` | `docker exec ... ls` |

---

## Quick Reference: Test Commands

**twin2multicloud_cli (safe to run):**
```bash
docker exec -e PYTHONPATH=/app master-thesis-0twin2multicloud-1 python -m pytest tests/ -v
```

**2-twin2clouds (safe to run):**
```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest tests/ -v
```

**3-cloud-deployer (safe to run):**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v
```

---

## Documentation Links

- **Optimizer docs:** `2-twin2clouds/docs/docs-overview.html`
- **Deployer docs:** `3-cloud-deployer/docs/docs-overview.html`

---

## During Work: Commit Workflow

### WIP Commits (Anytime)

You can make WIP commits at any point without user approval:

```bash
# 1. Check what files you've modified
git status

# 2. Update .ai-session.json with files you modified
# (add to files_modified array)

# 3. Stage your changes
git add <files-you-modified>

# 4. Commit with session ID and WIP prefix
git commit -m "[AI-1225-cc2e] WIP: <what you did>"
```

> 💡 WIP commits keep your work safe and provide checkpoints.

### Ensuring Only YOUR Changes Are Committed

**Before committing, ALWAYS verify:**

1. **Check `.ai-session.json`** for the files you should have modified
2. **List all modified files:** `git status`
3. **Compare against your session file:**
   - Only stage files listed in `files_modified`
   - If you see unexpected files, ask the user

4. **If you see changes you did NOT make:**
   - Do NOT stage those files
   - Use selective staging: `git add <only-your-files>`
   - Update `.ai-session.json` to reflect actual changes

---

## Task Completion: Merge Workflow (MANDATORY)

> ⚠️ **CRITICAL:** A task is NOT complete until it is:
> 1. ✅ Fully implemented
> 2. ✅ Thoroughly tested (unit tests pass, E2E tests if applicable)
> 3. ✅ **Explicitly approved by the user**

### When User Approves the Task

**Step 1: Final commit (if any uncommitted changes)**

```bash
# Verify you're on ai/dev
git branch --show-current

# Stage and commit remaining changes with session ID
git add <your-files>
git commit -m "[AI-1225-cc2e] feat: <final description>"
```

**Step 2: Push ai/dev to remote**

```bash
git push origin ai/dev
```

**Step 3: Create clean merge commit (User decides approach)**

Inform the user of these options:

| Option | Command | Result |
|--------|---------|--------|
| **Squash merge** (recommended) | `git checkout main && git merge --squash ai/dev` | Single clean commit on main |
| **Regular merge** | `git checkout main && git merge ai/dev` | Preserves all WIP commits |
| **Create PR** | Via GitHub/GitLab | Code review before merge |

**Squash merge example:**
```bash
git checkout main
git pull origin main
git merge --squash ai/dev
git commit -m "feat: <summary of all work from session AI-1225-cc2e>"
git push origin main
```

**Step 4: Reset ai/dev to main (after merge)**

```bash
git checkout ai/dev
git reset --hard main
git push origin ai/dev --force
```

### Rollback: If Something Goes Wrong

To revert all commits from a specific session:

```bash
# Find all commits from the session
git log --oneline --grep="AI-1225-cc2e"

# Option 1: Revert each commit (safe, preserves history)
git revert <commit-hash-1> <commit-hash-2> ...

# Option 2: Reset to before session started (destructive)
git reset --hard <commit-before-session>
```

### Session Cleanup

After successful merge, delete the session file:

```bash
# Delete session file (it's gitignored anyway)
rm .ai-session.json
```

> 💡 **Remember:** The AI agent creates commits on `ai/dev`, but the user controls when to merge to `main`.
