# Project Vision: Twin2MultiCloud

## 1. The Core Vision
**Twin2MultiCloud** is a unified application designed to bridge the gap between theoretical cost optimization and practical multi-cloud infrastructure deployment.

It is not merely an integration of scripts, but a cohesive platform with two interfaces:
-   **CLI**: For automated pipelines and power users.
-   **Flutter Frontend**: For interactive scenario modeling and visualization.

## 2. Theoretical Foundation
The project is strictly based on the scientific framework defined in the paper:
> **EDT_25__CloudDT_engineering.pdf**

This paper establishes:
1.  **The 5-Layer Architecture**: The standard structure for a cloud-based Digital Twin (Data Acquisition, Processing, Storage, Management, Visualization).
2.  **Cost Formulas**: The mathematical models used to calculate and predict costs across AWS, Azure, and GCP.
3.  **Optimization Logic**: The algorithms for determining the most cost-effective provider distribution.

## 3. System Architecture

The runtime consists of four distinct, interconnected projects:

### A. The Client: `twin2multicloud_flutter`

*   **Role**: Interactive Web and desktop user interface.
*   **Boundary**: Calls only the Management API. Direct calls to the Optimizer
    or Deployer are architecture defects.
*   **State ownership**: Riverpod owns runtime/API composition; feature BLoCs
    own complex workflows and transitions.

### B. The Orchestrator: `twin2multicloud_backend`

*   **Role**: Public Management API and durable application boundary.
*   **Responsibility**: Owns users, twins, configuration, cloud connections,
    immutable calculation/deployment evidence, lifecycle orchestration, and
    public contract shaping.
*   **Boundary**: Calls the Optimizer and Deployer through typed internal
    clients. Provider formula implementation and Terraform execution remain
    outside this service.

### C. The Brain: `2-twin2clouds`

*   **Role**: Pricing, formula, and cost-optimization engine.
*   **Input**: Trusted workload, pricing context, and versioned architecture
    references supplied by the Management API.
*   **Output**: Traceable cost results and immutable resolved deployment
    decisions for functionally complete supported paths.

### D. The Muscle: `3-cloud-deployer`

*   **Role**: Infrastructure execution engine.
*   **Input**: A validated deployment manifest produced by the Management API.
*   **Output**: Deterministic packages, typed Terraform inputs, operation
    evidence, and a deployed Digital Twin for supported paths.

## 4. The Workflow

1.  **Define**: The user defines a Twin and workload in Flutter or another
    supported Management API client.
2.  **Optimize**: The Management API validates and enriches the request, then
    calls the Optimizer.
3.  **Persist and review**: The Management API validates and atomically stores
    the result and its immutable evidence; Flutter renders typed read models.
4.  **Deploy**: The user selects a complete run and asks the Management API to
    deploy it.
5.  **Execute**: The Management API builds the deployment package and invokes
    the Deployer. Status and logs return through the Management API.

## 5. The Management Platform

The Flutter application is the command center for the supported Digital Twin
lifecycle, while the Management API is the public runtime and persistence
boundary.

### 5.1. Architecture: The Management API

*   **Database:** Stores users, twins, configuration, owner-scoped cloud
    connections, immutable calculation evidence, and deployment state.
*   **Authentication:** Handles development authentication and configured
    external identity providers.
*   **Orchestration:** Wraps the Deployer and Optimizer through typed internal
    clients.
*   **Streaming:** Exposes one-way operation updates to Flutter through SSE.

### 5.2. User Workflow
1.  **Configuration & Optimization:**
    *   User inputs requirements (data frequency, retention, etc.).
    *   **Data Fetching:** System fetches current cloud pricing and region mappings.
        *   **Live Logs:** App displays real-time status of price fetching (e.g., "Fetching AWS us-east-1 pricing...", "Updating Azure regions...").
    *   **Cost Optimizer** runs and proposes a multi-cloud architecture (e.g., "L1 in AWS, L2 in Azure").
    *   User reviews and selects a complete calculation run. Manual provider
        override remains separate backlog work and is not an implicit current
        capability.
2.  **Deployment:**
    *   User deploys the selected complete run through the Management API.
    *   **Live Logs:** The app receives one-way deployment logs through
        Management API SSE.
3.  **Operation & Monitoring:**
    *   **Twin List:** User sees all deployed twins.
    *   **Dashboard:** Selecting a twin shows:
        *   **Live Status:** Health of each layer.
        *   **Error/Warning Log:** Real-time feed of system errors (e.g., "L2 Connector Timeout", "L1 Sensor Offline").
        *   **Visualization:** Embedded Grafana view or link.
        *   **Management:** Supported lifecycle operations for the complete
            deployment.
        *   **Cost evidence:** Frozen estimated calculation evidence; observed
            billing reconciliation remains out of scope.
        *   **Specifications:** Full list of all specifications/configs made by the user for the twin.

### 5.3. Error Handling Strategy
Errors must be captured at every layer and surfaced to the user.
*   **Sources:**
    *   **Ingestion (L1):** Malformed data, device disconnects.
    *   **Processing (L2):** Validation failures, cross-cloud connector timeouts.
    *   **Storage (L3):** Write failures, quota exceeded.
*   **Reporting:**
    *   Current operations propagate structured, bounded errors and correlation
        evidence through the Management API.
    *   Event routing belongs to the independently owned Event Layer of the
        standalone Six-layer profile and its reviewed provider/deployment contracts.

## 6. Current Architecture Program And Remaining Evaluation

-   **Architecture profiles:** `six-layer-eventing@1` is the only active,
    deployable closed-world profile. The original Five-layer calculation is an
    Optimizer-only historical baseline.
-   **Functional completeness:** Incomplete provider paths are rejected before
    profile-local cost ranking.
-   **Remaining paper validation:** Phase 8.10 compares reproducible estimated
    costs and records separately approved observed/live evidence without
    treating the latter as a prerequisite for offline thesis evaluation.
-   **Final E2E:** Keep cost-incurring provider execution supervised and
    explicitly approved.

## 7. References

For detailed technical information, please refer to the project documentation:

### 2-twin2clouds (Optimizer)
-   **[Documentation Overview](2-twin2clouds/docs/docs-overview.html)**
-   **[Architecture](2-twin2clouds/docs/docs-architecture.html)**
-   **[Cost Formulas](2-twin2clouds/docs/docs-formulas.html)**

### 3-cloud-deployer (Deployer)
-   **[Documentation Overview](3-cloud-deployer/docs/docs-overview.html)**
-   **[Architecture](3-cloud-deployer/docs/docs-architecture.html)**
-   **[Integration Guide](3-cloud-deployer/docs/docs-twin2clouds-integration.html)**
