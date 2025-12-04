# Implementation Plan - Enhance Calculation Logic & UI Accuracy

## Goal Description
The goal is to refine the cost calculation engine to support "unlocked" optimization for Layer 2 (Hot Storage) and Layer 3 (Data Processing). Currently, the system "locks" L2 and L3 to the same provider to minimize data transfer costs (Data Gravity). However, recent investigations reveal that in certain high-data scenarios (e.g., Preset 2), a cross-cloud approach (e.g., Azure Storage + AWS Processing) can be cheaper even after accounting for transfer and glue code costs.

This plan outlines the changes to:
1.  **Unlock L2-L3 Optimization:** Calculate all 9 combinations of L2 Hot + L3, including transfer and glue costs, to find the true global minimum.
2.  **Refine UI Highlighting:** Ensure the UI correctly reflects the selected path, even if it involves cross-cloud jumps.
3.  **Document Findings:** Record the investigation results that led to this decision.

## User Review Required
> [!IMPORTANT]
> **Change in Optimization Logic:** The system will no longer force L2 and L3 to be on the same provider. This may result in "mixed" cloud architectures being recommended more frequently.
> 
> **Impact:** Users may see paths like `L2_Azure -> L3_AWS` as the optimal solution. The UI will need to clearly explain *why* (e.g., "Azure Storage is so cheap it offsets the transfer cost to AWS Lambda").

## Findings & Investigation
An investigation using `debug_unlocked_calc.py` with "Preset 2" (High Data) parameters yielded the following comparison:

| Combination | Total Cost | L2 Cost | L3 Cost | Transfer | Glue Code |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **L2(Azure) + L3(AWS)** | **$1,453.59** | $96.61 | $1,206.23 | $14.54 | $136.21 |
| **L2(AWS) + L3(AWS)** | **$1,522.54** | $316.31 | $1,206.23 | $0.00 | $0.00 |
| L2(GCP) + L3(AWS) | $3,216.80 | $1,854.30 | $1,206.23 | $20.05 | $136.21 |

**Conclusion:** The current "locked" logic selected **L2(AWS) + L3(AWS)** ($1522.54). However, the "unlocked" combination of **L2(Azure) + L3(AWS)** ($1453.59) is cheaper by ~$70/month, even with ~$150 in transfer/glue costs. This confirms that **locking L2 and L3 is suboptimal** when storage cost differences are significant.

## Proposed Changes

### Backend (`backend/calculation/engine.py`)
#### [MODIFY] [engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
-   **Remove Locking Logic:** Instead of summing `L2_AWS + L3_AWS`, iterate through all 9 combinations (`L2_AWS+L3_AWS`, `L2_AWS+L3_Azure`, etc.).
-   **Add Transfer & Glue Costs:** For each cross-cloud combination, calculate and add:
    -   **Egress Cost:** From L2 Provider to L3 Provider (based on data volume).
    -   **Glue Code Cost:** "Reader Function" or "Connector" at L3 to pull data from L2.
-   **Select Global Minimum:** Choose the combination with the absolute lowest total cost.
-   **Update Overrides:** The concept of "L2 Override" (forcing L2 to match L3) becomes obsolete or needs rephrasing as "Cross-Cloud Optimization".

### Frontend (`js/api-client.js`)
#### [MODIFY] [api-client.js](file:///d:/Git/master-thesis/2-twin2clouds/js/api-client.js)
-   **Refine Warnings:**
    -   If a cross-cloud path is chosen (e.g., Azure -> AWS), add a "Cross-Cloud Optimization" note explaining that the savings on storage outweigh the transfer costs.
    -   Remove the "Suboptimal L3" warning if it no longer applies (since we are now truly optimizing).

## Verification Plan

### Automated Tests
-   **New Test Script:** Create `tests/test_unlocked_optimization.py` to verify that:
    -   It selects `L2_Azure + L3_AWS` for Preset 2 parameters.
    -   It selects `L2_AWS + L3_AWS` for scenarios where transfer costs are prohibitive (e.g., very high data volume but low storage duration).

### Manual Verification
-   **Run `debug_calc.py`:** Verify the output matches the new logic.
-   **UI Check:** Ensure the "Cheapest Path" display shows the mixed path (e.g., `L2_Azure_Hot -> L3_AWS`) and cards are highlighted correctly.
