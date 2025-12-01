# Implementation Plan - Fix Test Overwrites, Add Schema Validation & Force Fetch

## Goal
1.  Prevent tests from overwriting production pricing files.
2.  Integrate schema validation into `engine.py` to reject invalid data.
3.  Add `force_fetch` parameter to pricing API endpoints to bypass age checks.
4.  Fix duplicate `calculate_cheapest_costs` function in `engine.py`.

## User Review Required
> [!IMPORTANT]
> I will be modifying `rest_api.py` to add `force_fetch` to pricing endpoints.
> I will modify `engine.py` to reject invalid pricing data and remove duplicate code.

## Proposed Changes

### 1. Prevent Tests Overwriting Files
#### [MODIFY] [test_pricing_orchestration.py](file:///d:/Git/master-thesis/2-twin2clouds/tests/test_pricing_orchestration.py)
- [x] Patch `pathlib.Path.write_text` to prevent file writes.

### 2. Schema Validation & Fix Duplication in Engine
#### [MODIFY] [engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
- [x] Remove duplicate `calculate_cheapest_costs` function (shadowed definition).
- [x] Update the active `calculate_cheapest_costs` to:
    - [x] Use `load_combined_pricing` instead of `load_json_file`.
    - [x] Import `validate_pricing_schema` from `backend.pricing_utils`.
    - [x] Validate the `pricing` dictionary for each provider.
    - [x] If validation fails, raise a `ValueError` with a clear message prompting a refresh.
- [x] Fix missing keys in `calculate_gcp_costs` return dictionary.

### 3. Force Fetch Parameter
#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- [x] Update `/api/fetch_pricing/aws`, `/api/fetch_pricing/azure`, `/api/fetch_pricing/gcp`.
- [x] Add `force_fetch: bool = False` parameter.
- [x] Update logic: `if not force_fetch and is_file_fresh(...)`.

## Verification Plan
### Automated Tests
- [x] `pytest tests/test_pricing_orchestration.py` (verify no file overwrite).
- [x] `pytest tests/test_optimization.py` (verify engine validation logic and calculation).

### Manual Verification
- [x] Check Swagger UI (`/docs`) to see `force_fetch` parameter.
