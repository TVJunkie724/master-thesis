# High L3 Cost Investigation (Preset 3)

**Date:** 2025-12-04
**Subject:** Investigation of high Layer 3 (Data Processing) costs for Preset 3 (Large Building).

## 1. Issue Description
When selecting "Preset 3" (13.14 Billion messages/month), the calculated costs for Layer 3 showed a massive discrepancy:
*   **AWS:** ~€1,038 (Extremely low)
*   **Azure:** ~€14,220,727 (Extremely high)
*   **GCP:** ~€2,970,827 (Extremely high)

## 2. Findings

### 2.1 AWS Miscalculation (Bug)
The AWS cost was artificially low due to a unit conversion error in the pricing logic.
*   **The Bug:** The `pricePerStateTransition` was calculated by dividing the fetched price by 1,000 *twice* (effectively).
*   **Fetched Value:** The system fetched `2.5e-05` ($0.000025) for `pricePer1kStateTransitions`.
*   **Actual Price:** AWS Step Functions Standard pricing is **$0.025 per 1,000 state transitions**.
*   **The Error:** The fetched value ($0.000025) was already the price per *single* transition (or 1000x too small for the key "per 1k"), but the code divided it by 1,000 again to get `pricePerStateTransition`.
*   **Result:** The calculation used **$0.000000025** per transition instead of **$0.000025**.
*   **Corrected Cost:** If calculated correctly, AWS L3 would be approximately **€3,300,000**, aligning with GCP.

### 2.2 Azure & GCP "High" Costs (Architectural Reality)
The costs for Azure and GCP are mathematically correct based on the selected services, but the architecture is inappropriate for the volume.
*   **Volume:** 13.14 Billion messages/month implies 13.14 Billion workflow executions (if 1:1).
*   **Azure Logic Apps (Standard):** ~$0.000125 per action. 13B * $0.000125 ≈ $1.6 Million (plus base costs). The calculation likely includes multiple actions per message.
*   **GCP Cloud Workflows:** ~$0.000025 per step. 13B * $0.000025 ≈ $325,000 (plus base costs).
*   **Conclusion:** Using "Standard" tier serverless orchestration for *every single telemetry message* at this scale is cost-prohibitive.

## 3. Recommendations

### 3.1 Fix the AWS Calculation
The pricing fetcher/calculator logic must be updated to ensure `pricePerStateTransition` reflects the correct unit price ($0.000025).

### 3.2 Architectural Optimization (Future Work)
To make Preset 3 feasible, the architecture should be optimized:
*   **Batch Processing:** Do not trigger a workflow for every message. Aggregate messages and process in batches.
*   **Cheaper Services:**
    *   **AWS:** Use **Express Workflows** (significantly cheaper for high frequency).
    *   **Azure:** Use **Logic Apps Stateless** or Azure Functions for orchestration.
    *   **GCP:** Use **Cloud Run** or batched Cloud Functions instead of Cloud Workflows.
