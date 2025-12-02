# Implementation Plan - Fix Price Fetchers & AWS Scheduler

**Goal**: Fix AWS and GCP price fetchers to correctly retrieve dynamic pricing for Egress, Lambda/Functions, and IoT (Pub/Sub for GCP), ensure known static values are returned by the fetchers (logged as INFO), and implement AWS Scheduler pricing.

**Scope**: This plan affects **only** the data fetching layer (`backend/fetch_data/`, `json/service_mapping.json`). The calculation logic (`backend/calculation/`) is **out of scope** for this iteration.

## User Review Required
> [!NOTE]
> **Logging Strategy**: 
> *   **Fetchers**: Will return static defaults for fields known to be static (e.g., Free Tiers), logging them as `INFO`.
> *   **Calculation Script**: Will continue to log `WARNING` if a value is missing from the fetcher output, as this indicates a failure to fetch or default correctly.

> [!IMPORTANT]
> **AWS Scheduler**: I will investigate the correct Service Code. "EventBridge" (currently in mapping) might need to be `AWSEvents` or `AmazonEventBridge`. I will verify this during implementation.

## Proposed Changes

### 1. Architecture Principle: Fetcher Responsibility
*   **Rule**: Fetchers (`cloud_price_fetcher_*.py`) must return a **complete** dictionary for the requested service.
*   **Mechanism**:
    1.  Try to fetch dynamic prices.
    2.  If a key is missing but exists in `STATIC_DEFAULTS`, use the default and log **INFO** ("Using static value...").
    3.  Return the merged dictionary.
*   **Result**: `calculate_up_to_date_pricing.py` receives all data. If it still finds a missing key, it correctly logs **WARNING** ("Using fallback..."), indicating a true failure (neither fetched nor static default found).

### 2. GCP Price Fetcher (`backend/fetch_data/cloud_price_fetcher_google.py`)

#### [MODIFY] Merge Logic (CRITICAL FIX)
*   **Problem**: Currently, the fetcher returns *only* fetched values, relying on the calculator for defaults. This causes the calculator to warn.
*   **Fix**: Implement the merge logic at the end of `fetch_gcp_price`:
    ```python
    defaults = STATIC_DEFAULTS_GCP.get(neutral_service, {})
    for k, v in defaults.items():
        if k not in fetched:
            fetched[k] = v
            logger.info(f"   ℹ️ Using static value for GCP.{neutral_service}.{k}")
    ```

#### [MODIFY] `GCP_SERVICE_KEYWORDS`
*   **IoT**: Update to match **Cloud Pub/Sub** (Ingestion/Message Delivery).
    *   `pricePerGiB`: Match "Message Delivery" or "Ingestion".
*   **Transfer**: Update to match **Internet Egress**.

### 3. AWS Price Fetcher (`backend/fetch_data/cloud_price_fetcher_aws.py`)

#### [MODIFY] `AWS_SERVICE_KEYWORDS` & Fetching Logic
*   **Lambda**: Fix `requestPrice` fetching (keywords).
*   **Transfer**: Fix `egressPrice` fetching (usagetype filter).

#### [MODIFY] `STATIC_DEFAULTS`
*   **Fix**: Ensure `STATIC_DEFAULTS` contains *all* keys that are expected to be static (e.g., `iotCore.pricePerDeviceAndMonth`).

### 4. AWS Scheduler Implementation

#### [MODIFY] `json/service_mapping.json`
*   **Investigation**: Verify if `EventBridge` is the correct service code. It is likely `AWSEvents` (same as Event Bus).
*   **Fix**: Update `scheduler.aws` to the correct code (e.g., `AWSEvents`).

#### [MODIFY] `backend/fetch_data/cloud_price_fetcher_aws.py`
*   **Fix**: Add `scheduler` keywords (EventBridge Scheduler) and map to `jobPrice`.
    *   Keywords: "Scheduler", "Scheduled", "Invocation".

#### [MODIFY] `backend/fetch_data/calculate_up_to_date_pricing.py`
*   **Fix**: Add `scheduler` schema build logic to `fetch_aws_data`.

### 5. Key Alignment (`backend/fetch_data/calculate_up_to_date_pricing.py`)

#### [MODIFY] Key Access
*   **Fix**: Update `_get_or_warn` calls to match fetcher output keys.
    *   **GCP IoT**: Change lookup from `pricePerMessage` to `pricePerGiB` (to correctly read the value returned by the fetcher). *Note: The output key in the JSON will remain `pricePerGiB` as per the GCP schema.*

## Verification Plan

### Automated Tests
*   Run `debug_engine_real_data.py` (regenerates pricing).
*   **Success Criteria**:
    *   **GCP**: `iot.pricePerGiB` is > 0 (fetched from Pub/Sub).
    *   **AWS**: `lambda.requestPrice` and `transfer.egressPrice` are > 0.
    *   **AWS**: `scheduler.jobPrice` is populated.
    *   **Logs**: 
        *   "ℹ️ Using static value" for known static fields (from fetcher).
        *   NO "⚠️ Using fallback" warnings (from calculation script).

### Manual Verification
*   Inspect `pricing_dynamic_gcp.json` and `pricing_dynamic_aws.json` to confirm values match expected ranges.
*   **Stop Point**: Do not proceed to verify calculation logic (`engine.py`) until this step is approved and verified.
