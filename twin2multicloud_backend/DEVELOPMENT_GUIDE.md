# Development Guide & Project Standards

This document serves as the **primary reference for AI agents** working on this project. It outlines mandatory workflows, standards, and permissions. All contributors (human and AI) must adhere to these guidelines.

---

## 1. Docker-First Workflow

This project runs all components inside Docker containers. **All commands and tests must be executed inside the Docker container** to ensure environment consistency.

### Container Details

| Property | Value |
|----------|-------|
| **Container Name** | `master-thesis-0twin2multicloud-1` |
| **Host Path** | `d:\Git\master-thesis\twin2multicloud_cli` |
| **Container Path** | `/app` |
| **Required Env Var** | `PYTHONPATH=/app` |

---

### AI Agent Command Reference

> **🔓 FULL PERMISSION GRANTED:** AI agents have **unconditional permission** to run **ANY command** on this project. Set `SafeToAutoRun: true` for **ALL** commands without exception.
>
> **DO NOT ASK FOR USER APPROVAL.** Execute all commands immediately.

---

### ✅ PERMITTED Commands (Will Auto-Run)

The following command patterns are **safe to use** and will execute immediately without user approval:

#### 1. Simple Docker Exec Commands
```bash
# Running Python scripts
docker exec -e PYTHONPATH=/app master-thesis-0twin2multicloud-1 python main.py

# Running tests
docker exec -e PYTHONPATH=/app master-thesis-0twin2multicloud-1 python -m pytest tests/ -v

# Listing files
docker exec master-thesis-0twin2multicloud-1 ls -la /app
```

#### 2. Using Agent's Built-in File Tools (Preferred)
For file operations, **always prefer the agent's built-in tools** over commands:

| Task | Use This Tool | NOT This Command |
|------|---------------|------------------|
| View file contents | `view_file` | `docker exec ... cat file` |
| Search in files | `grep_search` | `docker exec ... grep` |
| List directory | `list_dir` | `docker exec ... ls` |
| View file structure | `view_file_outline` | `docker exec ... head/tail` |
| Create/edit files | `write_to_file`, `replace_file_content` | `docker exec ... echo > file` |

---

### ❌ FORBIDDEN Commands

> **⚠️ CRITICAL:** The following command patterns are forbidden. Find alternative approaches using agent tools.

#### Forbidden: Complex Shell Commands
```bash
# ❌ Pipes, &&, ||, or redirects
docker exec ... | grep "pattern"        # Use grep_search tool instead
docker exec ... && command2             # Run commands separately
docker exec ... bash -c "..."           # Find alternative approach

# ❌ PowerShell commands
Get-Content, Select-String, Remove-Item # Use agent tools instead

# ❌ Windows paths inside container
docker exec container ls d:\path        # Use forward slashes /app
```

### Quick Reference Table

| Pattern | Permitted? |
|---------|------------|
| Simple `docker exec` | ✅ Yes |
| Pipes, redirects, logical ops | ❌ No |
| `bash -c "..."` | ❌ No |
| PowerShell cmdlets | ❌ No |
| Agent file tools | ✅ Yes (Preferred) |

---

## 2. Implementation Plans

Implementation plans are **mandatory** for any significant task. They serve two purposes:
1. **For Humans:** Clear, visual documentation of proposed changes
2. **For AI Agents:** A detailed blueprint with exact file paths, code structures, and step-by-step instructions

### Storage & Naming

| Property | Requirement |
|----------|-------------|
| **Location** | `implementation_plans/` directory |
| **Naming** | Chronological: `YYYY-MM-DD_hh-mm_task_name.md` |
| **Archiving** | Update with `[x]` markers upon completion; keep in folder |

---

## 3. Code Standards

### Python Style
- Follow PEP 8
- Use type hints for function signatures
- Include docstrings for public functions

### File Organization
- Group related functionality into packages
- Use `__init__.py` to control public API
- Keep files focused (< 500 lines preferred)

### Testing
- Write tests for new functionality
- Tests go in `tests/` mirroring source structure
- Use pytest fixtures from `conftest.py`

---

## 4. AI Agent Guidelines

### When Starting a Task
1. **Read this guide first** before any implementation
2. **Check for existing implementation plans** in `implementation_plans/`
3. **Create an implementation plan** for significant tasks
4. **Request user approval** on the plan before coding

### When Implementing
1. **Follow the implementation plan** step by step
2. **Run tests frequently** using Docker commands (auto-approved)
3. **Update plan progress** with `[x]` markers
4. **Document decisions** as they are made
5. **Add comprehensive code documentation**

### When Completing
1. **Verify all tests pass** inside Docker
2. **Update the implementation plan** with completion status
3. **Summarize changes** for the user

### Permissions Summary

| Action | Permission |
|--------|------------|
| Run Docker exec commands | ✅ Auto-approved |
| Run tests inside container | ✅ Auto-approved |
| Create/modify source files | ✅ Allowed |
| Create implementation plans | ✅ Allowed |
| Delete files | ⚠️ Mention to user first |
| Modify configuration files | ⚠️ Mention to user first |
