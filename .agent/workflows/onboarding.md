---
description: Onboarding workflow for AI agents working on any project in this repository
---

# Agent Onboarding Workflow

Follow these steps **in order** when starting work on any project in this repository.

---

## Step 0: Create Feature Branch (MANDATORY)

**Before starting ANY task**, create a dedicated feature branch:

```bash
# 1. Check current git status to see any existing changes
git status

# 2. Stash any uncommitted changes (if any exist from previous work)
git stash --include-untracked

# 3. Switch to main branch and pull latest
git checkout main
git pull origin main

# 4. Create and switch to a new feature branch
git checkout -b feature/<descriptive-task-name>
```

**Branch naming conventions:**
- Use lowercase with hyphens: `feature/fix-azure-e2e-tests`
- Be descriptive: `feature/add-gcp-firestore-index`
- Include ticket/issue if available: `feature/issue-42-fix-login`

> ⚠️ **CRITICAL:** Never work directly on `main` branch. Always create a feature branch first.

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
| `twin2multicloud_flutter` | Flutter UI | Nice to have |
| `2-twin2clouds` | Cost optimizer (Brain) | Core component |
| `3-cloud-deployer` | Cloud deployer (Muscle) | Core component |
| `twin2multicloud-latex` | Thesis document | Documentation |

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

## Task Completion: Commit Workflow (MANDATORY)

> ⚠️ **CRITICAL:** A task is NOT complete until it is:
> 1. ✅ Fully implemented
> 2. ✅ Thoroughly tested (unit tests pass, E2E tests if applicable)
> 3. ✅ **Explicitly approved by the user**

### When User Approves the Task

Only after the user explicitly approves the completed work, follow this commit workflow:

```bash
# 1. Verify you're on the correct feature branch
git branch --show-current
# Expected: feature/<your-task-name>

# 2. Check status to see ALL changes
git status

# 3. Review the diff to ensure ONLY your changes are present
git diff

# 4. Stage ONLY the files YOU modified (be selective!)
git add <specific-file-1> <specific-file-2>
# Or if all changes are yours:
git add -A

# 5. Commit with a descriptive message
git commit -m "feat: <descriptive message of what was accomplished>"
```

### Ensuring Only YOUR Changes Are Committed

**Before committing, ALWAYS verify:**

1. **List all modified files:**
   ```bash
   git status
   ```

2. **Review each file's changes:**
   ```bash
   git diff <filename>
   ```

3. **If you see changes you did NOT make:**
   - Do NOT stage those files
   - Use selective staging: `git add <only-your-files>`
   - Or use interactive staging: `git add -p` (to stage specific hunks)

4. **If unsure about any changes:**
   - Ask the user before committing
   - Never commit files you didn't intentionally modify

### Commit Message Format

Follow conventional commits:
- `feat: ` - New feature
- `fix: ` - Bug fix
- `docs: ` - Documentation changes
- `test: ` - Test additions/modifications
- `refactor: ` - Code refactoring

**Examples:**
```
feat: add GCP Firestore composite index for hot-reader queries
fix: resolve Azure L3 function discovery issue
test: add E2E test for single-cloud Azure deployment
```

### After Commit (User Decides Next Steps)

After committing, inform the user. They will decide whether to:
- Push to remote: `git push origin feature/<branch-name>`
- Create a pull request
- Merge to main
- Continue with additional work

> 💡 **Remember:** The AI agent creates commits, but the user controls when to push and merge.
