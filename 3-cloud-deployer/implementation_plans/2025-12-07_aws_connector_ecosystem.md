# AWS Connector Functions Implementation Plan

## Goal Description
Implement the complete "Connector" ecosystem for the AWS provider to enable seamless, secure, and user-configurable multi-cloud communication. This architecture allows specific layers (L1, L2, L3) to reside on different clouds while maintaining a cohesive data pipeline.

## User Review Required
- **Naming Strategy ("-processor" vs "-connector")**:
    - **Current Limitation**: The L1 Dispatcher currently hardcodes the target function name as `{device}-processor`.
    - **Solution**: We will modify the **Dispatcher** to use an environment variable `TARGET_FUNCTION_SUFFIX` (default: `-processor`).
    - **Multi-Cloud Behavior**: In a multi-cloud setup (e.g., L1 AWS -> L2 Azure), we configure this suffix to `-connector`. The deployed function will be named `{twin}-{device}-connector`.
    - **Reasoning**: This adheres to the Open-Closed Principle. We extend the Dispatcher's behavior via configuration without modifying its core routing logic or requiring complex lookup tables. It also aligns the function name with its actual role (proxy/connector).

- **Config Structure (`config_inter_cloud.json`)**:
    - **New File**: `upload/template/config_inter_cloud.json`.
    - **Purpose**: To securely separate cross-cloud credentials from standard cloud credentials, allowing for rotation and extensibility.
    - **Schema**:
      ```json
      {
          "connections": {
              "aws_l1_to_azure_l2": {
                  "provider": "azure",
                  "function": "ingestion", 
                  "token": "generated-secure-token",
                  "url": "https://func-ingest-xyz.azurewebsites.net/api/ingest"
              },
              "azure_l2_to_aws_l3": {
                  "provider": "aws",
                  "function": "writer",
                  "token": "generated-secure-token",
                  "url": "https://lambda-url-id.lambda-url.region.on.aws/"
              }
          }
      }
      ```
    - **Usage**: This file is optional for single-cloud but required for multi-cloud. The deployer will validate it if multi-cloud is detected.

- **User Logic & Code Merging Strategy**:
    - **Problem**: Users need to write custom processing logic (e.g., `pressure * 1.2`), but the system needs to guarantee that the `Persister` function is always called afterwards.
    - **Solution**: "Code Merging" at deployment time.
        1.  **System Wrapper**: We create `src/aws/lambda_functions/processor_wrapper`. This contains the `lambda_handler` that imports `process` and handles the output (invoking Persister).
        2.  **User Logic**: The user edits `upload/template/lambda_functions/processors/default_processor/process.py`. This only contains `def process(event): ...` and example JSON.
        3.  **Deployment**: The deployer creates a temporary directory, copies the System Wrapper, copies the User's `process.py` into it, and zips the result.
    - **Benefit**: The user cannot accidentally break the data pipeline (Persister invocation), but has full control over the data transformation.

- **Writer Function Architecture**:
    - **Role**: A dedicated entry point for L3 (Storage) when L2 is on a remote cloud.
    - **Reasoning & Security**:
        1.  **Isolation**: The DynamoDB table resides in a protected AWS environment. We do **not** want to issue AWS IAM Credentials with `DynamoDB:PutItem` permissions to a remote cloud (Azure/GCP).
        2.  **Proxying**: The "Writer" function acts as a secure gateway. The remote cloud only knows the Writer's Public URL and a specific `Inter-Cloud-Token`.
        3.  **Attack Surface Reduction**: If the token is compromised, an attacker can only write data. They cannot scan tables, delete tables, or access other AWS resources (which valid IAM keys might allow if misconfigured).
        4.  **Decoupling**: The remote cloud doesn't need to know *how* data is stored (DynamoDB vs S3 vs RDS). It just sends JSON to the Writer.

## Proposed Changes

### 1. Configuration & Constants

#### [MODIFY] `src/constants.py`
- Add `CONFIG_INTER_CLOUD_FILE = "config_inter_cloud.json"`.
- Add schema definition logic (if centralized there) or constants for keys (`connections`, `token`, `url`).

