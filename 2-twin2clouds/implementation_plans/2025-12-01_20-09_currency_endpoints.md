# Implementation Plan - Currency Endpoints

## Goal Description
Add API endpoints to expose currency file age and trigger currency rate fetching.

## Proposed Changes

### REST API
#### [MODIFY] `rest_api.py`
- Implement `GET /api/currency_age`
    - Returns the age of `currency.json`.
- Implement `POST /api/fetch_currency`
    - Calls `pricing_utils.get_currency_rates()` to fetch fresh rates.
    - Returns the fetched rates.

## Verification Plan
- Add integration tests in `tests/test_rest_api_endpoints.py`.
- Verify endpoints using `pytest` in Docker.
