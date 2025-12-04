# Cleanup JavaScript Code

## Goal Description
The user wants to clean up the JavaScript code by removing unnecessary comments, unused variables, and parameters.

## Proposed Changes

### Frontend (`js/ui-components.js`)
#### [MODIFY] [ui-components.js](file:///d:/Git/master-thesis/2-twin2clouds/js/ui-components.js)
- **`generateLayerCard`**: Remove unused parameters: `awsUrl`, `awsName`, `azureUrl`, `azureName`, `gcpUrl`, `gcpName`, `description`.
    - Update function signature and usage.
- **`generateResultHTML`**:
    - Remove logic that calculates `awsUrl`, `azureUrl`, `gcpUrl`.
    - Update call to `generateLayerCard` to match new signature.
- **`updateHtml`**:
    - Remove `// (Moved to top of function)` comment.
- **General**:
    - Remove `// Special handling for L4 when omitted - REVERTED` and associated commented-out code.

### Frontend (`js/api-client.js`)
#### [MODIFY] [api-client.js](file:///d:/Git/master-thesis/2-twin2clouds/js/api-client.js)
- **`calculateCheapestCostsFromUI`**:
    - Fix `results.gcpCosts || results.azureCosts` to just `results.gcpCosts` (assuming GCP costs are always returned or handled gracefully).

### Frontend (`js/calculation/ui.js`)
#### [MODIFY] [ui.js](file:///d:/Git/master-thesis/2-twin2clouds/js/calculation/ui.js)
- **`fillScenario`**: Remove duplicated comment `// Re-run toggleEntityInput to ensure UI state matches`.
- **`toggleEntityInput`**: Remove duplicated comment `// Show input if "Yes" is selected, hide if "No" is selected`.

## Verification Plan

### Manual Verification
1.  **Load Page**: Ensure the UI loads correctly.
2.  **Run Calculation**: Click "Calculate" and verify results are displayed correctly (cards, badges, service lists).
3.  **Check Console**: Ensure no errors in console.
