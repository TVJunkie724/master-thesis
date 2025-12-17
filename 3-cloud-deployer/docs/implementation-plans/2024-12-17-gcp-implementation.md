# GCP Implementation Plan

## Goal

Implement GCP cloud provider support (L1-L3) for the Digital Twin Multi-Cloud Deployer.

---

## User Review Required

> [!IMPORTANT]
> **L4/L5 Skipped**: GCP has no managed Digital Twin or Grafana services.

---

## Architecture Decisions

### L1: IoT Device Connectivity

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Protocol | HTTP REST | Simpler than gRPC, same auth |
| Auth | Service Account JSON | Standard GCP pattern |
| MQTT | Not needed | Pub/Sub uses HTTP/gRPC natively |

### L3: Storage Transitions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cold/Archive | Lifecycle Policy | Custom age days match `config.json` |
| NOT Autoclass | ❌ | Fixed 30/90/365 days - not configurable |

### Mover Functions

| Scenario | Hot→Cold | Cold→Archive |
|----------|----------|--------------|
| Single-cloud GCP | Function (Scheduler) | Lifecycle (auto) |
| Multi-cloud (L3 on other) | Cold Writer + Mover | Archive Writer + Mover |

> [!NOTE]
> Multi-cloud mover functions are conditional on differing L3 providers.

---

## Proposed Changes

### Phase 1: Terraform Infrastructure

---

#### [NEW] gcp_setup.tf

- Service Account for deployment
- Enable required APIs (Pub/Sub, Functions, Firestore, Storage)

---

#### [NEW] gcp_glue.tf

L0 Glue Functions (conditional on multi-cloud):
- Ingestion, Hot Writer/Reader, Cold Writer, Archive Writer
- Use `count` based on provider differences

---

#### [NEW] gcp_iot.tf

L1: Pub/Sub topics, subscriptions, Eventarc triggers

---

#### [NEW] gcp_compute.tf

L2: Cloud Functions Gen2 (Dispatcher, Processor, Persister)

---

#### [NEW] gcp_storage.tf

L3: Firestore, Cloud Storage buckets, Lifecycle policies, Hot-to-Cold mover

---

#### [MODIFY] variables.tf, main.tf, outputs.tf

Add GCP provider, variables, outputs

---

### Phase 2: Cloud Functions Review

---

#### [CHECK] `src/providers/gcp/cloud_functions/` (static functions - already exist)

17 functions exist - verify/adapt each:
- `dispatcher/`, `persister/`, `connector/`
- `hot-reader/`, `hot-reader-last-entry/`, `hot-writer/`
- `cold-writer/`, `archive-writer/`
- `hot-to-cold-mover/`, `cold-to-archive-mover/`
- `ingestion/`, `default-processor/`, `processor_wrapper/`
- `event-checker/`, `digital-twin-data-connector*`
- `_shared/` - Shared utilities

---

#### [CHECK] `upload/template/cloud_functions/` (user-editable functions)

Verify existing functions work for GCP:
- `processors/` - User processor logic
- `event_actions/` - Event handlers
- `event-feedback/` - Feedback handlers

> Compare with `lambda_functions/` (AWS) and `azure_functions/` (Azure).

---

### Phase 3: Provider Implementation

---

#### [MODIFY] provider.py

Minimal changes (Terraform handles deployment):
1. Add `naming` property (create `naming.py`)
2. Add `info_l1()` method (status check via SDK)
3. Initialize minimal clients for status checks only
4. Remove `get_deployer_strategy()` (not needed)

> [!NOTE]
> SDK clients are only for status checks. Terraform handles all deployments.

---

#### [NEW] naming.py

Resource naming following AWS/Azure patterns

---

#### [DELETE] deployer_strategy.py

Not needed - Terraform-first architecture

> [!WARNING]
> Update AI Layer Guide to reflect Terraform-first: no deployer_strategy needed.

---

### Phase 4: Credentials & Documentation

---

#### [NEW] gcp_credentials_checker.py

Validate GCP credentials and permissions

---

#### [NEW] docs-credentials-gcp.html

Service Account setup guide

---

#### [MODIFY] docs-gcp-deployment.html

Add Setup, L0, IAM sections

---

### Phase 5: Testing

---

#### [NEW] `tests/providers/test_gcp_*.py`

Unit tests for GCP provider and naming

---

## Verification Plan

### Automated Tests
```bash
docker exec master-thesis-3cloud-deployer-1 python -m pytest tests/providers/ -k gcp -v
```

### Manual Verification
- [ ] `terraform plan` succeeds with GCP config
- [ ] User functions in `cloud_functions/` work as expected
- [ ] Documentation pages render correctly
