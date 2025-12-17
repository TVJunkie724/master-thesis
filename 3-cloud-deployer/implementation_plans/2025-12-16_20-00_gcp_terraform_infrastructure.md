# GCP Terraform Infrastructure Implementation (Phase 1)

## 1. Executive Summary

### The Problem
GCP lacked Terraform infrastructure files for deploying Digital Twin layers L1-L3.

### The Solution
Create comprehensive Terraform configuration files for GCP resources matching the AWS/Azure patterns.

### Impact
GCP can now be deployed via Terraform for L1 (Pub/Sub), L2 (Cloud Functions), and L3 (Firestore/Storage).

---

## 2. Proposed Changes

### Component: Terraform Core

#### [x] [MODIFY] main.tf
- **Path:** `src/terraform/main.tf`
- **Description:** Added `deploy_gcp` local variable for conditional GCP deployment

#### [x] [MODIFY] variables.tf
- **Path:** `src/terraform/variables.tf`
- **Description:** Added `gcp_billing_account` variable for dynamic project creation

#### [x] [MODIFY] outputs.tf
- **Path:** `src/terraform/outputs.tf`
- **Description:** Added 16 GCP-specific outputs (project_id, topics, functions, buckets, etc.)

---

### Component: Terraform GCP Files

#### [x] [NEW] gcp_setup.tf
- **Path:** `src/terraform/gcp_setup.tf`
- **Description:** Foundation resources:
  - `google_project` - Dynamic project creation
  - `google_project_service` - API enablement
  - `google_service_account` - Functions service account
  - `google_storage_bucket` - Function source bucket

#### [x] [NEW] gcp_iot.tf
- **Path:** `src/terraform/gcp_iot.tf`
- **Description:** L1 Data Acquisition:
  - `google_pubsub_topic` - Telemetry and events topics
  - `google_cloudfunctions2_function` - Dispatcher function

#### [x] [NEW] gcp_compute.tf
- **Path:** `src/terraform/gcp_compute.tf`
- **Description:** L2 Data Processing:
  - `google_cloudfunctions2_function` - Processor function
  - `google_cloudfunctions2_function` - Persister function

#### [x] [NEW] gcp_storage.tf
- **Path:** `src/terraform/gcp_storage.tf`
- **Description:** L3 Data Storage:
  - `google_firestore_database` - Hot storage
  - `google_storage_bucket` - Cold/Archive storage (Nearline, Archive classes)
  - `google_cloudfunctions2_function` - Hot reader, Hot-to-cold mover
  - `google_cloud_scheduler_job` - Scheduled mover trigger
  - GCS lifecycle policies for automatic cold→archive transition

#### [x] [NEW] gcp_glue.tf
- **Path:** `src/terraform/gcp_glue.tf`
- **Description:** Multi-cloud connector functions (conditional deployment)

---

### Component: Configuration

#### [x] [MODIFY] config_credentials.json.example
- **Path:** `upload/template/config_credentials.json.example`
- **Description:** Added `gcp_billing_account` field, documented `gcp_project_id` as optional

#### [x] [MODIFY] tfvars_generator.py
- **Path:** `src/tfvars_generator.py`
- **Description:** Added `gcp_billing_account` extraction, explicit validation for project creation

---

## 3. Verification Checklist

- [x] `terraform validate` passes
- [x] All conditional deployments work (deploy_gcp, layer-specific flags)
- [x] Multi-cloud glue functions are conditional
- [x] Lifecycle policies configured for storage tiering

---

## 4. Design Decisions

### GCP Project Creation
Terraform can create a new project if `gcp_project_id` is empty but `gcp_billing_account` is provided.

### L3 Storage Tiering
- Hot: Firestore (real-time queries)
- Cold: Cloud Storage Nearline (30-90 days)
- Archive: Cloud Storage Archive (90+ days)
- Cold→Archive: GCS lifecycle policies (no function needed)
- Hot→Cold: Cloud Scheduler triggers mover function

### L4/L5 Not Implemented
GCP lacks managed Digital Twin and Grafana services. Noted in documentation for future self-hosted solutions.
