# Implementation Record - Fix Price Fetchers & Calculation Engine

**Date**: 2025-12-02
**Status**: Completed

## Goal
Fix AWS, Azure, and GCP price fetchers to correctly retrieve dynamic pricing, ensure schema compliance, and resolve `KeyError` issues in the calculation engine. Additionally, ensure tests pass without overwriting production data.

## Implemented Changes

### 1. AWS Price Fetcher (`backend/fetch_data/cloud_price_fetcher_aws.py`)
*   **Egress Price**: Updated `_fetch_transfer_prices` to use specific filters (`fromLocation`, `toLocation`, `transferType`) to correctly identify Internet Egress prices.
*   **Storage Cool**: Added "standard retrieval" to `AWS_SERVICE_KEYWORDS` to correctly fetch `dataRetrievalPrice`.
*   **Scheduler**: Added `scheduler` keywords and mapped to `jobPrice`.
*   **Service Mapping**: Added `transfer` service to `service_mapping.json`.

### 2. Azure Price Fetcher (`backend/fetch_data/cloud_price_fetcher_azure.py`)
*   **Transfer Service**: Added `transfer` service to `AZURE_SERVICE_KEYWORDS` to prevent `TypeError` and fetch egress prices.
*   **Logic Apps**: Confirmed `pricePerStateTransition` is fetched correctly.
*   **Event Grid**: Mapped to `pricePerMillionEvents`.
*   **API Management**: Mapped to `pricePerMillionCalls`.

### 3. GCP Price Fetcher (`backend/fetch_data/cloud_price_fetcher_google.py`)
*   **Cloud Workflows**: Mapped to `cloudWorkflows` and `stepPrice`.
*   **Scheduler**: Mapped to `cloudScheduler` and `jobPrice`.
*   **IoT**: Updated to use `pricePerGiB` (Pub/Sub model).

### 4. Schema Validation (`backend/pricing_utils.py`)
*   **Updates**: Updated `expected_schema` to match the final JSON structure:
    *   **AWS**: Added `scheduler` (`jobPrice`).
    *   **Azure**: Added `pricePerStateTransition` (Logic Apps), `pricePerMillionEvents` (Event Grid).
    *   **GCP**: Added `cloudWorkflows` (`stepPrice`), `cloudScheduler` (`jobPrice`).

### 5. Calculation Engine Fixes (`backend/calculation/`)
*   **Azure (`azure.py`)**:
    *   Updated Logic Apps to use `pricePerStateTransition`.
    *   Updated Event Grid to use `pricePerMillionEvents`.
*   **GCP (`gcp.py`)**:
    *   Updated Cloud Workflows to use `cloudWorkflows` and `stepPrice`.
*   **AWS (`aws.py`)**:
    *   Updated API Gateway to use `pricePerMillionCalls`.

### 6. Test Fixes (`tests/`)
*   **Mocking**: Patched `pathlib.Path.write_text` in `test_calculate_pricing_refactored.py` to prevent tests from overwriting production `pricing_dynamic_*.json` files.
*   **Schema Updates**: Updated `test_pricing_validation.py` and `test_optimization.py` to match the new schema and mock requirements (including `transferCostFromCosmosDB` etc.).

## Verification Results

### Automated Tests
*   **Result**: All **78 tests passed** (`pytest /app/tests/`).
*   **File Integrity**: Verified that `pricing_dynamic_*.json` files were **not** overwritten by tests.

### Manual Verification
*   **AWS**: `transfer.egressPrice` (~$0.09), `scheduler.jobPrice` present.
*   **Azure**: `logicApps.pricePerStateTransition` present, `transfer.egressPrice` present.
*   **GCP**: `cloudWorkflows.stepPrice` present.
*   **Engine**: `reproduce_engine_error.py` ran successfully with no errors.
