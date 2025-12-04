# Implement Storage Mover Functions in UI

## Goal Description
The user states that the architecture includes "Hot to Cold Mover Functions" and "Cold to Archive Mover Functions". These should be listed on the back of the Layer 2 Cool and Layer 2 Archive cards, respectively, to accurately reflect the architecture.

## User Review Required
> [!NOTE]
> This change only updates the **UI service list**. It does not add a new *cost component* (e.g., a separate Lambda cost) for these functions, assuming the existing "Lifecycle/Request" costs in the backend cover the operation or the cost is negligible/included.

## Proposed Changes

### Frontend (`js/ui-components.js`)
#### [MODIFY] [ui-components.js](file:///d:/Git/master-thesis/2-twin2clouds/js/ui-components.js)
- Update `getServicesForLayer` function:
    - For `l2_cool`: Add "Hot to Cold Mover Function" to the service list for all providers (AWS, Azure, GCP).
    - For `l2_archive`: Add "Cold to Archive Mover Function" to the service list for all providers.
    - Use appropriate links (e.g., generic Lambda/Function links or Lifecycle documentation if more appropriate, but user said "Function").

## Verification Plan

### Manual Verification
1.  **Scenario Setup**:
    - Use "Preset 1".
2.  **Verify L2 Cards**:
    - Flip **L2 Cool** card: Check for "Hot to Cold Mover Function".
    - Flip **L2 Archive** card: Check for "Cold to Archive Mover Function".