#### [NEW] `upload/template/config_inter_cloud.json`
- Create the template file with the `connections` schema structure.

### 2. Core Logic & Validation

#### [MODIFY] `src/globals.py`
- Add `initialize_config_inter_cloud()` to load the new JSON file.
- Add helper `get_inter_cloud_token(connection_id)` to safely retrieve tokens.

#### [MODIFY] `src/validator.py`
- **`validate_config_content`**: Add validation for `config_inter_cloud.json`. Ensure `connections` is a dictionary and entries have required fields (`token`, `provider`, `url`).
- **`validate_project_zip`**:
    - Add logic to look for `lambda_functions/processors/.../process.py`.
    - Validate the syntax of `process.py`.
- **`validate_python_code_aws`**: Ensure `process.py` defines `process(event)`; ensure `wrapper` defines `lambda_handler`.

### 3. AWS Implementation Files

#### [MODIFY] `src/aws/lambda_functions/dispatcher/lambda_function.py`
- Update logic to construct the target function name:
  ```python
  suffix = os.environ.get("TARGET_FUNCTION_SUFFIX", "-processor")
  function_name = f"{twin}-{device}{suffix}"
  ```

#### [NEW] `src/aws/lambda_functions/processor_wrapper/lambda_function.py`
- **Content**:
  ```python
  from process import process
  import boto3...
  def lambda_handler(event, context):
      result = process(event)
      # invoke persister...
  ```

#### [NEW] `upload/template/lambda_functions/processors/default_processor/process.py`
- **Content**:
  ```python
  # --- CONTEXT: System Wrapper (DO NOT EDIT) ---
  # from process import process
  # import boto3...
  # def lambda_handler(event, context):
  #     result = process(event)
  #     # invoke persister...
  # ---------------------------------------------
  
  # Example Event:
  # {
  #   "iotDeviceId": "temperature-sensor-1",
  #   "temperature": 25.5
  # }
  def process(event):
      # Modify your event here
      return event
  ```

#### [NEW] `src/aws/lambda_functions/connector/lambda_function.py`
- **Role**: L1 -> Remote L2.
- **Logic**:
    1.  Read `REMOTE_INGESTION_URL` and `INTER_CLOUD_TOKEN` (env vars).
    2.  Wrap event: `{ "source": "aws", "payload": event }`.
    3.  POST to URL with header `X-Inter-Cloud-Token`.

#### [NEW] `src/aws/lambda_functions/ingestion/lambda_function.py`
- **Role**: Remote L1 -> Local L2.
- **Logic**:
    1.  Validate `X-Inter-Cloud-Token` matches env var `INTER_CLOUD_TOKEN`.
    2.  Unwrap payload.
    3.  Invoke local `{twin}-{device}-processor`.

#### [NEW] `src/aws/lambda_functions/writer/lambda_function.py`
- **Role**: Remote L2 -> Local L3.
- **Logic**:
    1.  Validate `X-Inter-Cloud-Token`.
    2.  Put Item to DynamoDB table.

### 4. Deployment Logic

#### [MODIFY] `src/util.py`
- Add `compile_merged_lambda_function(base_path, custom_file_path)`.
    - `custom_file_path` will be resolved from `upload/<project_name>/lambda_functions/...`.
    - Creates a temp directory.
    - Copies contents of `base_path` (System Wrapper).
    - Copies `custom_file_path` to `process.py` in the temp dir.
    - Zips the directory.
    - Returns zip bytes.
    - Cleanup temp dir.

#### [MODIFY] `src/aws/iot_deployer_aws.py`
- **`create_processor_lambda_function`**:
    - **Scenario A (Remote L2)**: Deploy `Connector` code.
        - Name: `{device}-connector`.
        - Config: Inject `TARGET_FUNCTION_SUFFIX="-connector"` into Dispatcher.
    - **Scenario B (Local L2)**: Deploy `Merged` code.
        - Name: `{device}-processor`.
        - Source: Merge `processor_wrapper` + `upload/.../process.py`.
        - Config: Inject `TARGET_FUNCTION_SUFFIX="-processor"`.
