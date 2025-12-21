---
description: Onboarding workflow for AI agents working on any project in this repository
---

# Agent Onboarding Workflow

Follow these steps **in order** when starting work on any project in this repository.

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
1. Run the test
2. **STOP immediately** after test completes
3. Collect all outputs:
   - `test_results.txt` (from pytest hook)
   - `terraform_outputs.json` (if saved)
   - Console output
4. **Return to PLANNING mode**
5. Discuss results with user before any further action

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
