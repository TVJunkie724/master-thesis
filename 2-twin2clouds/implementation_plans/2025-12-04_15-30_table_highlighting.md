# Highlight Selected Provider in Comparison Tables

## Goal
Enhance the UI comparison tables (L1, L2, L4) to visually highlight the row corresponding to the selected provider or path. This improves readability and helps users quickly identify which option the system has chosen.

## User Review Required
> [!NOTE]
> This is a retroactive plan documenting work already completed on 2025-12-04.

## Proposed Changes

### Frontend

#### [MODIFY] [js/ui-components.js](file:///d:/Git/master-thesis/2-twin2clouds/js/ui-components.js)
- Update `updateHtml` to parse the `cheapestPath` array at the beginning of the function to extract selected providers for all layers.
- Update `generateComparisonTable`:
    - Accept a `selectedProviders` object.
    - For "L2/L3" tables: Highlight the row where `l2_provider` and `l3_provider` match the selection.
    - For "Cool" and "Archive" tables: Highlight the row where the path segments strictly match the selected Hot, Cool, and Archive providers.
    - Use `table-success` class for highlighting.
- Update `generateDetailedComparisonTable`:
    - Accept a `selectedProvider` string.
    - Highlight the row where the provider matches the selection.

## Verification Plan

### Manual Verification
- [x] Verify that the selected row is highlighted in green (`table-success`) for all warning tables.
- [x] Verify that the highlighting logic correctly handles paths with repeated providers (e.g., `Azure -> Azure -> Azure`) by strictly checking each segment.
