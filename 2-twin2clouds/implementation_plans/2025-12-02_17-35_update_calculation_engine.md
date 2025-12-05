# Implementation Plan - Update Calculation Engine (Revised v2)

## Goal
Refine the calculation engine to align with the `3-cloud-deployer` architecture and technical specifications. This includes adding new input parameters, implementing conditional logic for optional components (Event Checking, Error Handling), and correctly calculating API Gateway costs based on cross-provider dependencies.

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
> **API Gateway Logic**:
> API Gateway costs will be applied to **Layer 3** (Data Access) ONLY if **Layer 4** (Twin Management) is on a different provider than Layer 3.
> - `Cost(L4_Candidate) = Internal_Cost(L4_Candidate) + (API_Gateway_Cost(L3_Provider) if L3_Provider != L4_Candidate else 0)`

## Proposed Changes

### 1. Update API Interface
#### [MODIFY] [backend/rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- Update `CalcParams` class to include:
    - `useEventChecking: bool`
    - `triggerNotificationWorkflow: bool` (default False)
    - `returnFeedbackToDevice: bool` (default False)
    - `integrateErrorHandling: bool`
    - `orchestrationActionsPerMessage: int = 3`
    - `eventsPerMessage: int = 1`
    - `apiCallsPerDashboardRefresh: int = 1`

### 2. Update Provider Calculation Modules
Each provider module will be updated to calculate costs for these specific components, allowing `engine.py` or the module itself to conditionally include them.

#### [MODIFY] [backend/calculation/aws.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/aws.py)
- Update `calculate_aws_cost_data_processing`:
    - `useEventChecking` -> adds `Event Checker` (Lambda).
    - `triggerNotificationWorkflow` -> adds `Step Functions` cost.
    - `returnFeedbackToDevice` -> adds `IoT Core` (Publish) cost + `Feedback` (Lambda) cost.
    - `integrateErrorHandling` -> adds `Error Reporter` (Lambda) + `EventBridge` + `DynamoDB` (Write/Storage).
- Add `calculate_aws_api_gateway_cost(number_of_requests, pricing)`: Calculates potential API Gateway cost.

#### [MODIFY] [backend/calculation/azure.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/azure.py)
- Update `calculate_azure_cost_data_processing`:
    - `useEventChecking` -> adds `Event Checker` (Function).
    - `triggerNotificationWorkflow` -> adds `Logic Apps` cost.
    - `returnFeedbackToDevice` -> adds `IoT Hub` (C2D message) cost + `Feedback` (Function) cost.
    - `integrateErrorHandling` -> adds `Error Reporter` (Function) + `Event Grid` + `Cosmos DB` (Write/Storage).
- Add `calculate_azure_api_management_cost(number_of_requests, pricing)`: Calculates potential APIM cost.

#### [MODIFY] [backend/calculation/gcp.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/gcp.py)
- Update `calculate_gcp_cost_data_processing`:
    - `useEventChecking` -> adds `Event Checker` (Function).
    - `triggerNotificationWorkflow` -> adds `Cloud Workflows` cost.
    - `returnFeedbackToDevice` -> adds `Pub/Sub` (Publish) cost + `Feedback` (Function) cost.
    - `integrateErrorHandling` -> adds `Error Reporter` (Function) + `Pub/Sub` + `Firestore` (Write/Storage).
- Add `calculate_gcp_api_gateway_cost(number_of_requests, pricing)`: Calculates potential API Gateway cost.

### 3. Update Engine Orchestration
#### [MODIFY] [backend/calculation/engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
- Update `calculate_cheapest_costs`:
    - Calculate `api_gateway_cost` for all 3 providers upfront.
    - In the L4 selection logic:
        - Identify `l3_provider` (determined by Hot Storage).
        - When comparing L4 options, add `l3_provider`'s API Gateway cost if `l4_provider != l3_provider`.

## Verification Plan
### Automated Tests
- **New Test File**: `tests/test_calculation_scenarios.py`
    - Test Case 1: `useEventChecking=True` vs `False`.
    - Test Case 2: `triggerNotificationWorkflow=True` vs `False`.
    - Test Case 3: `returnFeedbackToDevice=True` vs `False`.
    - Test Case 4: `integrateErrorHandling=True` vs `False`.
    - Test Case 5: Cross-cloud L3-L4 (Verify API Gateway cost is added).

### Manual Verification
- Trigger calculation via API with different boolean flags.
- Inspect JSON output to confirm "supporter services" costs are present/absent as expected.
