# Development Guide & Project Standards

This document serves as the **primary reference for AI agents** working on this project. It outlines mandatory workflows, standards, and permissions. All contributors (human and AI) must adhere to these guidelines.

---

## 1. Docker-First Workflow

This project runs all components inside Docker containers. **All commands and tests must be executed inside the Docker container** to ensure environment consistency.

### Container Details

| Property | Value |
|----------|-------|
| **Container Name** | `master-thesis-3cloud-deployer-1` |
| **Host Path** | `d:\Git\master-thesis\3-cloud-deployer` |
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
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python src/main.py

# Running tests
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v

# Listing files
docker exec master-thesis-3cloud-deployer-1 ls -la /app
```

#### 2. Docker Exec with Bash Wrapper (Recommended for Complex Commands)
When you need pipes, redirects, or logical operators, **wrap the entire command inside `bash -c "..."`**:

```bash
# Piping INSIDE bash (correct)
docker exec master-thesis-3cloud-deployer-1 bash -c "cat /app/file.txt | grep 'pattern'"

# Logical operators INSIDE bash (correct)
docker exec master-thesis-3cloud-deployer-1 bash -c "ls /app || echo 'directory not found'"

# Redirects INSIDE bash (correct)
docker exec master-thesis-3cloud-deployer-1 bash -c "python script.py 2>&1"

# Multiple commands INSIDE bash (correct)
docker exec master-thesis-3cloud-deployer-1 bash -c "cd /app && python -m pytest tests/ -v"
```

#### 3. Terraform Commands
Terraform is installed in the Docker container.

> **IMPORTANT:** NEVER chain terraform commands with `&&`. Run each command **separately** and wait for completion before running the next.

```bash
# Step 1: Init (run separately, wait for completion)
docker exec master-thesis-3cloud-deployer-1 terraform -chdir=/app/src/terraform init

# Step 2: Validate (run separately)
docker exec master-thesis-3cloud-deployer-1 terraform -chdir=/app/src/terraform validate

# Step 3: Plan (use bash wrapper for -var-file)
docker exec master-thesis-3cloud-deployer-1 bash -c "cd /app/src/terraform && terraform plan -var-file=/app/upload/<project>/terraform/generated.tfvars.json"

# Step 4: Apply (after plan succeeds)
docker exec master-thesis-3cloud-deployer-1 bash -c "cd /app/src/terraform && terraform apply -auto-approve -var-file=/app/upload/<project>/terraform/generated.tfvars.json"

# Destroy (when needed)
docker exec master-thesis-3cloud-deployer-1 bash -c "cd /app/src/terraform && terraform destroy -auto-approve -var-file=/app/upload/<project>/terraform/generated.tfvars.json"
```

> **Note:** Use bash wrapper (`bash -c "cd ... && terraform ..."`) for commands with `-var-file` argument. The `&&` inside bash is for `cd` only, NOT for chaining multiple terraform commands.

#### 4. Using Agent's Built-in File Tools (Preferred)
For file operations, **always prefer the agent's built-in tools** over commands:

| Task | Use This Tool | NOT This Command |
|------|---------------|------------------|
| View file contents | `view_file` | `docker exec ... cat file` |
| Search in files | `grep_search` | `docker exec ... grep` |
| List directory | `list_dir` | `docker exec ... ls` |
| View file structure | `view_file_outline` | `docker exec ... head/tail` |
| Create/edit files | `write_to_file`, `replace_file_content` | `docker exec ... echo > file` |

---

### ❌ FORBIDDEN Commands (Will Trigger Approval Prompt)

> **⚠️ CRITICAL:** The following command patterns will **ALWAYS trigger an approval prompt** regardless of `SafeToAutoRun: true`. This is an IDE extension behavior that cannot be overridden.

#### Forbidden Pattern 1: Piping to Windows/PowerShell Commands
```bash
# ❌ FORBIDDEN - pipes to Windows command
docker exec container python -c "print('test')" | findstr "test"
docker exec container cat file.txt | Select-String "pattern"

