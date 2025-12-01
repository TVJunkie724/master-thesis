# Implementation Plan - Refine Google Cloud Price Fetcher

## Goal Description
Further refine the GCP price fetcher to maximize dynamic fetching and minimize reliance on static defaults.

## Proposed Changes

### Analysis & Debugging
- Analyze `STATIC_DEFAULTS_GCP` to identify fetchable values.
- Create `debug_gcp_comprehensive.py` to inspect API responses.

### Price Fetcher Enhancements
#### [MODIFY] `backend/fetch_data/cloud_price_fetcher_google.py`
- Update `GCP_SERVICE_KEYWORDS` for Firestore, Storage, Network, API Gateway.
- Implement logic to extract free tier limits where possible.
- Fix `computeEngine` fetching.
- Implement `negative_keywords` to exclude Spot/Preemptible instances.
- Reuse `twinmaker` fetched data for `computeEngine`.
- Correctly scale `pricePerMillionCalls` for API Gateway.

## Verification Plan
- Run `debug_gcp_comprehensive.py` to verify keyword matching.
- Run `calculate_up_to_date_pricing.py` and check for reduction in static defaults usage.
