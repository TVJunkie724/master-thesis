# Implementation Plan - Refactoring Price Fetching

## Goal Description
Refactor the price fetching logic to decouple it from the calculation engine, allowing for independent updates and cleaner architecture.

## Proposed Changes

### Configuration Loader
#### [MODIFY] `backend/config_loader.py`
- Implement `load_combined_pricing` to load pricing from separate files (`pricing_aws.json`, `pricing_azure.json`, `pricing_gcp.json`).

### Calculation Engine
#### [MODIFY] `backend/calculation/engine.py`
- Update to use `load_combined_pricing`.
- Handle missing pricing data gracefully.

### REST API
#### [MODIFY] `rest_api.py`
- Update endpoints to use `load_combined_pricing`.
- Refactor fetch endpoints to target specific providers.

## Verification Plan
- Verify that `calculate_up_to_date_pricing.py` generates separate files.
- Verify that the API still calculates costs correctly using the new loading mechanism.
