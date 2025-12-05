# Implementation Plan: Restore Utility Functions

**Date:** 2025-12-05
**Task:** Restore `resolve_folder_path` and update zip utilities in `src/util.py`.

## Goal
Improve path handling robustness by restoring the original `resolve_folder_path` helper function. This replaces the brittle, manual path manipulation logic currently in place.

## Analysis
-   **Current State:** `compile_lambda_function` manually strips drive letters to handle absolute paths. `zip_directory` assumes paths are relative to project root.
-   **Desired State:** `resolve_folder_path` intelligently handles both relative and absolute paths, verifying existence before proceeding.
-   **Benefits:**
    -   Host/Container OS independence (Windows/Linux).
    -   Better error reporting (`FileNotFoundError`).
    -   Cleaner code.

## Proposed Changes

### `src/util.py`

#### 1. Add `resolve_folder_path`
```python
def resolve_folder_path(folder_path):
  rel_path = os.path.join(globals.project_path(), folder_path)

  if os.path.exists(rel_path):
    return rel_path

  abs_path = os.path.abspath(folder_path)

  if os.path.exists(abs_path):
    return abs_path

  raise FileNotFoundError(
    f"Folder '{folder_path}' does not exist as relative or absolute path."
  )
```

#### 2. Update `zip_directory`
```python
def zip_directory(folder_path, zip_name='zipped.zip'):
  folder_path = resolve_folder_path(folder_path) # <--- Use helper
  output_path = os.path.join(folder_path, zip_name)

  with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(folder_path):
      for file in files:
        full_path = os.path.join(root, file)
        if full_path == output_path:
          continue
        arcname = os.path.relpath(full_path, start=folder_path)
        zf.write(full_path, arcname)

  return output_path
```

#### 3. Clean `compile_lambda_function`
```python
def compile_lambda_function(folder_path):
  zip_path = zip_directory(folder_path)

  with open(zip_path, "rb") as f:
    zip_code = f.read()

  return zip_code
```

## Verification Plan
-   Run existing tests: `docker exec master-thesis-3cloud-deployer-1 pytest -v tests/`
-   Ensure all tests (especially `aws/test_core_deployer_aws.py` which triggers this logic) pass.
