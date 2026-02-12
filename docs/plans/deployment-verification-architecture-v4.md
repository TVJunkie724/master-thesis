# Deployment Verification — Architecture Proposal (v4)

## Problem

After deploying, the user needs to verify the deployment is healthy — equivalent to the 18 E2E tests, with clear pass/fail results.

---

## E2E Test Coverage

| Mode | Tests | Count |
|------|-------|-------|
| **Infra** | L0 setup, L0 glue, L1 IoT, L2 functions, L3 storage, L4 twins, L5 grafana, IoT devices, TwinMaker entities, ADT twins, Azure functions, hot→cold mover, cold→archive mover | 13 |
| **Data** | Send message, verify hot storage, TwinMaker telemetry, ADT telemetry, event checker, action function, workflow trigger, feedback | 8 |

---

## UI Layout

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  🔍 DEPLOYMENT VERIFICATION                                                │
│                                                                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗   │
│  ║                    CHECK INFRASTRUCTURE                        ▶    ║   │
│  ╚═══════════════════════════════════════════════════════════════════════╝   │
│  Verifies that all cloud resources are deployed and accessible.             │
│  Checks each layer (L0–L5): IoT endpoints, processing functions,           │
│  storage buckets, digital twin instances, mover functions, and IoT          │
│  device registrations. This is a read-only check — no data is sent.        │
│  Duration: 5–15 seconds.  Cost: None (API calls only).                      │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  INFRASTRUCTURE RESULT (structured card)                              │ │
│  │  ✓ L0 Setup — 3 resources            ✓ L3 Hot (GCP)                  │ │
│  │  ✓ L1 IoT (AWS)                      ✓ L4 TwinMaker                  │ │
│  │  ...                                                                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│                                                                              │
│  ╔═══════════════════════════════════════════════════════════════════════╗   │
│  ║                     VERIFY DATA FLOW                           ▶    ║   │
│  ╚═══════════════════════════════════════════════════════════════════════╝   │
│  Sends a test IoT message through the entire deployed pipeline and          │
│  verifies it reaches every layer: ingestion → processing → hot storage      │
│  → digital twin update → event checking → feedback. Proves that data        │
│  actually flows end-to-end, not just that resources exist.                  │
│  Duration: 20–120 seconds.  Cost: Minimal (one IoT message).               │
│  Prerequisite: Infrastructure check should pass first.                      │
│                                                                              │
│  ⚠ If event checking or notification workflows are enabled, the payload    │
│  values must match the configured event conditions (in config_events.json)  │
│  to trigger the full event flow verification. Edit the payload below to     │
│  set matching values, or those checks will be reported as "not triggered".  │
│                                                                              │
│  ┌── Test Payload ──────────────────────────────── [Reset to Default] ──┐  │
│  │  {                                                                    │  │
│  │    "iotDeviceId": "temperature-sensor-1",                             │  │
│  │    "temperature": 28,                                                 │  │
│  │    "time": ""                                                         │  │
│  │  }                                                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  DATA FLOW LOG (terminal-style, SSE-streamed)                         │ │
│  │  [22:03:01] ✓ Message sent to AWS IoT (temperature-sensor-1)         │ │
│  │  [22:03:28] ✓ Data reached L3-Hot storage (26s)                      │ │
│  │  ...                                                                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Payload Editor