# ✅ CORRECT - pipe inside bash
docker exec container bash -c "python -c 'print(test)' | grep 'test'"
```

#### Forbidden Pattern 2: Stderr Redirection Outside Bash
```bash
# ❌ FORBIDDEN - redirect outside bash
docker exec container python script.py 2>&1 | Out-Null
docker exec container command 2>/dev/null

# ✅ CORRECT - redirect inside bash
docker exec container bash -c "python script.py 2>&1"
docker exec container bash -c "command 2>/dev/null"
```

#### Forbidden Pattern 3: Logical Operators Outside Bash
```bash
# ❌ FORBIDDEN - operators outside bash
docker exec container ls /app || echo "failed"
docker exec container test -f file && echo "exists"

# ✅ CORRECT - operators inside bash
docker exec container bash -c "ls /app || echo 'failed'"
docker exec container bash -c "test -f file && echo 'exists'"
```

#### Forbidden Pattern 4: PowerShell-Specific Commands
```bash
# ❌ FORBIDDEN - never use these
Get-Content file.txt
Select-String "pattern" file.txt
Remove-Item file.txt
$variable = docker exec ...

# ✅ CORRECT - use Docker or agent tools instead
docker exec container cat /app/file.txt
# Or better: use view_file tool
```

#### Forbidden Pattern 5: Windows Path Separators Inside Container
```bash
# ❌ FORBIDDEN - backslashes inside container
docker exec container ls d:\Git\project

# ✅ CORRECT - forward slashes inside container
docker exec container ls /app
```

---

### Quick Reference Table

| Pattern | Permitted? | Example |
|---------|------------|---------|
| Simple `docker exec` | ✅ Yes | `docker exec container python script.py` |
| `docker exec` with `bash -c "..."` | ✅ Yes | `docker exec container bash -c "cmd1 \| cmd2"` |
| Pipe (`\|`) outside bash | ❌ No | `docker exec ... \| findstr` |
| Redirect (`2>&1`, `>`) outside bash | ❌ No | `docker exec ... 2>&1` |
| Logical ops (`\|\|`, `&&`) outside bash | ❌ No | `docker exec ... \|\| echo` |
| PowerShell cmdlets | ❌ No | `Select-String`, `Get-Content` |
| Agent file tools | ✅ Yes (Preferred) | `view_file`, `grep_search`, `list_dir` |

---

### Why These Restrictions Exist

The IDE extension (Gemini Code Assist) has built-in security heuristics that flag "complex" shell patterns as potentially dangerous. When it sees pipes, redirects, or logical operators **at the PowerShell level**, it triggers an approval prompt regardless of `SafeToAutoRun: true`.

**The solution:** Keep everything inside Docker's bash shell. When the extension sees a single `docker exec ... bash -c "..."` command, it doesn't analyze the contents of the bash string, so it auto-approves.

---

### Container Limitations

> **Note:** The `head` and `tail` commands are not available in the minimal Docker container. Use Python or `cat` with `grep` for file inspection instead. Better yet, use the agent's `view_file` tool with line ranges.

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

### Required Content Structure

Every implementation plan must include the following sections:

#### 2.0 Table of Contents

#### 2.1 Executive Summary
- **The Problem:** What issue are we solving?
- **The Solution:** High-level overview (1-2 sentences)
- **Impact:** What changes when this is done?

#### 2.2 Diagrams & Visualizations
- Use ASCII diagrams to illustrate architecture, data flow, or patterns
- Visual representations help both humans and AI agents understand relationships
- Example:
  ```
  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
  │  Component  │ ───▶│  Component  │ ───▶ │  Component  │
  └─────────────┘      └─────────────┘      └─────────────┘
  ```

#### 2.3 Proposed Changes
- Group files by component or package
- For each file, specify:
  - **Action:** `[NEW]`, `[MODIFY]`, or `[DELETE]`
  - **File path:** Absolute path
  - **Description:** What changes and why
- Example:
  ```markdown
  ### Component: Core
  
  #### [NEW] protocols.py
  - Path: `src/core/protocols.py`
  - Description: Defines CloudProvider and DeployerStrategy protocols
  ```

#### 2.4 Code Examples
- Provide **before/after** code snippets for significant changes
- Include complete function signatures and key implementation details
- AI agents should be able to implement from these examples

#### 2.5 Migration/Implementation Phases
- Break work into phases
- Each phase should be independently verifiable
- Use tables to show steps:
  ```markdown
  | Step | File | Action |
  |------|------|--------|
  | 1.1  | `src/core/__init__.py` | Create empty package |
  ```

#### 2.6 Verification Checklist
- List all tests that must pass
- Include manual verification steps
- Provide Docker commands for running tests

#### 2.7 Design Decisions (if applicable)
- Document user-approved decisions
- Explain trade-offs considered
- Record reasoning for future reference

### Example Template

```markdown
# [Task Name]

