# UI Refactoring & Detailed Cost Tables

## Goal
Refactor the frontend code to improve maintainability by separating UI logic from API client logic. Additionally, implement detailed cost breakdown tables for Layer 1 and Layer 4 optimization warnings to provide better transparency into "Glue Code" and "Data Transfer" costs.

## User Review Required
> [!NOTE]
> This is a retroactive plan documenting work already completed on 2025-12-04.

## Proposed Changes

### Frontend

#### [NEW] [js/ui-components.js](file:///d:/Git/master-thesis/2-twin2clouds/js/ui-components.js)
- Create a new file to house UI generation logic.
- Move the following functions from `api-client.js`:
    - `generateComparisonTable`
    - `generateDetailedComparisonTable` (New function for L1/L4)
    - `insertWarning`
    - `getServicesForLayer`
    - `generateLayerCard`
    - `generateResultHTML`
    - `updateHtml`

#### [MODIFY] [js/api-client.js](file:///d:/Git/master-thesis/2-twin2clouds/js/api-client.js)
- Remove the UI generation functions listed above.
- Update `calculateCosts` to call `updateHtml` from the new `ui-components.js` file.
- Ensure `updateHtml` receives all necessary data, including `l1OptimizationOverride` and `l4OptimizationOverride`.

#### [MODIFY] [index.html](file:///d:/Git/master-thesis/2-twin2clouds/index.html)
- Add `<script src="js/ui-components.js"></script>` before `js/api-client.js`.
- Ensure `js/calculation/ui.js` is loaded first.

## Verification Plan

### Manual Verification
- [x] Verify that the UI still loads and functions correctly after refactoring.
- [x] Verify that L1 and L4 optimization warnings now display a detailed table with columns for "Base Cost", "Glue Code", and "Data Transfer".