**Behavior:**
- **Pre-filled** with first payload from [payloads.json](file:///Users/caroline/git/master-thesis/3-cloud-deployer/upload/template/iot_device_simulator/payloads.json) on page load
- **Editable** — user can change values (e.g., set `temperature: 30` to match an event condition)
- **Reset to Default** button restores first payload from [payloads.json](file:///Users/caroline/git/master-thesis/3-cloud-deployer/upload/template/iot_device_simulator/payloads.json)
- **Validated before send** — must be valid JSON, must contain `iotDeviceId`, device must exist in [config_iot_devices.json](file:///Users/caroline/git/master-thesis/3-cloud-deployer/upload/template/config_iot_devices.json)
- **[time](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/providers/terraform/deployer_strategy.py#812-857) auto-filled** — the [time](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/providers/terraform/deployer_strategy.py#812-857) field is injected server-side with current timestamp, regardless of what user enters
- **[trace_id](file:///Users/caroline/git/master-thesis/3-cloud-deployer/src/api/logs.py#49-52) auto-injected** — server-side, transparent to user

> [!TIP]
> This gives users the control to trigger event conditions without us needing to parse condition expressions. The description warning makes it clear that matching values are needed for full verification.

---

## Infrastructure Check — Output

Structured checklist card; checks conditional on twin's provider config. Non-applicable rows show `— N/A`.

```
INFRASTRUCTURE HEALTH CHECK                                    ⏱ 8s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Layer Setup
  ✓  L0 Setup resources                         3 resources found
  ✓  L0 Glue functions                          cold-writer, hot-reader

Ingestion (L1)
  ✓  IoT endpoint (AWS)                         endpoint active
  ✓  IoT devices registered                     2 devices

Processing (L2)
  ✓  Functions deployed (Azure)                 dispatcher, processor, persister

Storage (L3)
  ✓  Hot storage (GCP Firestore)                deployed
  ✓  Cold storage (AWS S3)                      deployed
  ✓  Archive storage (AWS S3 Glacier)           deployed
  ✓  Hot→Cold mover (AWS Lambda)                deployed, env vars OK
  ✓  Cold→Archive mover (AWS Lambda)            deployed, env vars OK

Digital Twins (L4)
  ✓  TwinMaker workspace (AWS)                  deployed
  ✓  TwinMaker entities                         2 entities created
  —  ADT twins                                  N/A (L4 not Azure)

Visualization (L5)
  ✓  Grafana workspace (AWS)                    deployed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESULT: 13/13 PASSED  (1 skipped)                         ✓ HEALTHY
```

---

## Data Flow — Terminal Output

### Success

```
DATA FLOW VERIFICATION                                         ⏱ 0s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase 1: Message Delivery
  [22:03:01] Sending test message to AWS IoT...
             Device: temperature-sensor-1
             Payload: {"temperature": 30}
  [22:03:02] ✓ Message sent successfully (trace: TRACE-A7F3B2C1)

Phase 2: Pipeline → Hot Storage (timeout: 120s)
  [22:03:04]   Waiting for data propagation...
  [22:03:28] ✓ Data reached L3-Hot storage (26s)

Phase 3: Digital Twin Update (timeout: 60s)
  [22:03:30]   Checking TwinMaker property history...
  [22:03:45] ✓ TwinMaker: temperature property updated (43s)

Phase 4: Event Flow
  [22:03:46]   Checking event-checker invocation... (timeout: 60s)
  [22:04:02] ✓ Event-Checker invoked (60s)
  [22:04:15] ✓ Action: high-temperature-callback called (73s)
  [22:04:30] ✓ Workflow triggered (88s)
  [22:04:45] ✓ Feedback sent to IoT device (103s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESULT: 7/7 PASSED                                        ✓ ALL OK
Total time: 103 seconds
```

### Failure

```
Phase 2: Pipeline → Hot Storage (timeout: 120s)
  [22:05:04] ✗ TIMEOUT — Data did not reach hot storage within 120s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESULT: 1/7 PASSED, 1 FAILED, 5 SKIPPED                  ✗ FAILED
  Failed at: Phase 2 — Pipeline Processing
  ⓘ Check cloud provider logs manually for exact error details:
    AWS:   CloudWatch → /aws/lambda/{twin-name}-*
    Azure: Log Analytics → AppTraces
    GCP:   Cloud Logging → resource.type="cloud_function"
```

### Event Checking Not Configured

```
Phase 4: Event Flow
  — Event Checker:    N/A — event checking not configured
  — Action function:  N/A — event checking not configured
  — Workflow trigger: N/A — notification workflow not configured
  — Feedback:         N/A — event checking not configured
```

---

## Backend Architecture

| Mode | Flow | Response |
|------|------|----------|
| **Infra** | `POST /twins/{id}/verify/infrastructure` → proxies to Deployer → returns JSON | Instant, structured JSON |
| **Data** | `POST /twins/{id}/verify/dataflow` → SSE session → 4-phase background task | SSE stream, terminal-style |

---

## Implementation Phases

| Phase | Scope | Effort |
|-------|-------|--------|
| **1** | Infrastructure check: extend deployer endpoint, backend proxy, Flutter structured card | 2-3 days |
| **2** | Data flow: backend endpoint + 4-phase orchestrator, SSE streaming, Flutter terminal + payload editor | 4-5 days |
