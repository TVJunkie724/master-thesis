# Implementation Plan - Pricing Schema Validation

## Goal Description
Enhance the file age endpoints to also validate the JSON schema of the pricing files. Ensure that the pricing files for AWS, Azure, and GCP contain all expected keys and subkeys.

## User Review Required
> [!IMPORTANT]
> The validation logic will be strict. If a key is missing, the file status will be marked as "incomplete". This might flag existing files as incomplete if they were generated with an older version of the fetcher, prompting a re-fetch.

## Proposed Changes

### Backend Utilities
#### [MODIFY] [pricing_utils.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/pricing_utils.py)
- Implement `validate_pricing_schema(provider: str, data: dict) -> dict`
    - Input: Provider name ('aws', 'azure', 'gcp') and the loaded JSON data.
    - Output: A dictionary with `status` ("valid", "incomplete", "missing") and `missing_keys` (list of strings).
    - Logic: Define the expected schema for each provider (based on `calculate_up_to_date_pricing.py`) and recursively check for existence of keys.

### Pricing Calculation
#### [MODIFY] [calculate_up_to_date_pricing.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/fetch_data/calculate_up_to_date_pricing.py)
- Import `validate_pricing_schema` from `backend.pricing_utils`.
- After fetching data (and before saving), call `validate_pricing_schema`.
- Log a warning if the schema is incomplete, listing the missing keys. This provides immediate feedback during the fetch process.

### REST API
#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- Update `GET /api/pricing_age/{provider}` endpoints.
    - Load the pricing file content.
    - Call `validate_pricing_schema`.
    - Return a JSON response including:
        - `age`: File age string (existing).
        - `status`: Validation status.
        - `missing_keys`: List of missing keys (if any).

## Verification Plan

### Automated Tests
- **Unit Tests**: Create `tests/test_pricing_validation.py` to test `validate_pricing_schema` with valid, incomplete, and malformed data.
- **Integration Tests**: Update `tests/test_rest_api_endpoints.py` to verify the new response structure of the pricing age endpoints.

### Manual Verification
- Trigger a pricing fetch (to generate valid files) and check the endpoint response.
- Manually corrupt a pricing file (remove a key) and verify the endpoint reports it as incomplete.
