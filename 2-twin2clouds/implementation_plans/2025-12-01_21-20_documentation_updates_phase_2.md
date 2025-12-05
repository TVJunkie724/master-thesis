# Implementation Plan - Documentation Updates (Phase 2)

## Goal Description
Update the project documentation to reflect the recent architectural changes, including refactored price fetching, new API endpoints (pricing, validation, currency), and the expanded test suite.

## User Review Required
> [!NOTE]
> This plan focuses on updating the HTML documentation files. The "Project Structure" diagram image will not be updated as part of this task, but the surrounding text will be corrected.

## Proposed Changes

### API Reference
#### [MODIFY] [docs-api-reference.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-api-reference.html)
- [x] **Remove** obsolete `GET /api/fetch_up_to_date_pricing`.
- [x] **Add** Provider-specific Pricing Fetch endpoints:
    - `POST /api/fetch_pricing/aws`
    - `POST /api/fetch_pricing/azure`
    - `POST /api/fetch_pricing/gcp`
- [x] **Add** File Age & Validation endpoints:
    - `GET /api/pricing_age/{provider}` (Response includes `status` and `missing_keys`)
    - `GET /api/regions_age/{provider}`
- [x] **Add** Currency endpoints:
    - `GET /api/currency_age`
    - `POST /api/fetch_currency`
- [x] **Add** Region Fetch endpoints:
    - `POST /api/fetch_regions/{provider}`

### Project Structure
#### [MODIFY] [docs-project-structure.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-project-structure.html)
- [x] **Update** `py/fetch_data/` section:
    - Reflect that `calculate_up_to_date_pricing.py` now orchestrates separate fetches.
- [x] **Update** `pricing/fetched_data/` section:
    - List separate pricing files: `pricing_aws.json`, `pricing_azure.json`, `pricing_gcp.json`.
- [x] **Update** `rest_api.py` section:
    - List the new granular endpoints.

### Testing Guide
#### [MODIFY] [docs-testing.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-testing.html)
- [x] **Update** "Test Organization" file tree:
    - Add `test_utils_file_age.py`
    - Add `test_rest_api_endpoints.py`
    - Add `test_calculate_pricing_refactored.py`
    - Add `test_pricing_validation.py`
- [x] **Update** "Integration Tests" section:
    - Mention Schema Validation and API Endpoint testing.

### Setup & Usage
#### [MODIFY] [docs-setup-usage.html](file:///d:/Git/master-thesis/2-twin2clouds/docs/docs-setup-usage.html)
- [x] **Update** "Fetching Pricing Data" section:
    - Explain how to fetch pricing for specific providers.
    - Explain how to fetch currency rates.

## Verification Plan
- **Manual Verification**: Open the HTML files in a browser (or inspect source) to verify the content is accurate and formatted correctly.
