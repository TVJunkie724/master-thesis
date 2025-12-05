# Implementation Plan: Multi-Cloud Roadmap & Optional Events

# Goal Description
Update the deployment documentation (`docs-*.html`) to strictly define the architecture for a **Multi-Cloud Digital Twin**. This includes:
1.  **Conditional Connectors:** Explicitly defining where "Shortcuts" (Single-Cloud) vs. "Connectors" (Multi-Cloud) are used.
2.  **Optional Events:** Making the Layer 2 Event System (Event Checker, Feedback Loop, Workflows) configurable via a boolean flag.
3.  **Parity:** Ensuring AWS, Azure, and GCP have equivalent architectural definitions per layer.

## User Review Required
> [!IMPORTANT]
> **Optional Events:** The Event System (Event Checker, Feedback Loop) will be marked as **Optional**. This means the deployer must support a flag (e.g., `enable_events=True/False`) to conditionally create these resources.

> [!NOTE]
> **No Code Implementation Yet:** This plan focuses solely on updating the **Documentation Roadmaps** to serve as the blueprint for future implementation.

## Proposed Changes

### 1. Documentation Updates (`3-cloud-deployer/docs/`)

We will update `docs-aws-deployment.html`, `docs-azure-deployment.html`, and `docs-gcp-deployment.html`.

#### Common Updates (All Providers)
*   **Layer 2 (Data Processing):**
    *   Mark `Event Checker Function` as **[Optional]**.
    *   Mark `Event Feedback Function` as **[Optional]**.
    *   Mark `Workflow/State Machine` as **[Optional]**.
    *   *Note:* The `Persister` function remains mandatory but its invocation of the Event Checker becomes conditional.

#### AWS Deployment Guide (`docs-aws-deployment.html`)
*   **L1 -> L2:**
    *   **Single Cloud:** IoT Rule -> Dispatcher Lambda.
    *   **Multi Cloud:** IoT Rule -> Dispatcher Lambda -> **Connector Lambda** (Masquerading) -> Remote Ingestion API.
*   **L2 -> L3:**
    *   **Single Cloud:** Persister -> DynamoDB (Boto3).
    *   **Multi Cloud:** Persister -> **HTTP Client** -> Remote Writer API.
*   **L3 -> L4/L5:**
    *   **Single Cloud:** Native TwinMaker/Grafana access.
    *   **Multi Cloud:** **API Gateway** + `hot_reader` Lambda (Public Endpoint).

#### Azure Deployment Guide (`docs-azure-deployment.html`)
*   **L1 -> L2:**
    *   **Single Cloud:** Event Grid -> Dispatcher Function.
    *   **Multi Cloud:** Event Grid -> Dispatcher Function -> **Connector Function** -> Remote Ingestion API.
    *   **Ingestion API:** Add `Ingestion Function` (HTTP Trigger) to receive data from remote L1.
*   **L2 -> L3:**
    *   **Single Cloud:** Persister -> Cosmos DB (SDK).
    *   **Multi Cloud:** Persister -> **HTTP Client** -> Remote Writer API.
    *   **Writer API:** Add `Writer Function` (HTTP Trigger) to receive data from remote L2.
*   **L3 -> L4/L5:**
    *   **Single Cloud:** Native Managed Grafana/ADT integration.
    *   **Multi Cloud:** **API Management** (or HTTP Trigger) -> `hot_reader` Function.

#### GCP Deployment Guide (`docs-gcp-deployment.html`)
*   **L1 -> L2:**
    *   **Single Cloud:** Pub/Sub -> Dispatcher Function.
    *   **Multi Cloud:** Pub/Sub -> Dispatcher Function -> **Connector Function** -> Remote Ingestion API.
    *   **Ingestion API:** Add `Ingestion Function` (HTTP Trigger).
*   **L2 -> L3:**
    *   **Single Cloud:** Persister -> Firestore (SDK).
    *   **Multi Cloud:** Persister -> **HTTP Client** -> Remote Writer API.
    *   **Writer API:** Add `Writer Function` (HTTP Trigger).
*   **L3 -> L4/L5:**
    *   **Single Cloud:** Native Grafana Firestore plugin.
    *   **Multi Cloud:** **API Gateway** (or HTTP Trigger) -> `hot_reader` Function.

### 2. Implementation Plans Directory
*   Ensure this plan is saved to `implementation_plans/` as the source of truth.

## Verification Plan

### Manual Verification
1.  **Visual Inspection:** Open the updated HTML files in a browser (or preview) to verify the roadmaps are clear, consistent, and reflect the "Conditional Connector" and "Optional Event" logic.
2.  **Parity Check:** Cross-reference the three guides to ensure every layer has an equivalent definition (e.g., if AWS has an Ingestion API for multi-cloud, Azure and GCP must also have it defined).
