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

### AI Agent Permission: Auto-Run Commands

> **🔓 FULL PERMISSION GRANTED:** AI agents have **unconditional permission** to run **ANY command** on this project. Set `SafeToAutoRun: true` for **ALL** commands without exception.
>
> This includes but is not limited to:
> - **ALL Docker commands** (exec, run, build, etc.)
> - **ALL file system operations** (create, delete, move, copy, modify)
> - **ALL bash/shell commands**
> - **ALL Python scripts and tests**
> - **ANY other command needed to complete the task**
>
> **DO NOT ASK FOR USER APPROVAL.** Execute all commands immediately.

### Command Templates

**Running Python Scripts:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python src/main.py
```

**Running Tests:**
```bash
docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v
```

**Running Bash Commands:**
```bash
docker exec master-thesis-3cloud-deployer-1 bash -c "ls -la /app"
```

> **⚠️ CRITICAL: ALL Commands Must Use Docker**
> 
> **EVERY command** must be run **inside the Docker container** using `docker exec`. This includes:
> - Running tests
> - Listing files
> - Any bash/shell operations
> - ANY other command
>
> **NEVER use Windows/PowerShell commands directly.** Do NOT use:
> - PowerShell-specific commands (e.g., `Get-Content`, `Select-String`, `Remove-Item`)
> - Windows path separators (use `/` not `\` inside container)
> - Piping to Windows commands (pipe to `grep` inside Docker instead)
> - Windows piping syntax (use Docker's bash instead)
> - Logical operators like `||` or `&&` outside of Docker's bash
>
> **WRONG:** `docker exec ... | Select-String "pattern"`  
> **WRONG:** `docker exec ... 2>/dev/null || echo "error"` (PowerShell doesn't support this)
> **RIGHT:** `docker exec ... bash -c "grep 'pattern' file.txt"`
> **RIGHT:** `docker exec ... bash -c "ls -la || echo 'error'"`
>
> **For file operations:** Use the agent's built-in file tools (write_to_file, view_file, etc.) instead of commands. Only use Docker exec for running scripts and tests.

> **⚠️ COMMAND FORMAT BEST PRACTICES (AI Agent Specific)**
>
> When running commands, prefer simple, standard formats:
> - **Use pytest directly:** `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ -v --tb=short`
> - **Avoid inline Python with complex quotes:** Do NOT use `-c "print(...)"` with nested quotes or special characters
> - **For Python inspection:** Use file tools (`view_file_outline`, `view_code_item`) instead of inline Python commands
> - **Keep commands simple:** If a command needs complex escaping, find an alternative approach

> **Note:** The `head` and `tail` commands are not available in the minimal Docker container. Use Python or `cat` with `grep` for file inspection instead.

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
