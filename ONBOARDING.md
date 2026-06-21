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

Read `integration_vision.md` to understand the complete ecosystem.

**Key concepts to understand:**
- The 5-Layer Architecture (Data Acquisition, Processing, Storage, Management, Visualization)
- How the 3 core projects relate: Orchestrator → Brain → Muscle

---

## Step 3: Identify the Target Project

| Project | Purpose | Priority |
|---------|---------|----------|
| `twin2multicloud_flutter` | Flutter UI and user-facing orchestration | Thesis application |
| `twin2multicloud_backend` | Management API and persistence boundary | Core component |
| `2-twin2clouds` | Cost optimizer (Brain) | Core component |
| `3-cloud-deployer` | Cloud deployer (Muscle) | Core component |
| `twin2multicloud-latex` | Thesis document | Documentation |

---

## Step 4: Read the Project's Development Guide

Each project has its own development guide with Docker commands and standards:

| Project | Development Guide |
|---------|-------------------|
| `twin2multicloud_backend` | `twin2multicloud_backend/DEVELOPMENT_GUIDE.md` |
| `2-twin2clouds` | `2-twin2clouds/DEVELOPMENT_GUIDE.md` |
| `3-cloud-deployer` | `3-cloud-deployer/development_guide.md` |

> **Note:** Read the development guide for your target project before making any changes.

---

## Step 5: Check Existing Implementation Plans

**ALWAYS** check for existing implementation plans before starting work:

```
<project>/implementation_plans/
```

Review any relevant plans to avoid duplicate work or conflicts.

---

## Before Starting Any Task

1. Read the relevant project documentation and current roadmap.
2. Check GitHub issues and `docs/plans/service_architecture_audit/` for known
   service-layer work.
3. Check if there is an existing implementation plan for the task.
4. Review established project-specific skills and plans before changing code.

---

## When Creating/Updating Implementation Plans

1. **PRESERVE ALL CONTEXT** - Never remove agreed-upon decisions
2. Include explicit sections for:
   - What files will be modified
   - What files will be created
   - What validation is needed
   - What tests are needed
3. If user provides feedback, ADD to the plan, don't replace content
4. Mark changes clearly with timestamps or revision notes if needed

---

## Step 6: Verify Docker Environment

All projects run in Docker. Verify containers are running:

```bash
docker ps
```

**Expected backend containers:**
| Container | Port | Project |
|-----------|------|---------|
| `master-thesis-2twin2clouds-1` | 5003 | 2-twin2clouds |
| `master-thesis-3cloud-deployer-1` | 5004 | 3-cloud-deployer |
| `master-thesis-management-api-1` | 5005 | twin2multicloud_backend |
| `thesis-latex` | - | twin2multicloud-latex (on-demand) |

If containers are not running:
```bash
docker compose up -d
```

---

## Step 7: Understand Credentials

Credential files may be mounted into containers for local development:
- `config_credentials.json` - legacy/local cloud provider credentials fixture
- `google-credentials.json` / `gcp_credentials.json` - legacy/local GCP service account fixtures

The current target architecture is Credentials SSOT through the Management API.
Local files are compatibility fixtures, not the final product model.

> ⚠️ **NEVER** share, log, or modify credentials without explicit user consent.

---

// turbo-all

## ⚠️ Critical Rules

> [!CAUTION]
> **NEVER lose details when updating plans or artifacts.**
> When updating any document, ALL previously agreed-upon details MUST be preserved.
> If you need to restructure content, ensure every decision, requirement, and context remains present.

### NEVER Auto-Run E2E Tests
E2E tests in `tests/e2e/` deploy real cloud resources that cost money.

```
❌ FORBIDDEN: Running E2E tests without explicit user instruction
✅ ALLOWED: Running unit/integration tests (--ignore=tests/e2e)
```

### ALWAYS Check implementation_plans/ First
Before creating a new implementation plan, check if one already exists for your task.

### Implementation Approval
- Follow the current user and developer instructions for autonomy.
- When a task explicitly asks for planning only, stop after the plan.
- When implementation is approved or already requested, proceed through
  implementation, verification, review, and commit without adding artificial
  approval pauses.

### Git Commit Message Format

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

> **Check existing commits first:** Run `git log --oneline -5` to see the format used in recent commits.

### E2E Test Flags

| Flag | Description |
|------|-------------|
| `--skip-cleanup` | Preserve infrastructure after test for log investigation |

> [!WARNING]
> Do NOT use environment variables like `E2E_SKIP_CLEANUP=true` - use the `--skip-cleanup` flag instead.

---

## Command Execution Rules

Prefer repository-local tools and Dockerized service runtimes. Use `rg` for
searching, direct file reads for inspection, and `docker run --rm` for
reproducible service verification. Do not run live cloud E2E unless the user
explicitly asks for it.

---

## Quick Reference: Test Commands

**Management API (safe to run):**
```bash
docker run --rm -v "$PWD/twin2multicloud_backend:/app" -w /app -e PYTHONPATH=/app -e DATABASE_URL=sqlite:////tmp/twin2multicloud_management_test.db -e SEED_DATA=false -e ENABLE_TEST_ENDPOINTS=false master-thesis-management-api:latest python -m pytest tests -q
```

**2-twin2clouds (safe to run):**
```bash
tmpdir=$(mktemp -d /tmp/optimizer-test.XXXXXX)
printf '{"aws": {}}\n' > "$tmpdir/config_credentials.json"
docker run --rm -v "$PWD/2-twin2clouds:/app" -v "$PWD/config.json:/config/config.json:ro" -v "$tmpdir/config_credentials.json:/config/config_credentials.json:ro" -w /app -e PYTHONPATH=/app 2twin2clouds:latest python -m pytest tests -q
rm -rf "$tmpdir"
```

**3-cloud-deployer (safe to run):**
```bash
docker run --rm -v "$PWD/3-cloud-deployer:/app" -w /app -e PYTHONPATH=/app 3cloud-deployer:latest python -m pytest tests/unit tests/api tests/integration tests/test_gcp_simulator.py -q
```

---

## Documentation Links

- **Optimizer docs:** `2-twin2clouds/docs/docs-overview.html`
- **Deployer docs:** `3-cloud-deployer/docs/docs-overview.html`
