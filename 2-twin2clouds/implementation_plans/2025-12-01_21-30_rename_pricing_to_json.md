# Implementation Plan - Rename Pricing Folder to JSON

## Goal Description
Rename the `pricing/` directory to `json/` to better reflect its content (JSON data files) and standardize the project structure. This involves updating code references, documentation, and tests.

## User Review Required
> [!NOTE]
> This change affects file paths. Any external scripts or manual commands relying on `pricing/` will need to be updated.

## Proposed Changes

### Directory Structure
#### [RENAME] `pricing/` -> `json/`
- Rename the physical directory on the filesystem.

### Backend Configuration
#### [MODIFY] [backend/constants.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/constants.py)
- Change `PRICING_BASE_PATH = Path("pricing")` to `PRICING_BASE_PATH = Path("json")`.

### Tests
#### [MODIFY] [tests/test_pricing_schema.py](file:///d:/Git/master-thesis/2-twin2clouds/tests/test_pricing_schema.py)
- Update `TEMPLATE_PATH` to point to `/app/json/pricing.json`.
- Update docstrings referencing `pricing/pricing.json`.

### Documentation
#### [MODIFY] [README.md](file:///d:/Git/master-thesis/2-twin2clouds/README.md)
- Update all references from `pricing/` to `json/`.

#### [MODIFY] [docs/docs-project-structure.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-project-structure.html)
- Update directory tree descriptions.
- Update file path references in "Data Flow" and "Caching Strategy".

#### [MODIFY] [docs/docs-setup-usage.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-setup-usage.html)
- Update file path references in "Fetching Pricing Data" and "Caching Behavior".

## Verification Plan
### Automated Tests
- Run `pytest` to ensure all tests pass with the new paths.
    - `docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python -m pytest /app/tests/ -v`

### Manual Verification
- Verify that the application starts and can read/write data to the new `json/` directory.
- Check `http://localhost:5003/api/pricing_age/aws` to confirm it can find the files.
