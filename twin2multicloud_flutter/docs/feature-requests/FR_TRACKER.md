---
title: "Frontend Feature Request Tracker"
description: "Central tracker for Management API capabilities required by planned Flutter work."
tags: [flutter, feature-request, management-api]
lastUpdated: "2026-08-11"
version: "1.5"
---

<!-- SOURCES:
- twin2multicloud_flutter/docs/feature-requests/FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md
EXTRACTED: 2026-08-11 | VERSION: 1.5
-->

# Frontend Feature Request Tracker

| ID | Status | Target | Required by | Summary |
|---|---|---|---|---|
| [FR-001](FR_001_DEPLOYMENT_LAYER_ACCESS_READ_MODEL.md) | Implemented offline; live sign-in pending | Management API, Deployer | Frontend Delta 8.6 | Secret-free L4/L5 deployment-access read model and GCP Grafana Viewer rotation |

The Phase 8.7 architecture-profile UI introduced no missing Management
capability: its seven profile/selection/resolution operations were already
implemented by Phase 8.4. Therefore #138 is tracked in the Phase 8 roadmap,
not as another frontend feature request. FR-001 is closed for the deterministic
offline PoC; Six-layer activation and provider browser sign-in remain
separate gates.
