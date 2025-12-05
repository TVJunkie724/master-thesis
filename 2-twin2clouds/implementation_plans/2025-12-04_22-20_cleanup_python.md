# Cleanup Python Code

## Goal Description
The user wants to clean up the Python code by removing unnecessary comments, unused variables, and parameters.

## Proposed Changes

### Backend (`backend/calculation/engine.py`)
#### [MODIFY] [engine.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/engine.py)
- Remove `print` statements used for debugging.
- Remove unnecessary empty lines.

### Backend (`rest_api.py`)
#### [MODIFY] [rest_api.py](file:///d:/Git/master-thesis/2-twin2clouds/rest_api.py)
- Remove duplicate comment `# Calculate costs using Python engine`.
- **NOTE**: User requested to keep `twin2clouds_config`.

### Backend (`backend/calculation/aws.py`)
#### [MODIFY] [aws.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/aws.py)
- Remove commented out `tier3_limit`.

### Backend (`backend/calculation/azure.py`)
#### [MODIFY] [azure.py](file:///d:/Git/master-thesis/2-twin2clouds/backend/calculation/azure.py)
- Remove verbose comments discussing hypothetical logic in `calculate_azure_cost_data_processing`.

## Verification Plan

### Manual Verification
1.  **Start API**: Run the API server.
2.  **Run Calculation**: Trigger a calculation from the UI.
3.  **Check Logs**: Ensure no "Optimal L2+L3" or "Optimized Storage Path" prints appear in the console (stdout), only logger output.
4.  **Verify Functionality**: Ensure calculation results are still returned correctly.
