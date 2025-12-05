# Implementation Plan - Enhance API Documentation

## Goal
Add detailed, Swagger-compatible documentation to all API endpoints in `rest_api.py`. This includes adding `summary`, `description`, and `response_description` to decorators, and improving docstrings.

## User Review Required
> [!NOTE]
> This is a documentation-only change. No logic will be altered.

## Proposed Changes

### 1. Enhance Endpoint Documentation
#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- **Pricing Endpoints**:
    - [x] `fetch_pricing_aws`, `fetch_pricing_azure`, `fetch_pricing_gcp`: Add details about caching behavior, `force_fetch` parameter, and return structure.
- **Region Endpoints**:
    - [x] `fetch_regions_aws`, `fetch_regions_azure`, `fetch_regions_gcp`: Add details about caching, `force_fetch`, and the region map format.
- **File Status Endpoints**:
    - [x] `get_regions_age_*`: Explain the return format (age string).
    - [x] `get_pricing_age_*`: Explain the return format (age, status, missing keys) and validation logic.
    - [x] `get_currency_age`: Explain return format.
- **Currency Endpoints**:
    - [x] `fetch_currency_rates`: Explain source (ECB via `forex-python` or similar) and return format.

## Verification Plan
### Manual Verification
- [x] Code review to ensure all endpoints have rich descriptions.
- [x] (User Action) Check Swagger UI (`/docs`) to verify the rendered documentation.
