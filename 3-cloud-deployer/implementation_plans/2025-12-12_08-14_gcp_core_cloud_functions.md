# GCP Core Cloud Functions Implementation

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Current State](#2-current-state)
3. [Proposed Changes](#3-proposed-changes)
4. [Implementation Phases](#4-implementation-phases)
5. [Verification Checklist](#5-verification-checklist)

---

## 1. Executive Summary

### The Problem
AWS has 17 Lambda functions in `/src/providers/aws/lambda_functions/`. Azure has 17 equivalent functions. GCP has no equivalent cloud_functions yet.

### The Solution
Create 17 fully functional GCP Cloud Functions (Gen 2) in `/src/providers/gcp/cloud_functions/` using the planned services from GCP deployment docs:

| Layer | GCP Service |
|-------|-------------|
| L1 - Data Acquisition | Cloud Pub/Sub |
| L2 - Data Processing | Cloud Functions (Gen 2) |
| L3 - Hot Storage | Firestore (Native mode) |
| L3 - Cool Storage | Cloud Storage (Nearline) |
| L3 - Archive Storage | Cloud Storage (Archive) |
| Supporting | Cloud Scheduler, Cloud Workflows |

### Impact
- GCP deployments will have full feature parity with AWS and Azure
- Multi-cloud deployments will work with GCP as any layer provider

---

## 2. Current State

### AWS → GCP SDK Mapping (Based on Deployment Docs)

| AWS SDK | GCP SDK |
|---------|---------|
| `boto3.client("lambda").invoke()` | HTTP POST via `requests` |
| `boto3.resource("dynamodb")` | `google.cloud.firestore` |
| `boto3.client("s3")` | `google.cloud.storage` (Nearline/Archive classes) |
| `boto3.client("iot-data").publish()` | `google.cloud.pubsub_v1` (Pub/Sub for feedback) |

---

## 3. Proposed Changes

### 3.1 Shared Module

#### [NEW] _shared/inter_cloud.py
- **Path:** `src/providers/gcp/cloud_functions/_shared/inter_cloud.py`
- **Description:** Token validation and remote POST helpers

---

### 3.2 L1 - Data Acquisition (Pub/Sub + Cloud Functions)

#### [NEW] dispatcher/main.py
- **Description:** Triggered by Pub/Sub (Eventarc), routes to device processor via HTTP

#### [NEW] connector/main.py
- **Description:** [Multi-Cloud] Wraps event and POSTs to remote Ingestion API

---

### 3.3 L2 - Data Processing (Cloud Functions Gen 2)

#### [NEW] ingestion/main.py
- **Description:** [Multi-Cloud] HTTP trigger, receives from remote Connector

#### [NEW] processor_wrapper/main.py
- **Description:** Wraps user logic, invokes persister

#### [NEW] default-processor/main.py
- **Description:** Default processing logic template

#### [NEW] persister/main.py
- **Description:** Writes to Firestore (single-cloud) or remote Writer (multi-cloud)

#### [NEW] event-checker/main.py
- **Description:** Checks events against rules, triggers Cloud Workflows

---

### 3.4 L3 - Storage (Firestore + Cloud Storage)

#### [NEW] hot-writer/main.py
- **Description:** [Multi-Cloud] HTTP trigger, writes to Firestore

#### [NEW] hot-reader/main.py
- **Description:** Reads from Firestore with time range queries

#### [NEW] hot-reader-last-entry/main.py
- **Description:** Gets last entry per device from Firestore

#### [NEW] hot-to-cold-mover/main.py
- **Description:** Cloud Scheduler trigger, moves Firestore → Cloud Storage (Nearline)

#### [NEW] cold-writer/main.py
- **Description:** [Multi-Cloud] Writes to Cloud Storage (Nearline class)

#### [NEW] cold-to-archive-mover/main.py
- **Description:** Cloud Scheduler trigger, moves Nearline → Archive class

#### [NEW] archive-writer/main.py
- **Description:** [Multi-Cloud] Writes to Cloud Storage (Archive class)

---

### 3.5 L4 - Digital Twin Data Access

#### [NEW] digital-twin-data-connector/main.py
- **Description:** Routes queries to hot-reader (local or remote)

#### [NEW] digital-twin-data-connector-last-entry/main.py
- **Description:** Routes last-entry queries

---

### 3.6 Tests

#### [NEW] test_gcp_cloud_functions.py
- **Path:** `tests/unit/gcp_functions/test_gcp_cloud_functions.py`
- **Description:** Unit tests for all 17 GCP functions

---

## 4. Implementation Phases

### Phase 1: Shared Module
| Step | File |
|------|------|
| 1.1 | `_shared/__init__.py` |
| 1.2 | `_shared/inter_cloud.py` |

### Phase 2: L1 Functions (Pub/Sub triggered)
| Step | File |
|------|------|
| 2.1 | `dispatcher/main.py` |
| 2.2 | `connector/main.py` |

### Phase 3: L2 Functions (Processing)
| Step | File |
|------|------|
| 3.1 | `ingestion/main.py` |
| 3.2 | `processor_wrapper/main.py` |
| 3.3 | `default-processor/main.py` |
| 3.4 | `persister/main.py` |
| 3.5 | `event-checker/main.py` |

### Phase 4: L3 Functions (Firestore + Cloud Storage)
| Step | File |
|------|------|
| 4.1 | `hot-writer/main.py` |
| 4.2 | `hot-reader/main.py` |
| 4.3 | `hot-reader-last-entry/main.py` |
| 4.4 | `hot-to-cold-mover/main.py` |
| 4.5 | `cold-writer/main.py` |
| 4.6 | `cold-to-archive-mover/main.py` |
| 4.7 | `archive-writer/main.py` |

### Phase 5: L4 Functions
| Step | File |
|------|------|
| 5.1 | `digital-twin-data-connector/main.py` |
| 5.2 | `digital-twin-data-connector-last-entry/main.py` |

### Phase 6: Tests
| Step | File |
|------|------|
| 6.1 | `tests/unit/gcp_functions/test_gcp_cloud_functions.py` |

---

## 5. Verification Checklist

- [x] All 17 GCP cloud functions created
- [x] All existing tests pass
- [x] New tests pass (20 tests)
- [x] Full test suite: **590 passed**
- [x] Test command: `docker exec -e PYTHONPATH=/app master-thesis-3cloud-deployer-1 python -m pytest tests/ --tb=short`
