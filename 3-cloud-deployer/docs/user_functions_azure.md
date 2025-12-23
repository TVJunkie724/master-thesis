# Azure User Functions Architecture

This document details the architecture, packaging, and data flow for **User Functions** (Processors) on Azure.

## 1. High-Level Architecture

The Azure implementation uses a **Decoupled HTTP Pattern** where the infrastructure wrapper invokes the user-defined logic via internal HTTP calls between Function Apps.

```mermaid
graph TD
    Ingestion[L0 Ingestion] -->|Internal Queue| Dispatcher[L1 Dispatcher]
    Dispatcher -->|Internal Queue| Wrapper[L2 Processor Wrapper]
    
    subgraph "L2 Function App (Infrastructure)"
        Wrapper
        Persister
    end
    
    subgraph "User Function App (User Code)"
        UserProc[User Processor\n(twin-device-processor)]
    end
    
    Wrapper -->|HTTP POST| UserProc
    UserProc -->|HTTP 200| Wrapper
    Wrapper -->|HTTP POST| Persister
    
    Persister -->|Write| CosmosDB[(L3 Hot Storage)]
```

### Key Components

| Component | App Resource | Function Name | Role |
| :--- | :--- | :--- | :--- |
| **Wrapper** | `l2-functions` | `processor` | Infrastructure. Routes events to user processors via HTTP. |
| **User Processor** | `user-functions` | `{twin}-{device}-processor` | User Code. Processes telemetry. |
| **Persister** | `l2-functions` | `persister` | Infrastructure. Writes to Cosmos DB. |

## 2. Naming & Discovery

*   **App URL**: `https://{twin}-user-functions.azurewebsites.net`
*   **Function Route**: `/api/{twin}-{device}-processor`
*   **Discovery**: The Wrapper uses the `FUNCTION_APP_BASE_URL` environment variable to locate the User Function App, then appends the specific processor path.
*   **Invocation**: Standard HTTP POST using `urllib`.

### Code Reference
*   **Source**: `src/providers/azure/azure_functions/processor_wrapper/function_app.py`
*   **Logic**:
    ```python
    def _get_processor_url(device_id: str) -> str:
        # FUNCTION_APP_BASE_URL injected by Terraform
        base_url = os.environ.get("FUNCTION_APP_BASE_URL", "")
        processor_name = f"{twin_name}-{device_id}-processor"
        return f"{base_url}/api/{processor_name}"
    ```

## 3. Packaging & Bundling

The bundling process is handled by `src/providers/terraform/package_builder.py`. Unlike AWS/GCP, Azure **bundles all user functions together**.

### Process
1.  **Iterate Devices**: Reads `config_iot_devices.json`.
2.  **Locate Code**: Looks for user code in `upload/{project}/azure_functions/processors/{device_id}/`.
3.  **Build Bundle**: Creates a **single** ZIP file containing all user processors, event actions, and feedback functions.
    *   File: `.build/azure/user_functions_combined.zip`
    *   **Structure**: 
        *   `host.json`
        *   `function_app.py` (Main entry point generated dynamically)
        *   `processor-{device_id}/` (User code module)
        *   `event-feedback/` (User code module)
4.  **Blueprint Registration**: The builder automatically generates a main `function_app.py` that imports and registers each user function as a Blueprint.

### Terraform Deployment
`src/terraform/azure_compute.tf` deploys this *single* bundle to the User Function App:

```hcl
resource "azurerm_linux_function_app" "user" {
  name = "${var.digital_twin_name}-user-functions"
  zip_deploy_file = var.azure_user_zip_path
  ...
}
```

## 4. Configuration & Environment

The Wrapper depends on correct Environment Variables to find the User App.

*   **Config Configured in**: `azurerm_linux_function_app.l2` (in `azure_compute.tf`)
*   **Key Variable**: `FUNCTION_APP_BASE_URL`
*   **Value Pattern**: `https://${var.digital_twin_name}-user-functions.azurewebsites.net`

## 5. Development Flow

1.  **Create Processor**: User creates a folder `processors/{device_id}`.
2.  **Add Code**: User adds `function_app.py` using the Blueprint pattern.
3.  **Deploy**: 
    *   `package_builder.py` bundles this folder into the combined ZIP.
    *   It generates a root `function_app.py` that registers `processor-{device_id}.function_app.bp`.
    *   Terraform updates the User Function App with the new ZIP.
