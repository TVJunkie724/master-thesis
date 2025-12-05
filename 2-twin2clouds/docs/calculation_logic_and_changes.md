# Calculation Logic & Recent Changes

## 1. Transfer Cost Reasoning

A key part of the optimization logic involves understanding when data transfer costs apply. The system distinguishes between **Service Transfers** and **Tier Changes**.

### Hot &rarr; Cool (Service Transfer)
*   **Scenario:** Moving data from a Hot Storage service (e.g., Azure Cosmos DB) to a separate Cool Storage service (e.g., Azure Blob Storage).
*   **Cost:** **Non-Zero**. Even within the same cloud provider, moving data between completely different services often incurs ingestion or transfer fees.
*   **Example (Azure):**
    *   Cosmos DB &rarr; Blob Storage
    *   Cost: ~$870 (for the specific data volume in Preset 3).
    *   *Reasoning:* This is an actual data movement operation between distinct services.

### Cool &rarr; Archive (Tier Change)
*   **Scenario:** Moving data from Cool Storage (e.g., Azure Blob Storage Cool Tier) to Archive Storage (e.g., Azure Blob Storage Archive Tier).
*   **Cost:** **Zero ($0.00)**.
*   **Reasoning:** This is typically a lifecycle policy change within the *same* service (Blob Storage). The data doesn't physically move "over the wire" in a way that incurs egress fees; it just changes its billing class.

### The Optimization Result
This distinction explains why the system sometimes prefers a **Cross-Cloud** path over a **Single-Cloud** path.

*   **Azure Only Path:** `Azure (Hot) -> Azure (Cool) -> Azure (Archive)`
    *   Incurs the ~$870 internal transfer fee (Cosmos -> Blob).
    *   Total: ~$2677.
*   **Cross-Cloud Path:** `Azure (Hot) -> GCP (Cool) -> GCP (Archive)`
    *   Incurs a similar transfer fee (Egress to GCP), but GCP's storage or other costs might be slightly lower overall, or the combination results in a lower total.
    *   Total: ~$2523.

## 2. Changes Implemented Today

### UI Refactoring
*   **Modularization:** Moved UI-specific logic (HTML generation, alerts) from `api-client.js` to a new `js/ui-components.js` file.
*   **Script Loading:** Updated `index.html` to load scripts in the correct dependency order (`ui.js` &rarr; `ui-components.js` &rarr; `api-client.js`).

### Detailed Cost Breakdowns
*   **L1 & L4 Warnings:** Implemented `generateDetailedComparisonTable` to show a granular breakdown of costs:
    *   **Base Cost:** The core service cost.
    *   **Glue Code:** Cost of Lambda/Functions needed for integration.
    *   **Data Transfer:** Egress/Ingestion fees.
    *   **Total:** The sum used for decision making.

### UI Enhancements
*   **Row Highlighting:** Updated all optimization tables (L1, L2, L4) to highlight the row corresponding to the **selected** provider/path.
    *   Uses `table-success` (green) for visibility.
    *   **Logic Fix:** Refined the highlighting logic for "Cool" and "Archive" tables to strictly match the full path (e.g., `Azure -> GCP -> GCP`) rather than loosely matching provider names, preventing false positives.

### Calculation Logic Fix (Backend)
*   **Discrepancy Fixed:** The UI tables for "Cool Storage" were previously showing **$0.00** for intra-cloud transfers (e.g., Azure Hot &rarr; Azure Cool), while the backend optimization engine was correctly calculating a cost.
*   **The Fix:** Updated `backend/calculation/engine.py` to use the centralized `transfer_costs` dictionary for generating the UI table data.
*   **Result:** The UI tables now accurately reflect the costs used by the algorithm, explaining why a single-cloud path might be more expensive than expected.
