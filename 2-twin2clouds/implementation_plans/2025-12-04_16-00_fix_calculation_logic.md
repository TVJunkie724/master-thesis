# Fix Calculation Discrepancy in UI Tables

## Goal
Ensure the costs displayed in the "Cool Storage" and "Archive Storage" optimization tables match the costs used by the system's optimization algorithm (Dijkstra). Previously, the table logic incorrectly assumed intra-cloud transfers (e.g., Azure Hot -> Azure Cool) were free, while the system correctly identified them as having a cost.

## User Review Required
> [!NOTE]
> This is a retroactive plan documenting work already completed on 2025-12-04.

## Proposed Changes

### Backend

#### [MODIFY] [engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
- Update the `l2_cool_combinations` calculation loop:
    - Replace manual transfer cost logic with a lookup from the `transfer_costs` dictionary.
    - Use keys like `f"{hot_provider}_Hot_to_{cool_prov}_Cool"`.
- Update the `l2_archive_combinations` calculation loop:
    - Replace manual transfer cost logic with `transfer_costs` lookup.
    - Use keys like `f"{current_cool_provider}_Cool_to_{arch_prov}_Archive"`.

## Verification Plan

### Automated Tests
- [x] Run `debug_preset3_calc.py` to verify that the "Total" cost for `Azure -> Azure -> Azure` includes the transfer fee (~$870) and matches the system's decision logic.

### Manual Verification
- [x] Refresh the UI with Preset 3 and verify that the "Optimization Note" table shows consistent values where the selected path is indeed the cheapest.
