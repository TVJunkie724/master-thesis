
# Implementation Plan - State Machine Validation & Google Cloud Support

## Goal Description
Enhance `file_manager.py` to strictly validate the *content* of state machine definition files (`aws_step_function.json`, `azure_logic_app.json`, and the new `google_cloud_workflow.json`) to ensuring they match the expected provider's schema. This prevents users from accidentally uploading a file intended for one provider to another.

Additionally, this plan includes the generation of a **Google Cloud Workflow** JSON template to match the existing "Function A -> Function B" workflow pattern used by AWS and Azure.

## User Review Required
> [!IMPORTANT]
> **Google Cloud Workflows Format**: Google Cloud Workflows are natively YAML-based. While they can be represented as JSON, it reduces readability. I have provided the JSON representation below as requested, but please confirm if you strictly prefer `.json` over `.yaml` for consistency with other providers.

## Proposed Changes

### 1. Constants Update (`src/constants.py`)
- Define `GOOGLE_STATE_MACHINE_FILE = "google_cloud_workflow.json"`.
- Update `REQUIRED_STATE_MACHINE_FIELDS` (or similar mapping) to store unique signature keys for validation:
    - **AWS**: Checks for `StartAt` and `States`.
    - **Azure**: Checks for `definition` and `$schema` (containing `logic.azure.com` or `schema.management.azure.com`).
    - **Google**: Checks for `main` and `steps`.

### 2. Validation Logic (`src/file_manager.py`)
- Implement `validate_state_machine_content(filename, content)`:
    - Parses the JSON content.
    - Identifies the provider based on the filename (using constants).
    - Verifies the presence of provider-specific root keys.
    - Raises `ValueError` if the content signature doesn't match the filename (e.g., AWS structure in an Azure file).
- Update `verify_project_structure`:
    - Call validation logic when checking `triggerNotificationWorkflow` dependency.

### 3. Google Cloud Template Generation
Create `google_cloud_workflow.json` in `upload/template/state_machines/` (Draft below).

#### Google Cloud Workflow JSON (Draft)
Equivalent to the AWS/Azure "LambdaA -> LambdaB" flow.
```json
{
  "main": {
    "params": ["args"],
    "steps": [
      {
        "init": {
          "assign": [
            { "inputData": "${args.InputData}" },
            { "funcA_url": "${args.FunctionA_URL}" }, 
            { "funcB_url": "${args.FunctionB_URL}" }
          ]
        }
      },
      {
        "callFunctionA": {
          "call": "http.post",
          "args": {
            "url": "${funcA_url}",
            "body": { "input": "${inputData}" }
          },
          "result": "resultA"
        }
      },
      {
        "callFunctionB": {
          "call": "http.post",
          "args": {
            "url": "${funcB_url}",
            "body": {
              "fromA": "${resultA.body}",
              "event": "${inputData}"
            }
          },
          "result": "resultB"
        }
      },
      {
        "returnResult": {
          "return": "${resultB.body}"
        }
      }
    ]
  }
}
```

### 4. API & Upload Integration
- **Zip Validation (`validate_project_zip` in `file_manager.py`)**:
    - Iterate through files in the zip.
    - If filename matches a known state machine file (e.g., `aws_step_function.json`), extract content and call `validate_state_machine_content`.
- **New Endpoint (`rest_api.py`)**:
    - `PUT /projects/{project_name}/state_machines/{provider}`
    - **Provider Dropdown**: Use `ProviderEnum` (aws, azure, google) to generate a dropdown in Swagger UI for the `provider` argument.
    - Accepts file upload.
    - Determines target filename based on provider (`aws` -> `aws_step_function.json`).
    - Validates content using `validate_state_machine_content`.
    - Saves file to `upload/{project_name}/state_machines/`.

## Verification Plan

### Automated Tests
- **Unit Tests (`tests/unit/test_validation.py`)**:
    - **Test AWS Success**: Valid ASL JSON passes.
    - **Test Azure Success**: Valid Logic App JSON passes.
    - **Test Google Success**: Valid Workflow JSON passes.
    - **Test Mismatch**:
        - Upload AWS JSON as `azure_logic_app.json` -> Fail.
        - Upload Azure JSON as `aws_step_function.json` -> Fail.
        - Upload Empty/Malformed JSON -> Fail.
    - **Test Zip Integration**: Zip containing invalid state machine fails `validate_project_zip`.
