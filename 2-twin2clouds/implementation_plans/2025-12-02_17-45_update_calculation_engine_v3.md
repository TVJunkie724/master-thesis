# Implementation Plan - Update Calculation Engine (Revised v3)

## Goal
Refine the calculation engine to align with the `3-cloud-deployer` architecture and technical specifications. This includes adding new input parameters, implementing conditional logic for optional components (Event Checking, Error Handling), correctly calculating API Gateway costs, and **adding missing cross-cloud compute costs**.

## User Review Required
> [!IMPORTANT]
> **New Input Parameters**:
> - `useEventChecking` (bool): Enables/disables the Event Checker component (Lambda/Function).
> - `triggerNotificationWorkflow` (bool): **[Requires useEventChecking=True]** If true, adds Orchestration costs (Step Functions/Logic Apps/Workflows).
> - `returnFeedbackToDevice` (bool): **[Requires useEventChecking=True]** If true, adds Feedback Loop costs (IoT messaging/egress).
> - `integrateErrorHandling` (bool): Enables/disables Error Reporter, Error Bus, and Error Storage costs.
> - `orchestrationActionsPerMessage` (int): Default **3** (based on analysis of `state_machines/*.json`).
> - `eventsPerMessage` (int): Default **1** (for Event Bus).
> - `apiCallsPerDashboardRefresh` (int): Default **1** (for API Gateway).

> [!NOTE]
> **Cross-Cloud Compute Logic**:
> When layers are distributed across different providers, additional "glue" functions are required. These incur compute costs (executions/duration) in addition to data transfer costs.
> - **L1 -> L2 (Cross-Cloud)**:
>     - Source Cloud: `Connector Function` (1 exec/msg).
>     - Target Cloud: `Ingestion Function` (1 exec/msg).
> - **L2 -> L3 (Cross-Cloud)**:
>     - Target Cloud: `Writer Function` (1 exec/msg).
> - **L3 -> L4 (Cross-Cloud)**:
>     - Target Cloud: `Hot Reader Function` (1 exec/dashboard_query).
>     - Target Cloud: `API Gateway` (1 call/dashboard_query).

## Proposed Changes

### 1. Update API Interface
#### [MODIFY] [backend/rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- Update `CalcParams` class to include new parameters.

### 2. Update Provider Calculation Modules
Add functions to calculate costs for specific components.

#### [MODIFY] [backend/calculation/aws.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/aws.py)
- Update `calculate_aws_cost_data_processing`: Add `Event Checker`, `Step Functions`, `Feedback Loop`, `Error Handling`.
- Add `calculate_aws_api_gateway_cost`.
- Add `calculate_aws_connector_function_cost` (L1->L2 Source).
- Add `calculate_aws_ingestion_function_cost` (L1->L2 Target).
- Add `calculate_aws_writer_function_cost` (L2->L3 Target).
- Add `calculate_aws_reader_function_cost` (L3->L4 Target).

#### [MODIFY] [backend/calculation/azure.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/azure.py)
- Update `calculate_azure_cost_data_processing`: Add `Event Checker`, `Logic Apps`, `Feedback Loop`, `Error Handling`.
- Add `calculate_azure_api_management_cost`.
- Add `calculate_azure_connector_function_cost`.
- Add `calculate_azure_ingestion_function_cost`.
- Add `calculate_azure_writer_function_cost`.
- Add `calculate_azure_reader_function_cost`.

#### [MODIFY] [backend/calculation/gcp.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/gcp.py)
- Update `calculate_gcp_cost_data_processing`: Add `Event Checker`, `Cloud Workflows`, `Feedback Loop`, `Error Handling`.
- Add `calculate_gcp_api_gateway_cost`.
- Add `calculate_gcp_connector_function_cost`.
- Add `calculate_gcp_ingestion_function_cost`.
- Add `calculate_gcp_writer_function_cost`.
- Add `calculate_gcp_reader_function_cost`.

### 3. Update Engine Orchestration
#### [MODIFY] [backend/calculation/engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
- Update `calculate_cheapest_costs`:
    - **L1 Selection**: When calculating `L1_Provider + Transfer_to_Hot`, add `Connector_Cost(L1)` + `Ingestion_Cost(L2)` if `L1 != L2`.
    - **L3 Selection**: When calculating `L3_Provider` (coupled to Hot Storage), add `Writer_Cost(L3)` if `L2 != L3`.
    - **L4 Selection**: When comparing L4 options, add `Reader_Cost(L3)` + `API_Gateway_Cost(L3)` if `L4 != L3`.

## Verification Plan
### Automated Tests
- **New Test File**: `tests/test_calculation_scenarios.py`
    - Test Case 1: `useEventChecking=True` vs `False`.
    - Test Case 2: `triggerNotificationWorkflow=True` vs `False`.
    - Test Case 3: `returnFeedbackToDevice=True` vs `False`.
    - Test Case 4: `integrateErrorHandling=True` vs `False`.
    - Test Case 5: Cross-cloud L1-L2 (Verify Connector/Ingestion costs).
    - Test Case 6: Cross-cloud L2-L3 (Verify Writer cost).
    - Test Case 7: Cross-cloud L3-L4 (Verify Reader/API Gateway cost).

### Manual Verification
- Trigger calculation via API with different boolean flags.
- Inspect JSON output to confirm "supporter services" and "cross-cloud glue" costs are present/absent as expected.
