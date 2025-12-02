# Implementation Plan - Add Force Fetch to Region Endpoints

## Goal
Add a `force_fetch` parameter to the AWS, Azure, and GCP region fetching endpoints in `rest_api.py`. This allows users to choose between using cached region data (if fresh) or forcing a refresh from the cloud provider APIs.

## User Review Required
> [!NOTE]
> This change aligns the region fetching behavior with the pricing fetching behavior.
> Default behavior will change: currently it always forces update. New default will be to use cache if fresh.

## Proposed Changes

### 1. Update Region Endpoints
#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- [x] Update `fetch_regions_aws`, `fetch_regions_azure`, `fetch_regions_gcp`.
- [x] Add `force_fetch: bool = False` parameter.
- [x] Implement cache check logic using `is_file_fresh` and `CONSTANTS.*_REGIONS_FILE_PATH`.
- [x] Return cached data if valid and `force_fetch` is False.
- [x] Call `fetch_region_map(force_update=True)` if cache is stale or `force_fetch` is True.

## Verification Plan
### Automated Tests
- [x] `pytest tests/test_rest_api_endpoints.py` (updated to mock `is_file_fresh`).

### Manual Verification
- [x] Check Swagger UI (`/docs`) to see `force_fetch` parameter.
- [x] Test endpoints with `force_fetch=False` (should use cache if fresh).
- [x] Test endpoints with `force_fetch=True` (should trigger fetch).
