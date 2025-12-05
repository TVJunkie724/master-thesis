# Development Guide & Project Standards

This document outlines the mandatory workflows and standards for working on the Twin2Clouds project. All contributors (human and AI) must adhere to these guidelines to ensure consistency and prevent errors.

## 1. Docker-First Workflow

This project runs most components inside Docker containers. **All commands and tests must be executed inside the Docker container** to ensure environment consistency.

### Main Container: `master-thesis-2twin2clouds-1`

The main application code is mapped to `/app` inside the container.

### Running Python Scripts
To run Python scripts, you must set `PYTHONPATH=/app` to ensure modules are resolved correctly.

```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python py/script_name.py
```

**Example: Running Pricing Calculation**
```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python py/calculate_up_to_date_pricing.py additional_debug=true
```

### Running Bash Commands
To run arbitrary bash commands:

```bash
docker exec master-thesis-2twin2clouds-1 bash -c "ls -la /app"
```

### File Paths
- **Host:** `d:\Git\master-thesis\2-twin2clouds`
- **Container:** `/app`

### Flutter
Flutter projects run locally on the host machine, not in Docker.

## 2. Implementation Plans

- **Creation:** Before starting any significant task, create an implementation plan.
- **Storage:** All implementation plans must be saved in the `implementation_plans/` directory.
- **Naming:** Use a chronological naming convention to keep them ordered (e.g., `YYYY-MM-DD_hh-mm_task_name.md`).
- **Archiving:** Once a task is complete, ensure the plan is updated with completion status (`[x]`) and remains in the archive folder.

## 3. Documentation Updates

**CRITICAL RULE:** When editing any documentation page (HTML files in `docs/`), you must **always replace or update the entire file content**.

- **Do NOT** use partial edits or search/replace on small blocks for HTML documentation.
- **Reasoning:** Partial edits often lead to truncation, corrupted tags, or missing sections due to the complexity of the HTML structure.
- **Procedure:** Read the full file, apply changes in memory, and write the *complete* new content back to the file.
