# Unlocked L2-L3 Optimization & UI Refinement

## Goal Description
The goal is to refine the "Unlocked L2-L3 Optimization" logic and its presentation in the UI. 
Currently, the system optimizes L2 (Hot Storage) and L3 (Processing) together.
Users found the UI confusing when the system selected a provider for L2 Cool or L2 Archive that appeared more expensive in isolation.
The user explicitly requested that the comparison tables show the **Full Path Combinations** (e.g., `Azure -> GCP -> GCP`) to clearly identify the source and destination of every transfer and storage cost.

## User Review Required
> [!IMPORTANT]
> **UI Change:** The comparison tables for Cool and Archive storage will now be "Path Combination" tables.
> They will list the full path: `Hot Provider -> Cool Provider -> Archive Provider`.
> Columns will be: `Path`, `Transfer (Hot->Cool)`, `Cool Cost`, `Transfer (Cool->Archive)`, `Archive Cost`, `Total`.

## Proposed Changes

### Backend (`backend/calculation/engine.py`)
#### [MODIFY] [engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
-   **Update `l2_cool_combinations`:**
    -   Iterate over all Cool providers (AWS, Azure, GCP).
    -   For each Cool provider, find the *cheapest* Archive provider to complete the path.
    -   Calculate the full breakdown: `Trans(H->C)`, `Cool Cost`, `Trans(C->A)`, `Archive Cost`.
    -   Return a list of these "Best Path per Cool Provider" options.
-   **Update `l2_archive_combinations`:**
    -   Assume Hot and Cool are fixed (based on selection).
    -   Iterate over all Archive providers.
    -   Calculate breakdown: `Trans(C->A)`, `Archive Cost`.
    -   Return list of options.

### Frontend (`js/api-client.js`)
#### [MODIFY] [api-client.js](file:///d:/Git/master-thesis/2-twin2clouds/js/api-client.js)
-   **Update `generateComparisonTable`:**
    -   Add a new mode (e.g., `"full_path"`) or update `"cool"`/`"archive"` modes.
    -   **Columns:**
        -   **Path:** e.g., "Azure → GCP → GCP"
        -   **Trans (H→C):** Cost of moving from Hot to Cool.
        -   **Cool Cost:** Storage cost.
        -   **Trans (C→A):** Cost of moving from Cool to Archive.
        -   **Archive Cost:** Storage cost.
        -   **Total:** Sum of all above.
-   **Update Warning Text:**
    -   Update "Why" text to point to the table: "See the table below for the full path cost breakdown."

## Verification Plan

### Automated Tests
-   Run `debug_unlocked_calc.py` to verify the backend logic produces the expected "Total Path" costs.

### Manual Verification
-   **Scenario:** Preset 2.
-   **Check:** The "L2 Cool Optimization" box should show a table with rows like `Azure -> Azure -> Azure` vs `Azure -> GCP -> GCP`.
-   **Check:** The costs should sum up correctly to the Total.
