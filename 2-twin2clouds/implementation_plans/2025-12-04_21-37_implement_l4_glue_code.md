# Implement L4 Glue Code Costs and UI Badge

## Goal Description
The user wants to account for "Glue Code" (API Gateway + Additional Function) costs when Layer 4 (Twin Management) is hosted on a different cloud provider than Layer 3 (Data Processing). These costs should be reflected in the total cost on the L4 card, and the card should display an "Includes Glue Code" badge and list the additional services on the back.

## User Review Required
> [!IMPORTANT]
> This change assumes that the "source" for Layer 4 is the *optimal* Layer 3 provider determined by the system. The cost displayed on non-optimal L4 cards will be "Cost of this L4 + Cost to transition from the Optimal L3".

## Proposed Changes

### Backend (`backend/calculation/engine.py`)
#### [MODIFY] [engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
- Update the logic for determining `l3_provider_name` to use the optimized `best_l3_provider_key` instead of `hot_storage_provider` (fixing a potential bug where L3 != L2).
- After calculating `updated_l4_options` with glue costs, iterate through them and update the main `aws_costs["resultL4"]`, `azure_costs["resultL4"]`, and `gcp_costs["resultL4"]` dictionaries.
    - Add a `glueCodeCost` field.
    - Add `glueCodeCost` to `totalMonthlyCost`.

### Frontend (`js/ui-components.js`)
#### [MODIFY] [ui-components.js](file:///d:/Git/master-thesis/2-twin2clouds/js/ui-components.js)
- Update `getServicesForLayer` function:
    - Add logic to check if glue code is needed for L4 (`isGlueNeededL3L4`).
    - This condition is true if `candidateProvider` (for L4) is different from `selectedProviders.l3`.
    - If true, add "API Gateway" and "Reader Function (Glue Code)" to the returned services list.
    - This will automatically trigger the "Includes Glue Code" badge due to the existing `hasGlueCode` check.

## Verification Plan

### Automated Tests
- None (Visual/Logic verification).

### Manual Verification
1.  **Scenario Setup**:
    - Use "Preset 1" (Smart Home).
    - Ensure the optimized path selects, for example, AWS for L3.
2.  **Verify L4 Cards**:
    - Check the **AWS L4** card: Should NOT have "Includes Glue Code".
    - Check the **Azure L4** card: SHOULD have "Includes Glue Code" badge.
    - Flip the Azure L4 card: Should list "Azure API Management" and "Reader Function (Glue Code)".
    - Verify the cost on the Azure L4 card includes the glue code cost (compare with manual calculation or previous value).
