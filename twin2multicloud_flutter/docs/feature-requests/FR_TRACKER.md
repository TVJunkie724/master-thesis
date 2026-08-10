---
title: "Frontend Feature Request Tracker"
description: "Central tracker for Management API capabilities required by planned Flutter work."
tags: [flutter, feature-request, management-api]
lastUpdated: "2026-08-11"
version: "1.5"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/feature-requests/FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md
- twin2multicloud_flutter/docs/feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md
EXTRACTED: 2026-08-11 | VERSION: 1.5
-->

# Frontend Feature Request Tracker

| ID | Status | Target | Required by | Summary |
|---|---|---|---|---|
| [FR-001](FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md) | Implemented offline; live sign-in pending | Management API, Deployer | Frontend Delta 8.6 | Secret-free L4/L5 deployment-access read model and GCP Grafana Viewer rotation |
| [FR-002](FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md) | Implemented offline; live adapters disabled | Management API, Deployer | Configuration Workspace Phase 9 | Request-scoped bootstrap authority, generated bounded CloudConnections, and resumable provider prerequisites |

The Phase 8.7 architecture-profile UI introduced no missing Management
capability: its seven profile/selection/resolution operations were already
implemented by Phase 8.4. Therefore #138 is tracked in the Phase 8 roadmap,
not as another frontend feature request. FR-001 is closed for the deterministic
offline PoC; Five-layer v2 activation and provider browser sign-in remain
separate gates. FR-002 is closed for the deterministic offline PoC; live
provider adapters remain a separately supervised boundary.
