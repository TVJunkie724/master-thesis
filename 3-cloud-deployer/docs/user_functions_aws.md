# AWS User Functions Architecture

This document details the architecture, packaging, and data flow for **User Functions** (Processors) on AWS.

## 1. High-Level Architecture

The AWS implementation uses a **Decoupled Invoke Pattern** where the infrastructure wrapper invokes the user-defined logic via the AWS Lambda SDK.

```mermaid
graph TD
    Ingestion[L0 Ingestion] -->|Async Invoke| Dispatcher[L1 Dispatcher]
    Dispatcher -->|Async Invoke| Wrapper[L2 Processor Wrapper]
    
    subgraph "L2 Processing Layer"
        Wrapper -->|SDK Invoke (Sync)| UserProc[User Processor\n(twin-device-processor)]
        UserProc -->|Return Result| Wrapper
        Wrapper -->|Async Invoke| Persister[L2 Persister]
    end
    
    Persister -->|Write| DynamoDB[(L3 Hot Storage)]
```

### Key Components

| Component | Resource Name | Type | Role |
| :--- | :--- | :--- | :--- |
| **Wrapper** | `{twin}-processor` | Lambda | Infrastructure code. Routes events to specific user processors. |
| **User Processor** | `{twin}-{device}-processor` | Lambda | User code. Processes telemetry for a specific device. |
| **Persister** | `{twin}-l2-persister` | Lambda | Infrastructure code. Writes processed data to storage. |

## 2. Naming & Discovery

*   **Pattern**: `{twin_name}-{device_id}-processor`
*   **Discovery**: The Wrapper constructs the target function name dynamically at runtime using the `device_id` from the incoming event.
*   **Invocation**: Uses `boto3.client('lambda').invoke()` with `InvocationType='RequestResponse'` (Synchronous).

### Code Reference
*   **Source**: `src/providers/aws/lambda_functions/processor_wrapper/lambda_function.py`
*   **Logic**:
    ```python
    def _get_processor_lambda_name(device_id: str) -> str:
        twin_name = _get_digital_twin_info()["config"]["digital_twin_name"]
        return f"{twin_name}-{device_id}-processor"
    ```

## 3. Packaging & Bundling

The bundling process is handled by `src/providers/terraform/package_builder.py`.

### Process
1.  **Iterate Devices**: Reads `config_iot_devices.json` to find all defined devices.
2.  **Locate Code**: Looks for user code in `upload/{project}/aws/lambda_functions/processors/{device_id}/`.
3.  **Build ZIP**: Creates an individual ZIP file for **each** device processor.
    *   File: `.build/aws/processor-{device_id}.zip`
    *   Contents: User's `lambda_function.py` + `_shared/` modules.
4.  **TfVars Generation**: `tfvars_generator.py` creates a list variable `aws_processors` containing `{name, zip_path}` objects.

### Terraform Deployment
`src/terraform/aws_compute.tf` iterates over this list to create resources:

```hcl
resource "aws_lambda_function" "user_processor" {
  for_each = { for p in var.aws_processors : p.name => p }
  function_name = "${var.digital_twin_name}-${each.value.name}-processor"
  ...
}
```

## 4. Security & IAM

To allow the Wrapper to call the dynamically named User Functions, a specific IAM policy is applied.

*   **Role**: `l2_lambda` (Shared by Wrapper and Persister)
*   **Policy**: `l2_invoke_lambda`
*   **Resource**: `arn:aws:lambda:{region}:{account}:function:{twin}-*`
*   **Action**: `lambda:InvokeFunction`

This allows the wrapper to invoke any function associated with the current Digital Twin deployment.

## 5. Development Flow

1.  **Create Processor**: User creates a folder `processors/{device_id}`.
2.  **Add Code**: User adds `lambda_function.py` with `def lambda_handler(event, context): ...`.
3.  **Deploy**: 
    *   `package_builder.py` zips the code.
    *   Terraform creates the new Lambda resource.
    *   IAM role automatically allows the Wrapper to call it.
