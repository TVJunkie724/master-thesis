# Implementation Plan - AWS Lambda Error Handling

**Goal:** Enhance the robustness of AWS Lambda functions by handling potential errors, ensuring safe data parsing, and improving logging and retry mechanisms.

## User Review Required
> [!IMPORTANT]
> **User Logic Failure Strategy:** Currently, if the user-defined `process()` function fails in `processor_wrapper`, we will catch the exception, log it, and **re-raise it**. This ensures that the AWS Lambda service marks the execution as failed and triggers its built-in retry mechanism (2 default retries for async events). This is preferred over swallowing the error.

## Proposed Changes

### 1. `src/aws/lambda_functions/dispatcher/lambda_function.py`
- **Logic:** Add `try-except` blocks around JSON parsing and Lambda invocation.
- **Validation:** Safely check for `iotDeviceId` and `DIGITAL_TWIN_INFO` keys.
- **Logging:** Log the destination function name before invoking.

### 2. `src/aws/lambda_functions/connector/lambda_function.py`
- **HTTP Handling:** Explicitly handle `urllib.error.HTTPError`.
  - **Fail Fast:** If status is 400, 401, 403, 404 (Client Errors), do **not** retry. Raise immediately.
  - **Retry:** Only retry on 500, 502, 503, 504 (Server Errors) or connection/timeout exceptions.
- **Logging:** Log the target URL and attempt number.

### 3. `src/aws/lambda_functions/ingestion/lambda_function.py`
- **Invocation Check:** Ensure `lambda_client.invoke` is wrapped.
- **Response:** If invocation fails, return `500` status code so the calling `connector` knows to retry.

### 4. `src/aws/lambda_functions/writer/lambda_function.py`
- **Validation:** Add stricter checks for `payload` structure.
- **DynamoDB:** Wrap `table.put_item` in `try-except`.

### 5. `src/aws/lambda_functions/processor_wrapper/lambda_function.py`
- **User Code Guard:** Wrap `process(event)` in `try-except`.
- **System Pipeline:** Wrap `Persister` invocation in `try-except`.
- **Logging:** Log clear delimiters for "User Logic Start/End" to separate system logs from user print statements.

## Verification Plan

### Automated Tests
- **Locations:** `tests/deployers/test_aws_connector_logic.py` (Update or New)
- **Scenarios:**
    - **Dispatcher:** Test with missing `iotDeviceId`.
    - **Connector:** Mock `urllib` to simulate 500 (retry) and 400 (fail fast).
    - **Ingestion/Writer:** Send malformed JSON payloads.

### Manual Verification
- Deploy the stack.
- Send a malformed payload via `iot_device_simulator` or `awscurl` to the Function URL.
- Verify CloudWatch logs show the structured error messages.
