---
title: "Frontend Feature Request Tracker"
description: "Central tracker for Management API capabilities required by planned Flutter work."
tags: [flutter, feature-request, management-api]
lastUpdated: "2026-08-03"
version: "1.3"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/feature-requests/FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md
- twin2multicloud_flutter/docs/feature-requests/FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md
EXTRACTED: 2026-08-03 | VERSION: 1.3
-->

# Frontend Feature Request Tracker

| ID | Status | Target | Required by | Summary |
|---|---|---|---|---|
| [FR-001](FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md) | Planned | Management API, Deployer | Frontend Delta 8.6 | Secret-free L4/L5 deployment-access read model and GCP Grafana Viewer rotation |
| [FR-002](FR_002_GUIDED_CLOUD_ACCESS_BOOTSTRAP.md) | Planned; [#154](https://github.com/TVJunkie724/master-thesis/issues/154) open | Management API, Deployer | Configuration Workspace Phase 9 | Request-scoped bootstrap authority, generated bounded CloudConnections, and resumable provider prerequisites |

The Phase 8.7 architecture-profile UI introduced no missing Management
capability: its seven profile/selection/resolution operations were already
implemented by Phase 8.4. Therefore #138 is tracked in the Phase 8 roadmap,
not as another frontend feature request. FR-001 and FR-002 remain the genuine
backend/deployer dependencies for later Layer Access and guided bootstrap.
