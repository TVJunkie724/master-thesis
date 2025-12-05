# Technical Specifications for Multi-Cloud Digital Twin Deployment

## Overview
This document formalizes the technical specifications required to implement the "Twin2MultiCloud" architecture. It addresses the critical implementation details for cross-cloud communication, security, data consistency, and error handling that are common across all cloud providers (AWS, Azure, GCP).

## 1. Cross-Cloud Configuration & Discovery

To enable functions in one cloud to communicate with resources in another, dynamic configuration injection is required at deployment time.

### Mechanism
*   **Environment Variables:** All Lambda functions, Azure Functions, and Cloud Functions will receive configuration via environment variables (or Application Settings in Azure).
*   **Injection Time:** The `3-cloud-deployer` (Python script) is responsible for resolving these values and injecting them during the deployment process (e.g., via `boto3`, `azure-mgmt`, or `google-cloud-functions` client libraries).

### Required Variables
| Variable Name | Description | Example Value |
| :--- | :--- | :--- |
| `REMOTE_INGESTION_URL` | URL of the remote cloud's Layer 1 Ingestion API (for L1->L2). | `https://func-ingest-xyz.azurewebsites.net/api/ingest` |
| `REMOTE_WRITER_URL` | URL of the remote cloud's Layer 3 Writer API (for L2->L3). | `https://us-central1-project.cloudfunctions.net/writer` |
| `REMOTE_READER_URL` | URL of the remote cloud's Layer 3 Reader API (for L4/L5 access). | `https://api-id.execute-api.us-east-1.amazonaws.com/prod/read` |
| `REMOTE_AUTH_TOKEN` | (Optional) Static API Key for cross-cloud authentication (if not using IAM/OIDC). | `x-api-key-value` |

## 2. Authentication for Public Endpoints

Since cross-cloud communication occurs over the public internet via HTTP, strict authentication is mandatory.

### Strategy by Provider

#### AWS (Receiver)
*   **Mechanism:** **AWS IAM (SigV4)** is preferred for internal calls, but for cross-cloud, **Function URL with IAM Auth** or **API Gateway with API Key** is used.
*   **Recommendation:** Use **API Gateway with API Keys** for simplicity in cross-cloud scenarios where the caller is a generic HTTP client (like an Azure Function).
    *   **Header:** `x-api-key: <generated-key>`

#### Azure (Receiver)
*   **Mechanism:** **Function Keys**.
*   **Implementation:** Azure Functions have built-in key management (`default` or `master` keys).
*   **Header:** `x-functions-key: <function-key>`

#### GCP (Receiver)
*   **Mechanism:** **OIDC Tokens** (Service Account Identity).
*   **Implementation:** The calling function (e.g., in AWS) generates an OIDC token signed by its identity provider, or (simpler for MVP) use a shared **API Key** validated by the receiving function or API Gateway.
*   **Recommendation:** For the initial MVP, a shared **Secret Token** stored in Secrets Manager (AWS/GCP) or Key Vault (Azure) and injected as an env var is acceptable.

## 3. Data Payload Contracts

To ensure interoperability, all "Connector" functions must wrap their payloads in a standard "Inter-Cloud Envelope".

### Standard Envelope Schema
This JSON structure is used for all HTTP POST requests between clouds (L1->L2 and L2->L3).

```json
{
  "source_cloud": "aws",          // "aws" | "azure" | "gcp"
  "target_layer": "L2",           // "L2" (Processing) | "L3" (Storage)
  "message_type": "telemetry",    // "telemetry" | "event" | "command"
  "timestamp": "2023-10-27T10:00:00Z", // ISO 8601 UTC
  "payload": {                    // The actual data content
    "device_id": "sensor-001",
    "temperature": 25.4,
    "humidity": 60
  },
  "trace_id": "abc-123-xyz"       // For distributed tracing (optional)
}
```

### Response Contract
*   **Success:** `200 OK` with body `{"status": "received", "id": "..."}`.
*   **Retryable Failure:** `429 Too Many Requests`, `5xx Server Error`.
*   **Permanent Failure:** `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`.

## 4. Error Handling & Reliability Strategy

Reliability is critical when crossing cloud boundaries.

### Reliability Mechanisms
1.  **Retries:** All "Connector" functions (the senders) must implement **Exponential Backoff** logic.
    *   *Initial Retry:* 1 second
    *   *Multiplier:* 2x
    *   *Max Retries:* 3
2.  **Dead Letter Queues (DLQ):**
    *   **AWS:** Lambda Async Configuration -> DLQ (SQS).
    *   **Azure:** Event Grid Subscription -> Dead Letter Blob Storage.
    *   **GCP:** Pub/Sub Subscription -> Dead Letter Topic.
3.  **Circuit Breaker:** (Advanced) If the remote endpoint fails consistently for 1 minute, stop sending for 5 minutes to prevent resource exhaustion.

### Centralized Error Reporting Pipeline
A "Cloud-First Persistence" error system ensures no data is lost, even if the Management App is offline.

#### Architecture
1.  **Source:** Any component (L1 Dispatcher, L2 Persister, Connector) detects a failure.
2.  **Publish:** The component publishes an event to a local **System Error Topic**.
    *   **AWS:** EventBridge (Rule: `source: ["aws.lambda"]`, `detail-type: "Error"`)
    *   **Azure:** Event Grid System Topic (`{twin}-errors`)
    *   **GCP:** Cloud Pub/Sub Topic (`{twin}-errors`)
3.  **Reporter:** A dedicated **Error Reporter Function** subscribes to this topic.
4.  **Persistence (Primary):** The Reporter writes the error to a dedicated **Error Table/Collection** in the cloud.
    *   **AWS:** DynamoDB Table (`{digital_twin_name}-system-errors`)
    *   **Azure:** Cosmos DB Container (`SystemErrors`)
    *   **GCP:** Firestore Collection (`system_errors`)
5.  **Notification (Secondary):** The Reporter *optionally* sends an HTTP POST to the Management Backend for live alerting, or the App can simply poll/subscribe to the Cloud Storage.

#### Error Payload to Database
```json
{
  "twin_id": "twin-001",
  "cloud_provider": "azure",
  "severity": "CRITICAL",       // "CRITICAL" | "WARNING" | "INFO"
  "component": "L2-Persister",
  "error_code": "DB_WRITE_FAIL",
  "message": "Cosmos DB quota exceeded for partition 'hot-data'.",
  "timestamp": "2023-10-27T10:05:00Z",
  "raw_data": "{ ... }"         // Optional: original payload that caused error
}
```

## 5. Live Logging & Monitoring

To support the "Management Platform" vision, live feedback is essential.

*   **Deployment Logs:** The `3-cloud-deployer` CLI will stream logs to the Flutter App via WebSocket/SSE (facilitated by the Management Backend).
*   **Optimization Logs:** The Cost Optimizer will emit "calculation events" (e.g., "Fetching AWS us-east-1 prices...") to the same stream.
*   **Operational Logs:** The **Error Reporter** handles operational alerts (as defined above). Standard logs (Info/Debug) remain in the cloud-native logging services (CloudWatch, Monitor, Cloud Logging) and are not streamed to the app to save bandwidth, unless explicitly requested via a "Debug Mode" toggle.
