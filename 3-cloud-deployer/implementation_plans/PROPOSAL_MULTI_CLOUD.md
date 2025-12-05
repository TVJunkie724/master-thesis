# Multi-Cloud Connector Layer Proposal

## 1. Overview

This document proposes the architecture for "Connector Layers" to enable the Multi-Cloud Digital Twin vision.
The goal is to allow each of the 5 layers to reside on different cloud providers while maintaining the simplicity of single-cloud deployments where possible.

## 2. Identified Gaps & "Shortcuts"

Our analysis confirms that **Single-Cloud** deployments often have "shortcuts" (native integrations) that bypass the need for explicit Connector functions. We should leverage these when possible and only use Connectors for Multi-Cloud transitions.

### 1. AWS (Single Cloud)
*   **L3 -> L4:** TwinMaker uses a native component/Lambda to read DynamoDB.
*   **L5 -> L4/L3:** Managed Grafana reads directly from TwinMaker (and potentially DynamoDB) using native data sources.
*   **Result:** The "Hot Reader API" (API Gateway) is **not required** for a pure AWS deployment.

### 2. Azure (Single Cloud - Planned)
*   **L5 -> L4:** Azure Managed Grafana connects natively to Azure Digital Twins.
*   **L5 -> L3:** Azure Managed Grafana has a native **Cosmos DB** plugin.
*   **Result:** An "API Management" layer is **not required** for a pure Azure deployment using Managed Grafana.

### 3. GCP / Self-Hosted (Single/Multi Cloud)
*   **L5 -> L3 (DynamoDB):** Self-hosted Grafana has a **free native plugin** for DynamoDB.
*   **L5 -> L3 (Cosmos DB):** The official Cosmos DB plugin is **Enterprise/Cloud only**.
    *   *Implication:* For Self-Hosted Grafana (OSS) to read from Cosmos DB, we **DO** need a Connector (L3 Reader API) to expose data via REST for the generic JSON/Infinity plugin.
*   **L5 -> L3 (Firestore):** Self-hosted Grafana has a native plugin.

**Conclusion:**
*   **Shortcuts:** Use native plugins for AWS (Managed), Azure (Managed), and GCP (Firestore).
*   **Connectors Required:**
    *   **Multi-Cloud:** When crossing boundaries (e.g., AWS L1 -> Azure L2).
    *   **OSS Limitations:** When accessing Cosmos DB from Self-Hosted Grafana (OSS).

## 3. Proposed Connector Architecture

We propose introducing **Connector Functions** that are conditionally deployed or used only when a layer transition crosses a cloud boundary.
*Note:* All serverless functions already receive `config_providers` in their environment variables, enabling them to make runtime routing decisions.

### A. Layer 1 -> Layer 2 (Data Processing)

**Flow:** `IoT Core` -> `Dispatcher` -> `Processor (Connector)` -> [HTTP] -> `Ingestion API` -> `Real Processor`

1.  **Cloud A (Source):**
    *   **Dispatcher:** Remains **unchanged**. It continues to dispatch events to a function named `[device_id]-processor`.
    *   **Connector:** We deploy a Lambda named `[device_id]-processor` (masquerading).
        *   **Logic:** Instead of processing, it wraps the event and sends it via HTTP POST to Cloud B.
2.  **Cloud B (Target):**
    *   **Ingestion API:** An HTTP-triggered function (e.g., Function URL or HTTP Trigger).
    *   **Logic:** Receives the event and invokes the **Real Processor** function locally.

### B. Layer 2 -> Layer 3 (Hot Storage Write)

**Flow:** `Persister` -> (Check Config) -> [Direct Write OR HTTP Call] -> `Writer API` -> `Database`

1.  **Cloud A (Source):**
    *   **Persister:** Adapted to check `config_providers`.
        *   **If Local:** Uses `boto3`/SDK to write directly to the database (Performance shortcut).
        *   **If Remote:** Sends the data via HTTP POST to the **Writer API** on Cloud B.
2.  **Cloud B (Target):**
    *   **Writer API:** An HTTP-triggered function.
    *   **Logic:** Receives the JSON data and performs the write operation to the local Hot Storage (DynamoDB/Cosmos/Firestore).
    *   *Why?* This abstracts the database credentials and network security, allowing a simple HTTPS call from Cloud A.

### C. Layer 3 -> Layer 4/5 (Read Access)

**Scenario:** L3 is on Cloud A (AWS), L4/L5 is on Cloud B (Azure).

*   **Current:** L3 exposes a Reader API (API Gateway).
*   **Proposal:**
    *   **Single Cloud:** Do not deploy API Gateway. Use native plugins/connectors.
    *   **Multi Cloud:** Deploy API Gateway (AWS) / API Management (Azure) / API Gateway (GCP).
    *   **L4/L5 Side (Cloud B):** Configure the TwinMaker Connector or Grafana Datasource to use the **Generic REST/JSON** plugin pointing to the remote L3 Reader API.

## 4. Summary of Changes

| Interaction | Single Cloud (Shortcut) | Multi-Cloud (Connector) |
| :--- | :--- | :--- |
| **L1 -> L2** | Direct Invocation / PubSub | **L1-L2 Connector** (Masquerading Lambda) -> **HTTP Ingestion API** |
| **L2 -> L3** | Direct DB Write (SDK) | **Persister Adaptation** (HTTP Client) -> **L3 Writer API** |
| **L3 -> L4/5** | Native Plugin / SDK | **L3 Reader API** (Gateway) <- **Generic REST Plugin** |

## 5. Next Steps

1.  **Discuss:** Confirm this "Conditional Connector" approach.
2.  **Prototype:** Implement the "Masquerading Connector" for L1->L2.
3.  **Implement:** Add Writer API to L3 (conditionally deployed).