- **`create_dispatcher_lambda_function`**:
    - Inject the environment variable `TARGET_FUNCTION_SUFFIX` based on the multi-cloud state (L1 vs L2).

#### [MODIFY] `src/aws/core_deployer_aws.py`
- **`create_writer_lambda_function`**:
    - **Condition**: Deploy if `L2 != AWS` AND `L3 == AWS`.
    - **Setup**: Helper to enable Function URL and inject Token.

## Verification Plan

### Automated Tests (`tests/deployers/test_aws_connector_logic.py`)
1.  **Validation Test**: Create a zip with invalid `config_inter_cloud.json` and ensure `validate_project_zip` throws an error.
2.  **Merging Test**: Call `util.compile_merged_lambda_function` with dummy paths. Verify (via `zipfile`) that the output zip contains both `lambda_function.py` and `process.py`.
3.  **Naming Logic Test**: Mock `globals.config_providers` to simulate Multi-Cloud. Verify `create_processor_lambda_function` calls `create_function` with `{device}-connector`.
4.  **Security Test**: Simulate a Writer deployment. Verify that `AuthType='NONE'` is set (for Function URL) but `INTER_CLOUD_TOKEN` is present in env vars.

### Manual Verification
- Deploy a dual-cloud project (AWS + Azure).
- Trigger an event on AWS L1.
- Verify logs in CloudWatch:
    - Dispatcher -> Connector -> Remote Ingestion (Azure).
- Intentionally send malformed data to verify:
    - Dispatcher: Logs "iotDeviceId missing".
    - Connector: Logs "Client Error (400)" for bad tokens.
    - Writer: Logs "Validation Error" for non-dict payloads.
    - Processor: Logs "[USER_LOGIC_ERROR]" for crashing scripts.

## Completion Status
- [x] All items implemented
- [x] Unit tests passing

## Phase 2: Remaining Lambda Functions (Extension)

### Goal
Extend robust error handling to all remaining Lambda functions in `src` and `upload/template`. Fix critical logic bugs identified during analysis.

### Critical Findings
1.  **Movers (Hot-to-Cold, Cold-to-Archive)**: `cutoff` time is calculated at **module scope**. In a warm Lambda container, this value will become stale, leading to incorrect data retention enforcement.
2.  **Event Checker**: 
    - Logic Error: `>` operator implementation mistakenly uses `<`.
    - Logic Error: `STRING` constant extraction is a no-op statement.
    - Error Handling: Swallows all exceptions without specific context.

### Proposed Changes

#### Movers & Persisters (Critical Data Path)
- **Files**: 
  - `src/aws/lambda_functions/hot-to-cold-mover/lambda_function.py`
  - `src/aws/lambda_functions/cold-to-archive-mover/lambda_function.py`
  - `src/aws/lambda_functions/persister/lambda_function.py`
- **Changes**:
  - Move `cutoff` calculation inside `lambda_handler`.
  - Wrap logic in `try-except`.
  - Validate required event keys (e.g., `time` in Persister).

#### Event Checker (Logic & Safety)
- **File**: `src/aws/lambda_functions/event-checker/lambda_function.py`
- **Changes**:
  - Fix `>` operator to use `>`.
  - Fix `STRING` extraction to return the sliced string.
  - Improve exception handling to log the specific event that failed but allow the loop to continue (partial failure).

#### Readers (API/Access)
- **Files**:
  - `src/aws/lambda_functions/hot-reader/lambda_function.py`
  - `src/aws/lambda_functions/hot-reader-last-entry/lambda_function.py`
- **Changes**:
  - Add `try-except` blocks.
  - Return distinct error responses for Client (400) vs Server (500) errors where applicable, or empty results with error logs.

#### Default Processor & Templates
- **Files**:
  - `src/aws/lambda_functions/default-processor/lambda_function.py`
  - `upload/template/lambda_functions/event-feedback/lambda_function.py`
- **Changes**:
  - Add `try-except` blocks.
  - Ensure failed executions are logged clearly.

### Verification Plan
- **Unit/Integration Tests**: Run existing `pytest` suite. The logic fixes (Event Checker) should drastically improve correctness.
- **Manual Review**: Verify the code changes specifically for the "Stale Time" fix.
