# Implement 3D Model Pricing Parameter

## Goal Description
Implement a new input parameter `average3DModelSizeInMB` (default 100MB) to calculate the storage cost of 3D models in Layer 4 (Twin Management). This cost will be added only if `needs3DModel` is true.

## User Review Required
> [!NOTE]
> This change introduces a new input field in the UI and modifies the API contract.

## Proposed Changes

### Backend

#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- Add `average3DModelSizeInMB` to `CalcParams` model (Optional, default=100.0).

#### [MODIFY] [example_input.json](file:///d:/Git/master-thesis/2-twin2clouds/example_input.json)
- Add `average3DModelSizeInMB` with default value 100.

#### [MODIFY] [backend/calculation/aws.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/aws.py)
- Update `calculate_aws_iot_twin_maker_cost` to accept `average3DModelSizeInMB`.
- Convert MB to GB (`size / 1024`).
- Add S3 storage cost calculation for the converted size.

#### [MODIFY] [backend/calculation/azure.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/azure.py)
- Update `calculate_azure_digital_twins_cost` to accept `average3DModelSizeInMB`.
- Convert MB to GB.
- Add Blob Storage cost calculation for the converted size.

#### [MODIFY] [backend/calculation/gcp.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/gcp.py)
- Update `calculate_gcp_twin_maker_cost` to accept `average3DModelSizeInMB`.
- Convert MB to GB.
- Add Cloud Storage cost calculation for the converted size.

#### [MODIFY] [backend/calculation/engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
- Update `calculate_aws_costs`, `calculate_azure_costs`, and `calculate_gcp_costs` to pass `params["average3DModelSizeInMB"]` to the respective L4 functions.
- Ensure this is passed only if `needs3DModel` is true (or handle logic inside the provider functions). *Decision: Pass it always, let provider function handle the conditional logic based on `needs3DModel` flag if passed, or just pass the size and let the caller decide. Better: Pass `needs3DModel` boolean and `average3DModelSizeInGB` to the provider functions.*

### Frontend

#### [MODIFY] [index.html](file:///d:/Git/master-thesis/2-twin2clouds/index.html)
- Add a new input field for "Average 3D Model Size (MB)" **inside** the `entityInputContainer` div. This ensures it is automatically hidden/shown when "Is a 3D Model Necessary?" is toggled.

#### [MODIFY] [js/ui-components.js](file:///d:/Git/master-thesis/2-twin2clouds/js/ui-components.js)
- No changes needed for visibility logic as it's handled by the container.

#### [MODIFY] [js/calculation/ui.js](file:///d:/Git/master-thesis/2-twin2clouds/js/calculation/ui.js)
- Update `fillScenario` to accept and populate `average3DModelSizeInMB`.
- Update presets in `index.html` to pass this new value.

#### [MODIFY] [js/api-client.js](file:///d:/Git/master-thesis/2-twin2clouds/js/api-client.js)
- Update `readParamsFromUi` to read `average3DModelSizeInMB` inside the `if (needs3DModel)` block.
- Add it to the JSON payload sent to `/calculate`.

### Documentation

#### [MODIFY] [docs/calculation_logic_and_changes.md](file:///d:/Git/master-thesis/2-twin2clouds/docs/calculation_logic_and_changes.md)
- Document the new parameter and how it affects the L4 cost calculation.

## Verification Plan

### Automated Tests
- [ ] Run `debug_preset1_calc.py` (after updating it to include the new param) and verify L4 costs change when `needs3DModel` is toggled or size is changed.

### Manual Verification
- [ ] Open the UI.
- [ ] Verify the new input field appears with default 100MB.
- [ ] Toggle "Is a 3D Model Necessary?" to "Yes".
- [ ] Change "Average 3D Model Size" and verify L4 cost updates.
- [ ] Toggle "Is a 3D Model Necessary?" to "No" and verify L4 cost decreases (removes storage cost).
