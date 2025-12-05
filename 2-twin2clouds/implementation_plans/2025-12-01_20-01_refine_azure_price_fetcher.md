# Implementation Plan - Refine Azure Price Fetcher

## Goal Description
Fix issues with Azure price fetching to ensure accurate dynamic pricing for Cosmos DB (`storage_hot`) and Blob Storage (`storage_cool`, `storage_archive`), and correct function pricing.

## Proposed Changes

### Price Fetcher
#### [MODIFY] `backend/fetch_data/cloud_price_fetcher_azure.py`
- Fix `functions` price fetching logic (Keywords: "Standard Total Executions", "Always Ready Execution Time").
- Fix `storage_hot` (Cosmos DB) price fetching (Keyword: "Data Stored").
- Implement `_get_or_warn` helper to log when default values are used.
- Ensure `readPrice` and `writePrice` for Blob Storage are correctly converted to per-operation costs.

## Verification Plan
- Run `calculate_up_to_date_pricing.py` with `additional_debug=True`.
- Verify logs for "Using default value" warnings.
- Check `pricing_dynamic.json` for correct values.
