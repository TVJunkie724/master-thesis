# Fix AWS Step Functions Pricing

## Goal Description
Fix the miscalculation of AWS Step Functions costs where the price per state transition is 1,000x lower than actual pricing due to a unit mismatch in the fetched data.

## Proposed Changes

### Backend (`backend/fetch_data/calculate_up_to_date_pricing.py`)
#### [MODIFY] [calculate_up_to_date_pricing.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/fetch_data/calculate_up_to_date_pricing.py)
- In the `fetch_aws_data` function, specifically for the `orchestration` (Step Functions) section:
    - Add a sanity check for `pricePer1kStateTransitions`.
    - If the value is suspiciously low (e.g., < 0.001), assume it represents the "per transition" price (or is 1000x too small) and multiply it by 1,000 to normalize it to "Price Per 1,000 Transitions" ($0.025).
    - Ensure `pricePerStateTransition` is calculated correctly from this normalized value.

## Verification Plan

### Automated Verification
1.  **Run Pricing Update:** Run `docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python backend/fetch_data/calculate_up_to_date_pricing.py aws`.
2.  **Check Output:** Inspect `json/fetched_data/pricing_dynamic_aws.json`.
    - Verify `stepFunctions.pricePer1kStateTransitions` is approx `0.025` (not `0.000025`).
    - Verify `stepFunctions.pricePerStateTransition` is approx `0.000025`.

### Manual Verification
1.  **UI Calculation:**
    - Select **Preset 3** in the UI.
    - Verify that AWS Layer 3 costs are now in the millions (comparable to GCP), rather than ~€1,000.