## 1. Executive Summary
### The Problem
[Description of the issue]

### The Solution
[High-level solution]

---

## 2. Current State
[Diagrams and description of current architecture]

---

## 3. Proposed Changes

### Component: [Name]

#### [NEW/MODIFY/DELETE] [filename]
- **Path:** `absolute/path/to/file`
- **Description:** [What changes]

---

## 4. Implementation Phases

### Phase 1: [Name]
| Step | File | Action |
|------|------|--------|
| 1.1  | ... | ... |

---

## 5. Verification Checklist
- [ ] All existing tests pass
- [ ] New tests pass
- [ ] Manual verification complete

---

## 6. Design Decisions
[Documented decisions and reasoning]
```

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
- Tests go in `tests/` mirroring `src/` structure
- Use pytest fixtures from `conftest.py`

#### Running Tests
**DO NOT RUN E2E TESTS UNLESS THE USER EXPLICITLY TELLS YOU TO.** E2E tests in `tests/e2e/` make real API calls to cloud providers and deploy real resources that cost money.

```bash
# Standard test run - USE THIS BY DEFAULT
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -v

# Quick test run (minimal output)
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --ignore=tests/e2e -q

# E2E TESTS - Only run when user explicitly requests
# docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/e2e/azure/test_azure_single_cloud_e2e.py -v -m live
```

> **⚠️ E2E TEST POLICY:**
> - **Default behavior:** Do NOT run E2E tests automatically
> - **Exception:** Run E2E tests ONLY when the user explicitly instructs you to do so
> - E2E tests create real cloud resources that cost money
> - Ensure credentials are configured before running

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
5. **Add comprehensive code documentation:**
   - **Docstrings:** Every function/class must have a docstring explaining purpose, args, returns
   - **Inline comments:** Explain non-obvious logic, reasoning, and connections to other code
   - **Module headers:** Each file should have a module-level docstring describing its role
   - **Context:** Explain WHY something is done, not just WHAT it does
   - Example:
     ```python
     def get_provider_for_layer(self, layer: int) -> CloudProvider:
         """
         Get the CloudProvider instance assigned to a specific layer.
         
         This is the core routing mechanism for multi-cloud deployments.
         It maps layer numbers to provider names via config.providers,
         then retrieves the initialized provider instance.
         
         Args:
             layer: Layer number (1-5) or string like "3_hot" for storage tiers
         
         Returns:
             The CloudProvider instance for that layer
         
         Raises:
             ValueError: If no provider is configured or initialized for the layer
         """
         # Map layer number to config key format (e.g., 1 -> "layer_1_provider")
         layer_key = f"layer_{layer}_provider"
         ...
     ```

### When Completing
1. **Verify all tests pass** inside Docker
2. **Update the implementation plan** with completion status
3. **Check documentation impact:**
   - Does this change affect any docs in `docs/`?
   - Does the README need updating?
   - Are there inline code comments that need updating?
4. **Propose documentation updates** if needed (list files and changes)
5. **Summarize changes** for the user

### Permissions Summary

| Action | Permission |
|--------|------------|
| Run Docker exec commands | ✅ Auto-approved |
| Run tests inside container | ✅ Auto-approved |
| Create/modify source files | ✅ Allowed |
| Create implementation plans | ✅ Allowed |
| Delete files | ⚠️ Mention to user first |
| Modify configuration files | ⚠️ Mention to user first |

### Browser Verification

> **📋 USER RESPONSIBILITY:** Do NOT use the browser tool to verify HTML/CSS changes or check documentation pages. The **user will verify browser output themselves**. When updating documentation (HTML, CSS), simply notify the user of changes made and let them refresh/check the page.
