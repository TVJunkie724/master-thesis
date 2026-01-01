# TODO: Infrastructure Deployment Feature

> **Status**: Not implemented
> **Priority**: Future work
> **Last Updated**: 2025-12-31

## Overview

This document outlines the requirements for implementing infrastructure deployment and destruction capabilities in the Flutter frontend and Management API backend. The deployer (3-cloud-deployer) is a standalone project with no knowledge of these systems.

---

## 1. Database Schema (SQLite)

```sql
ALTER TABLE twin_configurations ADD COLUMN deployment_status TEXT DEFAULT 'draft';
-- Values: 'draft', 'deploying', 'deployed', 'destroying', 'destroy_failed', 'error'

ALTER TABLE twin_configurations ADD COLUMN last_deployed_at TEXT NULL;  -- ISO timestamp
ALTER TABLE twin_configurations ADD COLUMN terraform_outputs TEXT NULL;  -- JSON string
ALTER TABLE twin_configurations ADD COLUMN is_locked INTEGER DEFAULT 0;  -- 1 = locked during deploy/destroy
```

---

## 2. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/twins/{id}/infrastructure-status` | GET | DB status + live Terraform state check |
| `/twins/{id}/deploy` | POST | SSE stream, updates status |
| `/twins/{id}/destroy` | POST | SSE stream, updates status |

**Response for infrastructure-status:**
```json
{
    "db_status": "deployed",
    "terraform_state_exists": true,
    "resource_count": 42,
    "can_destroy": true,
    "last_deployed_at": "2025-12-30T15:00:00Z"
}
```

---

## 3. Flutter UI Changes

### Dashboard Screen
- Add "Status" column to twins table
- Color-code: draft=gray, deployed=green, deploying=blue, error=red

### Twin View Screen
- Infrastructure section with:
  - Current status badge
  - "Deploy" button (enabled if draft/error and configs valid)
  - "Destroy" button (enabled if deployed)
  - Resource count (if deployed)
  - Last deployed timestamp

### Destroy Confirmation Dialog
```
⚠️ Destroy Infrastructure?

This will permanently delete all cloud resources for "MyTwin":
- IoT Hub/IoT Core
- Database (CosmosDB/DynamoDB/Firestore)
- Functions (Lambda/Azure Functions/Cloud Functions)
- Grafana dashboard
- Digital Twin resources

This action cannot be undone.

[Cancel] [Destroy]
```

### Destroy Progress Modal
- SSE-based log viewer (same pattern as pricing refresh)
- Progress stages: "Initializing...", "Destroying resources...", "SDK cleanup...", "Complete"
- Error handling with retry option

---

## 4. State Machine

```
draft → deploying → deployed → destroying → draft
         ↓                        ↓
       error                 destroy_failed
```

**Transitions:**
- `draft → deploying`: Deploy clicked
- `deploying → deployed`: Success
- `deploying → error`: Failure
- `deployed → destroying`: Destroy clicked
- `destroying → draft`: Success
- `destroying → destroy_failed`: Failure
- `error → deploying`: Retry Deploy
- `destroy_failed → destroying`: Retry Destroy
- `destroy_failed → deployed`: Cancel (keep resources)

---

## 5. Error Handling Considerations

- **Partial deployment**: If deploy fails mid-way, status = "error", user can retry or destroy
- **Partial destroy**: If destroy fails, status = "destroy_failed", user can retry
- **Stale state**: If user deploys outside the UI, add "Refresh Status" button
- **Concurrent access**: Lock twin during deploy/destroy operations (set `is_locked` flag in DB)

---

## Implementation Notes

- The deployer exposes `destroy_all()` which returns a `DestroyResult` dataclass
- SDK fallback cleanup is available via `sdk_fallback="always"` parameter
- Dry-run mode available via `dry_run=True` for testing
- Parallel cleanup of all providers with timeout/retry logic
