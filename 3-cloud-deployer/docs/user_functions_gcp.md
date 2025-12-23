# GCP User Functions Architecture

This document details the architecture, packaging, and data flow for **User Functions** (Processors) on Google Cloud Platform.

> [!WARNING]
> **Critical Infrastructure Note**: The current discovery mechanism checks for URLs at `...cloudfunctions.net/api/...`. 
> For **Cloud Functions Gen 2**, URLs are non-deterministic (containing a random hash) and do not natively support `/api/` path routing without an API Gateway. 
> *The architecture described below reflects the current implementation logic, but runtime discovery may fail without additional infrastructure (Gateway) or URL injection.*

## 1. High-Level Architecture

The GCP implementation uses a **Decoupled HTTP Pattern** where the infrastructure wrapper invokes the user-defined logic via HTTP calls.

```mermaid
graph TD
    Ingestion[L0 Ingestion] -->|Pub/Sub| Dispatcher[L1 Dispatcher]
    Dispatcher -->|Pub/Sub| Wrapper[L2 Processor Wrapper]
    
    subgraph "L2 Processing Layer"
        Wrapper -->|HTTP POST| UserProc[User Processor\n(twin-device-processor)]
        UserProc -->|Json Return| Wrapper
        Wrapper -->|HTTP POST| Persister[L2 Persister]
    end
    
    Persister -->|Write| Firestore[(L3 Hot Storage)]
```

### Key Components

| Component | Resource Name | Type | Role |
| :--- | :--- | :--- | :--- |
| **Wrapper** | `{twin}-processor` | Cloud Function V2 | Infrastructure. Routes events to user processors via HTTP. |
| **User Processor** | `{twin}-{device}-processor` | Cloud Function V2 | User Code. Processes telemetry. |
| **Persister** | `{twin}-persister` | Cloud Function V2 | Infrastructure. Writes to Firestore. |

## 2. Naming & Discovery

*   **Target Pattern**: `https://{region}-{project}.cloudfunctions.net/api/{twin_name}-{device_id}-processor` (**See Warning**)
*   **Discovery**: The Wrapper uses the `FUNCTION_APP_BASE_URL` logic (borrowed from Azure pattern) to construct the URL.
*   **Invocation**: Standard HTTP POST using `requests`.

### Code Reference
*   **Source**: `src/providers/gcp/cloud_functions/processor_wrapper/main.py`
*   **Logic**:
    ```python
    def _get_processor_url(device_id: str) -> str:
        base_url = os.environ.get("FUNCTION_APP_BASE_URL", "")
        # Result: base_url + /api/ + processor_name
        return f"{base_url}/api/{twin_name}-{device_id}-processor"
    ```

## 3. Packaging & Bundling

The bundling process is handled by `src/providers/terraform/package_builder.py`. Similar to AWS, GCP functions are **packaged individually**.

### Process
1.  **Iterate Devices**: Reads `config_iot_devices.json`.
2.  **Locate Code**: Looks for user code in `upload/{project}/gcp/cloud_functions/processors/{device_id}/`.
3.  **Build ZIP**: Creates an individual ZIP file for **each** device processor.
    *   File: `.build/gcp/processor-{device_id}.zip`
    *   Contents: User's `main.py` + `_shared/` modules.
4.  **TfVars Generation**: `tfvars_generator.py` creates a list variable `gcp_processors`.

### Terraform Deployment
`src/terraform/gcp_compute.tf` iterates over this list to create resources:

```hcl
resource "google_cloudfunctions2_function" "processor" {
  for_each = { for p in var.gcp_processors : p.name => p }
  name     = "${var.digital_twin_name}-${each.value.name}-processor"
  ...
}
```

## 4. Security & IAM

We use **Service Account Identity** for secure invocation.

*   **Service Account**: All L2 functions (Wrapper, Processor, Persister) run as the same `functions` service account.
*   **Permissions**: `google_cloud_run_service_iam_member` resources are created for *each* processor, explicitly granting `roles/run.invoker` to the `functions` service account.
*   **Authentication**: The Wrapper automatically attaches an OIDC token to its request (handled by `urllib`/`requests` or implicit in the infrastructure identity if using internal calls).

## 5. Development Flow

1.  **Create Processor**: User creates a folder `processors/{device_id}`.
2.  **Add Code**: User adds `main.py` with `def main(request): ...`.
3.  **Deploy**: 
    *   `package_builder.py` zips the code.
    *   Terraform creates the new Cloud Function V2 resource.
    *   IAM binding is created to allow the Wrapper to call it.
