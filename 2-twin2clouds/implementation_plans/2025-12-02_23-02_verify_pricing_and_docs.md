# Implementation Plan - Verify Pricing & Document Calculation

**Goal**: Verify the accuracy of the cost calculation engine by cross-referencing deployment docs, pricing formulas, and actual code. Create a new "Calculation Logic" documentation page to transparently explain the implemented model.

## User Review Required
> [!IMPORTANT]
> **Verification Scope**: I will check if the `engine.py` logic covers all resources mentioned in the deployment guides and uses the formulas described in `docs-formulas.html`. Any discrepancies will be noted and fixed or documented.

## Proposed Changes

### 1. Verification Phase
*   **Analyze Deployment Docs**: Review `docs-*-deployment.html` to list all deployed resources (e.g., IoT Hub, Functions, Storage, Event Grid).
*   **Analyze Formulas**: Review `docs-formulas.html` to understand the intended cost models.
*   **Analyze Code**: Audit `backend/calculation/` (`engine.py`, `aws.py`, `azure.py`, `gcp.py`) to ensure:
    *   All deployed resources are accounted for.
    *   Formulas match the documentation.
    *   Pricing keys match `pricing_dynamic_*.json`.
    *   Units are handled correctly (e.g., per million vs per unit).

### 2. Documentation Phase
*   **Create `docs/docs-calculation-logic.html`**:
    *   **Overview**: High-level explanation of the optimization algorithm (Graph-based shortest path).
    *   **Step-by-Step Flow**:
        1.  **Ingestion (L1)**: IoT Core/Hub -> Connector Function.
        2.  **Hot Storage (L2)**: DynamoDB/Cosmos/Firestore.
        3.  **Querying (L3)**: API Gateway + Reader Function.
        4.  **Visualization (L4)**: TwinMaker/Grafana.
        5.  **Cold/Archive Storage (L5)**: S3/Blob/Storage.
    *   **Detailed Formulas**: Breakdown of how each component's cost is calculated, referencing the specific Python functions.
    *   **Decision Logic**: Explain how the "Cheapest Path" is determined (e.g., comparing L1 options, Storage Transfer costs).
*   **Update Navigation**: Add "Calculation Logic" to the sidebar/menu in all `docs/*.html` files.

## Verification Plan

### Automated Tests
*   Run `tests/test_calculation_scenarios.py` to ensure the documented logic matches the test expectations.

### Manual Verification
*   The new documentation page itself serves as a verification artifact. If I can describe it accurately based on the code, and it makes sense, the verification is successful.

## Verification Results
- **Tests**: All 78 tests passed.
- **Data Integrity**: Confirmed that `pricing_dynamic_*.json` files are preserved and not overwritten by tests.
- **Logic Verification**:
    - Confirmed that `backend/calculation/engine.py` and provider modules (`aws.py`, `azure.py`, `gcp.py`) correctly implement the formulas described in `docs-formulas.html`.
    - Verified that all pricing keys used in the code (e.g., `scheduler.jobPrice`, `logicApps.pricePerStateTransition`) match the structure of the fetched `pricing_dynamic_*.json` files.
- **Documentation**:
    - Created `docs/docs-calculation-logic.html` to provide a detailed explanation of the optimization algorithm and component-level cost formulas.
    - Updated `docs/docs-nav.html` to include the new page in the sidebar.
    - Refined `docs/docs-calculation-logic.html` to include detailed sections on:
        - **Conditional Logic**: Event Checking, Orchestration (Step Functions, Logic Apps, Cloud Workflows), Feedback Loops, and Error Handling.
        - **Glue Code**: Cross-Cloud Ingestion (L1 -> L2) and Cross-Cloud Visualization (L3 -> L4/L5).
    - Updated `docs/docs-architecture.html` to include:
        - **Cross-Cloud Glue Architecture**: Detailed the specific components injected for cross-cloud data flow.
        - **Conditional Services**: Explicitly linked supporting services to their configuration flags.
    - Updated `docs/docs-api-reference.html` and `example_input.json` to match the latest `CalcParams` model.
